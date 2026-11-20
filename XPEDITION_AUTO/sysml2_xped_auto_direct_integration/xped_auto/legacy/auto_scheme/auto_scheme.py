import argparse
from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PIL.ImageEnhance import Color

from auto_sch_base import *
import shutil
import os


from win32com.client import Dispatch

def copy_file(source_path, destination_path):
    try:
        shutil.copy2(source_path, destination_path)  # copy2 preserves metadata
        print(f"File copied successfully from {source_path} to {destination_path}")
    except Exception as e:
        print(f"Error copying file: {e}")

#global definitions
prj_name = "Xpedition_Project"
toplevel_blockname = f"{prj_name}_TOPLEVEL"
# toplevel_connectors = f"{prj_name}_CONNECTORS"
toplevel_mechanics = f"{prj_name}_MECHANICS"
toplevel_blocks = [toplevel_blockname, toplevel_mechanics]

count_blocks_on_page = 0
i=1

def auto_scheme(architecture_json, project_path, bc_file_path, interface_template, project_name=None):
    # copy dx_designer.xml to zftmp!
    # source = r"M:\Mentor_Xpedition\Mentor_Config\DxDesigner.xml"
    # destination = r"C:\WDIR\DxDesigner.xml"
    #
    # copy_file(source, destination)
    # constants

    # globale defintions for COM Object access
    objApplication: IVdApp = None
    objBlock: IVdBlock = None
    objBlockParent: IVdBlock = None
    activeBlock: IVdBlock = None
    symbolBlock: IVdBlock = None
    objComponent: IVdComp = None
    objAttribute: IVdAttr = None
    NewPin: IVdPin = None
    Pin: IVdPin = None
    objRefDes_Start: IVdAttr  = None
    View: IVdView = None
    View_element: IVdView = None
    Blocks: IVdObjs = None
    Parent: IVdView = None
    sheets_per_domain: IStringList = None
    available_schematics: IStringList = None
    conn: IVdObjs = None
    CompPin: IVdCmpPin = None
    PinType:IVdAttr = None
    NewNet:IVdNet = None
    NewLabel: IVdLabel = None
    activate_sheet: IVdSchematicSheetDocuments = None
    Box: IVdBox = None

    # buscontent file
    bc_file = "busconts.ini"
    
    global prj_name, toplevel_blockname, toplevel_mechanics, toplevel_blocks
    prj_name = project_name or Path(project_path).stem
    toplevel_blockname = f"{prj_name}_TOPLEVEL"
    toplevel_mechanics = f"{prj_name}_MECHANICS"
    toplevel_blocks = [toplevel_blockname, toplevel_mechanics]

    # ArchJsonReader auto-detects native SysML architecture JSON and normalizes
    # it in memory for the existing auto_schem query routines.
    file2 = str(Path(architecture_json).resolve())
    progid = "ViewDraw.Application"
    project_path = str(Path(project_path).resolve())
    bc_file_path = str(Path(bc_file_path).resolve())

    #instantiate classes
    connect = asbc_connect(progid, project_path)
    routines = asbc_routines(file2)
    data_exchange = asbc_data_exchange(file2, interface_template)
    jfile_reader = jr.ArchJsonReader(file2)

    # Method variable
    internal_refdes_offset = 0
    sheetsize = asbc_constants.SheetSize_A2_LS
    toplevel_available = False

    # domains = jfile_reader.get_domains()
    system = jfile_reader.get_system_names()[0]
    print(f"System: {system}")
    domains = jfile_reader.get_domain_names(system)
    domains_wo_con = [d for d in domains if d != "CON"]

    # Get all AEs from design
    all_ae = []
    for domain in domains:
        try:
            all_ae.append(list(jfile_reader.get_ae_names_for_domain(system, domain)))
        except Exception as e:
            print(f"No key for {e}")

    all_ae_flat = [item for sublist in all_ae for item in sublist]
    ae_domain = {ae: domain for domain in domains for ae in jfile_reader.get_ae_names_for_domain(system, domain)}

    # full net info
    net_info_full = data_exchange.net_info_full(system)
    print(json.dumps(net_info_full, indent=4))

    # gather psu/soc/uc/peripherie/wless sub-domains!
    psu_sub_domain_cnt = 0
    psu_sub_domains = []
    soc_sub_domain_cnt = 0
    soc_sub_domains = []
    iuc_sub_domain_cnt = 0
    iuc_sub_domains = []
    peri_sub_domain_cnt = 0
    peri_sub_domains = []
    wl_sub_domain_cnt = 0
    wl_sub_domains = []

    for domain in domains:  # TODO: define dedicated start strings in asbc_constants !!!
        if domain.lower().startswith(("psu", "wake")):
            psu_sub_domains.append(domain)
        if domain.lower().startswith(("soc", "psoc", "cpu")):
            soc_sub_domains.append(domain)
        if domain.lower().startswith(("uc", "smc", "mcu")):
            iuc_sub_domains.append(domain)
        if domain.lower().startswith(("per", "peri")):
            peri_sub_domains.append(domain)
        if domain.lower().startswith(("wireless", "wl", "pos")):
            wl_sub_domains.append(domain)

    # connect to application
    connect.init_com()
    objApplication = connect.connect_to_application()
    connect.open_project()
    strDesign = objApplication.GetProjectData().GetiCDBDesignRootBlock(objApplication.GetActiveDesign())
    print(f"str_des={strDesign}")
    # create initial Toplevel Pages
    objApplication.PushPath(f"{strDesign}", "", toplevel_blockname)
    objApplication.PushPath(f"{strDesign}", "", f"CON_1")
    objApplication.PushPath(f"{strDesign}", "", toplevel_mechanics)

