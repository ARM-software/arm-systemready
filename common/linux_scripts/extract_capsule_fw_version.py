import chardet
import re
import sys

def extract_hex_value(file_path):
    # Regular expression to match 'FwVersion - 0x<hex_value>'
    pattern = sys.argv[1]

    # Detect file encoding using chardet
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding']

    try:
        # Read the file using the detected encoding
        with open(file_path, 'r', encoding=encoding) as file:
            lines = file.readlines()

        for line in lines:
            match = re.search(pattern, line)
            if match:
                return match.group(1)

    except UnicodeDecodeError:
        print(f"Error: Unable to decode the file {file_path} with detected encoding: {encoding}")
        return None

    return None

file_path = sys.argv[2]
hex_value = extract_hex_value(file_path)

# Print the result
if hex_value:
    print(hex_value)
else:
    print("No 'FwVersion' found in the file.")
