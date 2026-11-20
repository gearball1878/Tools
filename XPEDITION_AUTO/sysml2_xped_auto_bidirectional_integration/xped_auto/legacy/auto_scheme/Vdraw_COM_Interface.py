import win32com.client as win32
import comtypes
import os
import time
import json
from ifc import *
from ifc import constants as c

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

def design_creation():
    project_name = "IVI_Board"

    objApplication : IVdApp = None
    objComponent : IVdComp = None
    objAttribute : IVdAttr = None
    objBlock : IVdBlock = None

    init_com()
    # try:
        # Connect to the application
    objApplication = connect_to_application()
    # project_path = r"C:\Xpedition_Local\Auto2\Auto2.prj"
    project_path = r"C:\Xpedition_Local\Auto3\Auto3.prj"
    open_project(objApplication, project_path)
    # refresh_project_data(objApplication, project_path)
    print(objApplication)
    strDesignPath = objApplication.GetProjectData().GetProjectPath()
    print(strDesignPath)

    strDesign = objApplication.GetProjectData().GetiCDBDesignRootBlock(objApplication.GetActiveDesign())
    print(f"str_des={strDesign}")

    # lstComponents = objApplication.DesignComponents("", strDesign, "-1", "STD", True)
    # # print(lstComponents)
    # for objComponent in lstComponents:
    #     Name = objComponent.GetName(0)
    #     print("Name:", Name)
    #     UID = objComponent.UID
    #     print("UID:", UID)

    objApplication.PushPath(f"Schematic1.1", "", "1")

    data = open_ea_structure()
    domains = list(data.keys())
    colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
    for objBlock in colBlock:
        blockname = objBlock.GetName(c.SHORT_NAME)
        print(f"Block found: {blockname}")
        if blockname == "Schematic1":
            try:
                objBlock.AddFub(f"{project_name}", 1000, 1000, 1500, 1500)
            except Exception as e:
                print(f"Error adding Fub: {e}")

            for domain in domains:
                if domain != "CON":
                    objApplication.PushPath(f"Schematic1", f"{project_name}", f"{domain}")
                else: # Connectors on Toplevel!
                    values = list(data[domain].keys())
                    for value in values:
                        try:
                            objBlock.AddFub(f"{value}", 1000, 1000, 1500, 1500)
                        except Exception as e:
                            print(f"Error adding Fub: {e}")
                        objApplication.PushPath(f"Schematic1", f"{value}", f"1")

    colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
    for objBlock in colBlock:
        for domain in domains:
            blockname = objBlock.GetName(c.SHORT_NAME)
            print(f"Block found: {blockname}")
            act_sheetnum = objBlock.SheetNum
            print(act_sheetnum)
            if blockname == f"{project_name}" and act_sheetnum == domain:
                if domain != "CON":
                    try:
                        objBlock.AddFub(f"{domain}", 1000, 1000, 1500, 1500)
                    except Exception as e:
                        print(f"Error adding Fub: {e}")

    for domain in domains:
        values = list(data[domain].keys())
        print(values)
        for value in values:
            # print(value)
            if domain != "CON":
                objApplication.PushPath(f"{project_name}", domain, f"{value}")

    colBlock = objApplication.OpenBlocks(c.VDDT_SCHEMATIC)
    for objBlock in colBlock:
        for domain in domains:
            values = list(data[domain].keys())
            blockname = objBlock.GetName(c.SHORT_NAME)
            print(f"Block found: {blockname}")
            act_sheetnum = objBlock.SheetNum
            print(act_sheetnum)
            for value in values:
                if blockname == f"{domain}" and act_sheetnum == value:
                    if domain != "CON":
                        try:
                            objBlock.AddFub(f"{value}", 1000, 1000, 1500, 1500)
                        except Exception as e:
                            print(f"Error adding Fub: {e}")

    for domain in domains:
        values = list(data[domain].keys())
        for value in values:
            objApplication.PushPath(f"{domain}", f"{value}", f"1")


    objProjectData = objApplication.GetProjectData().GetiCDBDesigns()
    print(objProjectData)

    cleanup_com()

def testroutine():
    project_name = "IVI_Board"

    objApplication: IVdApp = None
    objComponent: IVdComp = None
    objAttribute: IVdAttr = None
    objBlock: IVdBlock = None

    init_com()
    # try:
    # Connect to the application
    objApplication = connect_to_application()
    # project_path = r"C:\Xpedition_Local\Auto2\Auto2.prj"
    project_path = r"C:\Xpedition_Local\Auto\Auto.prj"
    open_project(objApplication, project_path)
    # refresh_project_data(objApplication, project_path)
    print(objApplication)
    strDesignPath = objApplication.GetProjectData().GetProjectPath()
    print(strDesignPath)

    strDesign = objApplication.GetProjectData().GetiCDBDesignRootBlock(objApplication.GetActiveDesign())
    print(f"str_des={strDesign}")

    data = open_ea_structure()
    domains = list(data.keys())
    for domain in domains:
        values = list(data[domain].keys())
        for value in values:
            objApplication.PushPath(f"{domain}", f"{value}", f"1")

    cleanup_com()


def main():
    design_creation()
    # testroutine()

if __name__ == "__main__":
    main()
