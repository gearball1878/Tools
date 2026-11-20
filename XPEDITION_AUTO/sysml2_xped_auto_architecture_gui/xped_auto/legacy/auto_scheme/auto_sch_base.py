from re import match
from winreg import REG_FULL_RESOURCE_DESCRIPTOR
from pathlib import Path
import sys

LEGACY_ROOT = Path(__file__).resolve().parents[1]
if str(LEGACY_ROOT) not in sys.path:
    sys.path.insert(0, str(LEGACY_ROOT))

import win32com.client as win32
import comtypes
import os
import time
import json
import re

from winioctlcon import FILE_PREFETCH_TYPE_FOR_CREATE

from ifc import *
from ifc import constants as c
from BusGenerator import *

import arch_json_reader as jr

class asbc_constants:
    # SheetSizes (LS: Landscape; PO: Portrait --> [Width, Height])
    SheetSize_A0_LS = [4680, 3310]
    SheetSize_A0_PO = [3310, 4680]
    SheetSize_A1_LS = [3310, 2340]
    SheetSize_A1_PO = [2340, 3310]
    SheetSize_A2_LS = [2340, 1650]
    SheetSize_A2_PO = [1650, 2340]
    SheetSize_A3_LS = [1650, 1170]
    SheetSize_A3_PO = [1170, 1650]
    # Blocksize Spare (distance to edge of pattern field)
    BlockSize_Spare = 200
    # Pin Categories
    PowerIn = "PowerIn"
    PowerOut = "PowerOut"
    Control = "Control"
    Status = "Status"
    Interface = "Interface"
    Analog = "Analog"
    Pincategories = [PowerIn, Control, Analog, PowerOut, Interface, Status]
    # Pincategories = [PowerIn, Control, PowerOut, Interface, Status]
    Pincategories_domain_level = [Control, Analog, Interface, Status]
    # Pincategories_domain_level = [Control, Interface, Status]
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
    # Hierarchical Connectors
    hierarchcal_con = ["con_hier_i", "con_hier_o", "con_hier_bi", "con_hier_power_in", "con_hier_power_out", "con_hier_analog"]
    # Block Renumbering
    RDR_TRUE = "True"
    RDR_FALSE = "False"
    RDR_REFRESH = "Refresh"
    RDR_UNFIXED = "Unfixed"
    # RefDes Dict
    REFDES_DICT = {
        "RD_PSU": {"RefDesStart": 100000, "naming_eqs": ["PSU", "WAKE"]},
        "RD_IUC": {"RefDesStart": 300000, "naming_eqs": ["SMC", "uC", "MCU", "MC"]},
        "RD_PSOC_CPU": {"RefDesStart": 400000, "naming_eqs": ["CPU", "SoC", "PSoC"]},
        "RD_PERI": {"RefDesStart": 450000, "naming_eqs": ["PER", "Peri", "USB", "PCIe"]},
        "RD_ETH": {"RefDesStart": 500000, "naming_eqs": ["ETH"]},
        "RD_VIDEO": {"RefDesStart": 550000, "naming_eqs": ["VID", "VIDEO"]},
        "RD_cIVN": {"RefDesStart": 600000, "naming_eqs": ["cIVN", "IVN"]},
        "RD_WIRELESS": {"RefDesStart": 650000, "naming_eqs": ["Wireless", "WL", "POS"]},
        "RD_AUDIO": {"RefDesStart": 700000, "naming_eqs": ["AUD", "Audio"]},
        "RD_SENSE": {"RefDesStart": 750000, "naming_eqs": ["SENSE"]},
        "RD_DEBUG": {"RefDesStart": 800000, "naming_eqs": ["Debug", "DBG"]},
        "RD_MEM": {"RefDesStart": 850000, "naming_eqs": ["MEM", "SSD"]},
        "RD_CON": {"RefDesStart": 900000, "naming_eqs": ["CON"]}
    }
    RefDesStart_Con = 900000
    # Domain Sizes
    RD_SIZE_BIG = 200000
    RD_SIZE_NORMAL = 100000
    RD_SIZE_SMALL = 50000
    # RefDes Increments
    RDI_BLOCK = 1000
    RDI_INTER_DOMAIN = 50000
    # Block size Rating
    BSIZE_SMALL = "SMALL"
    BSIZE_BIG = "BIG"
    # design level
    DL_TOP = "TOPLEVEL"
    DL_DOMAIN = "DOMAIN"
    DL_AE = "AE"

# basic classes
class SetLocation:
    def __init__(self, lowerleft_x, lowerleft_y, upperright_x, upperright_y):
        # round to grit (0.100 inch)!
        self.lowerleft_x = round(lowerleft_x / 10) * 10
        self.lowerleft_y = round(lowerleft_y / 10) * 10
        self.upperright_x = round(upperright_x / 10) * 10
        self.upperright_y = round(upperright_y / 10) * 10

        # print(f"SetBlockLocation: ll_x={self.lowerleft_x}, ll_y={self.lowerleft_y}, ur_x={self.upperright_x}, ur_y={self.upperright_y}")

    def __repr__(self):
        return (f"SetLocation(lowerleft_x={self.lowerleft_x}, "
                f"lowerleft_y={self.lowerleft_y}, "
                f"upperright_x={self.upperright_x}, "
                f"upperright_y={self.upperright_y})")

class asbc_data_exchange:
    def __init__(self, jfile, interface_template=None):
        self.jfile = jfile
        self.jfile_reader = jr.ArchJsonReader(self.jfile)
        self.system = self.jfile_reader.get_system_names()[0]
        self.interface_template = interface_template

    def domain_for_ae(self, ae):
        for domain in self.jfile_reader.get_domain_names(self.system):
            if ae in self.jfile_reader.get_ae_names_for_domain(self.system, domain):
                return domain
        raise KeyError(f"Architecture element not found: {ae}")

    # get full Pin Information dependent on the Design Level! (CONs are on top!)
    def PinInfo(self, system, arch_element, domains, pin_name, design_level):
        netinfo_default = {'NoNet': [None, None, None]}
        if design_level == asbc_constants.DL_AE:
            domain = self.domain_for_ae(arch_element)
            pins_ae = self.jfile_reader.get_pin_names_for_ae(system, domain, arch_element)
            # print(pins)
            for category in pins_ae.keys():
                # print(category)
                pins_per_cat = self.jfile_reader.get_pins_of_type_for_ae(system, domain, arch_element, category)
                print(list(pins_per_cat.keys()))
                for Pin in pins_per_cat:
                    # print(Pin)
                    if Pin == pin_name:
                        netinfo = self.jfile_reader.get_nets_for_pin_of_ae(system, domain, arch_element, Pin)
                        if netinfo == {}:
                            return netinfo_default, category
                        else:
                            return netinfo, category
                        break

        elif design_level == asbc_constants.DL_DOMAIN:
            for domain in domains:
                aes = self.jfile_reader.get_ae_names_for_domain(system, domain)
                for ae in aes:
                    pins_ae = self.jfile_reader.get_pins_for_ae(system, domain, ae)
                    for category in pins_ae.keys():
                        pins_per_cat = self.jfile_reader.get_pins_of_type_for_ae(system, domain, ae, category)
                        print(list(pins_per_cat.keys()))
                        for Pin in pins_per_cat:
                            if Pin == pin_name:
                                netinfo = self.jfile_reader.get_nets_for_pin_of_ae(system, domain, ae, Pin)
                                if netinfo == {}:
                                    return netinfo_default, category
                                else:
                                    return netinfo, category
                                break

        elif design_level == asbc_constants.DL_TOP:
            aes = self.jfile_reader.get_ae_names_for_domain(system, "CON")
            for ae in aes:
                pins_ae = self.jfile_reader.get_pins_for_ae(system, "CON", ae)
                for category in pins_ae.keys():
                    pins_per_cat = self.jfile_reader.get_pins_of_type_for_ae(system, "CON", ae, category)
                    print(list(pins_per_cat.keys()))
                    for Pin in pins_per_cat:
                        if Pin == pin_name:
                            netinfo = self.jfile_reader.get_nets_for_pin_of_ae(system, "CON", ae, Pin)
                            if netinfo == {}:
                                return netinfo_default, category
                            else:
                                return netinfo, category
                            break

    # get the full netinformation from the JSON exchange format
    def net_info_full(self, system):
        net_info = {}

        domains = self.jfile_reader.get_domain_names(system)
        for domain in domains:
            try:
                aes = self.jfile_reader.get_ae_names_for_domain(system, domain)
                print("DOMAIN: ", domain)
                print("AES: ", aes)
            except Exception as e:
                print(f"No key for {e}")
                continue

            for ae in aes:
                print("AE: ", ae)
                for category in asbc_constants.Pincategories:
                    try:
                        # pins_ae = self.jfile_reader.get_pin_names_for_ae(system, domain, ae)
                        pins_ae = self.jfile_reader.get_pin_names_for_ae(system, domain, ae)
                        print("PINS_AE: ", pins_ae)
                    except Exception as e:
                        print(f"No key for {e}")
                        continue

                    for Pin in pins_ae:
                        try:
                            net_ae = self.jfile_reader.get_nets_for_pin_of_ae(system, domain, ae, Pin)
                            net_names = net_ae["Con Name"].tolist() if "Con Name" in net_ae else []
                        except Exception as e:
                            print(f"No key for {e}")
                            continue
                        for net in net_names:
                            if net not in net_info:
                                net_info[net] = []
                            entry = (domain, ae, Pin, category)
                            if entry not in net_info[net]:
                                net_info[net].append(entry)

        return net_info

    # gather all pins from all AEs within a single domain, to see the connectivity over the design!
    def pins_per_cat_domain(self, domain, pin_category, net_info):
        category_type_pins_domain = []
        # all_nets_on_aes = []
        aes = self.jfile_reader.get_ae_names_for_domain(self.system, domain)
        # where do the nets go?
        for net, info in net_info.items():
            for ae in aes:
                pins_ae = self.jfile_reader.get_pins_of_type_for_ae(self.system, domain, ae, pin_category)
                for Pin in pins_ae:
                    net_ae_dict = self.jfile_reader.get_nets_for_pin_of_ae(self.system, domain, ae, Pin)
                    try:
                        net_ae = list(net_ae_dict.keys())[0]
                    except IndexError:
                        net_ae = None
                        # print(f"Warning: No nets found for Pin '{Pin}' in AE '{ae}' under domain '{domain}'.")
                    if net == net_ae:
                        no_conns = len(info)
                        for i in range(no_conns):
                            conn_domain = info[i][0]
                            # only add Pin to Domain, when a net from a Pin is going to another domain
                            if conn_domain != domain:
                                category_type_pins_domain.append(Pin)
        # remove duplicates, keep order
        unique_list = list(dict.fromkeys(category_type_pins_domain))
        return unique_list


    def split_string_number(self, input_data):
        if isinstance(input_data, str):  # If a single string, convert to a list
            input_data = [input_data]

        result = []
        for s in input_data:
            prefix, num = s.rsplit("_", 1)  # Split at the last underscore
            result.append((prefix, int(num)))  # Convert num to int
        return result

    def gen_busses_for_project(self, bc_file):
        if_template = self.interface_template
        if not if_template:
            raise ValueError("An Interface_Template_File.json path is required.")
        net_info_full = self.net_info_full(self.system)

        # Step 1: Empty the file (or create it if it doesn’t exist)
        with open(bc_file, "w") as file:
            pass  # This will clear the file

        # Now recreate the file in append mode
        with open(bc_file, "a+") as file:
            for net_info in net_info_full:
                if "link" in net_info.lower():
                    result = self.split_string_number(str(net_info))  # Ensure net_info is in a list
                    IF_type = result[0][0]
                    IF_number = result[0][1]
                    IF_type = re.sub(r"(?i)link", "[Link/Port]", IF_type)

                    try:
                        new_bus = BusGenerator(bc_file, if_template).GenInterfaces(IF_type, IF_number, 1, "Link")
                        print(new_bus)
                        file.write(new_bus[0] + "\n")  # Append new_bus to the file
                    except Exception as e:
                        print(e)


