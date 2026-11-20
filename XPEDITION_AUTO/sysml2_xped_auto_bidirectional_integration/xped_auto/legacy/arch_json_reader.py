import json
from pathlib import Path
import pandas as pd
from Source.color_reader import ColorReader
from json_validator import JSONValidator

GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

class ArchJsonReader:
    def __init__(self, file_path, debug = False):
        self.debug = debug

        self.system = None
        self.domain = None
        self.ae = None
        self.port = None
        self.function = None
        self.net = None
        self.block = None

        with open(file_path, 'r') as json_file:
            try:
                self.imported_dict = json.load(json_file)
                if self.debug:
                    print("[DEBUG] JSON file found and opened by reader")
            except:
                 print(f"{RED}[ERROR]{RESET} JSON file not found:", json_file)

            val = JSONValidator(schema_path=Path(__file__).with_name("arch_export_format_json_schema.json"), debug=debug)
            val.json_data = self.imported_dict
            val.json_path = file_path
            val.validate_json()

            self.df = pd.DataFrame(self.imported_dict)

            self.system_ports_dfs = {}
            self.system_blocks_dfs = {}
            self.system_functions_dfs = {}

            self.domain_ports_dfs = {}
            self.domain_blocks_dfs = {}
            self.domain_functions_dfs = {}

            self.ae_ports_dfs = {}
            self.ae_blocks_dfs = {}
            self.ae_functions_dfs = {}

            self.port_cons_dfs = {}

            self.connectivity_dfs = {}

            # Get Systems
            if "System Name" in self.df.columns:
                for i, system in enumerate(self.df["System Name"].tolist()):


                    # Get Ports of System
                    self.system_ports_dfs[system] = pd.DataFrame(self.imported_dict[i]["System Ports"])

                    # Get Blocks of System (Modules)
                    self.system_blocks_dfs[system] = pd.DataFrame(self.imported_dict[i]["System Blocks"])

                    self.domain_ports_dfs[system] = {}
                    self.domain_blocks_dfs[system] = {}
                    self.domain_functions_dfs[system] = {}

                    self.ae_ports_dfs[system] = {}
                    self.ae_blocks_dfs[system] = {}
                    self.ae_functions_dfs[system] = {}

                    self.port_cons_dfs[system] = {}

                    self.connectivity_dfs[system] = {}

                    if "Module Name" in self.system_blocks_dfs[system].columns:
                        for j, domain in enumerate(self.system_blocks_dfs[system]["Module Name"].tolist()):
                            
                            # Get Ports of Module
                            self.domain_ports_dfs[system][domain] = pd.DataFrame(self.imported_dict[i]['System Blocks'][j]['Module Ports'])

                            self.ae_ports_dfs[system][domain] = {}

                            # Get Blocks of Module (AEs)
                            self.domain_blocks_dfs[system][domain] = pd.DataFrame(self.imported_dict[i]['System Blocks'][j]['Module Blocks'])

                            self.ae_blocks_dfs[system][domain] = {}
                            self.port_cons_dfs[system][domain] = {}
                            self.ae_functions_dfs[system][domain] = {}

                            self.connectivity_dfs[system][domain] = {}

                            if "AE Name" in self.domain_blocks_dfs[system][domain].columns:
                                for k, ae in enumerate(self.domain_blocks_dfs[system][domain]["AE Name"].tolist()):                     

                                    # Get Ports of AEs
                                    self.ae_ports_dfs[system][domain][ae] = pd.DataFrame(self.imported_dict[i]['System Blocks'][j]['Module Blocks'][k]['AE Ports'])

                                    self.port_cons_dfs[system][domain][ae] = {}
                                    
                                    self.connectivity_dfs[system][domain][ae] = {}

                                    if "AE Port Name" in self.ae_ports_dfs[system][domain][ae].columns:
                                        for m, port in enumerate(self.ae_ports_dfs[system][domain][ae]["AE Port Name"].tolist()):

                                            # Get Connectors / Nets / Busses
                                            self.port_cons_dfs[system][domain][ae][port] = pd.DataFrame(self.imported_dict[i]['System Blocks'][j]['Module Blocks'][k]['AE Ports'][m]["AE Port Cons"])

                                            self.connectivity_dfs[system][domain][ae][port] = {}

                                            if "Con Name" in self.port_cons_dfs[system][domain][ae][port].columns:
                                                for n, con in enumerate(self.port_cons_dfs[system][domain][ae][port]["Con Name"].tolist()):
                                                    
                                                    # Get Connections that belong to Nets/Busses
                                                    self.connectivity_dfs[system][domain][ae][port][con] = pd.DataFrame(self.imported_dict[i]['System Blocks'][j]['Module Blocks'][k]['AE Ports'][m]["AE Port Cons"][n]["Connectivity"])

                                    # Get Blocks of AEs
                                    self.ae_blocks_dfs[system][domain][ae] = pd.DataFrame(self.imported_dict[i]['System Blocks'][j]['Module Blocks'][k]['AE Components'])

                                    # Get Functions of AEs
                                    self.ae_functions_dfs[system][domain][ae] = pd.DataFrame(self.imported_dict[i]['System Blocks'][j]['Module Blocks'][k]['AE Functions'])

                            # Get Functions of Module
                            self.domain_functions_dfs[system][domain]= pd.DataFrame(self.imported_dict[i]['System Blocks'][j]['Module Functions'])

                    # Get Functions of System
                    self.system_functions_dfs[system] = pd.DataFrame(self.imported_dict[i]["System Functions"])

    def set_system(self, system):
        self.system = system

    def get_set_system(self):
        if self.system == None:
            print(f"{RED}[ERROR]{RESET} No system set. Please set system first via self.set_system().")
        else:
            return self.system

    def set_domain(self, domain, system=None):
        if system == None:
            system = self.get_set_system()
        self.domain = domain

    def get_set_domain(self):
        if self.domain == None:
            print(f"{RED}[ERROR]{RESET} No domain set. Please set domain first via self.set_domain().")
        else:
            return self.domain
        
    def set_ae(self, ae, domain=None, system=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        self.ae = ae

    def get_set_ae(self):
        if self.ae == None:
            print(f"{RED}[ERROR]{RESET} No ae set. Please set ae first via self.set_ae().")
        else:
            return self.ae
        
    def set_port(self, port):
        self.port = port

    def get_set_port(self):
        if self.port == None:
            print(f"{RED}[ERROR]{RESET} No port set. Please set port first via self.set_port().")
        else:
            return self.port

    def set_function(self, function):
        self.function = function

    def get_set_function(self):
        if self.function == None:
            print(f"{RED}[ERROR]{RESET} No function set. Please set function first via self.set_function().")
        else:
            return self.function
        
    def set_net(self, net, ae=None, domain=None, system=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        self.net = net

    def get_set_net(self):
        if self.net == None:
            print(f"{RED}[ERROR]{RESET} No net set. Please set net first via self.set_net().")
        else:
            return self.net
        
    def set_block(self, block, ae=None, domain=None, system=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        self.block = block

    def get_set_block(self):
        if self.block == None:
            print(f"{RED}[ERROR]{RESET} No block set. Please set block first via self.set_block().")
        else:
            return self.block

    def get_systems(self):
        # Returns pandas df of Systems
        return self.df
    
    def get_system_names(self):
        # Returns list of strings with system names
        return self.df["System Name"].tolist()
    
    def get_arch_id_for_system(self, system=None):
        if system == None:
            system = self.get_set_system()
        # Returns arch id as string for defined system (all specified by name)
        return self.df.loc[self.df["System Name"] == system, "System Arch ID"].values[0]
    
    def get_variants_for_system(self, system=None):
        if system == None:
            system = self.get_set_system()
        # Returns variants as list of strings for defined system (all specified by name)
        return self.df.loc[self.df["System Name"] == system, "System Variants"].tolist()[0]

    def get_pins_for_system(self, system=None):
        if system == None:
            system = self.get_set_system()
        # Returns pandas df of ports for system (all specified by name)
        return self.system_ports_dfs[system]

    def get_pin_names_for_system(self, system=None):
        if system == None:
            system = self.get_set_system()
        # Returns list of strings with system port names (all specified by name)
        if "System Port Name" in list(self.system_ports_dfs[system].keys()):
            return self.system_ports_dfs[system]["System Port Name"].tolist() 
        else:
            return [] 
    
    def get_schematic_id_for_pin_for_system(self, system=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if pin == None:
            pin = self.get_set_port()
        # Returns schematic id as string for port of system (all specified by name)
        pins = self.get_pins_for_system(system)
        return pins[pins["System Port Name"] == pin]["System Port SCM ID"].values[0]

    def get_arch_id_for_pin_for_system(self, system=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if pin == None:
            pin = self.get_set_port()
        # Returns architecture id as string for port of system (all specified by name)
        pins = self.get_pins_for_system(system)
        return pins[pins["System Port Name"] == pin]["System Port Arch ID"].values[0]
    
    def get_direction_for_pin_for_system(self, system=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if pin == None:
            pin = self.get_set_port()
        # Returns direction as string for port of system (all specified by name)
        pins = self.get_pins_for_system(system)
        return pins[pins["System Port Name"] == pin]["System Port Direction"].values[0]
    
    def get_variants_for_pin_of_system(self, system=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if pin == None:
            pin = self.get_set_port()
        # Returns variants as list of strings for pins of defined system (all specified by name)
        pins = self.get_pins_for_system(system)
        return pins[pins["System Port Name"] == pin]["System Port Variants"].tolist()[0]

    def get_functions_for_system(self, system=None):
        if system == None:
            system = self.get_set_system()
        # Returns pandas df of functions for system (specified by name)
        return self.system_functions_dfs[system]
    
    def get_function_names_for_system(self, system=None):
        if system == None:
            system = self.get_set_system()
        # Returns pandas df of functions for system (specified by name)
        return self.system_functions_dfs[system]["System Function Name"].tolist()
    
    def get_arch_id_for_function_for_system(self, system=None, function=None):
        if system == None:
            system = self.get_set_system()
        if function == None:
            function = self.get_set_function()
        # Returns string of arch id for function of system
        return self.system_functions_dfs[system].loc[self.system_functions_dfs[system]["System Function Name"] == function, "System Function Arch ID"].values[0]

    # def get_domains_ch(self):
    #     # TODO Check if works for CH      
    #     return self.get_domain_names(self.get_system_names()[0])
    
    def get_domains(self, system=None):
        if system == None:
            system = self.get_set_system()
        # Returns pandas df of domains for system (specified by name)
        return self.system_blocks_dfs[system]
    
    def get_domain_names(self, system=None):
        if system == None:
            system = self.get_set_system()
        # Returns list of strings with module names (specified by name)
        return self.system_blocks_dfs[system]["Module Name"].tolist()

    def get_schematic_id_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns schematic id as string for defined domain of system (all specified by name)
        return self.system_blocks_dfs[system].loc[self.system_blocks_dfs[system]["Module Name"] == domain, "Module SCM ID"].values[0]
    
    def get_arch_id_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns arch id as string for defined domain of system (all specified by name)
        return self.system_blocks_dfs[system].loc[self.system_blocks_dfs[system]["Module Name"] == domain, "Module Arch ID"].values[0]

    def get_color_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns color as string for defined domain of system (all specified by name)
        return self.system_blocks_dfs[system].loc[self.system_blocks_dfs[system]["Module Name"] == domain, "Module Color"].values[0]
    
    def get_variants_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns variants as list of strings for defined domain of system (all specified by name)
        return self.system_blocks_dfs[system].loc[self.system_blocks_dfs[system]["Module Name"] == domain, "Module Variants"].tolist()[0]
    
    def get_pins_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns pandas df of ports for domain of system (all specified by name)
        return self.domain_ports_dfs[system][domain]

    def get_pin_names_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns list of strings with domain port names (all specified by name)
        return self.domain_ports_dfs[system][domain]["Module Port Name"].tolist()  
    
    def get_schematic_id_for_pin_for_domain(self, system=None, domain=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if pin == None:
            pin = self.get_set_port()
        # Returns schematic id as string for port of domain of system (all specified by name)
        pins = self.get_pins_for_domain(system, domain)
        return pins[pins["Module Port Name"] == pin]["Module Port SCM ID"].values[0]

    def get_arch_id_for_pin_for_domain(self, system=None, domain=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if pin == None:
            pin = self.get_set_port()
        # Returns architecture id as string for port of domain of system (all specified by name)
        pins = self.get_pins_for_domain(system, domain)
        return pins[pins["Module Port Name"] == pin]["Module Port Arch ID"].values[0]
    
    def get_direction_for_pin_for_domain(self, system=None, domain=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if pin == None:
            pin = self.get_set_port()
        # Returns direction as string for port of domain of system (all specified by name)
        pins = self.get_pins_for_domain(system, domain)
        return pins[pins["Module Port Name"] == pin]["Module Port Direction"].values[0]
    
    def get_variants_for_pin_for_domain(self, system=None, domain=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if pin == None:
            pin = self.get_set_port()
        # Returns variants as list of strings for port of domain of system (all specified by name)
        pins = self.get_pins_for_domain(system, domain)
        return pins[pins["Module Port Name"] == pin]["Module Port Variants"].tolist()[0]

    # def get_aes_for_domain_ch(self, domain):
    #     # TODO Check if works for CH 
    #     return self.get_ae_names_for_domain(self.get_system_names()[0], domain)

    def get_aes_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns pandas df of aes for domain of system (all specified by name)
        return self.domain_blocks_dfs[system][domain]

    def get_ae_names_for_all_domains(self, system=None):
        if system == None:
            system = self.get_set_system()
        # Returns list of strings with ae names for all domain
        domains = self.get_domain_names(system)
        ae_names = []
        for domain in domains:
            ae_names = ae_names + self.get_ae_names_for_domain(system, domain)
        return ae_names

    def get_ae_names_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns list of strings with ae names for domain of systme (all specified by name)
        if "AE Name" in self.domain_blocks_dfs[system][domain].keys():
            return self.domain_blocks_dfs[system][domain]["AE Name"].tolist()  
        else:
            return []

    def get_functions_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns pandas df of functions for domain of system (all specified by name)
        return self.domain_functions_dfs[system][domain]
    
    def get_function_names_for_domain(self, system=None, domain=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        # Returns list of strings with function names of domain of system (all specified by name)
        return self.domain_functions_dfs[system][domain]["Module Function Name"].tolist()
    
    def get_arch_id_for_function_for_domain(self, system=None, domain=None, function=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if function == None:
            function = self.get_set_function()
        # Returns arch id as string for defined function of domain of system (all specified by name)
        return self.domain_functions_dfs[system][domain].loc[self.domain_functions_dfs[system][domain]["Module Function Name"] == function, "Module Function Arch ID"].values[0]
    
    def get_type_for_function_for_domain(self, system=None, domain=None, function=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if function == None:
            function = self.get_set_function()
        # Returns type as string for defined function of domain of system (all specified by name)
        return self.domain_functions_dfs[system][domain].loc[self.domain_functions_dfs[system][domain]["Module Function Name"] == function, "Module Function Type"].values[0]

    def get_asil_for_function_for_domain(self, system=None, domain=None, function=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if function == None:
            function = self.get_set_function()
        # Returns asil as string for defined function of domain of system (all specified by name)
        return self.domain_functions_dfs[system][domain].loc[self.domain_functions_dfs[system][domain]["Module Function Name"] == function, "Module Function ASIL"].values[0]

    def get_schematic_id_for_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
         # Returns scm id as string for defined ae of domain of system (all specified by name)
        return self.domain_blocks_dfs[system][domain].loc[self.domain_blocks_dfs[system][domain]["AE Name"] == ae, "AE SCM ID"].values[0]

    def get_arch_id_for_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns arch id as string for defined ae of domain of system (all specified by name)
        return self.domain_blocks_dfs[system][domain].loc[self.domain_blocks_dfs[system][domain]["AE Name"] == ae, "AE Arch ID"].values[0]

    def get_system_function_of_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns customer function as string for defined ae of domain of system (all specified by name)
        return self.domain_blocks_dfs[system][domain].loc[self.domain_blocks_dfs[system][domain]["AE Name"] == ae, "AE CustName"].values[0]
    
    def get_color_of_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns color as string for defined ae of domain of system (all specified by name)
        return self.domain_blocks_dfs[system][domain].loc[self.domain_blocks_dfs[system][domain]["AE Name"] == ae, "AE Color"].values[0]
    
    def get_block_type_of_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns block type as string for defined ae of domain of system (all specified by name)
        color = self.get_color_of_ae(system, domain, ae)
        color_reader = ColorReader()
        return color_reader.get_block_type_from_color(color)

    def get_power_modes_of_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns power modes as list of strings for defined ae of domain of system (all specified by name)
        return self.domain_blocks_dfs[system][domain].loc[self.domain_blocks_dfs[system][domain]["AE Name"] == ae, "AE Power Modes"].tolist()[0]

    def get_class_of_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns class as string for defined ae of domain of system (all specified by name)
        return self.domain_blocks_dfs[system][domain].loc[self.domain_blocks_dfs[system][domain]["AE Name"] == ae, "AE Class"].values[0]

    def get_variants_of_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns variants as list of strings for defined ae of domain of system (all specified by name)
        return self.domain_blocks_dfs[system][domain].loc[self.domain_blocks_dfs[system][domain]["AE Name"] == ae, "AE Variants"].tolist()[0]
    
    def get_functions_for_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns pandas df of functions for ae of domain of system (all specified by name)
        return self.ae_functions_dfs[system][domain][ae]

    def get_function_names_for_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns list of strings with ae function names of domain of system (all specified by name)
        if "AE Function Name" in list(self.ae_functions_dfs[system][domain][ae].keys()):
            return self.ae_functions_dfs[system][domain][ae]["AE Function Name"].tolist()#
        else:
            return []
    
    def get_arch_id_for_function_for_ae(self, system=None, domain=None, ae=None, function=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if function == None:
            function = self.get_set_function()
         # Returns arch id as string for defined function of of ae of domain of system (all specified by name)
        return self.ae_functions_dfs[system][domain][ae].loc[self.ae_functions_dfs[system][domain][ae]["AE Function Name"] == function, "AE Function Arch ID"].values[0]
    
    def get_type_for_function_for_ae(self, system=None, domain=None, ae=None, function=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if function == None:
            function = self.get_set_function()
         # Returns type as string for defined function of of ae of domain of system (all specified by name)
        return self.ae_functions_dfs[system][domain][ae].loc[self.ae_functions_dfs[system][domain][ae]["AE Function Name"] == function, "AE Function Type"].values[0]
    
    def get_asil_for_function_for_ae(self, system=None, domain=None, ae=None, function=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if function == None:
            function = self.get_set_function()
         # Returns asil as string for defined function of of ae of domain of system (all specified by name)
        return self.ae_functions_dfs[system][domain][ae].loc[self.ae_functions_dfs[system][domain][ae]["AE Function Name"] == function, "AE Function ASIL"].values[0]
    
    def get_states_for_function_for_ae(self, system=None, domain=None, ae=None, function=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if function == None:
            function = self.get_set_function()
         # Returns states as list of strings for defined function of of ae of domain of system (all specified by name)
        return self.ae_functions_dfs[system][domain][ae].loc[self.ae_functions_dfs[system][domain][ae]["AE Function Name"] == function, "AE Function States"].tolist()[0]

    # def get_pins_for_ea_ch(self, domain, ae):
    #     # TODO Check if works for CH  
    #     self.get_pin_names_for_ae(self.get_systems()[0], domain, ae)

    def get_pins_for_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns pandas df of ports for ae of domain of system (all specified by name)
        return self.ae_ports_dfs[system][domain][ae]

    def get_pin_names_for_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns list of strings with port names for ae of domain of system (all specified by name)
        if "AE Port Name" in self.ae_ports_dfs[system][domain][ae].keys():
            return self.ae_ports_dfs[system][domain][ae]["AE Port Name"].tolist()
        else:
            return []
    
    # TODO Discuss if required
    # def get_pins_for_ae_without_type(self, domain, ae):
    #     # Return list of pins 
    #     return (self.pins_for_ae[ae])

    def get_pins_of_type_for_ae(self, system=None, domain=None, ae=None, pin_type=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin_type == None:
            return []
        # Returns pandas df of ports for ae of domain of system of specific port type (all specified by name)
        pins = self.get_pins_for_ae(system, domain, ae)
        return pins[pins["AE Port Type"] == pin_type]
    
    def get_pin_names_of_type_for_ae(self, system=None, domain=None, ae=None, pin_type=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin_type == None:
            return []
        # Returns list of strings of pin names of ae of domain of system of specified port type (all specified by name)
        return self.get_pins_of_type_for_ae(system, domain, ae, pin_type)["AE Port Name"].tolist()
    
    def get_schematic_id_for_pin_of_ae(self, system=None, domain=None, ae=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        # Returns schematic id as string for port of ae of domain of system (all specified by name)
        pins = self.get_pins_for_ae(system, domain, ae)
        return pins[pins["AE Port Name"] == pin]["AE Port SCM ID"].values[0]

    def get_arch_id_for_pin_for_ae(self, system=None, domain=None, ae=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        # Returns architecture id as string for port of ae of domain of system (all specified by name)
        pins = self.get_pins_for_ae(system, domain, ae)
        if len(pins[pins["AE Port Name"] == pin]["AE Port Arch ID"].values) != 0:
            return pins[pins["AE Port Name"] == pin]["AE Port Arch ID"].values[0]
        else:
            return ""
    
    def get_direction_for_pin_for_ae(self, system=None, domain=None, ae=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        # Returns direction as string for port of ae of domain of system (all specified by name)
        pins = self.get_pins_for_ae(system, domain, ae)
        return pins[pins["AE Port Name"] == pin]["AE Port Direction"].values[0]

    def get_type_for_pin_for_ae(self, system=None, domain=None, ae=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        # Returns direction as string for port of ae of domain of system (all specified by name)
        pins = self.get_pins_for_ae(system, domain, ae)
        return pins[pins["AE Port Name"] == pin]["AE Port Type"].values[0]

    def get_variants_for_pin_for_ae(self, system=None, domain=None, ae=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        # Returns variants as list of strings for port of ae of domain of system (all specified by name)
        pins = self.get_pins_for_ae(system, domain, ae)
        return pins[pins["AE Port Name"] == pin]["AE Port Variants"].tolist()[0]
    
    def get_net_names_for_pin_of_ae(self, system=None, domain=None, ae=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        # Returns list of strings of names of ports of ae of domain of system (all specified by name)
        if "Con Name" in list(self.port_cons_dfs[system][domain][ae][pin].keys()):
            return self.port_cons_dfs[system][domain][ae][pin]["Con Name"].tolist()
        else:
            return []

    def get_nets_for_pin_of_ae(self, system=None, domain=None, ae=None, pin=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        # Returns pandas df of connectors of ports of ae of domain of system (all specified by name)
        return self.port_cons_dfs[system][domain][ae][pin]

    def get_schematic_id_for_net_of_pin_of_ae(self, system=None, domain=None, ae=None, pin=None, net=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        if net == None:
            net = self.get_set_net()
        # Returns schematic id as string for connector of ae of domain of system (all specified by name)
        cons = self.port_cons_dfs[system][domain][ae][pin]
        return cons[cons["Con Name"] == net]["Con SCM ID"].values[0]
    
    def get_arch_id_for_net_of_pin_of_ae(self, system=None, domain=None, ae=None, pin=None, net=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        if net == None:
            net = self.get_set_net()
        # Returns net architecture ids as list of strings for connectors of ae of domain of system (all specified by name)
        if "Connector Arch ID" in list(self.connectivity_dfs[system][domain][ae][pin][net].keys()):
            return self.connectivity_dfs[system][domain][ae][pin][net]["Connector Arch ID"].tolist()
        else:
            return []
    
    def get_connected_ports_arch_ids_for_net_of_pin_of_ae(self, system=None, domain=None, ae=None, pin=None, net=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        if net == None:
            net = self.get_set_net()
        # Returns port architecture ids as list of strings for connected ports of ae of domain of system (all specified by name)
        if "Connected Port Arch ID" in list(self.connectivity_dfs[system][domain][ae][pin][net].keys()):
            return self.connectivity_dfs[system][domain][ae][pin][net]["Connected Port Arch ID"].tolist()
        else:
            return []

    def get_connected_ports_scm_ids_for_net_of_pin_of_ae(self, system=None, domain=None, ae=None, pin=None, net=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        if net == None:
            net = self.get_set_net()
        # Returns port architecture ids as list of strings for connected ports of ae of domain of system (all specified by name)
        if "Connected Port SCM ID" in list(self.connectivity_dfs[system][domain][ae][pin][net].keys()):
            return self.connectivity_dfs[system][domain][ae][pin][net]["Connected Port SCM ID"].tolist()
        else:
            return []
    
    def get_type_for_net_of_pin_of_ae(self, system=None, domain=None, ae=None, pin=None, net=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        if net == None:
            net = self.get_set_net()
        # Returns type as string for connector of ae of domain of system (all specified by name)
        cons = self.port_cons_dfs[system][domain][ae][pin]
        return cons[cons["Con Name"] == net]["Con Type"].values[0]
    
    def get_arch_id_of_pin_parent(self, pin_arch_id):
        # Returns arch id of parent (ae, domain, system) as string for given pin arch id
        if pin_arch_id in self.arch_id_dict.keys():
            return self.arch_id_dict[pin_arch_id]["Parent"]
        else:
            return ""

    def get_names_of_blocks_of_ae(self, system=None, domain=None, ae=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        # Returns list of strings of names of blocks of ae of domain of system (all specified by name)
        return self.ae_blocks_dfs[system][domain][ae]["AE Component Name"].tolist()

    def get_schematic_id_for_block_of_ae(self, system=None, domain=None, ae=None, block=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if block == None:
            block = self.get_set_block()
        # Returns schematic id as string for block of ae of domain of system (all specified by name)
        return self.ae_blocks_dfs[system][domain][ae].loc[self.ae_blocks_dfs[system][domain][ae]["AE Component Name"] == block, "AE Component SCM ID"].values[0]
    
    def get_variants_for_block_of_ae(self, system=None, domain=None, ae=None, block=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if block == None:
            block = self.get_set_block()
        # Returns variants as list of strings for block of ae of domain of system (all specified by name)
        return self.ae_blocks_dfs[system][domain][ae].loc[self.ae_blocks_dfs[system][domain][ae]["AE Component Name"] == block, "AE Component Variants"].tolist()[0]

    def create_id_dicts(self, create_dicts_of_new_elements=False, create_all_new_elements=False):
        self.scm_id_dict = {}
        self.scm_id_paths = {}
        self.arch_id_dict = {}
        self.arch_id_paths = {}
        if create_dicts_of_new_elements:
            self.new_element_dict_for_arch = {}
            self.new_element_dict_for_arch["System"] = []
            self.new_element_dict_for_arch["Module"] = []
            self.new_element_dict_for_arch["AE"] = []
            self.new_element_dict_for_arch["System Port"] = []
            self.new_element_dict_for_arch["Module Port"] = []
            self.new_element_dict_for_arch["AE Port"] = []
            self.new_element_dict_for_arch["Connector"] = []
            self.new_element_dict_for_arch["System Function"] = []
            self.new_element_dict_for_arch["Module Function"] = []
            self.new_element_dict_for_arch["AE Function"] = []

        # Get Systems
        if "System Name" in self.df.columns:
            for system in self.get_system_names():

                # Store IDs of System
                arch_id = self.get_arch_id_for_system(system)
                variants = self.get_variants_for_system(system)
                self.arch_id_dict[arch_id] = {"Name": system,  "Variants": variants, "ElemType": "System"}
                if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                    self.new_element_dict_for_arch["System"].append({"Name": system, "Variants": variants, "Path": [system]})

                # System Ports
                if "System Port Name" in self.system_ports_dfs[system].columns:
                    for port in self.get_pin_names_for_system(system):
                        arch_id = self.get_arch_id_for_pin_for_system(system, port)
                        scm_id = self.get_schematic_id_for_pin_for_system(system, port)
                        direction = self.get_direction_for_pin_for_system(system, port)
                        variants = self. get_variants_for_pin_of_system(system, port)
                        if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                            self.new_element_dict_for_arch["System Port"].append({"Parent": self.get_arch_id_for_system(system), "Name": port, "SCM ID": scm_id, "Direction": direction, "Variants": variants, "Path": [system]})
                        self.arch_id_dict[arch_id] = {"Name": port, "SCM ID": scm_id, "Direction": direction, "Variants": variants, "ElemType": "System Port"}
                        self.scm_id_dict[scm_id] = {"Name": port, "SCM ID": scm_id, "Direction": direction, "Variants": variants, "ElemType": "System Port"}
                        self.arch_id_paths[arch_id] = [system]
                        self.scm_id_paths[scm_id] = [system]

                if "Module Name" in self.system_blocks_dfs[system].columns:
                    for domain in self.get_domain_names(system):
                        
                        # Store IDs of Modules
                        arch_id = self.get_arch_id_for_domain(system, domain)
                        scm_id = self.get_schematic_id_for_domain(system, domain)
                        color = self.get_color_for_domain(system, domain)
                        variants = self.get_variants_for_domain(system, domain)
                        if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                            self.new_element_dict_for_arch["Module"].append({"Parent": self.get_arch_id_for_system(system), "Name": domain, "SCM ID": scm_id, "Color": color, "Variants": variants, "Path": [system, domain]})
                        self.arch_id_dict[arch_id] = {"Name": domain, "SCM ID": scm_id, "Color": color, "Variants": variants, "ElemType": "Module"}
                        self.scm_id_dict[scm_id] = {"Name": domain, "Arch ID": arch_id, "Color": color, "Variants": variants, "ElemType": "Module"}
                        self.arch_id_paths[arch_id] = [system, domain]
                        self.scm_id_paths[scm_id] = [system, domain]
                        
                        # Module Ports
                        if "Module Port Name" in self.domain_ports_dfs[system][domain].columns:
                            for port in self.get_pin_names_for_domain(system, domain):
                                arch_id = self.get_arch_id_for_pin_for_domain(system, domain, port)
                                scm_id = self.get_schematic_id_for_pin_for_domain(system, domain, port)
                                direction = self.get_direction_for_pin_for_domain(system, domain, port)
                                variants = self.get_variants_for_pin_for_domain(system, domain, port)
                                if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                                    self.new_element_dict_for_arch["Module Port"].append({"Parent": self.get_arch_id_for_domain(system, domain), "Name": port, "SCM ID": scm_id, "Direction": direction, "Variants": variants, "Path": [system, domain]})
                                self.arch_id_dict[arch_id] = {"Name": port, "SCM ID": scm_id, "Direction": direction, "Parent": self.get_arch_id_for_system(system), "Variants": variants, "ElemType": "Module Port"}
                                self.scm_id_dict[scm_id] = {"Name": port, "Arch ID": arch_id, "Direction": direction, "Parent": self.get_arch_id_for_system(system), "Variants": variants, "ElemType": "Module Port"}
                                self.arch_id_paths[arch_id] = [system, domain]
                                self.scm_id_paths[scm_id] = [system, domain]

                        if "AE Name" in self.domain_blocks_dfs[system][domain].columns:
                            for ae in self.get_ae_names_for_domain(system, domain):                     

                                # Store IDs of AEs
                                arch_id = self.get_arch_id_for_ae(system, domain, ae)
                                scm_id = self.get_schematic_id_for_ae(system, domain, ae)
                                custname = self.get_system_function_of_ae(system, domain, ae)
                                color = self.get_color_of_ae(system, domain, ae)
                                power_modes = self.get_power_modes_of_ae(system, domain, ae)
                                ae_class = self.get_class_of_ae(system, domain, ae)
                                variants = self.get_variants_of_ae(system, domain, ae)
                                if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                                    self.new_element_dict_for_arch["AE"].append({"Parent": self.get_arch_id_for_domain(system, domain), "Name": ae, "SCM ID": scm_id, "Color": color, "CustName": custname, "PowerModes": power_modes, "Class": ae_class, "Variants": variants, "Path": [system, domain, ae]})
                                self.arch_id_dict[arch_id] = {"Name": ae, "SCM ID": scm_id, "Color": color, "CustName": custname, "Parent": self.get_arch_id_for_domain(system, domain), "PowerModes": power_modes, "Class": ae_class, "Variants": variants, "ElemType": "AE"}
                                self.scm_id_dict[scm_id] = {"Name": ae, "Arch ID": arch_id, "Color": color, "CustName": custname, "Parent": self.get_arch_id_for_domain(system, domain), "PowerModes": power_modes, "Class": ae_class, "Variants": variants, "ElemType": "AE"}
                                self.arch_id_paths[arch_id] = [system, domain, ae]
                                self.scm_id_paths[scm_id] = [system, domain, ae]

                                # AE Ports
                                if "AE Port Name" in self.ae_ports_dfs[system][domain][ae].columns:
                                    for port in self.get_pin_names_for_ae(system, domain, ae):

                                        # Store IDs of Ports
                                        arch_id = self.get_arch_id_for_pin_for_ae(system, domain, ae, port)
                                        scm_id = self.get_schematic_id_for_pin_of_ae(system, domain, ae, port) 
                                        direction = self.get_direction_for_pin_for_ae(system, domain, ae, port)
                                        type = self.get_type_for_pin_for_ae(system, domain, ae, port)
                                        variants = self.get_variants_for_pin_for_ae(system, domain, ae, port)
                                        if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                                            self.new_element_dict_for_arch["AE Port"].append({"Parent": self.get_arch_id_for_ae(system, domain, ae), "Name": port, "SCM ID": scm_id, "Direction": direction, "Type": type, "Variants": variants, "Path": [system, domain, ae]})
                                        self.arch_id_dict[arch_id] = {"Name": port, "SCM ID": scm_id, "Direction": direction, "Type": type, "Parent": self.get_arch_id_for_ae(system, domain, ae), "Variants": variants, "ElemType": "AE Port"}
                                        self.scm_id_dict[scm_id] = {"Name": port, "Arch ID": arch_id, "Direction": direction, "Type": type, "Parent": self.get_arch_id_for_ae(system, domain, ae), "Variants": variants, "ElemType": "AE Port"}
                                        self.arch_id_paths[arch_id] = [system, domain, ae, port]
                                        self.scm_id_paths[scm_id] = [system, domain, ae, port]

                                        if "Con Name" in self.port_cons_dfs[system][domain][ae][port].columns: 
                                            for con in self.get_net_names_for_pin_of_ae(system, domain, ae, port):
                                                arch_ids = self.get_arch_id_for_net_of_pin_of_ae(system, domain, ae, port, con)
                                                scm_id = self.get_schematic_id_for_net_of_pin_of_ae(system, domain, ae, port, con)
                                                con_port_arch_ids = self.get_connected_ports_arch_ids_for_net_of_pin_of_ae(system, domain, ae, port, con)
                                                con_port_scm_ids = self.get_connected_ports_scm_ids_for_net_of_pin_of_ae(system, domain, ae, port, con)
                                                con_type = self.get_type_for_net_of_pin_of_ae(system, domain, ae, port, con)
                                                for arch_id in arch_ids:
                                                    if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                                                        for con_port_scm_id in con_port_scm_ids:
                                                            if con_port_scm_id in list(self.scm_id_dict.keys()):
                                                                con_port_arch_id = self.scm_id_dict[con_port_scm_id]["Arch ID"]
                                                            else:
                                                                con_port_arch_id = ""
                                                            self.new_element_dict_for_arch["Connector"].append({"Parent": self.get_arch_id_for_pin_for_ae(system, domain, ae, port), "ConPort Arch ID": con_port_arch_id, "ConPort SCM ID": con_port_scm_id, "Name": con, "SCM ID": scm_id, "Con Type": con_type, "Path": [system, domain, ae, port]})
                                                for arch_id, con_port_arch_id, con_port_scm_id in zip(arch_ids, con_port_arch_ids, con_port_scm_ids):
                                                    self.arch_id_dict[arch_id] = {"Name": con, "SCM ID": scm_id, "ConPort Arch ID": con_port_arch_id, "ConPort SCM ID": con_port_scm_id, "ElemType": "Connector"}
                                                    self.arch_id_paths[arch_id] = [system, domain, ae, port, con]
                                                self.scm_id_dict[scm_id] = {"Name": con, "Arch ID": arch_ids, "ConPort Arch ID": con_port_arch_ids, "ConPort SCM ID": con_port_scm_ids, "ElemType": "Connector"}
                                                self.scm_id_paths[scm_id] = [system, domain, ae, port, con]

                                if "AE Component Name" in self.ae_ports_dfs[system][domain][ae].columns:
                                    for block in self.get_names_of_blocks_of_ae(system, domain, ae):
                                        scm_id = self.get_schematic_id_for_block_of_ae(system, domain, ae, block)
                                        variants = self.get_variants_for_block_of_ae(system, domain, ae, block)
                                        self.scm_id_dict[scm_id] = {"Name": block, "Parent": self.get_arch_id_for_ae(system, domain, ae), "Variants": variants, "ElemType": "AE Component"}
                                        self.scm_id_paths[scm_id] = [system, domain, ae]

                                if "AE Function Name" in self.ae_functions_dfs[system][domain][ae].columns:
                                    for function in self.get_function_names_for_ae(system, domain, ae):
                                        arch_id = self.get_arch_id_for_function_for_ae(system, domain, ae, function)
                                        type = self.get_type_for_function_for_ae(system, domain, ae, function)
                                        asil = self.get_asil_for_function_for_ae(system, domain, ae, function)
                                        states = self.get_states_for_function_for_ae(system, domain, ae, function)
                                        if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                                            self.new_element_dict_for_arch["AE Function"].append({"Allocation": self.get_arch_id_for_ae(system, domain, ae), "Name": function, "Type": type, "ASIL": asil, "States": states, "Path": [system, domain, ae]})
                                        self.arch_id_dict[arch_id] = {"Name": function, "Type": type, "ASIL": asil, "Allocation": self.get_arch_id_for_ae(system, domain, ae), "States": states, "ElemType": "AE Function"}
                                        self.arch_id_paths[arch_id] = [system, domain, ae]

                        # Get Functions of Module
                        if "Module Function Name" in self.domain_functions_dfs[system][domain].columns:
                            for function in self.get_function_names_for_domain(system, domain):
                                arch_id = self.get_arch_id_for_function_for_domain(system, domain, function)
                                type = self.get_type_for_function_for_domain(system, domain, function)
                                asil = self.get_asil_for_function_for_domain(system, domain, function)
                                if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                                    self.new_element_dict_for_arch["Module Function"].append({"Allocation": self.get_arch_id_for_domain(system, domain), "Name": function, "Type": type, "ASIL": asil, "Path": [system, domain]})
                                self.arch_id_dict[arch_id] = {"Name": function, "Type": type, "ASIL": asil, "Allocation": self.get_arch_id_for_domain(system, domain), "ElemType": "Module Function"}
                                self.arch_id_paths[arch_id] = [system, domain]

                # Get Functions of System
                if "System Function Name" in self.system_functions_dfs[system].columns:
                    for function in self.get_function_names_for_system(system):   
                        arch_id = self.get_arch_id_for_function_for_system(system, function)
                        if (arch_id == "" or create_all_new_elements) and create_dicts_of_new_elements:
                                self.new_element_dict_for_arch["System Function"].append({"Allocation": self.get_arch_id_for_system(system), "Name": function, "Path": [system]})
                        self.arch_id_dict[arch_id] = {"Name": function, "Allocation": self.get_arch_id_for_system(system), "ElemType": "System Function"}
                        self.arch_id_paths[arch_id] = [system]
        
        if "" in self.scm_id_dict.keys():
            self.scm_id_dict.pop("")
        if "" in self.arch_id_dict.keys():
            self.arch_id_dict.pop("")

    def get_connected_port_name_for_net_of_pin_of_ae(self, system=None, domain=None, ae=None, pin=None, net=None):
        if system == None:
            system = self.get_set_system()
        if domain == None:
            domain = self.get_set_domain()
        if ae == None:
            ae = self.get_set_ae()
        if pin == None:
            pin = self.get_set_port()
        if net == None:
            net = self.get_set_net()
        if not hasattr(self, "id_dict"):
            self.create_id_dicts()
        # Returns port names as list of strings for connected ports of ae of domain of system (all specified by name)
        return_list = []
        for cp in self.get_connected_ports_arch_ids_for_net_of_pin_of_ae(system, domain, ae, pin, net):
            if cp in self.arch_id_dict.keys():
                return_list.append(self.arch_id_dict[cp]["Name"])
        return return_list

    def get_name_of_element_with_schematic_id(self, schematic_id):
        if not hasattr(self, "id_dict"):
            self.create_id_dicts()
        # Returns the name of the element as string for defined schematic id
        return self.scm_id_dict[schematic_id]["Name"]

    def get_name_of_element_with_arch_id(self, arch_id):
        if not hasattr(self, "id_dict"):
            self.create_id_dicts()
        # Returns the name of the element as string for defined arch id
        return self.arch_id_dict[arch_id]["Name"]

    def get_schematic_id_for_element_with_arch_id(self, arch_id):
        if not hasattr(self, "id_dict"):
            self.create_id_dicts()
        # Returns the schematic id as string for given architecture id as string
        return self.arch_id_dict[arch_id]["SCM ID"]

    def get_arch_id_for_element_with_schematic_id(self, schematic_id):
        if not hasattr(self, "id_dict"):
            self.create_id_dicts()
        # Returns the arch id as string for given schematic id as string
        return self.scm_id_dict[schematic_id]["Arch ID"]
    
    def get_element_type_by_arch_id(self, arch_id):
        # returns element type as string for given arch id
        return self.arch_id_dict[arch_id]["ElemType"]

    def get_element_type_by_scm_id(self, scm_id):
        # returns element type as string for given scm id
        return self.scm_id_dict[scm_id]["ElemType"]

    # Should be moved to a checker function
    # def replace_empty_net_names_with_undefined(self):
    #     for domain in (self.imported_dict.keys()):
    #         for ae in (self.imported_dict[domain][3].keys()):
    #             for port_type in (self.imported_dict[domain][3][ae][4]["Pins"].keys()): 
    #                 for pin in self.imported_dict[domain][3][ae][4]["Pins"][port_type].keys():
    #                     list_of_nets = list((self.imported_dict[domain][3][ae][4]["Pins"][port_type][pin][2].keys()))
    #                     for net in list_of_nets:
    #                         if net == "":
    #                             self.imported_dict[domain][3][ae][4]["Pins"][port_type][pin][2]["Undefined"] = self.imported_dict[domain][3][ae][4]["Pins"][port_type][pin][2][net]
    #                             self.imported_dict[domain][3][ae][4]["Pins"][port_type][pin][2].pop(net)
    #     self.create_ae_dict()
    #     self.create_pins_of_aes_dict()
    #     self.create_id_dicts()

    # def generate_net_names_based_on_port_names(self):
    #     for domain in (self.imported_dict.keys()):
    #         for ae in (self.imported_dict[domain][3].keys()):
    #             for port_type in (self.imported_dict[domain][3][ae][4]["Pins"].keys()): 
    #                 for pin in self.imported_dict[domain][3][ae][4]["Pins"][port_type].keys():
    #                     list_of_nets = list((self.imported_dict[domain][3][ae][4]["Pins"][port_type][pin][2].keys()))
    #                     for net in list_of_nets:
    #                         if net == "":
    #                             net_name = pin.replace("Port", "Link")
    #                             self.imported_dict[domain][3][ae][4]["Pins"][port_type][pin][2][net_name] = self.imported_dict[domain][3][ae][4]["Pins"][port_type][pin][2][net]
    #                             self.imported_dict[domain][3][ae][4]["Pins"][port_type][pin][2].pop(net)
    #     self.create_ae_dict()
    #     self.create_pins_of_aes_dict()
    #     self.create_id_dicts()

    # def check_uniqueness_of_ae_names_over_domains(self):
    #     names = []
    #     for domain in (self.imported_dict.keys()):
    #         aes = self.imported_dict[domain][2]
    #         for ae in aes:
    #             if ae not in names: 
    #                 names.append(ae)
    #             else:
    #                 return False
    #     return True   


class arch_json_reader_tester:

    def __init__(self, json_file_test_path):
        reader = ArchJsonReader(json_file_test_path)

        print("Tests in", f"{GREEN} GREEN {RESET}", "are passed, in", f"{RED} RED {RESET}", "are failed")
        passed_counter = 0
        failed_counter = 0

        condition = bool(reader.get_systems()["System Name"][0]=="Example_System_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_systems {RESET}")

        condition = bool(reader.get_system_names()[0]=="Example_System_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_system_names {RESET}")

        condition = bool(reader.get_arch_id_for_system("Example_System_Name")=="{1AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_system {RESET}")

        condition = bool(reader.get_variants_for_system("Example_System_Name")==["Example_Variant_A", "Example_Variant_B"])
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_variants_for_system {RESET}")

        ## Test get_pins_for_system: Incomplete test coverage - deepen test if necessary
        condition = bool(reader.get_pins_for_system("Example_System_Name")["System Port Name"][0] == "Example_System_Port_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_pins_for_system {RESET}")

        condition = bool(reader.get_pin_names_for_system("Example_System_Name")[0] == "Example_System_Port_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_pin_names_for_system {RESET}")

        condition = bool(reader.get_schematic_id_for_pin_for_system("Example_System_Name", "Example_System_Port_Name")=="SP$PP")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_schematic_id_for_pin_for_system {RESET}")

        condition = bool(reader.get_arch_id_for_pin_for_system("Example_System_Name", "Example_System_Port_Name")=="{2AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_pin_for_system{RESET}")

        condition = bool(reader.get_direction_for_pin_for_system("Example_System_Name", "Example_System_Port_Name")=="in")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_direction_for_pin_for_system{RESET}")

        condition = bool(reader.get_variants_for_system("Example_System_Name")==["Example_Variant_A", "Example_Variant_B"])
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_variants_for_system({RESET}")

        condition = (reader.get_functions_for_system("Example_System_Name")["System Function Name"]=="Example_System_Function_Name").bool()
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_functions_for_system {RESET}")

        condition = bool(reader.get_function_names_for_system("Example_System_Name")[0]=="Example_System_Function_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_function_names_for_system {RESET}")

        condition = bool(reader.get_arch_id_for_function_for_system("Example_System_Name", "Example_System_Function_Name")=="{BAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_function_for_system {RESET}")

        condition = (reader.get_domains("Example_System_Name")["Module Name"]=="Example_Module_Name").bool()
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_domains {RESET}")

        condition = bool(reader.get_domain_names("Example_System_Name")[0]=="Example_Module_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_domain_names {RESET}")

        condition = bool(reader.get_schematic_id_for_domain("Example_System_Name", "Example_Module_Name")=="MM$MM")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_schematic_id_for_domain {RESET}")

        condition = bool(reader.get_arch_id_for_domain("Example_System_Name", "Example_Module_Name")=="{3AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_domain {RESET}")

        condition = bool(reader.get_color_for_domain("Example_System_Name", "Example_Module_Name")=="0xFFFFFF")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_color_for_domain {RESET}")

        condition = bool(reader.get_variants_for_domain("Example_System_Name", "Example_Module_Name")==["Example_Variant_A", "Example_Variant_B"])
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_variants_for_domain {RESET}")

        ## Test get_pins_for_domain: Incomplete test coverage - deepen test if necessary
        condition = bool(reader.get_pins_for_domain("Example_System_Name", "Example_Module_Name")["Module Port Name"][0] == "Example_Module_Port_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_pins_for_domain {RESET}")

        condition = bool(reader.get_pin_names_for_domain("Example_System_Name", "Example_Module_Name")[0] == "Example_Module_Port_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_pin_names_for_domain {RESET}")

        condition = bool(reader.get_schematic_id_for_pin_for_domain("Example_System_Name", "Example_Module_Name", "Example_Module_Port_Name")=="MP$PP")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_schematic_id_for_pin_for_domain {RESET}")

        condition = bool(reader.get_arch_id_for_pin_for_domain("Example_System_Name", "Example_Module_Name", "Example_Module_Port_Name")=="{4AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_pin_for_domain{RESET}")

        condition = bool(reader.get_direction_for_pin_for_domain("Example_System_Name", "Example_Module_Name", "Example_Module_Port_Name")=="in")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_direction_for_pin_for_domain{RESET}")

        condition = bool(reader.get_variants_for_pin_for_domain("Example_System_Name", "Example_Module_Name", "Example_Module_Port_Name")==["Example_Variant_A", "Example_Variant_B"])
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_variants_for_pin_for_domain{RESET}")

        ## Test get_aes_for_domain: Incomplete test coverage - deepen test if necessary
        condition = bool(reader.get_aes_for_domain("Example_System_Name", "Example_Module_Name")["AE Name"][0] == 'Example_Architectural_Element_Name')
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_aes_for_domain {RESET}")

        condition = bool(reader.get_ae_names_for_domain("Example_System_Name", "Example_Module_Name")[0] == 'Example_Architectural_Element_Name')
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_aes_for_domain {RESET}")

        condition = (reader.get_functions_for_domain("Example_System_Name", "Example_Module_Name")["Module Function Name"] == 'Example_Module_Function_Name').bool()
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_functions_for_domain {RESET}")
        
        condition = bool(reader.get_function_names_for_domain("Example_System_Name", "Example_Module_Name")[0] == 'Example_Module_Function_Name')
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_function_names_for_domain {RESET}")

        condition = bool(reader.get_arch_id_for_function_for_domain("Example_System_Name", "Example_Module_Name", "Example_Module_Function_Name") == '{0AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}')
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_function_for_domain {RESET}")

        condition = bool(reader.get_type_for_function_for_domain("Example_System_Name", "Example_Module_Name", "Example_Module_Function_Name") == 'Software')
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_type_for_function_for_domain {RESET}")
        
        condition = bool(reader.get_asil_for_function_for_domain("Example_System_Name", "Example_Module_Name", "Example_Module_Function_Name") == 'ASIL D')
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_asil_for_function_for_domain {RESET}")
        
        condition = bool(reader.get_schematic_id_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")=="AA$AA")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_schematic_id_for_ae {RESET}")

        condition = bool(reader.get_arch_id_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")=="{5AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_ae {RESET}")

        condition = bool(reader.get_system_function_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")=="Example_AE_Customer_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_system_function_of_ae {RESET}")

        condition = bool(reader.get_color_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")=="0xFFFFFF")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_color_of_ae {RESET}")

        condition = bool(reader.get_block_type_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")=="TEST_BLOCK")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_block_type_of_ae {RESET}")

        condition = bool(reader.get_power_modes_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")==["Example_AE_Power_Mode", "Example_Other_AE_Power_Mode"])
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_power_modes_of_ae {RESET}")

        condition = bool(reader.get_class_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")=="Example_AE_Class")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_class_of_ae {RESET}")

        condition = bool(reader.get_variants_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")==["Example_Variant_A", "Example_Variant_B"])
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_variants_of_ae {RESET}")

        condition = (reader.get_functions_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")["AE Function Name"]=="Example_AE_Function_Name").bool()
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_functions_for_ae {RESET}")

        condition = bool(reader.get_function_names_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")[0]=="Example_AE_Function_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_functions_for_ae {RESET}")

        condition = bool(reader.get_arch_id_for_function_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Function_Name") == "{9AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_function_for_ae {RESET}")

        condition = bool(reader.get_type_for_function_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Function_Name") == "Hardware")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_type_for_function_for_ae {RESET}")
        
        condition = bool(reader.get_asil_for_function_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Function_Name") == "ASIL D")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_asil_for_function_for_ae {RESET}")

        condition = bool(reader.get_states_for_function_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Function_Name") == ["Example_AE_Function_State", "Example_Other_AE_Function_State"])
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_states_for_function_for_ae {RESET}")   

        condition = bool(reader.get_name_of_element_with_schematic_id("AA$AA")=="Example_Architectural_Element_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_name_of_element_with_schematic_id {RESET}")

        condition = bool(reader.get_name_of_element_with_arch_id("{5AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")=="Example_Architectural_Element_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_name_of_element_with_arch_id {RESET}")

        condition =  bool(reader.get_schematic_id_for_element_with_arch_id("{5AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")=="AA$AA")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_schematic_id_for_element_with_arch_id {RESET}")

        condition = bool(reader.get_arch_id_for_element_with_schematic_id("AA$AA")=="{5AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_element_with_schematic_id {RESET}")

        ## Test get_pins_for_ae: Incomplete test coverage - deepen test if necessary
        condition = bool(reader.get_pins_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")["AE Port Name"][0] == "Example_AE_Port_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_pins_for_ae {RESET}")

        condition = bool(reader.get_pin_names_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")[0] == "Example_AE_Port_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_pins_for_ae {RESET}")

        # ## Test get_pins_for_ae_without_type: Incomplete test coverage - deepen test if necessary
        # condition = bool("Pin Schematic Unique Identifier"==reader.get_pins_for_ae_without_type("Architectural Element Name")["Pin Name"][0])
        # if condition == True:
        #     passed_counter = passed_counter + 1
        # else:
        #     failed_counter = failed_counter + 1
        # print(f"{GREEN if condition else RED} Test get_pins_for_ae_without_type {RESET}")
        
        ## Test get_pins_of_type_for_ae: Incomplete test coverage - deepen test if necessary
        condition = bool(reader.get_pins_of_type_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Interface")["AE Port Name"][0] == "Example_AE_Port_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_pins_of_type_for_ae {RESET}")

        condition = bool(reader.get_pin_names_of_type_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Interface")[0] == "Example_AE_Port_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_pin_names_of_type_for_ae {RESET}")

        condition = bool(reader.get_schematic_id_for_pin_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name")=="AP$PP")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_schematic_id_for_pin_of_ae {RESET}")

        condition = bool(reader.get_arch_id_for_pin_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name")=="{6AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_pin_for_ae{RESET}")

        condition = bool(reader.get_direction_for_pin_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name")=="in")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_direction_for_pin_for_ae{RESET}")

        condition = bool(reader.get_type_for_pin_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name")=="Interface")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_type_for_pin_for_ae{RESET}")

        condition = bool(reader.get_variants_for_pin_for_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name")==["Example_Variant_A", "Example_Variant_B"])
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_variants_for_pin_for_ae{RESET}")
        
        condition = bool(reader.get_net_names_for_pin_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name")[0]=="Example_Con_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_net_names_for_pin_of_ae{RESET}")

        ## Test get_nets_for_pin_of_ae: Incomplete test coverage - deepen test if necessary
        condition = bool(reader.get_nets_for_pin_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name")["Con Name"][0]=="Example_Con_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_nets_for_pin_of_ae {RESET}")

        condition = bool(reader.get_schematic_id_for_net_of_pin_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name", "Example_Con_Name")=="CC$CC")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_schematic_id_for_net_of_pin_of_ae {RESET}")

        condition = bool(reader.get_arch_id_for_net_of_pin_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name", "Example_Con_Name")[0]=="{7AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_for_net_of_pin_of_ae {RESET}")
        
        condition = bool(reader.get_connected_ports_arch_ids_for_net_of_pin_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name", "Example_Con_Name")[0]=="{6AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_connected_ports_arch_ids_for_net_of_pin_of_ae {RESET}")

        condition = bool(reader.get_connected_port_name_for_net_of_pin_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name", "Example_Con_Name")[0]=="Example_AE_Port_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_connected_port_name_for_net_of_pin_of_ae {RESET}")

        condition = bool(reader.get_connected_ports_scm_ids_for_net_of_pin_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name", "Example_Con_Name")[0]=="PC$CC")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_connected_ports_scm_ids_for_net_of_pin_of_ae {RESET}")

        condition = bool(reader.get_type_for_net_of_pin_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Port_Name", "Example_Con_Name")=="Bus")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_type_for_net_of_pin_of_ae {RESET}")       

        condition = bool(reader.get_arch_id_of_pin_parent("{6AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")=="{5AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA}")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_arch_id_of_pin_parent {RESET}")      

        condition = bool(reader.get_names_of_blocks_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name")[0]=="Example_AE_Block_Name")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_names_of_blocks_of_ae {RESET}")

        condition = bool(reader.get_schematic_id_for_block_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Block_Name")=="BB$BB")
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_schematic_id_for_block_of_ae {RESET}")

        condition = bool(reader.get_variants_for_block_of_ae("Example_System_Name", "Example_Module_Name", "Example_Architectural_Element_Name", "Example_AE_Block_Name")==["Example_Variant_A", "Example_Variant_B"])
        if condition == True:
            passed_counter = passed_counter + 1
        else:
            failed_counter = failed_counter + 1
        print(f"{GREEN if condition else RED} Test get_variants_for_block_of_ae {RESET}")

        # Belongs to checker
        # ## Call replacement command before checking outcome
        # reader.replace_empty_net_names_with_undefined()
        # condition = bool(reader.get_name_of_element_with_schematic_id("Connector 3 Schematic Unique Identifier")=="Undefined")
        # if condition == True:
        #     passed_counter = passed_counter + 1
        # else:
        #     failed_counter = failed_counter + 1
        # print(f"{GREEN if condition else RED} Test replace_empty_net_names_with_undefined{RESET}")

        #  ## Load file again to reset empty names and call replacement command before checking outcome
        # reader = ArchJsonReader(json_file_test_path)
        # reader.generate_net_names_based_on_port_names()
        # condition = bool(reader.get_name_of_element_with_schematic_id("Connector 3 Schematic Unique Identifier")=="Link Name 2")
        # if condition == True:
        #     passed_counter = passed_counter + 1
        # else:
        #     failed_counter = failed_counter + 1
        # print(f"{GREEN if condition else RED} Test generate_net_names_based_on_port_names {RESET}")
        
        # condition = bool(not(reader.check_uniqueness_of_ae_names_over_domains()))
        # if condition == True:
        #     passed_counter = passed_counter + 1
        # else:
        #     failed_counter = failed_counter + 1
        # print(f"{GREEN if condition else RED} Test check_uniqueness_of_ae_names_over_domains {RESET}")

        condition = bool(failed_counter==0)
        print(f"{GREEN if condition else RED}", "Passed", passed_counter, "of", passed_counter+failed_counter, "Tests.", f"{RESET}")


if __name__ == "__main__":
    tester = arch_json_reader_tester("arch_export_format.json")
