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
            
            file_num = str(i).zfill(3)
            file_directory.update({f"FILE_{file_num}" :{"offset": offset, "file_size": file_size, "original_id": original_id, "compression_flag": compression_flag}})

        # print(file_directory)
    return file_directory

# Create JSON file with file data
def create_json(filepath: str, data: dict):
    with open(f"{filepath}", 'w') as j:
        json.dump(data, j)


def extract_subfiles(infile: str, subfile_infomation: dict):
    with open(infile, "rb") as infile:
        for key, value in subfile_infomation.items():
            
            # Get file offset & size
            offset = value["offset"]
                #print(offset)
            file_size = value["file_size"]
                #print(file_size)

            # Get file data
            infile.seek(offset)
            subfile_data = infile.read(file_size)
        
            with open(f"extracted_iso/{key}.bin", "wb") as outfile:
                outfile.write(subfile_data)



# Run the function
if __name__ == "__main__":
    file_information = parse_pointer_table('target_files/DAT.BIN')
    create_json("DAT_info.json", file_information)
    extract_subfiles("target_files/DAT.BIN", file_information)