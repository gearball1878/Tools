# ********************************************************************************************************************
#   ZZZZZZZZZZ   FFFFFFFFFF
#   ZZZZZZZZZZ   FFFFFFFFFF
#         ZZZ    FFF
#        ZZZ     FFF
#       ZZZ      FFFFFFFF
#      ZZZ       FFFFFFFF
#     ZZZ        FFF
#    ZZZ         FFF
#   ZZZZZZZZZZ   FFF
#   ZZZZZZZZZZ   FFF          FRIEDRICHSHAFEN AG
#   ******************************************************************************************************************
#   scope                      Generate Bus Signals from JSON-File Template with GUI BC_Wizard
#   \file                      BusGenerator.py
#   \author                    Christian Hopper
#   \date                      2024-04-04
#   \version                   0.00
#   \brief                     Generate Bus Signals from JSON-File Template with GUI BC_Wizard
# ********************************************************************************************************************
import sys
# from PySide6.QtWidgets import QApplication, QMainWindow
# from BC_Wizard import Ui_MainWindow

import json
from ParseBCFile import *
import re

# constants
powersignals = "Power_Signals"

class BusGenerator:
    def __init__(self, bc_file_path, json_file_path):
        self.bc_file_path = bc_file_path
        self.json_file_path = json_file_path
        self.interface_data = None
        self.third_level_keys = None
        self.first_level_keys = None
        self.name_already_exists = False
        self.already_generated_signals = ""
        self.new_signal = ""

    @staticmethod
    def extract_first_level_keys(obj):
        return list(obj.keys())

    @staticmethod
    def extract_second_level_keys(obj):
        keys = []
        for value in obj.values():
            if isinstance(value, dict):
                keys.extend(value.keys())
        return keys

    @staticmethod
    def extract_third_level_keys(obj):
        # Ensure obj is a dictionary
        if isinstance(obj, dict):
            # Extract third level keys
            return list(obj.keys())
        else:
            # Return an empty list if obj is None or not a dictionary
            return []

    def return_keys_of_json_file(self, prime_key):
        try:
            with open(self.json_file_path, "r") as file:
                json_data = json.load(file)
                # Extract second level keys
                prime_keys = self.extract_first_level_keys(json_data[prime_key])  # Use prime_key here
                secondary_keys = self.extract_second_level_keys(json_data[prime_key])  # Use prime_key here
                # print(list(keys))

                # for key in keys:
                    # next_level_keys = json_data[prime_key][key].keys()  # Use prime_key here
                    # print(f"Next level keys for {key}: {list(next_level_keys)}")
        except FileNotFoundError:
            print("The specified JSON file does not exist.")
        except IOError as e:
            print("An error occurred while reading the JSON file:", e)

        return list(prime_keys), list(secondary_keys)

    def GenInterfaces(self, interface_type, start_index, amount, link_or_port):

        try:
            with open(self.json_file_path, "r") as file:
                json_data = json.load(file)
                # Check if interface_type exists in json_data["Interface_Temp"]
                if interface_type in json_data["Interface_Temp"]:
                    self.interface_data = json_data["Interface_Temp"][interface_type]
                    # Extract third level keys for the specified second level key
                    self.third_level_keys = self.extract_third_level_keys(self.interface_data)
                    # if third_level_keys:
                    #     print(third_level_keys)
                    # else:
                    #     print(f"No third level keys found for interface type '{interface_type}'.")
                else:
                    print(f"No data found for interface type '{interface_type}'.")

        except FileNotFoundError:
            print("The specified JSON file does not exist.")
        except IOError as e:
            print("An error occurred while reading the JSON file:", e)

        # generate new busses with indices
        data = []
        for index in range(start_index, start_index + amount):
            string = ""
            bus = ""
            i = 0
            if link_or_port == "Link":
                bus = interface_type.replace("[Link/Port]", f"Link_{index}")
            elif link_or_port == "Port":
                bus = interface_type.replace("[Link/Port]", f"Port_{index}")

            string = f"{bus} "

            for i, signal_name in enumerate(self.third_level_keys):
                if link_or_port == "Link":
                    string += signal_name.replace("[Link/Port]", f"Link_{index}")
                    # data.append(signal_name.replace("[Link/Port]", f"Link_{index}"))
                elif link_or_port == "Port":
                    string += signal_name.replace("[Link/Port]", f"Port_{index}")
                    # data.append(signal_name.replace("[Link/Port]", f"Port_{index}"))

                if i < len(self.third_level_keys) - 1:
                    string += ","

            data.append(string)

        return data

    def GenControlStatus(self, ctrl_status_bus, signal_type, sensitivity, voltage_level, additional_info, already_generated_signals):

        bus = ""
        self.ctrl_status_bus = ParseBCFile(self.bc_file_path, ctrl_status_bus, None).search_instances_of_selected_bus()[1]
        self.ctrl_status_bus_w_signals = ParseBCFile(self.bc_file_path, ctrl_status_bus, None).search_instances_of_selected_bus()[2]

        if "Wireless" not in ctrl_status_bus:
            self.domain_info = ctrl_status_bus[:3]
        else:
            self.domain_info = "WL"

        if self.ctrl_status_bus == [] and already_generated_signals == []:
            bus = f"{ctrl_status_bus} {signal_type}{sensitivity}_{self.domain_info}_{additional_info}_{voltage_level}"
            self.new_signal = f"{signal_type}{sensitivity}_{self.domain_info}_{additional_info}_{voltage_level}"
        elif self.ctrl_status_bus == [] and already_generated_signals != []:
            append_string = f",{signal_type}{sensitivity}_{self.domain_info}_{additional_info}_{voltage_level}"
            self.new_signal = append_string.lstrip(",")
            already_generated_string = ""
            for item in already_generated_signals:
                already_generated_string += f"{item},"
            bus = f"{ctrl_status_bus} {already_generated_string}{self.new_signal}"

            self.ctrl_status_bus_w_signals += already_generated_signals

        else:
            bus = f"{self.ctrl_status_bus_w_signals[0]}"
            append_string = f",{signal_type}{sensitivity}_{self.domain_info}_{additional_info}_{voltage_level}"
            self.new_signal = append_string.lstrip(",")
            # print(self.new_signal)

            for item in already_generated_signals:
                # print(item)
                if item != self.new_signal:
                    bus += f",{item}"

            bus += append_string

            self.ctrl_status_bus_w_signals = self.ctrl_status_bus_w_signals[0].split(" ")
            self.ctrl_status_bus_w_signals = self.ctrl_status_bus_w_signals[1].split(",")

            self.ctrl_status_bus_w_signals += already_generated_signals

            # print(self.ctrl_status_bus_w_signals)

        for i, signal_name in enumerate(self.ctrl_status_bus_w_signals):
            if signal_name == self.new_signal:
                self.name_already_exists = True
                print(f"Signal name already exists for {signal_name}")
                break
                # bus = ""
            else:
                self.name_already_exists = False

        return bus, self.new_signal, self.name_already_exists

    def GenAnalog(self, analog_bus, signal_type, domain, differential, additional_info, frequency, already_generated_signals):

        try:
            with open(self.json_file_path, "r") as file:
                json_data = json.load(file)
                # print(json_data)
                # Check if interface_type exists in json_data["Interface_Temp"]
                if signal_type in json_data["Analog_Signal_Temp"]:
                    self.signal_data = json_data["Analog_Signal_Temp"][signal_type]
                    # Extract third level keys for the specified second level key
                    self.third_level_keys = self.extract_third_level_keys(self.signal_data)
                    # if self.third_level_keys:
                    #     print(self.third_level_keys)
                    # else:
                    #     print(f"No third level keys found for interface type '{signal_type}'.")
                else:
                    print(f"No data found for interface type {signal_type}")

        except FileNotFoundError:
            print("The specified JSON file does not exist.")
        except IOError as e:
            print("An error occurred while reading the JSON file:", e)

        new_signals=[]
        append_string = ""
        # string signal manipulation
        for i, signal_name in enumerate(self.third_level_keys):
            bussignal = signal_name.replace("[Domain]",f"{domain}_{additional_info}")
            bussignal = bussignal.replace("[frequency]",frequency)
            bussignal = bussignal.replace(".","_")
            append_string += f"{bussignal},"
            new_signals.append(bussignal)

        if differential == True:
            append_string = append_string.rstrip(",")
        else:
            append_string = new_signals[0][::-1].split("_", 1)[-1][::-1]
            new_signals = [append_string]

        # print(new_signals)

        self.analog_bus = ParseBCFile(self.bc_file_path, analog_bus, None).search_instances_of_selected_bus()[1]
        self.analog_bus_w_signals = ParseBCFile(self.bc_file_path, analog_bus, None).search_instances_of_selected_bus()[2]

        # print(self.analog_bus_w_signals)

        if self.analog_bus == [] and already_generated_signals == []:
            bus = f"{analog_bus} {append_string}"
        elif self.analog_bus == [] and already_generated_signals != []:
            already_generated_string = ""
            for item in already_generated_signals:
                already_generated_string += f"{item},"
            bus = f"{analog_bus} {already_generated_string}{append_string}"

            self.analog_bus_w_signals += already_generated_signals
        else:
            bus = f"{self.analog_bus_w_signals[0]}"
            bus += f",{append_string}"

            # for signal in new_signals:
            for item in already_generated_signals:
                bus += f",{item}"

            # print(bus)

            self.analog_bus_w_signals = self.analog_bus_w_signals[0].split(" ")
            self.analog_bus_w_signals = self.analog_bus_w_signals[1].split(",")

            self.analog_bus_w_signals += already_generated_signals

        for i in range(len(new_signals)):
            for signal_name in self.analog_bus_w_signals:
                if signal_name == new_signals[i]:
                    self.name_already_exists = True
                    print(f"Signal name already exists for {signal_name}")
                    break
                    # bus = ""
                else:
                    self.name_already_exists = False

        return bus, new_signals, self.name_already_exists

    def GenGlobalSignals(self, power_bus, voltage_type, domain, additional_info, voltage_level, already_generated_signals):
        self.power_bus = ParseBCFile(self.bc_file_path, power_bus, None).search_instances_of_selected_bus()[1]
        self.power_bus_w_signals = ParseBCFile(self.bc_file_path, power_bus, None).search_instances_of_selected_bus()[2]

        if self.power_bus == [] and already_generated_signals == []:
            bus = f"{power_bus} {voltage_type}_{domain}_{additional_info}_{voltage_level}"
            self.new_signal = f"{voltage_type}_{domain}_{additional_info}_{voltage_level}"
        elif self.power_bus == [] and already_generated_signals != []:
            append_string = f",{voltage_type}_{domain}_{additional_info}_{voltage_level}"
            self.new_signal = append_string.lstrip(",")
            already_generated_string = ""
            for item in already_generated_signals:
                already_generated_string += f"{item},"
            bus = f"{power_bus} {already_generated_string}{self.new_signal}"

            self.power_bus_w_signals += already_generated_signals

        else:
            bus = f"{self.power_bus_w_signals[0]}"
            append_string = f",{voltage_type}_{domain}_{additional_info}_{voltage_level}"
            self.new_signal = append_string.lstrip(",")
            # print(self.new_signal)

            for item in already_generated_signals:
                # print(item)
                if item != self.new_signal:
                    bus += f",{item}"

            bus += append_string

            self.power_bus_w_signals = self.power_bus_w_signals[0].split(" ")
            self.power_bus_w_signals = self.power_bus_w_signals[1].split(",")

            self.power_bus_w_signals += already_generated_signals

            for i, signal_name in enumerate(self.power_bus_w_signals):
                # print(signal_name)
                # print(bus)
                if signal_name == self.new_signal:
                    self.name_already_exists = True
                    print(f"Signal name already exists for {signal_name}")
                    break
                    # bus = ""
                else:
                    self.name_already_exists = False

        return bus, self.new_signal, self.name_already_exists

    def GenMemInterfaces(self, num_devices, technology, subtechnology, device_config, domain, additional_info, already_generated_interfaces):
        self.new_mem_bus_core_name = []
        self.already_generated_interfaces_core_name = []
        self.new_mem_bus_master_name = f"{subtechnology}_{domain}_{additional_info}"
        self.memory_bus = ParseBCFile(self.bc_file_path, self.new_mem_bus_master_name, None).search_instances_of_selected_bus()[1]
        # print(self.memory_bus)

        for i in range(len(self.memory_bus)):
            self.new_mem_bus_core_name.append(re.sub(r'_DEV\d+', '', self.memory_bus[i]))

        for i in range(len(already_generated_interfaces)):
            self.already_generated_interfaces_core_name.append(re.sub(r'_DEV\d+', '', already_generated_interfaces[i]))

        try:
            with open(self.json_file_path, "r") as file:
                json_data = json.load(file)
                # Check if technology exists in json_data["Memory_Interface_Temp"]
                if subtechnology in json_data["Memory_Interface_Temp"][technology]:
                    self.memory_interface_data = json_data["Memory_Interface_Temp"][technology][subtechnology]
                    # Extract third level keys for the specified second level key
                    self.first_level_keys = self.extract_first_level_keys(self.memory_interface_data)
                    # if self.first_level_keys:
                    #     print(self.first_level_keys)
                    # else:
                    #     print(f"No third level keys found for memory interface type '{subtechnology}'.")
                else:
                    print(f"No data found for interface type '{subtechnology}'.")

        except FileNotFoundError:
            print("The specified JSON file does not exist.")
        except IOError as e:
            print("An error occurred while reading the JSON file:", e)

        if technology == "DRAM":
            if "Single-Channel" in device_config:
                self.channels = 1
            elif "Dual-Channel" in device_config:
                self.channels = 2
            elif "Quad-Channel" in device_config:
                self.channels = 4
            else:
                self.channels = 0

            data = []
            if num_devices > 1:
                for k in range(num_devices):
                    string = f"{subtechnology}_{domain}_{additional_info}_DEV{k+1} "
                    for j in range(self.channels):
                        for i, signal_name in enumerate(self.first_level_keys):
                            string += f"{subtechnology}_{domain}_{additional_info}_DEV{k+1}_CH{j+1}_{signal_name},"

                        string = string.rstrip(",")

                    data.append(string)
            else:
                string = f"{subtechnology}_{domain}_{additional_info} "
                for j in range(self.channels):
                    for i, signal_name in enumerate(self.first_level_keys):
                        string += f"{subtechnology}_{domain}_{additional_info}_CH{j+1}_{signal_name},"

                    string = string.rstrip(",")

                data.append(string)

        elif technology == "Flash":

            data = []
            if num_devices > 1:
                for k in range(num_devices):
                    string = f"{subtechnology}_{domain}_{additional_info}_DEV{k+1} "
                    for i, signal_name in enumerate(self.first_level_keys):
                        string += f"{subtechnology}_{domain}_{additional_info}_DEV{k+1}_{signal_name},"

                    string = string.rstrip(",")

                    data.append(string)
            else:
                string = f"{subtechnology}_{domain}_{additional_info} "
                for i, signal_name in enumerate(self.first_level_keys):
                    string += f"{subtechnology}_{domain}_{additional_info}_{signal_name},"

                string = string.rstrip(",")
                data.append(string)

        for i in range(len(already_generated_interfaces)):
            self.new_mem_bus_core_name.append(self.already_generated_interfaces_core_name[i])
            self.memory_bus.append(already_generated_interfaces[i])

        # print(self.memory_bus)

        self.existing_no_of_instances = 0
        for i, bus in enumerate(self.new_mem_bus_core_name):
            # print(bus)
            if bus == self.new_mem_bus_master_name:
                self.name_already_exists = True
                print(f"{self.memory_bus[i]} already exists!")
                self.existing_no_of_instances = i + 1
                # break
        else:
            if self.existing_no_of_instances == 0:
                self.name_already_exists = False

        # print(self.existing_no_of_instances)

        return data, self.new_mem_bus_master_name, self.existing_no_of_instances, self.name_already_exists


