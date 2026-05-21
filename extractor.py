import struct
import json

def analyse_header(filepath):
    # Open the file in raw binary mode
    with open(filepath, 'rb') as f:

        # Read the first 16 bytes of the file
        header_data = f.read(16)

        # struct.unpack decodes the raw binary. 
        # '<' means Little-Endian. 
        # 'IIII' means we are expecting four 32-bit Integers (4 bytes each).
        item_count, data_offset, block_count, unknown = struct.unpack('<IIII', header_data)

        print("--- DAT.BIN HEADER ANALYSIS ---")
        print(f"Total Items: {item_count}")
        print(f"Data Starts At: {hex(data_offset)} (Hex) / {data_offset} (Decimal)")
        print(f"Block Count: {block_count}")

def parse_pointer_table(infile):
    # Store results as a dictionary
    file_directory = {}

    with open(infile, 'rb') as f:
        # --- Read in header values ---
        # Read the first 16 bytes of the file
        header_data = f.read(16)
        item_count, data_offset, block_count, unknown = struct.unpack('<IIII', header_data)
        
        # Save pointer info to json
        for i in range(item_count):
            # Read pointer data & add to the dict 
            pointer_data = f.read(24)
            offset, file_size, original_id, compression_flag, unknown_1, unknown_2 = struct.unpack('<IIIIII', pointer_data)
            
            file_directory.update({f"FILE_{i}" :{"offset": offset, "file_size": file_size, "original_id": original_id, "compression_flag": compression_flag}})

        print(file_directory)
    return file_directory


# Run the function
if __name__ == "__main__":
    parse_pointer_table('target-files/DAT.BIN')