#############################################################################################################################################################
#############################################################################################################################################################
################################################### GENERATE/UPDATE BUSCONTENT FILE IN PROJECT PATH #########################################################
#############################################################################################################################################################
#############################################################################################################################################################

    data_exchange.gen_busses_for_project(bc_file_path)

#############################################################################################################################################################
#############################################################################################################################################################
################################################### TOPLEVEL BLOCK CREATION & UPDATE ########################################################################
#############################################################################################################################################################
#############################################################################################################################################################

    lstComponents = objApplication.DesignComponents("", strDesign, "-1", "STD", False)
    for objComponent in lstComponents:
        objBlock = objComponent.Symbolblock
        Fub = objBlock.IsFub
        Name = objBlock.GetName(c.SHORT_NAME)
        if Fub:
            if Name == toplevel_blockname:
                toplevel_available = True

    # Generate Toplevelblock, Connector Blocks & Domain Pages
    colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
    for objBlock in colBlock:
        blockname = objBlock.GetName(c.SHORT_NAME)
        act_sheetnum = objBlock.SheetNum
        # print(f"Block found: {blockname}")
        if blockname == strDesign and act_sheetnum == toplevel_blockname:
            block_size_info = {}
            if toplevel_available == False:
                no_pins = []
                drawing_size = c.VDSHEET_A0_SIZE
                for pin_category in asbc_constants.Pincategories_domain_level:
                    nested_pinlist = []
                    try:
                        conn_aes = jfile_reader.get_ae_names_for_domain(system, "CON")
                        for conn in conn_aes:
                            # print(conn)
                            pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, "CON", conn, pin_category)
                            nested_pinlist.append(list(pins_per_cat.keys()))
                    except Exception as e:
                        print(f"No domain CON within Exchnage format: {e}")

                    pinlist = [item for sublist in nested_pinlist for item in sublist]
                    pinlist = list(dict.fromkeys(pinlist))
                    no_pins.append(len(pinlist))

                # Block dimensioning
                blocksize = routines.calculate_blocksize(no_pins, 40, 20, 40, asbc_constants.DL_TOP)
                blocksize_x = blocksize[0]
                blocksize_y = blocksize[1]
                sheetsize = blocksize[2]

                block_ll_x = sheetsize[0]/2 - blocksize_x/2
                block_ll_y = sheetsize[1]/2 - blocksize_y/2
                block_ur_x = sheetsize[0]/2 + blocksize_x/2
                block_ur_y = sheetsize[1]/2 + blocksize_y/2

                block_location = SetLocation(block_ll_x, block_ll_y, block_ur_x, block_ur_y)
                routines.add_block(objBlock, toplevel_blockname, block_location, None, None, None)

                # add Pins to blocks --> all Pins, that come from a connector block need to be added to the Toplevel Block --> remove duplicates!
                # no_pins = []
                for pin_category in asbc_constants.Pincategories_domain_level:
                    nested_pinlist = []
                    try:
                        conn_aes = jfile_reader.get_ae_names_for_domain(system, "CON")
                        for conn in conn_aes:
                            # print(conn)
                            pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, "CON", conn, pin_category)
                            nested_pinlist.append(list(pins_per_cat.keys()))
                    except Exception as e:
                        print(f"No domain CON within Exchnage format: {e}")

                    pinlist = [item for sublist in nested_pinlist for item in sublist]
                    # remove duplicates, keep order
                    pinlist = list(dict.fromkeys(pinlist))
                    routines.add_pins(objApplication, pin_category, toplevel_blockname, pinlist, no_pins, asbc_constants.DL_TOP)

            # update toplevel block
            if toplevel_available == True:
                no_pins = []
                for pin_category in asbc_constants.Pincategories_domain_level:
                    nested_pinlist = []
                    try:
                        conn_aes = jfile_reader.get_ae_names_for_domain(system, "CON")
                        for conn in conn_aes:
                            pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, "CON", conn, pin_category)
                            nested_pinlist.append(list(pins_per_cat.keys()))
                    except Exception as e:
                        print(f"No domain CON within Exchnage format: {e}")

                    pinlist = [item for sublist in nested_pinlist for item in sublist]
                    # remove duplicates, keep order
                    pinlist = list(dict.fromkeys(pinlist))
                    no_pins.append(len(pinlist))

                blocksize = routines.calculate_blocksize(no_pins, 40, 20, 40, asbc_constants.DL_TOP)
                sheetsize = blocksize[2]

                delta_blocksize = routines.update_blocksize(objApplication, toplevel_blockname, blocksize)
                block_size_info[toplevel_blockname] = delta_blocksize, blocksize

                for pin_category in asbc_constants.Pincategories_domain_level:
                    nested_pinlist = []
                    try:
                        conn_aes = jfile_reader.get_ae_names_for_domain(system, "CON")
                        for conn in conn_aes:
                            # print(conn)
                            pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, "CON", conn, pin_category)
                            nested_pinlist.append(list(pins_per_cat.keys()))
                    except Exception as e:
                        print(f"No domain CON within Exchnage format: {e}")

                    pinlist = [item for sublist in nested_pinlist for item in sublist]
                    # remove duplicates, keep order
                    pinlist = list(dict.fromkeys(pinlist))
                    routines.update_block(objApplication, pin_category, toplevel_blockname, pinlist, no_pins, asbc_constants.DL_TOP)

            # update Nets in design
            update_existing_nets = True
            routines.add_nets(objApplication, strDesign, toplevel_blockname, None, None, None,None, update_existing_nets, block_size_info, asbc_constants.DL_TOP)

            if toplevel_available == True:
                no_pins = []
                for pin_category in asbc_constants.Pincategories_domain_level:
                    nested_pinlist = []
                    try:
                        conn_aes = jfile_reader.get_ae_names_for_domain(system, "CON")
                        for conn in conn_aes:
                            pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, "CON", conn, pin_category)
                            nested_pinlist.append(list(pins_per_cat.keys()))
                    except Exception as e:
                        print(f"No domain CON within Exchnage format: {e}")

                    pinlist = [item for sublist in nested_pinlist for item in sublist]
                    # remove duplicates, keep order
                    pinlist = list(dict.fromkeys(pinlist))
                    no_pins.append(len(pinlist))

                for pin_category in asbc_constants.Pincategories_domain_level:
                    nested_pinlist = []
                    try:
                        conn_aes = jfile_reader.get_ae_names_for_domain(system, "CON")
                        for conn in conn_aes:
                            pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, "CON", conn, pin_category)
                            nested_pinlist.append(list(pins_per_cat.keys()))
                    except Exception as e:
                        print(f"No domain CON within Exchnage format: {e}")


                    pinlist = [item for sublist in nested_pinlist for item in sublist]
                    # remove duplicates, keep order
                    pinlist = list(dict.fromkeys(pinlist))
                    routines.add_pins(objApplication, pin_category, toplevel_blockname, pinlist, no_pins, asbc_constants.DL_TOP)

            # add Nets to toplevel block
            update_existing_nets = False
            routines.add_nets(objApplication, strDesign, toplevel_blockname, None, None, None, None, update_existing_nets, None, asbc_constants.DL_TOP)

            #update drawing size if necessary
            if sheetsize == asbc_constants.SheetSize_A0_LS:
                drawing_size = c.VDSHEET_A0_SIZE
            elif sheetsize == asbc_constants.SheetSize_A1_LS:
                drawing_size = c.VDSHEET_A1_SIZE
            elif sheetsize == asbc_constants.SheetSize_A2_LS:
                drawing_size = c.VDSHEET_A2_SIZE

            objBlock.SheetSize = drawing_size

            # add pages for domains
            for domain in domains_wo_con:
                objApplication.PushPath(f"{strDesign}", f"{toplevel_blockname}", f"{domain}")
                objBlock.SheetSize = c.VDSHEET_A2_SIZE

