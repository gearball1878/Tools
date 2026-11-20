import json
import re

from auto_sch_base import *
from collections import defaultdict

# This class is used to get a full set of design information via the COM Interface from Xpedition Designer
#
# 1. Get all Blocks with Level Information and attached attributes
#   a) Level Info: Toplevel, Domain, Architectural Element (AE), Functional (MB)
#   b) Attributes: Architecture UID, XD UID, Systemfunction, Colour, RefDes Start
#
# 2. Get all Pins with corresponding Information for All Blocks
#   a) Parent Block
#   a) Attributes Architecture UID, XD UID, connected Net, Pintype
#
# 3. Get all Nets/Busses with corresponding Information
#   a) connected Pins
#   a) Attributes Architecture UID, XD UID, additional Info (Net Voltages, Net class, etc...)
#
# 4. Get all functional Parts
#   a) list all attribtues
#   b) list all electrical connected parts --> (autoname short nets?!)

class const:
    # Design Levels
    DESIGN_LEVEL = "DESIGN_LEVEL"
    TOP_LEVEL = "TOP_LEVEL"
    DOMAIN_LEVEL = "DOMAIN_LEVEL"
    AE_LEVEL = "AE_LEVEL"
    FUNCT_LEVEL = "FUNCT_LEVEL"
    BLOCK_LEVEL = "BLOCK_LEVEL"

    # Domain Keywords
    CON = "CON"
    PSU = "PSU"
    SMC = "SMC"
    uC =   "uC"
    MCU = "MCU"
    PSoC = "PSoC"
    CPU = "CPU"
    SoC = "SoC"
    ETH = "ETH"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"
    cIVN = "cIVN"
    POS = "POS"
    WLAN = "WLAN"
    BT = "BT"
    WAKE = "WAKE"
    SENSE = "SENSE"
    DEBUG  = "DEBUG"
    MEM = "MEM"
    SSD = "SSD"
    PER = "PER"

    # Power Pin Identifier
    Power_Pin_Identifier = ["VCC", "VDD", "VBAT"]

    # Pin Categories
    PowerIn = "PowerIn"
    PowerOut = "PowerOut"
    Control = "Control"
    Status = "Status"
    Interface = "Interface"
    Analog = "Analog"
    Pincategories = [PowerIn, Control, Analog, PowerOut, Interface, Status]

    # Pin Types (PT)
    PT_ANALOG = "ANALOG"
    PT_BI = "BI"
    PT_GROUND = "GROUND"
    PT_IN = "IN"
    PT_OCL = "OCL"
    PT_OEM = "OEM"
    PT_OUT = "OUT"
    PT_POWER = "POWER"
    PT_TERMINAL = "TERMINAL"
    PT_TRI = "TRI"

    # Pin Side on Block (PS)
    PS_TOP = 0
    PS_BOTTOM = 1
    PS_LEFT = 2
    PS_RIGHT = 3

    # Standard Attribute Sets for Parts
    attr_generic = ["Part Number", "ORDER_CODE", "PACKAGE"]

