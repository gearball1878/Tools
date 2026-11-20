import json
from deepdiff import DeepDiff

class ArchJsonWriter:

    def __init__(self):
        self.system_dicts = []

    def add_system(self, system_name, system_arch_id = None, variants = None):
        system_dict = {}

        system_dict["System Name"] = system_name
        system_dict["System Arch ID"] = system_arch_id
        system_dict["System Variants"] = variants
        system_dict["System Ports"] = []
        system_dict["System Blocks"] = []
        system_dict["System Functions"] = []
        self.system_dicts.append(system_dict)

    def add_port_to_system(self, system_name, port_name, port_arch_id = None, port_scm_id = None, port_direction = None, variants = None):
        ports_dict = {}

        ports_dict["System Port Name"] = port_name
        ports_dict["System Port Arch ID"] = port_arch_id
        ports_dict["System Port SCM ID"] = port_scm_id
        ports_dict["System Port Direction"] = port_direction
        ports_dict["System Port Variants"] = variants
        
        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                system_dict["System Ports"].append(ports_dict)

    def add_module_to_system(self, system_name, module_name, module_arch_id = None, module_scm_id = None, module_color = "0xFFFFFF", variants = None):
        blocks_dict = {}

        blocks_dict["Module Name"] = module_name
        blocks_dict["Module Arch ID"] = module_arch_id
        blocks_dict["Module SCM ID"] = module_scm_id
        blocks_dict["Module Color"] = module_color
        blocks_dict["Module Variants"] = variants
        blocks_dict["Module Ports"] = []
        blocks_dict["Module Blocks"] = []
        blocks_dict["Module Functions"] = []    
        
        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                system_dict["System Blocks"].append(blocks_dict)

    def add_function_to_system(self, system_name, function_name, function_arch_id = None):
        functions_dict = {}

        functions_dict["System Function Name"] = function_name
        functions_dict["System Function Arch ID"] = function_arch_id

        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                system_dict["System Functions"].append(functions_dict)
        pass
        
    def add_port_to_module(self, system_name, module_name, port_name, port_arch_id = None, port_scm_id = None, port_direction = None, variants = None):
        ports_dict = {}

        ports_dict["Module Port Name"] = port_name
        ports_dict["Module Port Arch ID"] = port_arch_id
        ports_dict["Module Port SCM ID"] = port_scm_id
        ports_dict["Module Port Direction"] = port_direction
        ports_dict["Module Port Variants"] = variants
        
        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                for module_dict in system_dict["System Blocks"]:
                    if module_dict.get("Module Name") == module_name:
                        module_dict["Module Ports"].append(ports_dict)

    def add_ae_to_module(self, system_name, module_name, ae_name, ae_cust_name = None, ae_arch_id = None, ae_scm_id = None, ae_color = "0xFFFFFF", power_modes = None, ae_class = None, variants = None):
        ae_dict = {}

        ae_dict["AE Name"] = ae_name
        ae_dict["AE CustName"] = ae_cust_name
        ae_dict["AE Arch ID"] = ae_arch_id
        ae_dict["AE SCM ID"] = ae_scm_id
        ae_dict["AE Color"] = ae_color
        ae_dict["AE Power Modes"] = power_modes
        ae_dict["AE Class"] = ae_class
        ae_dict["AE Variants"] = variants
        ae_dict["AE Ports"] = []
        ae_dict["AE Components"] = []
        ae_dict["AE Functions"] = []
        
        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                for module_dict in system_dict["System Blocks"]:
                    if module_dict.get("Module Name") == module_name:
                        module_dict["Module Blocks"].append(ae_dict)

    def add_function_to_module(self, system_name, module_name, function_name, function_arch_id = None, function_type = None, asil = None):
        function_dict = {}

        function_dict["Module Function Name"] = function_name
        function_dict["Module Function Arch ID"] = function_arch_id
        function_dict["Module Function Type"] = function_type
        function_dict["Module Function ASIL"] = asil
        
        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                for module_dict in system_dict["System Blocks"]:
                    if module_dict.get("Module Name") == module_name:
                        module_dict["Module Functions"].append(function_dict)

    def add_port_to_ae(self, system_name, module_name, ae_name, port_name, port_arch_id = None, port_scm_id = None, port_direction = None, port_type = None, variants = None):
        ports_dict = {}

        ports_dict["AE Port Name"] = port_name
        ports_dict["AE Port Arch ID"] = port_arch_id
        ports_dict["AE Port SCM ID"] = port_scm_id
        ports_dict["AE Port Direction"] = port_direction
        ports_dict["AE Port Type"] = port_type
        ports_dict["AE Port Variants"] = variants
        ports_dict["AE Port Cons"] = []
        
        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                for module_dict in system_dict["System Blocks"]:
                    if module_dict.get("Module Name") == module_name:
                        for ae_dict in module_dict["Module Blocks"]:
                            if ae_dict.get("AE Name") == ae_name:
                                ae_dict["AE Ports"].append(ports_dict)

    def add_component_to_ae(self, system_name, module_name, ae_name, component_name, component_scm_id = None, variants = None):
        component_dict = {}

        component_dict["AE Component Name"] = component_name
        component_dict["AE Component SCM ID"] = component_scm_id
        component_dict["AE Component Variants"] = variants
        component_dict["AE Components"] = []

        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                for module_dict in system_dict["System Blocks"]:
                    if module_dict.get("Module Name") == module_name:
                        for ae_dict in module_dict["Module Blocks"]:
                            if ae_dict.get("AE Name") == ae_name:
                                ae_dict["AE Components"].append(component_dict)

    def add_component_to_ae_component(self, system_name, module_name, ae_name, ae_component_name, component_name, component_refdes = None):
        component_dict = {}

        component_dict["Component Name"] = component_name
        component_dict["Component RefDes"] = component_refdes

        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                for module_dict in system_dict["System Blocks"]:
                    if module_dict.get("Module Name") == module_name:
                        for ae_dict in module_dict["Module Blocks"]:
                            if ae_dict.get("AE Name") == ae_name:
                                for comp_dict in ae_dict["AE Components"]:
                                    if comp_dict.get("AE Component Name") == ae_component_name:
                                        comp_dict["AE Components"].append(component_dict)

    def add_function_to_ae(self, system_name, module_name, ae_name, function_name, function_arch_id = None, function_type = None, asil = None, states = None):
        function_dict = {}

        function_dict["AE Function Name"] = function_name
        function_dict["AE Function Arch ID"] = function_arch_id
        function_dict["AE Function Type"] = function_type
        function_dict["AE Function ASIL"] = asil
        function_dict["AE Function States"] = states

        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                for module_dict in system_dict["System Blocks"]:
                    if module_dict.get("Module Name") == module_name:
                        for ae_dict in module_dict["Module Blocks"]:
                            if ae_dict.get("AE Name") == ae_name:
                                ae_dict["AE Functions"].append(function_dict)

    def add_connectors_to_port(self, system_name, module_name, ae_name, port_name, connector_name, connector_scm_id = None, connector_type = None):
        con_dict = {}

        con_dict["Con Name"] = connector_name
        con_dict["Con SCM ID"] = connector_scm_id
        con_dict["Con Type"] = connector_type
        con_dict["Connectivity"] = []
        
        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                for module_dict in system_dict["System Blocks"]:
                    if module_dict.get("Module Name") == module_name:
                        for ae_dict in module_dict["Module Blocks"]:
                            if ae_dict.get("AE Name") == ae_name:
                                for port_dict in ae_dict["AE Ports"]:
                                    if port_dict.get("AE Port Name") == port_name:
                                        port_dict["AE Port Cons"].append(con_dict)

    def add_connectivity_to_connector(self, system_name, module_name, ae_name, port_name, connector_name, connector_arch_id = None, connected_port_arch_id = None, connected_port_scm_id = None):
        connectivity_dict = {}

        connectivity_dict["Connected Port Arch ID"] = connected_port_arch_id
        connectivity_dict["Connected Port SCM ID"] = connected_port_scm_id
        connectivity_dict["Connector Arch ID"] = connector_arch_id

        for system_dict in self.system_dicts:
            if system_dict.get("System Name") == system_name:
                for module_dict in system_dict["System Blocks"]:
                    if module_dict.get("Module Name") == module_name:
                        for ae_dict in module_dict["Module Blocks"]:
                            if ae_dict.get("AE Name") == ae_name:
                                for port_dict in ae_dict["AE Ports"]:
                                    if port_dict.get("AE Port Name") == port_name:
                                        for con_dict in port_dict["AE Port Cons"]:
                                            if con_dict.get("Con Name") == connector_name:
                                                con_dict["Connectivity"].append(connectivity_dict)

