import json
try:
    import jsonschema
    from jsonschema import validate
except ImportError:  # The bridge itself intentionally has no jsonschema dependency.
    jsonschema = None
    validate = None

RED = '\033[91m'
RESET = '\033[0m'

class JSONValidator:

    def __init__(self, schema_path = "arch_export_format_json_schema.json", debug=False):
        self.debug = debug
        self.json_path = "load.json not called"
        # Load the JSON schema
        with open(schema_path, 'r') as schema_file:
            self.schema = json.load(schema_file)

    def load_json(self, json_path):
        self.json_path = json_path
        # Load the JSON data from the file
        with open(json_path, 'r') as data_file:
            self.json_data = json.load(data_file)

    def validate_json(self):
        if validate is None:
            if self.debug:
                print("[DEBUG] jsonschema is not installed; legacy schema validation skipped")
            return True
        # Validate the JSON data against the schema
        try:
            validate(instance=self.json_data, schema=self.schema)
            if self.debug: 
                print("[DEBUG] JSON data is valid for file:", self.json_path)
            return True
        except (jsonschema.exceptions.ValidationError, jsonschema.exceptions.SchemaError) as err:
            print(f"{RED}[ERROR]{RESET} JSON data is invalid for file", self.json_path)
            print("Error Message:", err.message)
            print("Error Path:", err.path)
            return False

if __name__ == "__main__":
    val = JSONValidator(debug = True)
    val.load_json("arch_export_format.json")
    val.validate_json()