class gather_design_info:
    def __init__(self):
        pass

    def merge_dicts_over_key(self, dict1, dict2):
        merged_dict = defaultdict(list)

        for k, v in dict1.items():
            merged_dict[k].append(v)

        for k, v in dict2.items():
            merged_dict[k].append(v)

        return merged_dict

    def find_key(self, data, target_key):
        if isinstance(data, dict):
            for key, value in data.items():
                if key == target_key:
                    return value
                result = self.find_key(value, target_key)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self.find_key(item, target_key)
                if result is not None:
                    return result
        return None  # Key not found

    def evaluate_design_level(self, full_path_block_name, short_name):
        count = full_path_block_name.count("\\")
        hier_level = full_path_block_name.split("\\")  # Splitting by '\'
        # print("hier_level:", hier_level)

        if count == 0:
            if const.CON in hier_level[0]:
                parent = "CON"
                super_parent = None
                return parent, const.AE_LEVEL, super_parent
            else:
                parent = None
                super_parent = None
                return parent, const.TOP_LEVEL, super_parent
        elif count == 1:
            if const.CON in hier_level[0]:
                parent = hier_level[0]
                super_parent = None
                return parent, const.FUNCT_LEVEL, super_parent
            else:
                parent = hier_level[0]
                super_parent = None
                return parent, const.DOMAIN_LEVEL, super_parent
        elif count == 2:
            parent = hier_level[1]
            super_parent = hier_level[0]
            return parent, const.AE_LEVEL, super_parent
        elif count == 3:
            parent = hier_level[2]
            super_parent = hier_level[1]
            return parent, const.FUNCT_LEVEL, super_parent
        else:
            parent = hier_level[3]
            super_parent = hier_level[2]
            return parent, const.BLOCK_LEVEL, super_parent

    def get_blocks(self, app, design_block):
        # COM types Xpedition
        objComponent : IVdComp = None
        CompLabel : IVdLabel = None
        objBlock: IVdBlock = None
        block_architecture_uid_attribute: IVdAttr = None
        sys_funct_attribute: IVdAttr = None
        name_attribute: IVdAttr = None
        refdes_attribute: IVdAttr = None

        # dictionaries
        dict_design = {}
        dict_ae = {}
        dict_domain_attr = {}
        dict_components_ae = {}

        # lists
        block_list = []
        domains = []

        # get all functional components
        all_components = self.get_components(app, design_block)
        # print(json.dumps(all_components, indent=4))

        for block in app.SchematicSheetDocuments().GetAvailableSchematics():
            block_list.append(block)
        # print(block_list)

        # get all domains from design
        lstComponents = app.DesignComponents("", design_block, "-1", "STD", True)
        for objComponent in lstComponents:
            short_name = objComponent.GetName(c.SHORT_NAME)
            objBlock = objComponent.SymbolBlock
            block_name = objBlock.GetName(c.SHORT_NAME)
            # print("block_name: ", block_name)
            if block_name in block_list:
                # print("short_name: ", short_name)
                full_path_name = objComponent.GetName(c.FULL_PATH_NAME)
                design_level = self.evaluate_design_level(full_path_name, short_name)
                if design_level[1] == const.DOMAIN_LEVEL:
                    domains.append(short_name)

        # Generate a list of dictionaries
        domain_dicts = [{domain: {}} for domain in domains]
        # print(domain_dicts)

        lstComponents = app.DesignComponents("", design_block, "-1", "STD", True)
        for objComponent in lstComponents:
            short_name =  objComponent.GetName(c.SHORT_NAME)
            objBlock = objComponent.SymbolBlock
            block_name = objBlock.GetName(c.SHORT_NAME)

            if block_name in block_list:
                full_path_name = objComponent.GetName(c.FULL_PATH_NAME)
                parent_block = self.evaluate_design_level(full_path_name, short_name)[0]
                design_level = self.evaluate_design_level(full_path_name, short_name)[1]
                # print(f"Block Name: {full_path_name}", f"Design Level: {design_level}", f"Parent Block: {parent_block}")
                # get IDs
                uid = objComponent.UID
                block_architecture_uid_attribute = objComponent.FindAttribute("Architecture UID")

                # get system function
                sys_funct_attribute = objComponent.FindAttribute("System Function")
                if sys_funct_attribute:
                    sys_funct = sys_funct_attribute.Value
                else:
                    sys_funct = ""

                if block_architecture_uid_attribute:
                    architecture_uid = block_architecture_uid_attribute.Value
                else:
                    architecture_uid = ""

                if design_level == const.AE_LEVEL:
                    Pinlist = self.get_pin_list(objComponent)
                    dict_components_ae = self.get_components_for_ae(short_name, all_components)
                    # print(json.dumps(dict_components_ae, indent=4))
                    ae_values = [uid, architecture_uid, sys_funct, Pinlist, dict_components_ae]
                    # print(ae_values)

                    # Find the correct dictionary and update it
                    # Dynamically find the dictionary corresponding to parent_block
                    for domain_dict in domain_dicts:
                        if parent_block in domain_dict:
                            # If parent_block exists in the current dictionary, add the new data
                            domain_dict[parent_block][short_name] = ae_values
                            break

                elif design_level == const.DOMAIN_LEVEL:
                    dict_domain_attr[short_name] = uid, architecture_uid

        for domain_dict in domain_dicts:
            # print(domain_dict)
            for domain, ae in domain_dict.items():
                for domain2, domain_attr in dict_domain_attr.items():
                    uid = domain_attr[0]
                    architecture_uid = domain_attr[1]
                    if domain == domain2:
                        dict_design[domain] = uid, architecture_uid, ae
        # print(json.dumps(dict_design, indent=4))
        return dict_design


    # Pinlists for AEs
    def get_pin_list(self, component : IVdComp):
        # COM types Xpedition
        conn: IVdConnection = None
        cmpPin : IVdCmpPin  = None
        Pin : IVdPin = None
        type_attribute : IVdAttr = None
        pin_architecture_uid_attribute : IVdAttr = None
        net_architecture_uid_attribute: IVdAttr = None
        conSegm: IVdSegment = None
        Net: IVdNet = None

        # dictionaries
        dict_Pinlist = {}
        dict_Pincategories = {}
        dict_PowerIn = {}
        dict_PowerOut = {}
        dict_Control = {}
        dict_Status = {}
        dict_Interface = {}
        dict_Analog = {}
        dict_Connections = {}

        connections = component.GetConnections
        for conn in connections:
            dict_Net = {}
            # get segments
            conSegm = conn._GetSegment
            cmpPin = conn.CompPin
            Pin = cmpPin.Pin
            PinName = Pin.GetName(c.SHORT_NAME)
            type_attribute = Pin.FindAttribute("Pin Type")
            pin_architecture_uid_attribute = Pin.FindAttribute("Architecture UID")
            Pintype = type_attribute.Value
            PinSide = Pin.Side
            Net = conSegm.Parent
            Netname = Net.GetConnectedNetName(conSegm)
            # print(f"Connected Net: {Netname}")
            net_UID = Net.UID
            net_architecture_uid_attribute = Net.FindAttribute("Architecture UID")
            # print(f"Net UID: {net_UID}")
            if pin_architecture_uid_attribute:
                pin_architecture_uid = pin_architecture_uid_attribute.Value
            else:
                pin_architecture_uid = None

            if net_architecture_uid_attribute:
                net_architecture_uid = net_architecture_uid_attribute.Value
            else:
                net_architecture_uid = None

            pin_UID = Pin.UID
            net_UID = Net.UID

            dict_Net[Netname] = net_UID, net_architecture_uid
            singlePin_values = pin_UID, pin_architecture_uid, dict_Net
            # print(singlePin_values)

            # check, whether Pin is of type PowerX
            power_pin = any(value.lower() in PinName.lower() for value in const.Power_Pin_Identifier)

            if Pintype == const.PT_IN:
                dict_Control[PinName] = singlePin_values
            elif Pintype == const.PT_OUT:
                dict_Status[PinName] = singlePin_values
            elif Pintype == const.PT_BI:
                dict_Interface[PinName] = singlePin_values
            elif Pintype == const.PT_ANALOG:
                if power_pin and PinSide == const.PS_LEFT:
                    dict_PowerIn[PinName] = singlePin_values
                elif power_pin and PinSide == const.PS_RIGHT:
                    dict_PowerOut[PinName] = singlePin_values
                else:
                    dict_Analog[PinName] = singlePin_values

        dict_Pincategories[const.PowerIn] = dict_PowerIn
        dict_Pincategories[const.Control] = dict_Control
        dict_Pincategories[const.Analog] = dict_Analog
        dict_Pincategories[const.PowerOut] = dict_PowerOut
        dict_Pincategories[const.Interface] = dict_Interface
        dict_Pincategories[const.Status] = dict_Status
        dict_Pinlist["Pins"] = dict_Pincategories

        return dict_Pinlist

        # print(json.dumps(dict_Pinlist, indent=4))

    # info for functional parts
    def get_connections(self, component):
        # COM types Xpedition
        conn: IVdConnection = None
        net_conn: IVdConnection = None
        cmpPin: IVdCmpPin = None
        relComp: IVdComp = None
        Pin: IVdPin = None
        type_attribute: IVdAttr = None
        pin_architecture_uid_attribute: IVdAttr = None
        net_architecture_uid_attribute: IVdAttr = None
        refdes_attribute: IVdAttr = None
        conSegm: IVdSegment = None
        Net: IVdNet = None

        Netname = None

        dict_pin_cons = {}

        connections = component.GetConnections
        for conn in connections:
            # get segments
            conSegm = conn._GetSegment
            cmpPin = conn.CompPin
            Pin = cmpPin.Pin
            PinName = Pin.GetName(c.SHORT_NAME)
            # print("PinName: ", PinName)
            try:
                Net = conSegm.Parent
                Netname = Net.GetConnectedNetName(conSegm)
                # print(f"Connected Net: {Netname}")
                net_connections = Net.Connections
            except Exception as e:
                print(f"{e}")

            if Netname:
                dict_pin_cons[PinName] = Netname
            else:
                dict_pin_cons[PinName] = None

        return dict_pin_cons

    def get_components(self, app, design_block):
        # Lists
        block_list = []

        # Dictionaries
        dict_funct_parts = {}
        dict_block_parent = {}

        for block in app.SchematicSheetDocuments().GetAvailableSchematics():
            block_list.append(block)

        # Get components and build dictionaries
        lstComponents = app.DesignComponents("", design_block, "-1", "STD", True)
        for objComponent in lstComponents:
            short_name = objComponent.GetName(c.SHORT_NAME)
            full_path_name = objComponent.GetName(c.FULL_PATH_NAME)
            parent_block, design_level, super_parent_block = self.evaluate_design_level(full_path_name, short_name)
            objBlock = objComponent.SymbolBlock
            block_name = objBlock.GetName(c.SHORT_NAME)

            if block_name in block_list:
                if design_level == const.FUNCT_LEVEL:
                    # Ensure parent block exists in dict_block_parent
                    if parent_block not in dict_block_parent:
                        dict_block_parent[parent_block] = {}

                    # Ensure short_name exists as a key inside parent_block
                    if short_name not in dict_block_parent[parent_block]:
                        dict_block_parent[parent_block][short_name] = {}

                elif design_level == const.AE_LEVEL:
                    if short_name not in dict_funct_parts:
                        dict_funct_parts[short_name] = {}

        # print(json.dumps(dict_block_parts, indent=4))
        # print(json.dumps(dict_block_parent, indent=4))
        # print(json.dumps(dict_funct_parts, indent=4))

        # get Refdes and fill dicts
        lstComponents = app.DesignComponents("", design_block, "-1", "STD", True)
        for objComponent in lstComponents:
            ref_des_components = {}

            short_name = objComponent.GetName(c.SHORT_NAME)
            full_path_name = objComponent.GetName(c.FULL_PATH_NAME)
            parent_block, design_level, super_parent_block = self.evaluate_design_level(full_path_name, short_name)
            objBlock = objComponent.SymbolBlock
            block_name = objBlock.GetName(c.SHORT_NAME)
            RefDes = objComponent.Refdes

            if RefDes:
                gen_attr = self.get_attr_for_component(objComponent)
                pin_conn = self.get_connections(objComponent)
                ref_des_components[RefDes] = gen_attr, pin_conn
                if design_level == const.BLOCK_LEVEL:
                    dict_block_parent[super_parent_block][parent_block].update(ref_des_components)
                elif design_level == const.FUNCT_LEVEL:
                    dict_funct_parts[parent_block].update(ref_des_components)

        dict_components = self.merge_dicts_over_key(dict_block_parent, dict_funct_parts)
        # print(json.dumps(dict_funct_parts, indent=4))
        # print(json.dumps(dict_block_parent, indent=4))
        # print(json.dumps(dict_components, indent=4))

        return dict_components

    def generate_arch_structure_from_design(self):
        pass

    def get_attr_for_component(self, component):
        generic_attribute: IVdAttr = None

        generic_attributes = []
        # get system function
        for attr in const.attr_generic:
            generic_attribute = component.FindAttribute(f"{attr}")
            if generic_attribute:
                generic_attributes.append(generic_attribute.Value)
            else:
                generic_attributes.append("")

        return generic_attributes

    def get_components_for_ae(self, ae, all_components):
        dict_comp = {}
        dict_components_ae = self.find_key(all_components, ae)
        dict_comp["Components"] = dict_components_ae
        return dict_comp

# for testing functions ONLY!
def main():
    # connect to application
    asbc_connect.init_com
    objApplication = asbc_connect.connect_to_application()
    project_path = r"C:\Xpedition_Local\Auto_401\Auto_401.prj"
    # project_path = r"C:\Xpedition_Local\A0084L5495\A0084L5495.prj"
    asbc_connect.open_project(objApplication, project_path)
    strDesign = objApplication.GetProjectData().GetiCDBDesignRootBlock(objApplication.GetActiveDesign())
    print(f"str_des={strDesign}")

    # gather_design_info().get_blocks(objApplication, strDesign)

    # asbc_connect.close_project(objApplication)

if __name__ == "__main__":
    main()