if __name__ == "__main__":

    writer = ArchJsonWriter()

    writer.add_system("Example_System_Name", "{1AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", ["Example_Variant_A", "Example_Variant_B"])

    writer.add_port_to_system("Example_System_Name", "Example_System_Port_Name", "{2AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", "SP$PP", "in", ["Example_Variant_A", "Example_Variant_B"])

    writer.add_module_to_system("Example_System_Name", "Example_Module_Name", "{3AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", "MM$MM", "0xFFFFFF", ["Example_Variant_A", "Example_Variant_B"])

    writer.add_function_to_system("Example_System_Name", "Example_System_Function_Name", "{BAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")

    writer.add_port_to_module("Example_System_Name", "Example_Module_Name", "Example_Module_Port_Name", "{4AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", "MP$PP", "in", ["Example_Variant_A", "Example_Variant_B"])

    writer.add_ae_to_module("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Customer_Name", "{5AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", "AA$AA", "0xFFFFFF", ["Example_AE_Power_Mode", "Example_Other_AE_Power_Mode"], "Example_AE_Class", ["Example_Variant_A", "Example_Variant_B"])

    writer.add_function_to_module("Example_System_Name", "Example_Module_Name", "Example_Module_Function_Name", "{0AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", "Software", "ASIL D")

    writer.add_port_to_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name", "{6AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", "AP$PP", "in", "Interface", ["Example_Variant_A", "Example_Variant_B"])

    writer.add_component_to_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Block_Name", "BB$BB", ["Example_Variant_A", "Example_Variant_B"])

    writer.add_component_to_ae_component("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Block_Name", "Example_AE_Component", "Example_AE_Component_RefDes")

    writer.add_function_to_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Function_Name", "{9AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", "Hardware", "ASIL D", ["Example_AE_Function_State", "Example_Other_AE_Function_State"])

    writer.add_connectors_to_port("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name", "Example_Con_Name", "CC$CC", "Bus")

    writer.add_connectivity_to_connector("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name", "Example_Con_Name", "{7AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", "{6AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}", "PC$CC")

    # Dump the updated list of dictionaries to a JSON file
    with open("Test_Export.json", 'w') as json_file:
        json.dump(writer.system_dicts, json_file, indent=4)

    print("Test Dictionary has been saved.")

    
    with open("Test_Export.json", 'r') as f1, open("arch_export_format.json", 'r') as f2:
        json1 = json.load(f1)
        json2 = json.load(f2)

    diff = DeepDiff(json1, json2, ignore_order=True)

    GREEN = '\033[92m'
    RESET = '\033[0m'

    if not diff:
        print(f"{GREEN}[SUCCESS] Writer creates specified format of file arch_export_format.json {RESET}")
    else:
        print(diff)