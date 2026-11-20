from doctest import debug
from typing import AnyStr

import win32com.client as win32, pythoncom
from win32com.client import VARIANT
import comtypes
import os
import time
import json

# from Demos.win32cred_demo import attrs

# from Python_COM_Wrapper.ifc import SchematicSheetDocuments
from ifc import *
from ifc import constants as c

# This will work if IVdCmpPin is instantiable
# NullPin: IVdCmpPin = None

# Initialize and cleanup COM
def init_com():
    try:
        comtypes.CoInitialize()
    except Exception as e:
        print(f"Error initializing COM: {e}")


def cleanup_com():
    try:
        comtypes.CoUninitialize()
    except Exception as e:
        print(f"Error uninitializing COM: {e}")


def connect_to_application(progid="ViewDraw.Application"):
    """Reconnect to the application."""
    retries = 5
    for attempt in range(retries):
        try:
            app = win32.Dispatch(progid)
            print(f"Successfully connected to {progid}.")
            return app
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)  # Wait before retrying
    raise RuntimeError(f"Unable to connect to {progid} after {retries} attempts.")

def refresh_project_data(app, project_path):
    """Refresh project data to clear cached values."""
    try:
        # Close and reopen the project
        app.CloseProject()
        time.sleep(1)  # Small delay to ensure resources are freed
        app.OpenProject(project_path)
        print("Project reloaded successfully.")
    except Exception as e:
        print(f"Error refreshing project data: {e}")
        raise

def open_project(app, project_path):
    """Open a specific project using the COM API."""
    app.OpenProject(project_path)
    # try:
    #     project_data = app.GetProjectData()
    #     print(f"Available methods in ProjectData: {dir(project_data)}")
    #
    #     # Try to open the project
    #     if hasattr(project_data, "OpenProject"):
    #         project_data.OpenProject(project_path)
    #         print(f"Project opened: {project_path}")
    #     elif hasattr(project_data, "LoadProject"):
    #         project_data.LoadProject(project_path)
    #         print(f"Project loaded: {project_path}")
    #     else:
    #         print("No method to open or load the project was found.")
    #         raise AttributeError("OpenProject/LoadProject method not available.")
    # except Exception as e:
    #     print(f"Error opening project: {e}")
    #     raise

def close_project(app):
    app.CloseProject()

def get_project_designs(app):
    """Retrieve designs in the current project."""
    try:
        project_data = app.GetProjectData()
        designs = project_data.GetiCDBDesigns()
        print(f"Available designs: {designs}")
        return designs
    except Exception as e:
        print(f"Error retrieving designs: {e}")
        return []


def open_design_blocks(app, design_name):
    """Open blocks within the specified design."""
    try:
        app.GetProjectData().SetActiveDesign(design_name)
        col_blocks = app.OpenBlocks(2)  # Assuming VDDT_SCHEMATIC = 2
        for block in col_blocks:
            block_name = block.GetName(2)  # FULL_PATH_NAME = 2
            print(f"Block found: {block_name}")
    except Exception as e:
        print(f"Error opening blocks: {e}")
        raise

def open_ea_structure(struct_file="Python_COM_Wrapper/structured_architecture.json"):
   with open(struct_file, "r") as file:
       data = json.load(file)

       return data
       # domains = list(data.keys())
       # # print(domains)
       # for key in data:
       #     values = list(data[key].keys())
       #     # print(values)

