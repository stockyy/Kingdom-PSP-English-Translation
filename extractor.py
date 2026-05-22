import struct
import json
import re

INFILES = ["DAT", "MSN", "UI"]

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
    with open(f"{filepath}", 'w', encoding="utf-8") as j:
        json.dump(data, j)

# NOT NEEDED - Was a funcation to extrcat subfiles from DAT.BIN, discovered to be unnecessary
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

def parse_binary(infile: str):
    string_locations = {}
    current_word = bytearray()
    start_offset = ""
    word_length = ""

    with open(infile, "rb") as fp:
        data = fp.read()
    
    i = 0
    current_length = 0
    while i < len(data):
        byte = data[i]

        # If the byte is in japanese
        if (byte >= 0x81 and byte <=0x9F) or (byte >= 0xE0 and byte <= 0xFC):
            # append entire japanese char
            if i+1 < len(data):
                current_word.append(byte)
                current_word.append(data[i+1])
            if current_length == 0:
                start_offset = i 
            current_length += 1
            i += 2
            continue

        # If the byte is in english ASCII
        elif (byte >= 0x20 and byte <= 0x7E):
            current_word.append(byte)
            if current_length == 0:
                start_offset = i 
            current_length += 1
        
        # If not a relevant char, reset variables 
        else:
            if current_length > 3:
                try:
                    decoded_text = current_word.decode("shift_jis")
                    string_locations[start_offset] = {"word_length": current_length, "text": decoded_text}
                
                except UnicodeDecodeError:
                    # It wasn't just text
                    pass
            
            current_word = bytearray()
            current_length = 0

        i += 1

    return string_locations
    # print(string_locations)

# Try to srtip out garbage data from the UI file
def parse_UI():
    with open("extracted_letter_sequences/text_UI.json") as fp:
        data = json.load(fp)

        items = list(data.items())
        last_good_index = 0
    
    # Scan every string for Japanese Hiragana, Katakana, or Kanji
    for i, (key, val) in enumerate(items):
        text = val.get("text", "")
        if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text):
            last_good_index = i

    print(f"Total items in file: {len(items)}")
    print(f"The last Japanese character appears at list index: {last_good_index}")
    print(f"You only need to translate up to index: {last_good_index + 100} (adding a small buffer)")

# Run the function
if __name__ == "__main__":
    for i in INFILES:
        string_locations = parse_binary(f"target_files/{i}.BIN")
        create_json(f"extracted_letter_sequences/text_{i}.json", string_locations)
    parse_UI()