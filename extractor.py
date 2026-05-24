"""Module for extracting Japanese string sequences from PSP binary files."""

import json
import re
import struct
import os

INFILES = ["DAT", "MSN", "UI"]


def analyse_header(filepath):
    """Analyses the 16-byte header of the binary file."""
    with open(filepath, "rb") as file:
        header_data = file.read(16)

        # struct.unpack decodes the raw binary.
        # '<' means Little-Endian.
        # 'IIII' means we are expecting four 32-bit Integers (4 bytes each).
        item_count, data_offset, block_count, _ = struct.unpack("<IIII", header_data)

        print("--- DAT.BIN HEADER ANALYSIS ---")
        print(f"Total Items: {item_count}")
        print(f"Data Starts At: {hex(data_offset)} (Hex) / {data_offset} (Decimal)")
        print(f"Block Count: {block_count}")


def parse_pointer_table(infile_path):
    """Parses the pointer table to map out subfile locations."""
    file_directory = {}

    with open(infile_path, "rb") as file:
        header_data = file.read(16)
        item_count, _, _, _ = struct.unpack("<IIII", header_data)

        for i in range(item_count):
            pointer_data = file.read(24)
            offset, file_size, original_id, compression_flag, _, _ = struct.unpack(
                "<IIIIII", pointer_data
            )

            file_num = str(i).zfill(3)
            file_directory[f"FILE_{file_num}"] = {
                "offset": offset,
                "file_size": file_size,
                "original_id": original_id,
                "compression_flag": compression_flag,
            }

    return file_directory


def create_json(filepath: str, data: dict):
    """Saves a dictionary to a JSON file with UTF-8 encoding."""
    with open(filepath, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file)


def extract_subfiles(infile_name: str, subfile_information: dict):
    infile_path = f"target_files/{infile_name}.BIN"

    print(f"Extracting from: {infile_path}")

    """Extracts subfiles from a main BIN file based on pointer data."""
    with open(infile_path, "rb") as bin_file:
        counter = 0
        for key, value in subfile_information.items():
            offset = value["offset"]
            file_size = value["file_size"]

            bin_file.seek(offset)
            subfile_data = bin_file.read(file_size)

            create_dir_if_needed(f"extracted_iso/{infile_name}/")
            with open(f"extracted_iso/{infile_name}/{key}.bin", "wb") as outfile:
                outfile.write(subfile_data)
            
            counter += 1

    print(f"\t Files extracted: {counter}")

def parse_binary(infile_path: str):
    """Scans binary data for Shift-JIS and ASCII string sequences."""
    string_locations = {}
    current_word = bytearray()
    start_offset = 0

    with open(infile_path, "rb") as file:
        data = file.read()

    idx = 0
    current_length = 0
    while idx < len(data):
        byte = data[idx]

        # If the byte is in japanese
        if (0x81 <= byte <= 0x9F) or (0xE0 <= byte <= 0xFC):
            # append entire japanese char
            if idx + 1 < len(data):
                current_word.append(byte)
                current_word.append(data[idx + 1])
            if current_length == 0:
                start_offset = idx
            current_length += 1
            idx += 2
            continue

        # If the byte is in english ASCII
        if 0x20 <= byte <= 0x7E:
            current_word.append(byte)
            if current_length == 0:
                start_offset = idx
            current_length += 1

        # If not a relevant char, reset variables
        else:
            if current_length > 3:
                try:
                    decoded_text = current_word.decode("shift_jis")
                    string_locations[start_offset] = {
                        "word_length": current_length,
                        "text": decoded_text,
                    }

                except UnicodeDecodeError:
                    pass

            current_word = bytearray()
            current_length = 0

        idx += 1

    return string_locations


def parse_ui():
    """Identifies the range of actual Japanese text in the UI JSON file."""
    with open(
        "extracted_letter_sequences/text_UI.json", "r", encoding="utf-8"
    ) as json_file:
        data = json.load(json_file)

        items = list(data.items())
        last_good_index = 0

    for i, (_, val) in enumerate(items):
        text = val.get("text", "")
        if re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]", text):
            last_good_index = i

    print(f"Total items in file: {len(items)}")
    print(f"The last Japanese character appears at list index: {last_good_index}")
    print(
        f"You only need to translate up to index: {last_good_index + 100} (adding a small buffer)"
    )

# Create a directory from a str, desired directory must be in the allowed strings list for error mitigation (if wanted)
def create_dir_if_needed(directory: str, allowed_strings: list = None):
    if allowed_strings:
        if directory in allowed_strings:
            if not os.path.exists(directory):
                os.mkdir(directory)
    else:
        if not os.path.exists(directory):
            os.mkdir(directory)
        
        


if __name__ == "__main__":
    for filename in INFILES:
        locations = parse_binary(f"target_files/{filename}.BIN")
        create_dir_if_needed("extracted_letter_sequences/")
        create_json(f"extracted_letter_sequences/text_{filename}.json", locations)
    parse_ui()

    for infile in INFILES:
        pointer_data = parse_pointer_table(f"target_files/{infile}.BIN")
        extract_subfiles(infile, pointer_data)
