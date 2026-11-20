import os
import json
from gather_design_info import *
from datetime import datetime

class json_exchange:
    def __init__(self):
        pass

    # Writing to a JSON file
    def write_exchange_json(self, file_path, data):
        with open(f"{file_path}", "w") as file:
            json.dump(data, file, indent=4)

    def aes(self, domains):
        pass

    def pins(self, ae, category):
        pass

    def connections(self, ae):
        pass

    def attributes(self, obj):
        pass


# for testing functions ONLY!
def main():
    prj_name = "SSD"
    asbc_connect.init_com
    objApplication = asbc_connect.connect_to_application()
    project_path = r"C:\Xpedition_Local\Auto_401\Auto_401.prj"
    asbc_connect.open_project(objApplication, project_path)
    strDesign = objApplication.GetProjectData().GetiCDBDesignRootBlock(objApplication.GetActiveDesign())
    print(f"str_des={strDesign}")

    directory = r"C:\git\Xpedition\xpedition\Designer_Automation\dev\auto_scheme\Python_COM_Wrapper\json_eax_exports"
    filename = f"eax_exchange_{prj_name}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"

    # Ensure the directory exists
    os.makedirs(directory, exist_ok=True)

    # Full file path
    file_path = os.path.join(directory, filename)

    dict_design = gather_design_info().get_blocks(objApplication, strDesign)
    json_exchange().write_exchange_json(file_path, dict_design)

if __name__ == "__main__":
    main()