#############################################################################################################################################################
#############################################################################################################################################################
################################################### DOAMAIN BLOCK CREATION & UPDATE #########################################################################
#############################################################################################################################################################
#############################################################################################################################################################
    # gather Pins of Toplevel block!
    lstComponents = objApplication.DesignComponents("", strDesign, "-1", "STD", False)
    for objComponent in lstComponents:
        objBlock = objComponent.Symbolblock
        Fub = objBlock.IsFub
        Name = objBlock.GetName(c.SHORT_NAME)
        if Fub and Name  == toplevel_blockname:
            placed_pins = routines.placed_pins(objApplication, Name)
            pinlist_superior = (list(placed_pins.keys()))

    placed_domains = []

    lstComponents = objApplication.DesignComponents("", toplevel_blockname, "-1", "STD", False)
    for objComponent in lstComponents:
        objBlock = objComponent.Symbolblock
        Fub = objBlock.IsFub
        Name = objBlock.GetName(c.SHORT_NAME)
        if Fub:
            placed_domains.append(Name)

    unplaced_domains = [x for x in domains_wo_con if x not in placed_domains]

    # Generate Domain Blocks
    for domain in unplaced_domains:
        no_pins = []
        block_size_info = {}
        drawing_size = c.VDSHEET_A2_SIZE
        for pin_category in asbc_constants.Pincategories_domain_level:
            pinlist = data_exchange.pins_per_cat_domain(domain, pin_category, net_info_full)
            no_pins.append(len(pinlist))

        blocksize = routines.calculate_blocksize(no_pins, 40, 20, 40, asbc_constants.DL_DOMAIN)
        blocksize_x = blocksize[0]
        blocksize_y = blocksize[1]
        sheetsize = blocksize[2]

        # Block dimensioning
        block_ll_x = sheetsize[0] / 2 - blocksize_x / 2
        block_ll_y = sheetsize[1] / 2 - blocksize_y / 2
        block_ur_x = sheetsize[0] / 2 + blocksize_x / 2
        block_ur_y = sheetsize[1] / 2 + blocksize_y / 2

        block_location = SetLocation(block_ll_x, block_ll_y, block_ur_x, block_ur_y)

        # if domain != "CON":
        if domain.lower().startswith(("psu", "wake")):
            refdes_start = routines.generate_rd_start(domain, psu_sub_domains, psu_sub_domain_cnt, 0, asbc_constants.RD_SIZE_BIG)
            psu_sub_domain_cnt = psu_sub_domain_cnt + 1
        elif domain.lower().startswith(("soc", "psoc", "cpu")):
            refdes_start = routines.generate_rd_start(domain, soc_sub_domains, soc_sub_domain_cnt, 0, asbc_constants.RD_SIZE_SMALL)
            soc_sub_domain_cnt = soc_sub_domain_cnt + 1
        elif domain.lower().startswith(("uc", "smc", "mcu")):
            refdes_start = routines.generate_rd_start(domain, iuc_sub_domains, iuc_sub_domain_cnt, 0, asbc_constants.RD_SIZE_NORMAL)
            iuc_sub_domain_cnt = iuc_sub_domain_cnt + 1
        elif domain.lower().startswith(("per", "peri")):
            refdes_start = routines.generate_rd_start(domain, peri_sub_domains, peri_sub_domain_cnt, 0, asbc_constants.RD_SIZE_SMALL)
            peri_sub_domain_cnt = peri_sub_domain_cnt + 1
        elif domain.lower().startswith(("wireless", "wl", "pos")):
            refdes_start = routines.generate_rd_start(domain, wl_sub_domains, wl_sub_domain_cnt, 0, asbc_constants.RD_SIZE_SMALL)
            wl_sub_domain_cnt = wl_sub_domain_cnt + 1
        else:
            refdes_start = routines.generate_rd_start(domain, None, 0, 0, 0)

        if sheetsize == asbc_constants.SheetSize_A0_LS:
            drawing_size = c.VDSHEET_A0_SIZE
        elif sheetsize == asbc_constants.SheetSize_A1_LS:
            drawing_size = c.VDSHEET_A1_SIZE
        elif sheetsize == asbc_constants.SheetSize_A2_LS:
            drawing_size = c.VDSHEET_A2_SIZE

        # get ea block attributes
        # Enterprise Architcect id
        ea_Id = jfile_reader.get_arch_id_for_domain(system, domain)
        # Systemfunction
        # None for domain!

        colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
        for objBlock in colBlock:
            blockname = objBlock.GetName(c.SHORT_NAME)
            act_sheetnum = objBlock.SheetNum
            if blockname == f"{toplevel_blockname}" and act_sheetnum == domain:
                routines.add_block(objBlock, domain, block_location, refdes_start, ea_Id, None)
                objApplication.PushPath(f"{toplevel_blockname}", f"{domain}", f"{domain}_1")

            objBlock.SheetSize = drawing_size

        # add Pins to blocks
        for pin_category in asbc_constants.Pincategories_domain_level:
            pinlist = data_exchange.pins_per_cat_domain(domain, pin_category, net_info_full)
            routines.add_pins(objApplication, pin_category, domain, pinlist, no_pins, asbc_constants.DL_DOMAIN)

    # Update Domain Blocks
    for domain in placed_domains:
        no_pins = []
        for pin_category in asbc_constants.Pincategories_domain_level:
            pinlist = data_exchange.pins_per_cat_domain(domain, pin_category, net_info_full)
            no_pins.append(len(pinlist))

        blocksize = routines.calculate_blocksize(no_pins, 40, 20, 40, asbc_constants.DL_DOMAIN)

        delta_blocksize = routines.update_blocksize(objApplication, domain, blocksize)
        block_size_info[domain] = delta_blocksize, blocksize


        for pin_category in asbc_constants.Pincategories_domain_level:
            pinlist = data_exchange.pins_per_cat_domain(domain, pin_category, net_info_full)
            routines.update_block(objApplication, pin_category, domain, pinlist, no_pins, asbc_constants.DL_DOMAIN)

    # update Nets in design
    update_existing_nets = True
    routines.add_nets(objApplication, strDesign, toplevel_blockname, None, domains_wo_con, pinlist_superior,None, update_existing_nets, block_size_info, asbc_constants.DL_DOMAIN)

    for domain in placed_domains:
        no_pins = []
        for pin_category in asbc_constants.Pincategories_domain_level:
            pinlist = data_exchange.pins_per_cat_domain(domain, pin_category, net_info_full)
            no_pins.append(len(pinlist))

        # add new Pins to domain blocks
        for pin_category in asbc_constants.Pincategories_domain_level:
            pinlist = data_exchange.pins_per_cat_domain(domain, pin_category, net_info_full)
            routines.add_pins(objApplication, pin_category, domain, pinlist, no_pins, asbc_constants.DL_DOMAIN)

    # add Nets to design
    update_existing_nets = False
    routines.add_nets(objApplication, strDesign, toplevel_blockname, None, domains_wo_con, pinlist_superior, None, update_existing_nets, block_size_info, asbc_constants.DL_DOMAIN)