if __name__ == "__main__":
    new_busses = BusGenerator(r"C:\test_data\Xpedition_BC_wizard\busconts.ini", r"M:\Mentor_Xpedition\xpedition\Designer_Automation\config\Interface_Template_File.json").GenInterfaces("UART_[Link/Port]", 2, 5,  "Link")
    # def GenControlStatus(self, ctrl_status_bus, signal_type, senitivity, voltage_level, additional_info):
    # new_control_status_bus = BusGenerator().GenControlStatus("PSU_Control","EN", "", "3V3", "AURIX_231",  ['arsch'])
    # new_powerbus = BusGenerator().GenGlobalSignals(powersignals, "VCC", "ETH", "88Q5052", "1V8", ['a', 'b'])
    # new_analog_bus = BusGenerator().GenAnalog("Clock_Signals","CLK_XTAL", "Control", True, "AURIX_1", "25MHz", ['CLK_XTAL_25MHz_Control_AURIX_1_P', 'CLK_XTAL_25MHz_Control_AURIX_1_N'])
    # new_memory_interface = BusGenerator(r"C:\test_data\Xpedition_BC_wizard\busconts.ini", r"M:\Mentor_Xpedition\xpedition\Designer_Automation\config\Interface_Template_File.json").GenMemInterfaces(4,"DRAM","LPDDR3","Quad-Die, Single-Channel", "PSOC", "ORIN", [])

    # return_keys = BusGenerator().return_keys_of_json_file("Memory_Interface_Temp")

    print(new_busses)
    # for i in range(len(new_memory_interface)):
    #     print(new_memory_interface[i])