# connect class
class asbc_connect:
    def __init__(self, progid, project_path):
        self.project_path = project_path
        self.progid = progid

    # Initialize and cleanup COM
    def init_com(self):
        try:
            comtypes.CoInitialize()
        except Exception as e:
            print(f"Error initializing COM: {e}")

    def cleanup_com(self):
        try:
            comtypes.CoUninitialize()
        except Exception as e:
            print(f"Error uninitializing COM: {e}")

    def connect_to_application(self):
        """Reconnect to the application."""
        retries = 5
        for attempt in range(retries):
            try:
                self.app = win32.Dispatch(self.progid)
                print(f"Successfully connected to {self.progid}.")
                return self.app
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2)  # Wait before retrying
        raise RuntimeError(f"Unable to connect to {self.progid} after {retries} attempts.")

    def open_project(self):
        """Open a specific project using the COM API."""
        try:
            self.app.OpenProject(self.project_path)
        except Exception as e:
            raise RuntimeError(f"Error opening project {self.project_path}: {e}") from e

    def close_project(self):
        """Open a specific project using the COM API."""
        self.app.CloseProject()

# routine class
class asbc_routines:
    def __init__(self, jfile):
        self.jfile = jfile
        self.jfile_reader = jr.ArchJsonReader(self.jfile)
        self.data_exchange = asbc_data_exchange(self.jfile)
        self.system = self.jfile_reader.get_system_names()[0]

    def domain_for_ae(self, ae):
        for domain in self.jfile_reader.get_domain_names(self.system):
            if ae in self.jfile_reader.get_ae_names_for_domain(self.system, domain):
                return domain
        raise KeyError(f"Architecture element not found: {ae}")

    def get_number_at_end(self, s):
        match = re.search(r'\d+$', s)
        if match:
            return int(match.group())  # Return the number as an integer
        return None  # Return None if no number is found

    def hex_to_rgb(self, hex_color):
        """
        Convert a hex color code to its RGB components.

        Args:
        hex_color (str): Hex color string in the format '#RRGGBB'.

        Returns:
        tuple: A tuple (R, G, B) with values ranging from 0 to 255.
        """
        hex_color = hex_color.lstrip('#')  # Remove '#' if present
        if len(hex_color) != 6:
            raise ValueError("Invalid hex color format. Must be '#RRGGBB'.")

        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return r, g, b

    # calculate Blocksize with the amount of pins
    def calculate_blocksize(self, no_pins, spare = 20, pindistance = 20, y_indent = 40, design_Level = asbc_constants.DL_DOMAIN):
        # variables
        spare_factor_left = 0
        spare_factor_right = 0
        # minimum dimensions of a block
        min_width = 200
        min_height = 200

        if design_Level == asbc_constants.DL_AE:
            # number of pins per category
            no_pwr_in_pins = no_pins[0]
            no_control_pins = no_pins[1]
            no_analog_pins = no_pins[2]
            # no_analog_pins = 0
            no_pwr_out_pins = no_pins[3]
            no_interfaces = no_pins[4]
            no_status_pins = no_pins[5]
        elif design_Level in (asbc_constants.DL_DOMAIN, asbc_constants.DL_TOP):
            no_pwr_in_pins = 0
            no_control_pins = no_pins[0]
            no_analog_pins = no_pins[1]
            # no_analog_pins = 0
            no_pwr_out_pins = 0
            no_interfaces = no_pins[2]
            no_status_pins = no_pins[3]

        # calculate the spare room
        if no_pwr_in_pins:
            spare_factor_left = spare_factor_left + 1
        if no_control_pins:
            spare_factor_left = spare_factor_left + 1
        if no_analog_pins:
            spare_factor_left = spare_factor_left + 1

        if no_pwr_out_pins:
            spare_factor_right = spare_factor_right + 1
        if no_interfaces:
            spare_factor_right = spare_factor_right + 1
        if no_status_pins:
            spare_factor_right = spare_factor_right + 1

        blocksize_left = (no_pwr_in_pins + no_control_pins + no_analog_pins) * pindistance + spare_factor_left * spare
        blocksize_right = (no_status_pins + no_interfaces + no_pwr_out_pins) * pindistance + spare_factor_right * spare
        if blocksize_left >= blocksize_right:
            blocksize_x = blocksize_left
            blocksize_y = blocksize_left + 2 * y_indent
            if blocksize_x < min_width:
                blocksize_x = min_width
            if blocksize_y < min_height:
                blocksize_y = min_height
        else:
            blocksize_x = blocksize_right
            blocksize_y = blocksize_right + 2 * y_indent
            if blocksize_x < min_width:
                blocksize_x = min_width
            if blocksize_y < min_height:
                blocksize_y = min_height

        if blocksize_y <= asbc_constants.SheetSize_A2_LS[1] - asbc_constants.BlockSize_Spare:
            sheetsize = asbc_constants.SheetSize_A2_LS
        elif blocksize_y > (asbc_constants.SheetSize_A2_LS[1] - asbc_constants.BlockSize_Spare) and blocksize_y <= (asbc_constants.SheetSize_A1_LS[1] - asbc_constants.BlockSize_Spare):
            sheetsize = asbc_constants.SheetSize_A1_LS
        elif blocksize_y > (asbc_constants.SheetSize_A1_LS[1] - asbc_constants.BlockSize_Spare) and blocksize_y <= (asbc_constants.SheetSize_A0_LS[1] - asbc_constants.BlockSize_Spare):
            sheetsize = asbc_constants.SheetSize_A0_LS
        else:
            sheetsize = asbc_constants.SheetSize_A0_LS

        return blocksize_x, blocksize_y, sheetsize

    # gather next free spot on a given page to place a new block
    def next_free_spot(self, app, domain, strDesign, num_sheets, toplevel_blocks):
        count_blocks_on_page = 0
        all_refdes_starts = []
        count_sheets = 0
        sheet_info = {}
        spot_free = True
        next_free_spot = 0
        next_free_sheet = ""
        all_blocks = []
        placed_blocks = []
        placed_blocks_small = []
        placed_blocks_big = []

        block_size_info = {}
        block_info = {}  # Key: Name, Values --> size, located on sheet?
        block_dim_x = []
        block_dim_y = []
        block_size_placed = []
        placed_blocks_dim = []
        size_rating = asbc_constants.BSIZE_SMALL

        if domain == "CON":
            lstComponents = app.DesignComponents("", strDesign, "-1", "STD", False)
        else:
            lstComponents = app.DesignComponents("", domain, "-1", "STD", False)

        for objComponent in lstComponents:
            # Name = objComponent.GetName(0)
            location = objComponent.GetLocation
            objBlock = objComponent.Symbolblock
            Fub = objBlock.IsFub
            Name = objBlock.GetName(c.SHORT_NAME)
            if Fub and Name not in toplevel_blocks:
                objBlockParent = objComponent.Parent
                SheetNum = objBlockParent.SheetNum
                placed_blocks.append(Name)
                for vd_corner in [c.VDLOWERLEFT, c.VDUPPERRIGHT]:
                    block_dim = objBlock.GetBboxPoint(vd_corner)
                    block_dim_x.append(block_dim.X)
                    block_dim_y.append(block_dim.Y)

                block_size_placed = [max(block_dim_x) - min(block_dim_x), max(block_dim_y) - min(block_dim_y)]
                if block_size_placed[1] <= (asbc_constants.SheetSize_A2_LS[1] - asbc_constants.BlockSize_Spare) / 2:
                    placed_blocks_small.append(Name)
                    size_rating = asbc_constants.BSIZE_SMALL
                else:
                    placed_blocks_big.append(Name)
                    size_rating = asbc_constants.BSIZE_BIG

                block_info[Name] = SheetNum, size_rating

                # print("Block Name: ", Name)
                # print("RefDes Start = ", refdes_start_block, all_refdes_starts)
                # print("Location: ", location.X, location.Y)

        for l in range(num_sheets):
            current_sheet_name = f"{domain}_{l + 1}"
            for block_meta in block_info:
                block_on_sheet = block_info[block_meta][0]
                size_rating = block_info[block_meta][1]
                if block_on_sheet == current_sheet_name:
                    if size_rating == asbc_constants.BSIZE_SMALL:
                        count_blocks_on_page = count_blocks_on_page + 1
                        if count_blocks_on_page < 4:
                            spot_free = True
                        elif count_blocks_on_page == 4:
                            count_blocks_on_page = 0
                            spot_free = False
                        else:
                            next_free_sheet = block_on_sheet
                    elif size_rating == asbc_constants.BSIZE_BIG:
                        # count_blocks_on_page = 1
                        spot_free = False

            sheet_info[current_sheet_name] = spot_free, count_blocks_on_page

        for sheet in sheet_info:
            count_sheets = count_sheets + 1
            if sheet_info[sheet][0] == True:
                print(sheet)
                next_free_spot = count_blocks_on_page + 1
                next_free_sheet = sheet
                break
            else:
                if count_sheets == num_sheets:
                    next_free_spot = 1
                    next_sheet_cnt = self.get_number_at_end(sheet) + 1
                    next_free_sheet = f"{domain}_{next_sheet_cnt}"

        return next_free_spot, next_free_sheet

    # Determin Reference Designator Start Value per Block (Connectors, Domains, Architectural Elements only); values in naming equivalents are NOT case-sensitive!
    def generate_rd_start(self, domain, sub_domains, sub_domain_cnt, internal_offset, domain_size):
        rd_start = 0
        length_sub = 0
        domain_offset = 0
        if sub_domains:
            length_sub = len(sub_domains)
            # integer fractioning
            domain_offset = domain_size//length_sub
        # Iterate through REFDES_DICT
        for rd_name, rd_data in asbc_constants.REFDES_DICT.items():
            naming_eqs = rd_data["naming_eqs"]  # Access naming equivalents
            # Check substrings with case insensitivity
            found = any(value.lower() in domain.lower() for value in naming_eqs)  # Convert to lowercase
            if found:
                # print(f"{rd_name} matches: {found}")
                rd_start = rd_data["RefDesStart"]  # Set the RefDesStart value
                break

        rd_start = rd_start + sub_domain_cnt*domain_offset + internal_offset
        # print(rd_start)
        return rd_start

    # gather placed pins to calculate position of newly added pins!
    def placed_pins(self, app, block):
        symbol_Block = app.SchematicSheetDocuments().OpenSymbol(block, "1")
        placed_pins = {}
        i = 0  # only 0° Orientation in Symbol View considered
        for View in symbol_Block.GetViews():
            if i == 0:
                i = i + 1
                View.Activate()
                # Pins_x = []
                # Pins_y = []
                Pins = View.Query(c.VDM_PIN, c.VD_ALL)
                for Pin in Pins:
                    PinName = Pin.GetName(c.SHORT_NAME)
                    # placed_Pins.append(PinName)
                    PinLocation = Pin.GetLocation(c.VDPIN_INTERIOR)
                    placed_pins[PinName] = [PinLocation.X, PinLocation.Y]

        return placed_pins

    # add Functional Block (Fub) to design with RefDes Start- and Renumber-Property. Also Add Systemfunction and IDs to AEs if already known
    def add_block(self, block, new_name, location: SetLocation, RefDesStart, ea_Id, sys_funct):
        new_block: IVdComp = None
        symbolblock: IVdBlock = None
        try:
            new_block = block.AddFub(f"{new_name}", location.lowerleft_x, location.lowerleft_y, location.upperright_x, location.upperright_y)
            block_location = new_block.GetLocation
            # print("BLOCK_LOCATION:", block_location.X, block_location.Y)
            #add ea_Id to
            if ea_Id != None:
                new_block.AddAttribute(f"Architecture UID = {ea_Id}", block_location.X, block_location.Y, c.VDINVISIBLE)
            if sys_funct != None:
                new_block.AddAttribute(f"System Function = {sys_funct}", block_location.X, block_location.Y, c.VDINVISIBLE)
            # add RefDesStart to Block
            if RefDesStart != None:
                new_block.AddAttribute(f"RefDes Start={RefDesStart}", block_location.X, block_location.Y - 10, c.VDVISIBLE)
                new_block.AddAttribute(f"RefDes Renumber={asbc_constants.RDR_TRUE}", block_location.X, block_location.Y - 20, c.VDVISIBLE)
        except Exception as e:
            print(f"Error adding Fub {block}: {e}")

    def update_blocksize(self, app, block, new_blocksize):
        symbol_Block = app.SchematicSheetDocuments().OpenSymbol(block, "1")
        i = 0  # only 0° Orientation in Symbol View considered
        for View in symbol_Block.GetViews():
            if i == 0:
                i = i + 1
                box = 0
                start_pnt_from_top = 0
                pin_cnt = 0
                Box_x_old = []
                Box_y_old = []
                Box_x = []
                Box_y = []

                Box_delta_x = 0
                Box_delta_y = 0

                Boxes = View.Query(c.VDM_BOX, c.VD_ALL)
                for Box in Boxes:
                    for loc_const in [c.VDLOWERLEFT, c.VDUPPERRIGHT]:
                        Location = Box.GetLocation(loc_const)
                        Box_x_old.append(Location.X)
                        Box_y_old.append(Location.Y)

                Box_delta_x = new_blocksize[0] - max(Box_x_old)
                Box_delta_y = new_blocksize[1] - max(Box_y_old)

                Boxes = View.Query(c.VDM_BOX, c.VD_ALL)
                for Box in Boxes:
                    if box == 0:
                        Box.SetLocation(10, 10, new_blocksize[0] - 10, new_blocksize[1] - 10)
                    elif box == 1:
                        Box.SetLocation(0, 0, new_blocksize[0], new_blocksize[1])
                    box = box + 1

                    for loc_const in [c.VDLOWERLEFT, c.VDUPPERRIGHT]:
                        Location = Box.GetLocation(loc_const)
                        Box_x.append(Location.X)
                        Box_y.append(Location.Y)

        symbol_Block.UpdateSymbolInDesign()
        symbol_Block.Close(False, "none")

        return Box_delta_x, Box_delta_y

    # unused!
    # def add_update_border_symbol(self, block, sheetsize, first_sheet):
    #     # block : IVdBlock = None
    #     sym_partition = "Borders"
    #     sym_border = ""
    #     if sheetsize == c.VDSHEET_A0_SIZE:
    #         if first_sheet == True:
    #             sym_border = "gee_a0glbl1_landscape_xa"
    #         else:
    #             sym_border = "gee_a0glbl2_landscape_xa"
    #     elif sheetsize == c.VDSHEET_A1_SIZE:
    #         if first_sheet == True:
    #             sym_border = "gee_a1glbl1_landscape_xa"
    #         else:
    #             sym_border = "gee_a1glbl2_landscape_xa"
    #     elif sheetsize == c.VDSHEET_A2_SIZE:
    #         if first_sheet == True:
    #             sym_border = "gee_a2glbl1_landscape_xa"
    #         else:
    #             sym_border = "gee_a2glbl2_landscape_xa"
    #     else:
    #         if first_sheet == True:
    #             sym_border = "gee_a2glbl1_landscape_xa"
    #         else:
    #             sym_border = "gee_a2glbl2_landscape_xa"
    #
    #     try:
    #         block.AddSymbolInstance(sym_partition, sym_border, 0, 0)
    #         # time.sleep(300 / 1000)
    #     except Exception as e:
    #         print(f"Error adding Border: {e}")

    def update_block(self, app, category, block, PinList, no_pins, design_level):
        # defintions for COM Object access
        NewPin: IVdPin = None
        View: IVdView = None
        Box: IVdBox = None
        symbol_Block: IVdDoc = None
        activeBlock: IVdBlock = None
        Pin: IVdPin = None
        PinLabel: IVdLabel = None

        # initialize variables
        no_unplaced_pins = 0

        # number of pins per category dependent of design level
        if design_level == asbc_constants.DL_AE:
            no_pwr_in_pins = no_pins[0]
            no_control_pins = no_pins[1]
            no_analog_pins = no_pins[2]
            # no_analog_pins = 0
            no_pwr_out_pins = no_pins[3]
            no_interfaces = no_pins[4]
            no_status_pins = no_pins[5]
        elif design_level in (asbc_constants.DL_DOMAIN, asbc_constants.DL_TOP):
            no_pwr_in_pins = 0
            no_control_pins = no_pins[0]
            no_analog_pins = no_pins[1]
            # no_analog_pins = 0
            no_pwr_out_pins = 0
            no_interfaces = no_pins[2]
            no_status_pins = no_pins[3]

        placed_pins = []
        placed_pins_category = []
        unplaced_pins = []
        pin_locations_x = []
        pin_locations_y = []

        placed_pin_info = self.placed_pins(app, block)
        for PinName, PinLocation in placed_pin_info.items():
            for Pin in PinList:
                if Pin == PinName:
                    placed_pins_category.append(Pin)
                    pin_locations_x.append(PinLocation[0])
                    pin_locations_y.append(PinLocation[1])
                    break

        unplaced_pins = [x for x in PinList if x not in placed_pins_category]
        deleted_pins_in_arch = [x for x in placed_pins_category if x not in PinList]

        if sorted(placed_pins_category) != sorted(PinList):
            symbol_Block = app.SchematicSheetDocuments().OpenSymbol(block, "1")
            i = 0 # only 0° Orientation in Symbol View considered
            for View in symbol_Block.GetViews():
                if i == 0:
                    i = i + 1
                    box = 0
                    start_pnt_from_top  = 0
                    pin_cnt = 0
                    Box_x=[]
                    Box_y=[]

                    Boxes = View.Query(c.VDM_BOX, c.VD_ALL)
                    for Box in Boxes:
                        for loc_const in [c.VDLOWERLEFT, c.VDUPPERRIGHT]:
                            Location = Box.GetLocation(loc_const)
                            Box_x.append(Location.X)
                            Box_y.append(Location.Y)

                    Pins = View.Query(c.VDM_PIN, c.VD_ALL)
                    if placed_pins_category:
                        maxPinLocation_y_old = max(pin_locations_y)

                    for Pin in Pins:
                        PinName = Pin.GetName(c.SHORT_NAME)
                        if PinName in placed_pins_category:
                            PinLabel = Pin.Label
                            PinLocationInterior = Pin.GetLocation(c.VDPIN_INTERIOR)
                            PinLocationBoundary = Pin.GetLocation(c.VDPIN_BOUNDARY)
                            if category == asbc_constants.PowerIn:
                                start_pnt_from_top = max(Box_y) - 40
                                delta_y = start_pnt_from_top - maxPinLocation_y_old
                                x_interior_new = PinLocationInterior.X
                                x_boundary_new = PinLocationBoundary.X
                                y_new = (PinLocationInterior.Y + delta_y)
                                x_label_new = PinLocationInterior.X + 10
                            elif category == asbc_constants.Control:
                                start_pnt_from_top = max(Box_y)  - no_pwr_in_pins*20 - 2*40
                                delta_y = start_pnt_from_top - maxPinLocation_y_old
                                x_interior_new = PinLocationInterior.X
                                x_boundary_new = PinLocationBoundary.X
                                y_new = (PinLocationInterior.Y + delta_y)
                                x_label_new = PinLocationInterior.X + 10
                            elif category == asbc_constants.Analog:
                                start_pnt_from_top = max(Box_y)  - no_pwr_in_pins*20 - no_analog_pins*20 - 3*40
                                delta_y = start_pnt_from_top - maxPinLocation_y_old
                                x_interior_new = PinLocationInterior.X
                                x_boundary_new = PinLocationBoundary.X
                                y_new = (PinLocationInterior.Y + delta_y)
                                x_label_new = PinLocationInterior.X + 10
                            elif category == asbc_constants.PowerOut:
                                start_pnt_from_top = max(Box_y) - 40
                                delta_y = start_pnt_from_top - maxPinLocation_y_old
                                x_interior_new = max(Box_x) - 10
                                x_boundary_new = max(Box_x)
                                y_new = (PinLocationInterior.Y + delta_y)
                                x_label_new = x_interior_new - 10
                            elif category == asbc_constants.Interface:
                                start_pnt_from_top = max(Box_y) - no_pwr_out_pins*20 - 2*40
                                delta_y = start_pnt_from_top - maxPinLocation_y_old
                                x_interior_new = max(Box_x) - 10
                                x_boundary_new = max(Box_x)
                                y_new = (PinLocationInterior.Y + delta_y)
                                x_label_new = x_interior_new - 10
                            elif category == asbc_constants.Status:
                                start_pnt_from_top = max(Box_y) - no_pwr_out_pins*20 - no_interfaces*20 - 3*40
                                delta_y = start_pnt_from_top - maxPinLocation_y_old
                                x_interior_new = max(Box_x) - 10
                                x_boundary_new = max(Box_x)
                                y_new = (PinLocationInterior.Y + delta_y)
                                x_label_new = x_interior_new - 10

                            # Set new Pin Location!
                            Pin.SetLocation(x_interior_new, y_new, x_boundary_new, y_new)
                            PinLabel.SetLocation(x_label_new, y_new)
                            # symbol_Block.UpdateSymbolInDesign()

                            pin_cnt = pin_cnt + 1

            symbol_Block.UpdateSymbolInDesign()
            symbol_Block.Close(False, "none")
        else:
            print("No unplaced Pins --> Block didn't change")


    # add Pins to Symbol of Fubs depending on their category #TODO: add dynamic pinspacing per category if needed!
    def add_pins(self, app, category, block, PinList, no_pins, design_level):
        # defintions for COM Object access
        NewPin: IVdPin = None
        View: IVdView = None
        Box: IVdBox = None
        symbol_Block: IVdDoc = None
        activeBlock: IVdBlock = None
        Pin: IVdPin = None

        # constants
        SPARE_BTW_PINGROUPS = 40

        # initialize variables
        cnt_pins = 0
        dummy_pin = "DUMMY"
        x = 0
        y = 0
        x_interior = 0
        y_max_interior = 0
        x_boundery = 0
        y_max_boundery = 0
        x_label = 0
        y_label = 0

        # placed_pins = []
        placed_pins_category = []
        # unplaced_pins = []
        pin_locations_x = []
        pin_locations_y = []

        # number of pins per category dependent of design level
        if design_level == asbc_constants.DL_AE:
            no_pwr_in_pins = no_pins[0]
            no_control_pins = no_pins[1]
            no_analog_pins = no_pins[2]
            # no_analog_pins = 0
            no_pwr_out_pins = no_pins[3]
            no_interfaces = no_pins[4]
            no_status_pins = no_pins[5]
        elif design_level in (asbc_constants.DL_DOMAIN, asbc_constants.DL_TOP):
            no_pwr_in_pins = 0
            no_control_pins = no_pins[0]
            no_analog_pins = no_pins[1]
            # no_analog_pins = 0
            no_pwr_out_pins = 0
            no_interfaces = no_pins[2]
            no_status_pins = no_pins[3]

        placed_pin_info = self.placed_pins(app, block)
        for PinName, PinLocation in placed_pin_info.items():
            for Pin in PinList:
                if Pin == PinName:
                    placed_pins_category.append(Pin)
                    pin_locations_x.append(PinLocation[0])
                    pin_locations_y.append(PinLocation[1])
                    break

        # workaround (part 1) to get rid of the rotated first Pin on the right side of each block!
        if design_level == asbc_constants.DL_AE:
            if category == asbc_constants.PowerOut and not placed_pins_category:
                PinList.insert(0, dummy_pin)
        elif design_level in (asbc_constants.DL_DOMAIN, asbc_constants.DL_TOP):
            if category == asbc_constants.Interface and not placed_pins_category:
                PinList.insert(0, dummy_pin)

        unplaced_pins = [x for x in PinList if x not in placed_pins_category]

        symbol_Block = app.SchematicSheetDocuments().OpenSymbol(block, "1")
        # no_pins = len(PinList)
        i = 0 # only 0° Orientation in Symbol View considered
        for View in symbol_Block.GetViews():
            if i == 0:
                View.Activate()
                i = i + 1
                activeBlock = View.ActiveBlock()
                if sorted(placed_pins_category) != sorted(PinList):
                    # print(activeBlock.GetName(1))
                    Box_x=[]
                    Box_y=[]
                    Boxes = View.Query(c.VDM_BOX, c.VD_ALL)
                    for Box in Boxes:
                        for loc_const in [c.VDLOWERLEFT, c.VDUPPERRIGHT]:
                            Location = Box.GetLocation(loc_const)
                            Box_x.append(Location.X)
                            Box_y.append(Location.Y)

                    min_y_value = min(pin_locations_y) if pin_locations_y else max(Box_y) - 20
                    # max_y_value = max(pin_locations_y) if pin_locations_y else min(Box_y) + 20

                    for Pin in unplaced_pins:
                        if Pin != dummy_pin:
                            cnt_pins = cnt_pins + 1
                        if category == asbc_constants.PowerIn:
                            pintype = asbc_constants.PT_ANALOG
                            x_interior = min(Box_x) + 10
                            y_max_interior = min_y_value - 20*cnt_pins
                            x_boundery = min(Box_x)
                            y_max_boundery = min_y_value - 20*cnt_pins
                            x_label = x_interior + 10
                            y_label = y_max_boundery
                        elif category == asbc_constants.Control:
                            pintype = asbc_constants.PT_IN
                            x_interior = min(Box_x) + 10
                            if placed_pins_category:
                                y_max_interior = min_y_value - 20 * cnt_pins
                                y_max_boundery = min_y_value - 20 * cnt_pins
                            else:
                                y_max_interior = min_y_value - 20 * cnt_pins - no_pwr_in_pins * 20 - SPARE_BTW_PINGROUPS
                                y_max_boundery = min_y_value - 20 * cnt_pins - no_pwr_in_pins * 20 - SPARE_BTW_PINGROUPS
                            x_boundery = min(Box_x)
                            x_label = x_interior + 10
                            y_label = y_max_boundery
                        elif category == asbc_constants.Analog:
                            pintype = asbc_constants.PT_ANALOG
                            x_interior = min(Box_x) + 10
                            if placed_pins_category:
                                y_max_interior = min_y_value - 20 * cnt_pins
                                y_max_boundery = min_y_value - 20 * cnt_pins
                            else:
                                y_max_interior = min_y_value - 20 * cnt_pins - no_pwr_in_pins * 20 - no_control_pins * 20 - 2 * SPARE_BTW_PINGROUPS
                                y_max_boundery = min_y_value - 20 * cnt_pins - no_pwr_in_pins * 20 - no_control_pins * 20 - 2 * SPARE_BTW_PINGROUPS
                            x_boundery = min(Box_x)
                            x_label = x_interior + 10
                            y_label = y_max_boundery
                        elif category == asbc_constants.PowerOut:
                            pintype = asbc_constants.PT_ANALOG
                            x_interior = max(Box_x) - 10
                            y_max_interior = min_y_value - 20*cnt_pins
                            x_boundery = max(Box_x)
                            y_max_boundery = min_y_value - 20*cnt_pins
                            x_label = x_interior - 10
                            y_label = y_max_boundery
                        elif category == asbc_constants.Interface:
                            pintype = asbc_constants.PT_BI
                            x_interior = max(Box_x) - 10
                            if placed_pins_category:
                                y_max_interior = min_y_value - 20 * cnt_pins
                                y_max_boundery = min_y_value - 20 * cnt_pins
                            else:
                                y_max_interior = min_y_value - 20 * cnt_pins - no_pwr_out_pins * 20 - SPARE_BTW_PINGROUPS
                                y_max_boundery = min_y_value - 20 * cnt_pins - no_pwr_out_pins * 20 - SPARE_BTW_PINGROUPS

                            x_boundery = max(Box_x)
                            x_label = x_interior - 10
                            y_label = y_max_boundery
                        elif category == asbc_constants.Status:
                            pintype = asbc_constants.PT_OUT
                            x_interior = max(Box_x) - 10
                            if placed_pins_category:
                                y_max_interior = min_y_value - 20 * cnt_pins
                                y_max_boundery = min_y_value - 20 * cnt_pins
                            else:
                                y_max_interior = min_y_value - 20 * cnt_pins - no_pwr_out_pins * 20 - no_interfaces * 20 - 2 * SPARE_BTW_PINGROUPS
                                y_max_boundery = min_y_value - 20 * cnt_pins - no_pwr_out_pins * 20 - no_interfaces * 20 - 2 * SPARE_BTW_PINGROUPS

                            x_boundery = max(Box_x)
                            x_label = x_interior - 10
                            y_label = y_max_boundery
                        else:
                            print(f"Unknown category: {category}")

                        if design_level == asbc_constants.DL_AE and Pin != dummy_pin:
                            domain = self.domain_for_ae(block)
                            ea_Id = self.jfile_reader.get_arch_id_for_pin_for_ae(self.system, domain, block, Pin)
                        else:
                            ea_Id = None

                        NewPin = activeBlock.AddPin(x, y)
                        NewPin.SetLocation(x_boundery, y_max_boundery, x_interior, y_max_interior)
                        NewPin.AddLabel(f"{Pin}", x_label, y_label)
                        NewPin.AddAttribute(f"Pin Type = {pintype}", 0, 0, c.VDINVISIBLE)
                        if ea_Id is not None:
                            NewPin.AddAttribute(f"Architecture UID = {ea_Id}", 0, 0, c.VDINVISIBLE)

                if category == asbc_constants.Status:
                    # workaround (part 2) to get rid of the rotated first Pin on the right side of each block!
                    View.SelectByName(dummy_pin)
                    activeBlock.DeleteSelected(True)

        try:
            symbol_Block.UpdateSymbolInDesign()
            symbol_Block.Close(False, "none")
        except Exception as e:
            print(f"Error updating Symbol: {e}")

    # adds all available nets to the architectural elements of a single domain
    def add_nets(self, app, rootdesign, toplevel, domain, domains, PinList_superior, num_sheets, update_existing, block_size_info, design_level):
        # defintions for COM Object access
        oblBlock: IVdBlock = None
        View: IVdView = None
        objComponent: IVdComp = None
        symbolBlock: IVdBlock = None
        conn: IVdConnection = None
        CompPin: IVdCmpPin = None
        connCompPin: IVdCmpPin = None
        connComponent: IVdComp = None
        connSegm: IVdSegment = None
        connNet: IVdNet = None
        Pin: IVdPin = None
        NewNet: IVdNet = None
        Net: IVdNet = None
        segment: IVdSegment = None
        conSegm: IVdSegment = None
        NewLabel: IVdLabel = None
        PowerAttr: IVdAttr = None
        labelSegm: IVdLabel = None
        NewSheetCon: IVdComp = None
        NetConnection: IVdObjs = None
        NewLocation = IVdPoint = None
        CompIsPower: IVdAttr = None

        # initialize Net Attribute Variables
        ConnectedNet = ""
        NetProperties = []
        Category = ""

        block_already_done = []

        schematic = None
        sheetname = None
        sheet = None
        no_sheets = 0
        hier_con = False

        con_offset = 0
        label_offset = 0

        PowerValue = None

        if design_level == asbc_constants.DL_AE:
            if domain == "CON":
                schematic = rootdesign
            else:
                schematic = domain
            no_sheets = num_sheets
        elif design_level == asbc_constants.DL_DOMAIN:
            schematic = toplevel
            no_sheets = len(domains)
            print("PINLIST SUPERIOR:", PinList_superior)
        elif design_level == asbc_constants.DL_TOP:
            schematic = rootdesign
            no_sheets = 1

        # domain_data = data[domain]
        for i in range(no_sheets):
            if design_level == asbc_constants.DL_AE:
                sheet = f"{domain}_{i + 1}"
            elif design_level == asbc_constants.DL_DOMAIN:
                sheet = f"{domains[i]}"
            elif design_level == asbc_constants.DL_TOP:
                sheet = f"{toplevel}"

            app.PushPath(f"{schematic}", "", f"{sheet}")
            colBlock = app.OpenBlocks(c.VDDT_SCHEMATIC)
            for objBlock in colBlock:
                blockname = objBlock.GetName(c.SHORT_NAME)
                sheetnum = objBlock.SheetNum
                if blockname == schematic and sheetnum == f"{sheet}":
                    for View in app.SchematicSheetDocuments().Open(f"{schematic}", f"{sheet}").GetViews():
                        Components = View.Query(c.VDM_COMP, c.VD_ALL)
                        app.Activate()
                        View.Activate()
                        for objComponent in Components:
                            power_pins_in = []
                            power_pins_out = []
                            power_pins_in_flattened = []
                            power_pins_out_flattened = []

                            y_power_pins_in = []
                            y_power_pins_out = []

                            # Name = objComponent.GetName(c.SHORT_NAME)
                            # print("Component:", Name)
                            symbolBlock = objComponent.Symbolblock
                            Fub = symbolBlock.IsFub
                            Name = symbolBlock.GetName(c.SHORT_NAME)
                            if Fub and Name not in block_already_done:
                                block_already_done.append(Name)

                                try:
                                    ae_domain = self.domain_for_ae(Name)
                                    power_pins_in.append(self.jfile_reader.get_pin_names_of_type_for_ae(self.system, ae_domain, Name, asbc_constants.PowerIn))
                                    power_pins_out.append(self.jfile_reader.get_pin_names_of_type_for_ae(self.system, ae_domain, Name, asbc_constants.PowerOut))
                                    power_pins_in_flattened = [item for sublist in power_pins_in for item in sublist]
                                    power_pins_out_flattened = [item for sublist in power_pins_out for item in sublist]
                                    print("Power Pins In: ", power_pins_in_flattened)
                                    print("Power Pins Out: ", power_pins_out_flattened)
                                    placed_pin_info = self.placed_pins(app, Name)
                                    for PinName, PinLocation in placed_pin_info.items():
                                        if PinName in power_pins_in_flattened:
                                            y_power_pins_in.append(PinLocation[1])
                                            y_power_pins_in.sort(reverse=True)
                                            print("PinName: ", PinName)
                                            print("PinLocation: ", PinLocation)
                                        elif PinName in power_pins_out_flattened:
                                            y_power_pins_out.append(PinLocation[1])
                                            y_power_pins_out.sort(reverse=True)

                                except Exception as e:
                                    print(f"Block {Name} does not have Power Pins: {e}")

                                BlockLocation = objComponent.GetLocation
                                connections = objComponent.GetConnections
                                # print(f"BlockLocation: [{BlockLocation.X} ; {BlockLocation.Y}]")
                                for conn in connections:
                                    # initialize values
                                    power_net = False
                                    net_length = 0
                                    label_correct = False

                                    # get segments
                                    conSegm = conn._GetSegment
                                    # print("conSegm = ", conSegm)
                                    CompPin = conn.CompPin
                                    Pin = CompPin._GetPin
                                    PinName = Pin.GetName(c.SHORT_NAME)
                                    print("Pin Name: ", PinName)
                                    try:
                                        if PinName in PinList_superior:
                                            hier_con = True
                                        else:
                                            hier_con = False
                                    except Exception as e:
                                        print(f"Error searching Pin in PinList_superior: {e}")

                                    PinSide = CompPin.Side
                                    PinLocation = Pin.GetLocation(c.VDPIN_BOUNDARY)
                                    PinType = Pin.FindAttribute("Pin Type")
                                    PinDirection = PinType.Value
                                    # if no segment on Pin found
                                    if conSegm == None and update_existing == False:
                                        print(PinName, PinDirection, PinSide)
                                        # PinInfo = asbc_data_exchange().extract_pin_information(data, domain, Name, None, PinName)
                                        if design_level == asbc_constants.DL_AE:
                                            PinInfo_new = self.data_exchange.PinInfo(self.system, Name, None, PinName, asbc_constants.DL_AE)
                                        elif design_level == asbc_constants.DL_DOMAIN:
                                            PinInfo_new = self.data_exchange.PinInfo(self.system, None, domains, PinName, asbc_constants.DL_DOMAIN)
                                        elif design_level == asbc_constants.DL_TOP:
                                            PinInfo_new = self.data_exchange.PinInfo(self.system, None, None, PinName, asbc_constants.DL_TOP)

                                        print("PinInfo_new: ", PinInfo_new)
                                        # try:
                                        ConnectedNet = list(PinInfo_new[0].keys())[0]
                                        NetProperties = list(PinInfo_new[0].values())[0]
                                        Category = PinInfo_new[1]
                                        ea_uid = NetProperties[1]

                                        # except Exception as e:
                                        #     print(f"No Pin Information given for {PinName}: {e}")

                                        print("ConnectedNet: ", ConnectedNet)
                                        print("NetProperties: ", NetProperties)
                                        print("Category: ", Category)

                                        if Category == asbc_constants.Interface:
                                            net_length = 200
                                            if hier_con == True:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "con_hier_bi"
                                                label_correct = False
                                            else:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "onsheet_bi"
                                                label_correct = False

                                            sym_rotate = True
                                            nettype = c.VD_BUS
                                        elif Category == asbc_constants.Control:
                                            net_length = 200
                                            if hier_con == True:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "con_hier_i"
                                            else:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "onsheet_in"
                                            sym_rotate = False
                                            nettype = c.VD_WIRE
                                        elif Category == asbc_constants.Status:
                                            net_length = 200
                                            if hier_con == True:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "con_hier_o"
                                            else:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "onsheet_out"
                                            sym_rotate = False
                                            nettype = c.VD_WIRE
                                        elif Category == asbc_constants.Analog:
                                            net_length = 200
                                            if hier_con == True:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "con_hier_analog"
                                            else:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "onsheet_bi"
                                            sym_rotate = False
                                            nettype = c.VD_WIRE
                                        elif Category == asbc_constants.PowerIn:
                                            index = y_power_pins_in.index(PinLocation.Y)
                                            net_length = 100 + index*40
                                            if hier_con == True:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "con_hier_power_in"
                                            else:
                                                sym_partition = "Globals"
                                                sym_sheet_con = "power_in"
                                                power_net = True
                                            sym_rotate = False
                                            nettype = c.VD_WIRE
                                        elif Category == asbc_constants.PowerOut:
                                            index = y_power_pins_out.index(PinLocation.Y)
                                            net_length = 100 + index*40
                                            if hier_con == True:
                                                sym_partition = "builtin"
                                                sym_sheet_con = "con_hier_power_out"
                                                sym_rotate = True
                                            else:
                                                sym_partition = "Globals"
                                                sym_sheet_con = "power_out"
                                                power_net = True
                                                sym_rotate = False
                                            nettype = c.VD_WIRE

                                        # left side of the block
                                        if PinSide == 2:
                                            x_loc_Start = BlockLocation.X + PinLocation.X - net_length
                                            y_loc_Start = BlockLocation.Y + PinLocation.Y
                                            x_loc_End = BlockLocation.X + PinLocation.X -10
                                            y_loc_End = BlockLocation.Y + PinLocation.Y

                                            # add net with label
                                            try:
                                                NewNet = objBlock.AddNet(x_loc_Start, y_loc_Start, x_loc_End, y_loc_End, pythoncom.Nothing, pythoncom.Nothing, nettype)
                                                NetSegments = NewNet.GetSegments
                                                for segment in NetSegments:
                                                    isBus = segment.IsBus
                                                    NewLabel = NewNet.AddLabel(segment, f"{ConnectedNet}", 0, 0)
                                                    NewNet.AddAttribute(segment, f"Architecture UID={ea_uid}", 0, 0, c.VDINVISIBLE)
                                                    if isBus:
                                                        NewLabel.SetLocation(x_loc_End, y_loc_Start + 10)
                                                        NewLabel.Origin = c.VDALIGN_MR
                                                    else:
                                                        NewLabel.SetLocation(x_loc_End, y_loc_Start)
                                                        NewLabel.Origin = c.VDALIGN_LR

                                                # connect to block after renaming (only way that works!)
                                                objBlock.AddNet(x_loc_End + 10, y_loc_Start, x_loc_End, y_loc_End, pythoncom.Nothing, pythoncom.Nothing, nettype)
                                            except Exception as e:
                                                print(f"Error adding net {ConnectedNet}: {e}")

                                            # add Sheet Connector or global Power Symbol
                                            try:
                                                NewSheetCon = objBlock.AddSymbolInstance(sym_partition, sym_sheet_con, 0, 0)
                                                if hier_con == True:
                                                    NewLabel = NewSheetCon.AddLabel(f"{PinName}", 0, 0)
                                                    con_offset = 0
                                                    label_offset = 70
                                                    y_offset = 0
                                                elif power_net == True:
                                                    PowerAttr = NewSheetCon.AddAttribute(f"Global Signal Name={ConnectedNet}", 0, 0, c.VDVISIBLE)
                                                    con_offset = 0
                                                    label_offset = 0
                                                    y_offset = 20
                                                else:
                                                    NewLabel = NewSheetCon.AddLabel(f"{ConnectedNet}", 0, 0)
                                                    con_offset = 10
                                                    label_offset = 40
                                                    y_offset = 0

                                                if sym_rotate:
                                                    NewSheetCon.Orientation = c.VDORIENT_ROT180

                                                NewSheetCon.SetLocation(x_loc_Start - con_offset, y_loc_Start + y_offset)
                                                if power_net == True:
                                                    PowerAttr.SetLocation(x_loc_Start - label_offset, y_loc_Start + 2*y_offset)
                                                    PowerAttr.Origin = c.VDALIGN_LC
                                                else:
                                                    NewLabel.SetLocation(x_loc_Start - label_offset, y_loc_Start)
                                                    NewLabel.Origin = c.VDALIGN_MR
                                            except Exception as e:
                                                print(f"Error adding SheetConnector {ConnectedNet}: {e}")

                                        # right side of the block
                                        elif PinSide == 3:
                                            x_loc_Start = BlockLocation.X + PinLocation.X + 10
                                            y_loc_Start = BlockLocation.Y + PinLocation.Y
                                            x_loc_End = BlockLocation.X + PinLocation.X + net_length
                                            y_loc_End = BlockLocation.Y + PinLocation.Y

                                            # add net with label
                                            try:
                                                NewNet = objBlock.AddNet(x_loc_Start, y_loc_End, x_loc_End, y_loc_End, pythoncom.Nothing, pythoncom.Nothing, nettype)
                                                NetSegments = NewNet.GetSegments
                                                for segment in NetSegments:
                                                    isBus = segment.IsBus
                                                    NewLabel = NewNet.AddLabel(segment, f"{ConnectedNet}", 0, 0)
                                                    NewNet.AddAttribute(segment, f"Architecture UID={ea_uid}", 0, 0, c.VDINVISIBLE)
                                                    if isBus:
                                                        NewLabel.SetLocation(x_loc_Start , y_loc_Start + 10)
                                                        NewLabel.Origin = c.VDALIGN_ML
                                                    else:
                                                        NewLabel.SetLocation(x_loc_Start, y_loc_Start)
                                                        NewLabel.Origin = c.VDALIGN_LL

                                                # connect to block after renaming (only way that works!)
                                                objBlock.AddNet(x_loc_Start - 10, y_loc_Start, x_loc_Start, y_loc_End, pythoncom.Nothing, pythoncom.Nothing, nettype)
                                            except Exception as e:
                                                print(f"Error adding net {ConnectedNet}: {e}")

                                            # add Sheet Connector or global Power Symbol
                                            try:
                                                NewSheetCon = objBlock.AddSymbolInstance(sym_partition, sym_sheet_con, 0, 0)
                                                if hier_con == True:
                                                    NewLabel = NewSheetCon.AddLabel(f"{PinName}", 0, 0)
                                                    con_offset = 0
                                                    label_offset = 70
                                                    y_offset = 0
                                                elif power_net == True:
                                                    PowerAttr = NewSheetCon.AddAttribute(f"Global Signal Name={ConnectedNet}", 0, 0, c.VDVISIBLE)
                                                    con_offset = 0
                                                    label_offset = 0
                                                    y_offset = 20
                                                else:
                                                    NewLabel = NewSheetCon.AddLabel(f"{ConnectedNet}", 0, 0)
                                                    con_offset = 10
                                                    label_offset = 40
                                                    y_offset = 0

                                                if sym_rotate:
                                                    NewSheetCon.Orientation = c.VDORIENT_ROT180

                                                NewSheetCon.SetLocation(x_loc_End + con_offset, y_loc_Start + y_offset)
                                                if power_net == True:
                                                    PowerAttr.SetLocation(x_loc_End + label_offset, y_loc_Start + 2*y_offset)
                                                    PowerAttr.Origin = c.VDALIGN_LC
                                                else:
                                                    NewLabel.SetLocation(x_loc_End + label_offset, y_loc_Start)
                                                    NewLabel.Origin = c.VDALIGN_MR
                                                    if label_correct == True:
                                                        NewLabel.Origin = c.VDALIGN_MR
                                                    else:
                                                        NewLabel.Origin = c.VDALIGN_ML

                                            except Exception as e:
                                                print(f"Error adding SheetConnector {ConnectedNet}: {e}")

                                    # update position of existing nets!
                                    elif conSegm and update_existing == True:
                                        Net = conSegm.Parent
                                        LocationLow = conSegm.Location(c.VDJ_LOW)
                                        LocationHigh = conSegm.Location(c.VDJ_HIGH)
                                        try:
                                            labelSegm = Net.GetLabel(conSegm)
                                            LabelLoc = labelSegm.GetLocation
                                            print("LabelLoc: ", LabelLoc.X, LabelLoc.Y)
                                        except:
                                            pass
                                        isBus = conSegm.IsBus
                                        NetName = Net.GetConnectedNetName(conSegm)
                                        print("NetName: ", NetName)
                                        print("LocationLow: ", LocationLow.X, LocationLow.Y)
                                        print("LocationHigh: ", LocationHigh.X, LocationHigh.Y)
                                        for conn in Net.Connections:
                                            connCompPin = conn._GetCompPin
                                            connComponent = connCompPin._GetComp
                                            symbolBlock = connComponent.Symbolblock
                                            Fub = symbolBlock.IsFub
                                            if Fub:
                                                side_connCompPin = connCompPin.Side
                                                connComponentName = connComponent.GetName(c.SHORT_NAME)
                                                delta_blocksize = block_size_info[connComponentName][0]
                                                delta_blocksize_x = delta_blocksize[0]
                                                delta_blocksize_y = delta_blocksize[1]

                                        for conn in Net.Connections:
                                            connCompPin = conn._GetCompPin
                                            connComponent = connCompPin._GetComp
                                            symbolBlock = connComponent.Symbolblock
                                            Fub = symbolBlock.IsFub

                                            if not Fub:
                                                CompLocation = connComponent.GetLocation
                                                CompIsPower = connComponent.FindAttribute("Global Signal Name")
                                                if CompIsPower:
                                                    PowerValue = CompIsPower.EitherValue
                                                    print("PowerValue", PowerValue)
                                                else:
                                                    PowerValue = None

                                                x_Complocation = CompLocation.X
                                                y_CompLocation = CompLocation.Y
                                                y_loc_Pin = BlockLocation.Y + PinLocation.Y
                                                print("y_loc_Pin: ", y_loc_Pin)
                                                if side_connCompPin == 3:
                                                    x_loc_comp_new = x_Complocation + delta_blocksize_x
                                                    if PowerValue:
                                                        y_loc_comp_new = y_loc_Pin + 20
                                                    else:
                                                        y_loc_comp_new = y_loc_Pin

                                                    connComponent.SetLocation(x_loc_comp_new, y_loc_comp_new)
                                                elif side_connCompPin == 2:
                                                    if PowerValue:
                                                        y_loc_comp_new = y_loc_Pin + 20
                                                    else:
                                                        y_loc_comp_new = y_loc_Pin
                                                    connComponent.SetLocation(x_Complocation, y_loc_comp_new)

                                        # move labels to new position
                                        new_blocksize = block_size_info[connComponentName][1]
                                        new_blocksize_x = new_blocksize[0]
                                        try:
                                            if side_connCompPin == 3: # right side of block
                                                x_loc_label_new = BlockLocation.X + new_blocksize_x + 10
                                                if isBus:
                                                    y_loc_label_new = y_loc_Pin + 10
                                                else:
                                                    y_loc_label_new = y_loc_Pin
                                            elif side_connCompPin == 2:  # left side of block
                                                x_loc_label_new = LabelLoc.X
                                                y_loc_label_new = y_loc_Pin

                                            labelSegm.SetLocation(x_loc_label_new, y_loc_label_new)
                                        except Exception as e:
                                            print(f"Error moving label of {NetName}: {e}")

                    # stop, when found!
                    break

    def sheetsize_decoding(self, sheetsize):
        sheet_dim = []
        if sheetsize == c.VDSHEET_A0_SIZE:
            sheet_dim = asbc_constants.SheetSize_A0_LS
        elif sheetsize == c.VDSHEET_A1_SIZE:
            sheet_dim = asbc_constants.SheetSize_A1_LS
        elif sheetsize == c.VDSHEET_A2_SIZE:
            sheet_dim = asbc_constants.SheetSize_A2_LS

        sheet_width = sheet_dim[0]
        sheet_height = sheet_dim[1]

        return sheet_width, sheet_height, sheet_dim

    def sheet_sectioning(self, sheetsize, x_devide, y_devide, spare, section):
        spare_min_x = 250
        spare_min_y = 100
        spare_x = 0
        spare_y = 0

        if spare != None:
            if spare[0] < spare_min_x:
                spare[0] = spare_min_x
            else:
                spare_x = spare[0]

            if spare[1] < spare_min_y:
                spare[1] = spare_min_y
            else:
                spare_y = spare[1]
        else:
            spare_x = spare_min_x
            spare_y = spare_min_y

        sheet_width = self.sheetsize_decoding(sheetsize)[0]
        sheet_height = self.sheetsize_decoding(sheetsize)[1]

        startpoints = []

        dim_x_sections = round((sheet_width/x_devide)/10) * 10
        dim_y_sections = round((sheet_height/y_devide)/10) * 10

        for x in range(x_devide):
            startpoint_x = x * dim_x_sections + spare_x
            for y in range(y_devide):
                startpoint_y = sheet_height - (y * dim_y_sections + spare_y)
                startpoints.append([startpoint_x, startpoint_y])

        try:
            return startpoints[section]
        except Exception as e:
            print(f"'Section {section}' out of range from possible Startpoints: {e}")

    def add_hier_con_to_funct_lvl(self, app, objBlock, block, pin_category, sheetsize):
        Component : IVdComp = None
        Component_Label : IVdLabel = None
        symbol_block : IVdBlock = None
        NewLabel : IVdLabel = None
        NewSheetCon : IVdComp = None
        NewNet : IVdNet = None
        NetSegments : IVdSegment = None

        distance = 30
        # pins per category in AE
        domain = self.domain_for_ae(block)
        pins = self.jfile_reader.get_pin_names_of_type_for_ae(self.system, domain, block, pin_category)

        # select sheet section by category
        x_devide = 3
        y_devide = 3
        startpoint = []
        sym_partition = "builtin"
        if pin_category == asbc_constants.PowerIn:
            startpoint = self.sheet_sectioning(sheetsize, x_devide, y_devide, None, 0)
            sym_sheet_con = "con_hier_power_in"
            label_origin = c.VDALIGN_MR
            label_offset = -70
            sym_rotate = False
            nettype = c.VD_WIRE
        elif pin_category == asbc_constants.Control:
            startpoint = self.sheet_sectioning(sheetsize, x_devide, y_devide, None, 1)
            sym_sheet_con = "con_hier_i"
            label_origin = c.VDALIGN_MR
            label_offset = -70
            sym_rotate = False
            nettype = c.VD_WIRE
        elif pin_category == asbc_constants.Analog:
            startpoint = self.sheet_sectioning(sheetsize, x_devide, y_devide, None, 2)
            sym_sheet_con = "con_hier_analog"
            label_origin = c.VDALIGN_MR
            label_offset = -70
            sym_rotate = False
            nettype = c.VD_WIRE
        elif pin_category == asbc_constants.PowerOut:
            startpoint = self.sheet_sectioning(sheetsize, x_devide, y_devide, None, 6)
            sym_sheet_con = "con_hier_power_out"
            label_origin = c.VDALIGN_ML
            label_offset = 70
            sym_rotate = False
            nettype = c.VD_WIRE
        elif pin_category == asbc_constants.Interface:
            startpoint = self.sheet_sectioning(sheetsize, x_devide, y_devide, None, 7)
            sym_sheet_con = "con_hier_bi"
            label_origin = c.VDALIGN_ML
            label_offset = 70
            sym_rotate = True
            nettype = c.VD_BUS
        elif pin_category == asbc_constants.Status:
            startpoint = self.sheet_sectioning(sheetsize, x_devide, y_devide, None, 8)
            sym_sheet_con = "con_hier_o"
            label_origin = c.VDALIGN_ML
            label_offset = 70
            sym_rotate = False
            nettype = c.VD_WIRE

        # already placed connectors
        count_cons = 0
        placed_cons = []
        lstComponents = app.DesignComponents("", block, "-1", "STD", False)
        for Component in lstComponents:
            symbol_block = Component.SymbolBlock
            symbol_name = symbol_block.GetName(1)
            if symbol_name in sym_sheet_con:
                count_cons = count_cons + 1
                Component_Label = Component.Label
                comp_loc = Component.GetLocation
                comp_name = Component_Label.ResolvedName
                placed_cons.append(comp_name)

        # postioning of hierarchical connector & adding Net Segment
        startpoint_x = startpoint[0]
        startpoint_y = startpoint[1]
        print("startpoint_y: ", startpoint_y)
        for Pin in  pins:
            if Pin not in placed_cons:
                count_cons = count_cons + 1
                x_pos = startpoint_x
                y_pos = startpoint_y - count_cons*distance
                print("count_cons: ", count_cons)
                print("y_pos: ", y_pos)
                NewSheetCon = objBlock.AddSymbolInstance(sym_partition, sym_sheet_con, x_pos, y_pos)
                if sym_rotate:
                    NewSheetCon.Orientation = c.VDORIENT_ROT180
                NewLabel = NewSheetCon.AddLabel(f"{Pin}", x_pos + label_offset, y_pos)
                NewLabel.Origin = label_origin
                try:
                    connected_nets = self.jfile_reader.get_net_names_for_pin_of_ae(self.system, domain, block, Pin)
                    connected_net = connected_nets[0] if connected_nets else None
                    print(connected_net)
                except Exception as e:
                    connected_net = None
                    print(e)
                if connected_net:
                    if label_origin == c.VDALIGN_MR:
                        NewNet = objBlock.AddNet(x_pos + 10, y_pos, x_pos + 200, y_pos, pythoncom.Nothing, pythoncom.Nothing, nettype)
                        NetSegments = NewNet.GetSegments
                        for segment in NetSegments:
                            isBus = segment.IsBus
                            NewLabel = NewNet.AddLabel(segment, f"{connected_net}", 0, 0)
                            if isBus:
                                NewLabel.SetLocation(x_pos + 10, y_pos + 10)
                                NewLabel.Origin = c.VDALIGN_ML
                            else:
                                NewLabel.SetLocation(x_pos + 10, y_pos)
                                NewLabel.Origin = c.VDALIGN_LL

                        # connect to block after renaming (only way that works!)
                        objBlock.AddNet(x_pos, y_pos, x_pos + 10, y_pos, pythoncom.Nothing, pythoncom.Nothing, nettype)
                    elif label_origin == c.VDALIGN_ML:
                        NewNet = objBlock.AddNet(x_pos - 200, y_pos, x_pos - 10, y_pos, pythoncom.Nothing, pythoncom.Nothing, nettype)
                        NetSegments = NewNet.GetSegments
                        for segment in NetSegments:
                            isBus = segment.IsBus
                            NewLabel = NewNet.AddLabel(segment, f"{connected_net}", 0, 0)
                            if isBus:
                                NewLabel.SetLocation(x_pos - 10, y_pos + 10)
                                NewLabel.Origin = c.VDALIGN_MR
                            else:
                                NewLabel.SetLocation(x_pos - 10, y_pos)
                                NewLabel.Origin = c.VDALIGN_LR

                        # connect to block after renaming (only way that works!)
                        objBlock.AddNet(x_pos - 10, y_pos, x_pos, y_pos, pythoncom.Nothing, pythoncom.Nothing, nettype)