#############################################################################################################################################################
#############################################################################################################################################################
################################################### ARCHITECTURAL ELEMENTS BLOCK CREATION & UPDATE ##########################################################
#############################################################################################################################################################
#############################################################################################################################################################

# connectors are on toplevel --> All others are within domains

    for domain in domains:
        refdes_start_domain = 0
        all_refdes_starts = []
        all_blocks = []
        placed_blocks = []
        block_size_info = {}

        refdes_start = 0
        refdes_start_offset = 0

        # if domain != "CON":
        aes = jfile_reader.get_ae_names_for_domain(system, domain)

        for arch_element in aes:
            all_blocks.append(arch_element)

        if domain == "CON":
            lstComponents = objApplication.DesignComponents("", strDesign, "-1", "STD", False)
        else:
            lstComponents = objApplication.DesignComponents("", domain, "-1", "STD", False)

        for objComponent in lstComponents:
            objBlock = objComponent.Symbolblock
            Fub = objBlock.IsFub
            Name = objBlock.GetName(c.SHORT_NAME)
            if Fub:
                if domain == "CON" and toplevel_blockname.lower() != Name.lower():
                    placed_blocks.append(Name)
                else:
                    placed_blocks.append(Name)
                try:
                    # existing RefDesStarts
                    objRefDes_Start = objComponent.FindAttribute("RefDes Start")
                    refdes_start_block = objRefDes_Start.Value
                    all_refdes_starts.append(refdes_start_block)
                except:
                    pass

        placed_pins = routines.placed_pins(objApplication, domain)
        pinlist_superior = (list(placed_pins.keys()))
        print("pinlist_superior", pinlist_superior)

        if all_refdes_starts:
            refdes_start_offset = int(max(all_refdes_starts))
            print(refdes_start_offset)
        else:
            # find RefDes Start of Domain Blocks
            if domain == "CON":
                refdes_start_domain = asbc_constants.RefDesStart_Con
            else:
                lstComponents = objApplication.DesignComponents("", toplevel_blockname, "-1", "STD", False)
                for objComponent in lstComponents:
                    # Name = objComponent.GetName(0)
                    location = objComponent.GetLocation
                    symbolBlock = objComponent.Symbolblock
                    Fub = symbolBlock.IsFub
                    Name = symbolBlock.GetName(c.SHORT_NAME)
                    if Fub and Name == domain:
                        objRefDes_Start = objComponent.FindAttribute("RefDes Start")
                        refdes_start_domain = int(objRefDes_Start.Value)
                        print("refdes_start_domain: ", refdes_start_domain)
                        # break

        unplaced_blocks = [x for x in all_blocks if x not in placed_blocks]
        print("Unplaced Blocks:", unplaced_blocks)

        # place new blocks routine
        for value in unplaced_blocks:
            if value and value not in toplevel_blocks:
                num_sheets = 0
                no_pins = []
                drawing_size = c.VDSHEET_A2_SIZE
                for pin_category in asbc_constants.Pincategories:
                    pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, ae_domain[value], value, pin_category)
                    pinlist = list(pins_per_cat.keys())
                    no_pins.append(len(pinlist))

                blocksize = routines.calculate_blocksize(no_pins, 40, 20, 40, asbc_constants.DL_AE)
                blocksize_x = blocksize[0]
                blocksize_y = blocksize[1]
                sheetsize = blocksize[2]

                if blocksize_y <= (sheetsize[1] - asbc_constants.BlockSize_Spare)/2:
                    blocks_per_page = 4
                elif blocksize_y > (sheetsize[1] - asbc_constants.BlockSize_Spare)/2:
                    blocks_per_page = 1

                colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
                for objBlock in colBlock:
                    try:
                        BlockName = objBlock.GetName(c.SHORT_NAME)
                        # print("BlockName: ", BlockName)
                        objBlock.SheetSize = c.VDSHEET_A2_SIZE
                    except:
                        pass

                # gather number of Domain Sheets
                if domain == "CON":
                    sheets_per_domain = objApplication.SchematicSheetDocuments().GetAvailableSheets(strDesign)
                else:
                    sheets_per_domain = objApplication.SchematicSheetDocuments().GetAvailableSheets(domain)

                if sheets_per_domain:
                    for sheet in sheets_per_domain:
                        if re.fullmatch(fr"{domain}_\d+", sheet):  # Ensures "domain_" followed by a number
                            num_sheets += 1

                position_info = routines.next_free_spot(objApplication, domain, strDesign, num_sheets, toplevel_blocks)

                print(position_info)

                next_free_spot = position_info[0]
                next_free_sheet = position_info[1]
                if domain == "CON":
                    objApplication.PushPath(f"{strDesign}", f"", f"{next_free_sheet}")
                else:
                    objApplication.PushPath(f"{toplevel_blockname}", f"{domain}", f"{next_free_sheet}")

                colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
                for objBlock in colBlock:
                    blockname = objBlock.GetName(c.SHORT_NAME)
                    act_sheetnum = objBlock.SheetNum
                    if domain == "CON":
                        dedicated_blockname = strDesign
                    else:
                        dedicated_blockname = domain

                    if blockname == dedicated_blockname and act_sheetnum == f"{next_free_sheet}":
                        if blocks_per_page == 4:
                            # Block dimensioning & placement
                            if next_free_spot == 1:
                                block_ll_x = 1*sheetsize[0]/4  - blocksize_x / 2
                                block_ll_y = 3*sheetsize[1]/4 - blocksize_y / 2
                                block_ur_x = 1*sheetsize[0]/4  + blocksize_x / 2
                                block_ur_y = 3*sheetsize[1]/4 + blocksize_y / 2
                            elif next_free_spot == 2:
                                block_ll_x = 3*sheetsize[0]/4  - blocksize_x / 2
                                block_ll_y = 3*sheetsize[1]/4 - blocksize_y / 2
                                block_ur_x = 3*sheetsize[0]/4  + blocksize_x / 2
                                block_ur_y = 3*sheetsize[1]/4 + blocksize_y / 2
                            elif next_free_spot == 3:
                                block_ll_x = 1 * sheetsize[0] / 4 - blocksize_x / 2
                                block_ll_y = 1 * sheetsize[1] / 4 - blocksize_y / 2
                                block_ur_x = 1 * sheetsize[0] / 4 + blocksize_x / 2
                                block_ur_y = 1 * sheetsize[1] / 4 + blocksize_y / 2
                            elif next_free_spot == 4:
                                block_ll_x = 3*sheetsize[0]/4  - blocksize_x / 2
                                block_ll_y = 1*sheetsize[1]/4 - blocksize_y / 2
                                block_ur_x = 3*sheetsize[0]/4  + blocksize_x / 2
                                block_ur_y = 1*sheetsize[1]/4 + blocksize_y / 2
                        elif blocks_per_page == 1:
                                block_ll_x = sheetsize[0] / 2 - blocksize_x / 2
                                block_ll_y = sheetsize[1] / 2 - blocksize_y / 2
                                block_ur_x = sheetsize[0] / 2 + blocksize_x / 2
                                block_ur_y = sheetsize[1] / 2 + blocksize_y / 2

                        block_location = SetLocation(block_ll_x, block_ll_y, block_ur_x, block_ur_y)
                        # if domain != "CON":
                        # generate RefDesStart for all new AEs within domain
                        if refdes_start_offset > 0:
                            refdes_start = refdes_start_offset  + asbc_constants.RDI_BLOCK
                        elif refdes_start > 0:
                            refdes_start = refdes_start + asbc_constants.RDI_BLOCK
                        else:
                            refdes_start = refdes_start_domain + asbc_constants.RDI_BLOCK

                        # get ea block attributes
                        # Enterprise Architcect id
                        ea_Id = jfile_reader.get_arch_id_for_ae(system, ae_domain[value], value)
                        # Systemfunction
                        sys_funct = jfile_reader.get_system_function_of_ae(system, ae_domain[value], value)

                        refdes_start_offset = 0
                        if sheetsize == asbc_constants.SheetSize_A0_LS:
                            routines.add_block(objBlock, value, block_location, refdes_start, ea_Id, sys_funct)
                            drawing_size = c.VDSHEET_A0_SIZE
                        elif sheetsize == asbc_constants.SheetSize_A1_LS:
                            routines.add_block(objBlock, value, block_location, refdes_start, ea_Id, sys_funct)
                            drawing_size = c.VDSHEET_A1_SIZE
                        elif sheetsize == asbc_constants.SheetSize_A2_LS:
                            routines.add_block(objBlock, value, block_location, refdes_start, ea_Id, sys_funct)
                            drawing_size = c.VDSHEET_A2_SIZE

                        if domain == "CON":
                            objApplication.PushPath(f"{strDesign}", f"{value}", f"{value}_1")
                        else:
                            objApplication.PushPath(f"{domain}", f"{value}", f"{value}_1")

                        objBlock.SheetSize = drawing_size
                        sheetsize = objBlock.SheetSize
                        # print(f"SHEETSIZE AFTER ADDING BLOCK: {sheetsize}")

            else:
                print("Block with empty name can not be placed!")

            # add Pins to blocks
            for pin_category in asbc_constants.Pincategories:
                pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, ae_domain[value], value, pin_category)
                pinlist = list(pins_per_cat.keys())
                pinlist_domain = data_exchange.pins_per_cat_domain(domain, pin_category, net_info_full)
                routines.add_pins(objApplication, pin_category, value, pinlist, no_pins, asbc_constants.DL_AE)

        # update blocks routine
        for value in placed_blocks:
            if value not in toplevel_blocks:
                no_pins = []
                print("Block: ", value)
                for pin_category in asbc_constants.Pincategories:
                    pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, ae_domain[value], value, pin_category)
                    pinlist = list(pins_per_cat.keys())
                    no_pins.append(len(pinlist))

                blocksize = routines.calculate_blocksize(no_pins, 40, 20, 40, asbc_constants.DL_AE)

                delta_blocksize = routines.update_blocksize(objApplication, value, blocksize)
                block_size_info[value] = delta_blocksize, blocksize

                for pin_category in asbc_constants.Pincategories:
                    pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, ae_domain[value], value, pin_category)
                    pinlist = list(pins_per_cat.keys())
                    routines.update_block(objApplication, pin_category, value, pinlist, no_pins, asbc_constants.DL_AE)

        # gather number of Domain Sheets
        num_sheets = 0
        if domain == "CON":
            sheets_per_domain = objApplication.SchematicSheetDocuments().GetAvailableSheets(strDesign)
        else:
            sheets_per_domain = objApplication.SchematicSheetDocuments().GetAvailableSheets(domain)

        if sheets_per_domain:
            for sheet in sheets_per_domain:
                if re.fullmatch(fr"{domain}_\d+", sheet):  # Ensures "domain_" followed by a number
                    num_sheets += 1

        # update Nets in design
        update_existing_nets = True
        routines.add_nets(objApplication, strDesign, toplevel_blockname, domain, None, pinlist_superior, num_sheets, update_existing_nets, block_size_info, asbc_constants.DL_AE)

        for value in placed_blocks:
            if value not in toplevel_blocks:
                no_pins = []
                for pin_category in asbc_constants.Pincategories:
                    pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, ae_domain[value], value, pin_category)
                    pinlist = list(pins_per_cat.keys())
                    no_pins.append(len(pinlist))

                for pin_category in asbc_constants.Pincategories:
                    pins_per_cat = jfile_reader.get_pins_of_type_for_ae(system, ae_domain[value], value, pin_category)
                    pinlist = list(pins_per_cat.keys())
                    no_pins.append(len(pinlist))
                    routines.add_pins(objApplication, pin_category, value, pinlist, no_pins, asbc_constants.DL_AE)

        # add Nets to design
        update_existing_nets = False
        routines.add_nets(objApplication, strDesign, toplevel_blockname, domain, None, pinlist_superior, num_sheets, update_existing_nets, block_size_info, asbc_constants.DL_AE)

