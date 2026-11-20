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
#   scope                      Parse busconts.ini to check against existing signals and busses
#   \file                      ParseBCFile.py
#   \author                    Christian Hopper
#   \date                      2024-04-08
#   \version                   0.00
#   \brief                     Parse busconts.ini to check new busses against existing signals and busses
# ********************************************************************************************************************
import sys
# from PySide6.QtWidgets import QApplication, QMainWindow
# from BC_Wizard import Ui_MainWindow

import json
import re

class ParseBCFile:
    def __init__(self, bc_file_path, search_for_bus=None, search_for_signal=None):
        self.bc_file_path = bc_file_path
        self.search_for_bus = search_for_bus
        self.search_for_signal = search_for_signal
        # self.search_instances_of_selected_bus()

        # self.available_busses_BC_data()

    def available_busses_BC_data(self):
        data = []

        try:
            with open(self.bc_file_path, 'r') as file:
                lines = file.readlines()
                # print(lines)
                data = []  # Initialize an empty list to store bus names
                data_line = []
                for i, line in enumerate(lines):
                    line = line.strip()  # Strip trailing newline characters
                    bus_name = line.split(" ")[0]  # Extract bus name from line
                    data.append(bus_name)  # Append bus_name to the data list
                    data_line.append(line)

                    # print(f"{data[i]}")  # Print the current bus name
                # print(data)

                return data, data_line

        except FileNotFoundError:
            print("The specified file does not exist.")
        except IOError as e:
            print("An error occurred while reading the file:", e)

    def find_unused_integers(self, arr):
        # Sort the array
        arr.sort()

        unused_integers = []
        unique_elements = []

        for item in arr:
            if item not in unique_elements:
                unique_elements.append(item)

        # Initialize start index and end index
        start_index = unique_elements[0]
        end_index = unique_elements[0]

        for num in unique_elements[1:]:
            if num == end_index + 1:
                # Extend the range if the next number is consecutive
                end_index = num
            else:
                # If there is a gap, add the range of unused numbers to the result
                if start_index != end_index:
                    unused_integers.extend(range(end_index + 1, num))
                else:
                    unused_integers.append(start_index)
                start_index = num
                end_index = num

        # Check for any remaining unused numbers after the last element of the array
        if start_index != end_index:
            unused_integers.extend(range(end_index + 1, unique_elements[-1] + 1))

        return unused_integers

    @staticmethod
    def find_numbers_in_string(input_string):
        numbers_found_flat = '0'
        # Regular expression pattern to match numbers
        pattern = r'_\d+'

        # Using re.findall() to find all numbers in the string
        numbers_found = re.findall(pattern, input_string)
        if numbers_found != []:
            numbers_found_flat = numbers_found[0].replace("_", "")
            # print(numbers_found_flat)
        return numbers_found_flat

    def search_instances_of_selected_bus(self):
        search_result_list = []
        search_result_list_w_signals = []
        instance_numbers = []
        unused_integers = []
        all_busses = self.available_busses_BC_data()[0]
        all_busses_w_signals = self.available_busses_BC_data()[1]
        # print(all_busses_w_signals)
        search_string = self.search_for_bus
        for bus in all_busses:
            if search_string in bus:
                number = int(self.find_numbers_in_string(bus))
                instance_numbers.append(number)
                search_result_list.append(bus)
        for bus in all_busses_w_signals:
            if bus.startswith(search_string):
                search_result_list_w_signals.append(bus)

        if instance_numbers:
            max_number = max(instance_numbers)
            unused_integers = self.find_unused_integers(instance_numbers)
        else:
            max_number = 0


        return instance_numbers, search_result_list, search_result_list_w_signals, max_number, unused_integers

    def search_signals_in_bus(self):
        self.bus_signals = []



if __name__ == "__main__":
    search_results = ParseBCFile(r"C:\test_data\Xpedition_BC_wizard\busconts.ini","CAN_Link","").search_instances_of_selected_bus()
    print(search_results[0])
    print(search_results[1])
    print(search_results[2])
    print(search_results[3])
    # ParseBCFile()
    # print("Go")