def testroutine():
    init_com()

    project_name = "Test_Block"

    objApplication: IVdApp = None
    objComponent: IVdComp = None
    objAttribute: IVdAttr = None
    objBlock: IVdBlock = None
    Block: IVdBlock = None
    objPin: IVdCmpPin = None
    objNet: IVdNet = None
    objCon : IVdObjs = None
    segment: IVdSegment = None
    signal_item: IStringList = None
    item : IStringList = None
    SchSD : IVdSchematicSheetDocument = None
    View : IVdView = None
    Pin_attr : IVdObjs = None
    Pin : IVdPin = None
    attr : IVdAttr = None
    location : IVdPoint = None
    objLabel : IVdLabel = None
    Box : IVdBox = None
    CompPin : IVdCmpPin = None
    Net : IVdNet = None
    segments : IVdSegment = None

    # try:
    # Connect to the application
    objApplication = connect_to_application()
    # project_path = r"C:\Xpedition_Local\Auto2\Auto2.prj"
    # project_path = r"C:\Xpedition_Local\Auto4\Auto4.prj"
    # open_project(objApplication, project_path)
    # refresh_project_data(objApplication, project_path)
    # print(objApplication)
    strDesignPath = objApplication.GetProjectData().GetProjectPath()
    # print(strDesignPath)

    # objApplication.SchematicSheetDocuments().OpenSymbol()

    strDesign = objApplication.GetProjectData().GetiCDBDesignRootBlock(objApplication.GetActiveDesign())
    print(f"str_des={strDesign}")

    #select nets routine
    # objApplication.SelectNet("Schematic1","1","Pin1")
    # objApplication.SelectPath("Schematic1", "Pin2", "1", 0, True, True)

    # lstComponents = objApplication.DesignComponents("", strDesign, "-1", "STD", True)
    # # lstPins = objApplication("", strDesign, "-1", "STD", True)
    # for objComponent in  lstComponents:
    #     Name = objComponent.GetName(0)
    #     location = objComponent.GetLocation
    #
    #     print("Name: ", Name)
    #     print("Location: ", location.X, location.Y)

    # for objPin in lstPins:
    #     print(objPin)
    # Name = objComponent.GetName(0)
    # print("Name:", Name)
    # UID = objComponent.UID
    # print("UID:", UID)

    # for objComponent in lstComponents:
    #     Name = objComponent.GetName(0)
    #     print("Name:", Name)
    # UID = objComponent.UID
    # print("UID:", UID)

    # objApplication.PushPath(f"Schematic1.1", "", "1")
    # # Net Creation Routine
    # colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
    # for objBlock in colBlock:
    #     print(objBlock)
    #     blockname = objBlock.GetName(c.SHORT_NAME)
    #     print(f"Block found: {blockname}")
    #     if blockname == "Schematic1":
    #         # objBlock.Activate()
    #         for View in objApplication.SchematicSheetDocuments().Open(blockname, '1').GetViews():
    #             lstComponents = objApplication.DesignComponents("", strDesign, "-1", "STD", False)
    #             # lstPins = objApplication("", strDesign, "-1", "STD", True)
    #             for objComponent in lstComponents:
    #                 Name = objComponent.GetName(0)
    #                 Block_location = objComponent.GetLocation
    #                 print("Name: ", Name)
    #                 print("Block_Location: ", Block_location.X, Block_location.Y)
    #                 # objComponent.SetLocation(Block_location.X - 100, Block_location.Y - 100)
    #             Pins = View.Query(c.VDM_COMPPIN, c.VD_ALL)
    #             for objPin in Pins:
    #                 Name = objPin.Pin.GetName(0)
    #                 Pin_Location = objPin.Pin.GetLocation(1)
    #                 print(f"{Name} Location", f"X: {Pin_Location.X}", f"Y: {Pin_Location.Y}")
    #
    #                 x_loc_Start = Block_location.X - 100
    #                 y_loc_start = Block_location.Y + Pin_Location.Y
    #
    #                 print(f"Net Coordinets: X = {x_loc_Start}, Y = {y_loc_start}")
    #
    #                 try:
    #                     objBlock.AddNet(x_loc_Start, y_loc_start, 0, 0, pythoncom.Nothing, objPin,c.VD_BUS)
    #                 except Exception as e:
    #                     print(f"Error adding block: {e}")

    # print(objPin.Pin.GetName(0))


    #     for i in range(20):
    #         objBlock.AddNet(110, 2000-i*10, 310, 2000-i*10, pythoncom.Nothing, pythoncom.Nothing, c.VD_BUS)
    # print(type(Nullpin))
    # Nullpin_variant = VARIANT(pythoncom.VT_DISPATCH, Nullpin)
    # objBlock.AddNetEx(0, 0, 10, 0, Nullpin_variant, Nullpin_variant, c.VD_BUS)
    # objBlock.AddNetEx(0,0,10,0, Nullpin, Nullpin, c.VD_BUS)
    #     pass


    # Pin Creation Routine
    # colBlock = objApplication.OpenBlocks(c.VDDT_SYMBOL)
    # for objBlock in colBlock:
    #     blockname = objBlock.GetName(c.SHORT_NAME)
    #     print(f"Block found: {blockname}")
    #     if blockname == "Test_Block":
    symbol_Block = objApplication.SchematicSheetDocuments().OpenSymbol("Test_Block","1")
    colBlock = objApplication.OpenBlocks(c.VDDT_SYMBOL)
    for objBlock in colBlock:
        blockname = objBlock.GetName(c.SHORT_NAME)
        # print(f"Block found: {blockname}")
        if blockname == "Test_Block":
            print(f"Block found: {blockname}")
        #     for i in range(5):
        #         try:
        #             y = i*20+20
        #             objBlock.AddPin(0, y)
        #         except Exception as e:
        #             print(f"Error adding pin {i}: {e}")
        #     # symbol_Block.Save()
        #     symbol_Block.UpdateSymbolInDesign()
    #         break
    # symbol_Block.Close(False, "none")

    # Pin Modification Routine
    # colBlock = objApplication.OpenBlocks(c.VDDT_SYMBOL)
    # i=0
    # j=0
    # k=0
    # l=0
    # pin_uids = []
    # for objBlock in colBlock:
    #     i = i + 1
    #     blockname = objBlock.GetName(c.SHORT_NAME)
    #     print(f"Block found: {blockname}")
    #     if blockname == "Test_Block":
    #         # symbol_Block = objApplication.SchematicSheetDocuments().OpenSymbol(blockname,"1")
    #         symbol_Block = objApplication.SchematicSheetDocuments().OpenSymbol(blockname, "1")
    #         symbol_Block.Activate()
    #         for View in symbol_Block.GetViews():
    #             j = j + 1
    #             # View.Activate()
    #             # print(View.SelectObject(c.VDTS_COMPPIN, "*", False, True, False))
    #             # print(View.SelectByName("$1P696"))
    #             Pins = View.Query(c.VDM_PIN, c.VD_ALL)
    #             Boxes = View.Query(c.VDM_BOX, c.VD_ALL)
    #             for Box in Boxes:
    #                 print(Box.GetLocation(c.VDLOWERLEFT).X)
    #                 print(Box.GetLocation(c.VDLOWERLEFT).Y)
    #                 print(Box.GetLocation(c.VDUPPERRIGHT).X)
    #                 print(Box.GetLocation(c.VDUPPERRIGHT).Y)
    #             for Pin in Pins:
    #                 k = k + 1
    #                 location = Pin.GetLocation(0)
    #                 pin_uids.append(Pin.UID)
    #                 print(Pin.UID)
    #                 View.SelectByName(Pin.UID)
    #                 x = location.X
    #                 y = location.Y
    #                 print(y)
    #                 print(Pin.Id)
    #                 # objLabel = Pin.Label
    #                 Labelloc=Pin.Label
    #                 print(f"Location: {Labelloc.GetLocation.X, Labelloc.GetLocation.Y}")
    #                 Pin.Label.SetLocation(x+10,y)
    #                 Pin.Label.Orientation = c.VDORIENT_MX
    #                 Pin.Label.Origin = c.VDALIGN_ML
    #
    #                 try:
    #                     Pin.AddLabel(f"Pin{k}",-10, y)
    #                 except Exception as e:
    #                     print(f"Error adding label {k}: {e}")
    #
    #                 # Pin.SetLocation(10,k*20,10,10)
    #                 # Pin.SetLocation(490, k * 20, 500, k * 20)
    #                 # Label_Loc = Pin.Label.GetLocation()
    #                 # print(Label_Loc.X)
    #
    #
    #                 # Pin.SetLocation(10, k*20, 0, k*20)
    #                 # Label_Loc = objLabel.GetLocation()
    #                 # print(Label_Loc.X, Label_Loc.Y)
    #             break
    #
    #         symbol_Block.UpdateSymbolInDesign()
    #         break

    # print(pin_uids)
    #
    # for uid in pin_uids:
    #     l=l+1
    #     print(uid)
    #     View.SelectByName(uid)
    #     Pin.AddLabel(f"Pin{l}",0,0)

    # break

    #     symbol_Block.Activate()



    # print(i, j, k, l)
    #

    # print(View.SelectObject(c.VDTS_BLOCK, "", False, True, False))
    # print(View.SelectByName("Test_Block"))
    # for View in symbol_Block.GetViews():
    #     Pins = View.Query(c.VDM_PIN, c.VD_SELECTED)
    #     for objPin in Pins:
    #         print(objPin.Type)
    # print(objPin.AddAttribute("Label=bratwurst", 0, 0, c.VDVISIBLE))
    # for objComponent in lstComponents:
    #     for objCon in objComponent.GetConnections:
    #         # print(f"Net: {objCon.Net.GetSignals}")
    #         print(f"Pin: {objCon.CompPin.Pin.GetName(0)}")
    #         objCon.CompPin.Pin.AddLabel("bratwurst", 0, 0)


    # # NullPin = None  # Assign a valid instance
    # # print(objBlock.GetChildBlock)
    # for objBlock in colBlock:
    #     blockname = objBlock.GetName(c.SHORT_NAME)
    #     print(f"Block found: {blockname}")
    #     if blockname == "Test_Block":
    #         for i in range(20):
    #             objBlock.AddPin(0,i*20)

    # objApplication.SchematicSheetDocuments().OpenSymbol(blockname, "1").Close(2, "Test")

    # objBlock.AddNet(0 ,0 , 100, 100, NullPin, NullPin, c.VD_WIRE)
    # pass
    #     try:
    #         objBlock.AddFub(f"{project_name}", 1000, 1000, 1500, 1500)
    #     except Exception as e:
    #         print(f"Error adding Fub: {e}")
    #     objApplication.PushPath(f"Schematic1.1", f"{project_name}", "1")

    # Sheets = objApplication.SchematicSheetDocuments().GetAvailableSheets("Test_Block")
    # for SheetName in Sheets:
    #     print(f"Sheet found: {SheetName}")

    strDesign = objApplication.GetProjectData().GetiCDBDesignRootBlock(objApplication.GetActiveDesign())
    print(f"str_des={strDesign}")

    #Select Nets
    colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
    Open_Sheet = objApplication.SchematicSheetDocuments().Open("Schematic1", "1")
    # for objBlock in colBlock:
    # for View in Open_Sheet.GetViews():
    #     View.Activate()
    #     Nets = View.Query(c.VDM_NET, c.VD_ALL)
        # for i in range(1000):
        #     if i!=8:
        #         View.SelectObject(i,'*', True, True, True)
            # View.SelectObject(c.VDTS_COMPONENT, '*', False, True, False)
        # for Net in Nets:
            # Netname = Net.GetSignals.GetItem(2)
            # for segment in Net.GetSegments:
            #     print(segment.Type)
            #     Net.SelectSegment(segment)
            #     for objBlock in colBlock:
            #         objBlock.DeleteSelected(True)
                # objLabel = Net.GetLabel(segment)
                # print(objLabel.ResolvedName)
            # print(Netname)
            # View.SelectByName(Netname)
            # for objBlock in colBlock:
            #     objBlock.DeleteSelected(True)