#############################################################################################################################################################
#############################################################################################################################################################
################################################### ADD BORDERSYMBOLS TO DESIGN #############################################################################
#############################################################################################################################################################
#############################################################################################################################################################

    available_schematics = objApplication.SchematicSheetDocuments().GetAvailableSchematics()
    for scm in available_schematics:
        print(f"scm={scm}")
        sheets_per_domain = objApplication.SchematicSheetDocuments().GetAvailableSheets(scm)
        for sheet in sheets_per_domain:
            print(f"    sheet={sheet}")
            objApplication.PushPath(f"{scm}", "", f"{sheet}")
            colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
            for objBlock in colBlock:
                blockname = objBlock.GetName(1)
                sheetnum = objBlock.SheetNum
                print(blockname, sheetnum)
                if blockname == scm and sheetnum == sheet:
                    objBlock.InsertBorder()
                    break

#############################################################################################################################################################
#############################################################################################################################################################
################################################### ADD HIERARCHICAL CONNECTORS TO UNDERLAYING AE PAGES #####################################################
#############################################################################################################################################################
#############################################################################################################################################################

    available_schematics = objApplication.SchematicSheetDocuments().GetAvailableSchematics()
    for scm in available_schematics:
        if scm in all_ae_flat:
            print(f"scm={scm}")
            sheets_per_domain = objApplication.SchematicSheetDocuments().GetAvailableSheets(scm)
            for sheet in sheets_per_domain:
                print(f"    sheet={sheet}")
                objApplication.PushPath(f"{scm}", "", f"{sheet}")
                colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
                for objBlock in colBlock:
                    blockname = objBlock.GetName(1)
                    sheetnum = objBlock.SheetNum
                    sheetsize = objBlock.SheetSize
                    # print(blockname, sheetnum)
                    if blockname == scm and sheetnum == sheet:
                        print(blockname, sheetnum)
                        for category in asbc_constants.Pincategories:
                            routines.add_hier_con_to_funct_lvl(objApplication, objBlock, blockname, category, sheetsize)
                        break

