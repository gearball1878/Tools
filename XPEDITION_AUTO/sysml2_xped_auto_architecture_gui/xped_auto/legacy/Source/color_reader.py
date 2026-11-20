import csv
import os

GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

def convert_list_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

def convert_hex_to_list(hex_color):
    if "#" in hex_color:
        hex_color = hex_color.lstrip('#')
    elif "0x" in hex_color:
        hex_color = hex_color.lstrip('0x')
    return list(str(int(hex_color[i:i+2], 16)) for i in (0, 2, 4))


class ColorReader:

    def __init__(self):
        file_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'color_code_importable.csv'))  # Replace with your CSV file path
        self.colors = {}
        self.read_csv(file_path)

    # Function to read a CSV file
    def read_csv(self, file_path):
        with open(file_path, mode='r') as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                self.colors[row[0]]= row[1:]

    def get_color(self, block_type, convert_to_hex=True):
        if block_type in list(self.colors.keys()):
            if not convert_to_hex:
                return self.colors(block_type)
            else:
                return convert_list_to_hex(self.colors[block_type])
        else:
            print(f"{RED}[ERROR]{RESET} Could not find color for block type", block_type)
            return None

    def get_block_type_from_color(self, color, as_hex=True):
        if color is None:
            return "unclassified"
        if as_hex:
            color = convert_hex_to_list(color)
        for block_type, color_per_block in self.colors.items():
            if color == color_per_block:
                return block_type
        return "unclassified"