#     segment = View.Query(c.VDM_SEGMENT, c.VD_ALL)
        #     Type = Net.Type
        #     print(Netname, Type)
        #     print(Net.SelectSegment(segment))
            # print(segment)
            # print(type(segment), segment)
            # segment.GetJointType(c.VDJ_HIGH)
            # Net.SelectSegment(segment.GetJointType(c.VDJ_HIGH))
            # print(Net.GetSegments.GetJointType(c.VDJ_HIGH))
                # objBlock.DeleteSelected(True)
                # View.Activate()
                # objApplication.Delete()
                # Segments = View.Query(c.VDM_SEGMENT, c.VD_ALL)
                # print(Net.UID)
                # for segment in Segments:
                #     print(Net.SelectSegment(segment).Type)

        # print(objNet.GetConnectedNetName)
        # for segment in objNet.GetSegments:
        #     objNet.AddAttribute(segment,"Bit Size=77",0,0,0)
        # print(objNet.GetConnectedNetName(segment))
        # print(segment.Location(c.VDJ_HIGH).X)
        # print(segment.Location(c.VDJ_HIGH).Y)
        # for item in segment.Attributes:
        #     for attr in item.Attributes:
        #         print(f"Signal: {attr}")

        # for signal_item in objNet.GetSignals:
        #     print(f"Signal: {signal_item}")
        # print(signal_item.GetCount)
        # signal_item.Append("test")
        # objNet.AddAttribute(None, "VoltageLevel = Add_Level_here",0,0,0)
        # Label = objNet.GetLabel
        # print(f"Label: {Label}")

    # lstComponents = objApplication.DesignComponents("", strDesign, "-1", "STD", True)
    # lstPins = objApplication.Pin("", strDesign, "-1", "STD", True)
    # print(lstComponents)
    # for objComponent in lstComponents:
    # Name = objComponent.GetName(0)
    # print(f"Component Name: {Name}")
    # try:
    #     objComponent.AddAttribute("Safttuete = CapriSonne",0,0,c.VDVALUEVISIBLE)
    # except:
    #     pass
    # for objCon in objComponent.GetConnections:
    # print(f"Net: {objCon.Net.GetSignals}")
    # print(f"Pin: {objCon.CompPin.Pin.GetName(0)}")
    # objCon.CompPin.Pin.AddLabel("bratwurst",0,0)
    # Pinname = objCon.CompPin.Pin.FindAttribute("Pin Type")
    # print(f"Pintype: {Pinname.Value}")
    # label = objCon.CompPin.Pin.Label.Application
    # print(label)


    # UID = objComponent.UID
    # print("UID:", UID)

    # colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
    # for objBlock in colBlock:
    #     NullPin = pythoncom.Empty
    #     blockname = objBlock.GetName(c.SHORT_NAME)
    #     print(f"Block found: {blockname}")
    #     if blockname == project_name:
    #         objBlock.AddNet(0,0, 0, 0, objPin, objPin, c.VD_BUS)
    #
    #         print("Bus added")
    #     # if objBlock.GetName(c.SHORT_NAME) == "Schematic1":

    #identify amount of subblocks in block
    # colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
    # Open_Sheet = objApplication.SchematicSheetDocuments().Open("Schematic1", "1")
    # for objBlock in colBlock:
    #     sheetnum =  objBlock.SheetNum
    #     blockname = objBlock.GetName(c.SHORT_NAME)
    #     # objApplication.PushPath(f"{blockname}", f"", f"")
    #     print(sheetnum)

    # lstComponents = objApplication.DesignComponents("", "MP_CPU", "-1", "STD", True)
    # # lstPins = objApplication("", strDesign, "-1", "STD", True)
    # for objComponent in  lstComponents:
    #     Name = objComponent.GetName(0)
    #     # print(Name)
    #     type = objComponent.symbolblock.GetName(c.FULL_PATH_NAME)
    #     # location = objComponent.GetLocation
    #     print(type)

    # Open_Sheet = objApplication.SchematicSheetDocuments().Open("MP_CPU", "MP_CPU_1")
    # for View in Open_Sheet.GetViews():
    #     View.Activate()
    #     View.SelectByName("MP_CPU_RAM")
    #     Blocks = View.Query(c.VDM_COMP, c.VD_SELECTED)
    #     for Block in Blocks:
    #         Name = Block.GetName(1)
    #         # Name = Block.Type
    #         print(f"Block found: {Name}")

    cleanup_com()
    # close_project(objApplication)

def main():
    # for i in range(2):
    testroutine()

if __name__ == "__main__":
    main()
