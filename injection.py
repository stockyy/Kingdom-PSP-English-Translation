import os
import struct

def read_headers(directory):
    print(f"--- Getting header details for the files in {directory} ---")

    for file in os.scandir(directory):
        if file.is_file():
            with open(file, "r") as fp:
                header_data = fp.read(16)
                magic_number, string_count, pointer_table_offset, string_data_offset = struct.unpack("<IIII", header_data)

                print(f"\n-- {file}--")
                print(f"\tFirst 4 Bytes: {magic_number}")
                print(f"\tSecond 4 Bytes: {string_count}")
                print(f"\tThird 4 Bytes: {pointer_table_offset}")
                print(f"\tFourth 4 Bytes: {string_data_offset}\n")


if __name__ == "__main__":
    # Ensure the target file folder exists
    if not os.path.exists("target_files/"):
        print("Cannot find binary files ")

    read_headers("target files/")
    read_headers("extracted_iso/USRDIR/")

        