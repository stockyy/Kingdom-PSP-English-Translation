import os
import struct

INFILES = ["DAT", "MSN", "UI"]

def read_headers(directory):
    print(f"--- Getting header details for the files in {directory} ---")

    for file in os.scandir(directory):
        if file.is_file():
            with open(file, "rb") as fp:
                header_data = fp.read(16)
                magic_number, string_count, pointer_table_offset, string_data_offset = struct.unpack("<IIII", header_data)

                print(f"\t-- Headers for: {file}--")
                print(f"\t\tFirst 4 Bytes: {magic_number}")
                print(f"\t\tSecond 4 Bytes: {string_count}")
                print(f"\t\tThird 4 Bytes: {pointer_table_offset}")
                print(f"\t\tFourth 4 Bytes: {string_data_offset}\n")


if __name__ == "__main__":
    # Ensure the target file folder exists
    if not os.path.exists("target_files/"):
        print("Cannot find binary files ")

    for file in INFILES:
        read_headers(f"extracted_iso/{file}/")

        