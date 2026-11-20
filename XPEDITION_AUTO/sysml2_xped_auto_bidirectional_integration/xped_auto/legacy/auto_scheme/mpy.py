import sys
from win32com.client import makepy

# sys.argv.append('HyperLynxDRC 7.96 Type Library')
sys.argv.append("Viewdraw.Application")
makepy.main()

# import win32com.client.gencache as gc

# def run():
    # mod = gc.GetModuleForCLSID('{635AAC32-343B-49CE-BED7-37FC07236ED1}')
    # if (mod != None):
    #     print(mod)