#############################################################################################################################################################
#############################################################################################################################################################
################################################### SET BLOCK COLOURS FOR DOMAINS AND AEs ###################################################################
#############################################################################################################################################################
#############################################################################################################################################################

    available_schematics = objApplication.SchematicSheetDocuments().GetAvailableSchematics()
    for scm in available_schematics:
        i=0

        if scm in all_ae_flat:
            # Block Colour EA
            ea_colour = jfile_reader.get_color_of_ae(system, ae_domain[scm], scm)
            if ea_colour:
                red = routines.hex_to_rgb(ea_colour)[0]
                green = routines.hex_to_rgb(ea_colour)[1]
                blue = routines.hex_to_rgb(ea_colour)[2]
                # print(red, green , blue)
                symbolBlock = objApplication.SchematicSheetDocuments().OpenSymbol(scm, "1")
                for View in symbolBlock.GetViews():
                    if i == 0:
                        View.Activate()
                        i = i + 1
                        activeBlock = View.ActiveBlock()
                        Boxes = View.Query(c.VDM_BOX, c.VD_ALL)
                        for Box in Boxes:
                            Colour = Box.GetObjectColor
                            Colour.r = red
                            Colour.g = green
                            Colour.b = blue
                            try:
                                Box.SetObjectFillColor(Colour)
                            except Exception as e:
                                print(f"Error adding color: {e}")
                            Box.FillStyle = c.VDFILL_DIAGDN1
                            Box.LineStyle = c.VDLINE_SOLID

                symbolBlock.UpdateSymbolInDesign()
                symbolBlock.Close(False, "none")

        elif scm in domains:
            ea_colour = jfile_reader.get_color_for_domain(system, scm)
            if ea_colour:
                red = routines.hex_to_rgb(ea_colour)[0]
                green = routines.hex_to_rgb(ea_colour)[1]
                blue = routines.hex_to_rgb(ea_colour)[2]
                symbolBlock = objApplication.SchematicSheetDocuments().OpenSymbol(scm, "1")
                for View in symbolBlock.GetViews():
                    if i == 0:
                        View.Activate()
                        i = i + 1
                        activeBlock = View.ActiveBlock()
                        Boxes = View.Query(c.VDM_BOX, c.VD_ALL)
                        for Box in Boxes:
                            Colour = Box.GetObjectColor
                            Colour.r = red
                            Colour.g = green
                            Colour.b = blue
                            try:
                                Box.SetObjectFillColor(Colour)
                            except Exception as e:
                                print(f"Error adding color: {e}")
                            Box.FillStyle = c.VDFILL_DIAGDN1
                            Box.LineStyle = c.VDLINE_SOLID

                symbolBlock.UpdateSymbolInDesign()
                symbolBlock.Close(False, "none")


    connect.close_project()

def main():
    parser = argparse.ArgumentParser(description="Run auto_schem from a SysML architecture JSON file.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--architecture-json", help="native SysML2 Architecture Builder JSON (preferred)")
    source_group.add_argument("--exchange-json", help="internal xped_auto exchange JSON (compatibility input)")
    parser.add_argument("--project", required=True)
    parser.add_argument("--bus-content", required=True)
    parser.add_argument("--interface-template", required=True)
    parser.add_argument("--project-name")
    args = parser.parse_args()
    auto_scheme(args.architecture_json or args.exchange_json, args.project, args.bus_content, args.interface_template, args.project_name)

if __name__ == "__main__":
    main()