# for testing functions ONLY!
def main():
    # NewLocation = IVdPoint
    # NewLocation.X = 0
    # NewLocation.Y = 0
    # print(f"NewLocation coordinates: X={NewLocation.X}, Y={NewLocation.Y}")
    # PinList = [1, 2, 3, 4]
    # placed_pins_category = []
    # unplaced_pins = [x for x in PinList if x not in placed_pins_category]
    # print(unplaced_pins)
    file = r"C:\git\xpedition\Designer_Automation\dev\auto_scheme\Python_COM_Wrapper\JSON_Files\ssd_arch_export.json"
    # block = "SSD_CON_B2B"
    # for pin_cat in asbc_constants.Pincategories:
    #     # print(pin_cat)
    #     Pins = asbc_routines().add_hier_con_to_funct_lvl(file, block, pin_cat)
    #     print(f"{pin_cat}: {list(Pins.keys())}")

    # print(asbc_routines().sheet_sectioning(c.VDSHEET_A2_SIZE, 3, 3, None, 8))

    # bc_path = r"C:\XpeditionLocal\auto_scheme\busconts.ini"
    # if_template = r"M:\Mentor_Xpedition\xpedition\Designer_Automation\config\Interface_Template_File.json"
    # def split_string_number(input_data):
    #     if isinstance(input_data, str):  # If a single string, convert to a list
    #         input_data = [input_data]
    #
    #     result = []
    #     for s in input_data:
    #         prefix, num = s.rsplit("_", 1)  # Split at the last underscore
    #         result.append((prefix, int(num)))  # Convert num to int
    #     return result
    #
    # net_info_full = asbc_data_exchange().net_info_full(file)
    #
    # with open(bc_path, "a") as file:  # Open in append mode
    #     for net_info in net_info_full:
    #         if "link" in net_info.lower():
    #             result = split_string_number([net_info])  # Ensure net_info is in a list
    #             IF_type = result[0][0]
    #             IF_number = result[0][1]
    #             IF_type = IF_type.replace("LINK", "[Link/Port]")
    #
    #             try:
    #                 new_bus = BusGenerator(bc_path, if_template).GenInterfaces(IF_type, IF_number, 1, "Link")
    #                 print(new_bus)
    #                 file.write(new_bus[0] + "\n")  # Append new_bus to the file
    #             except Exception as e:
    #                 print(e)

            # print(json.dumps(net_info_full, indent=4))

    # Example usage:
    # hex_color = "#d1bc8a"
    # rgb = asbc_routines().hex_to_rgb(hex_color)
    # print(f"RGB values: {rgb}")

    raise SystemExit("Use 'python -m xped_auto.runner' instead of this legacy test entry point.")

    data_exchange = asbc_data_exchange(file2)
    jfile_reader = jr.ArchJsonReader(file2)

    # domains = jfile_reader.get_domains()
    system = jfile_reader.get_system_names()[0]
    print(f"System: {system}")

    # full net info
    net_info_full = data_exchange.net_info_full(system)
    print(json.dumps(net_info_full, indent=4))

if __name__ == "__main__":
    main()
