"""Module for translating game JSON data using the Gemini API."""

import json
import math
import os
import re
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

INFILES = ["MSN", "DAT", "UI"]
MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
]


def find_infile():
    """Prompts the user to select which game file to translate."""
    options = "\n".join(f"\t{i}. {file}" for i, file in enumerate(INFILES, start=1))
    print("Which of the following files would you like to translate?")
    os.makedirs("gemini_translations", exist_ok=True)

    while True:
        user_choice = input(f"{options}\nChoice: ")

        try:
            idx = int(user_choice)
            if 1 <= idx <= len(INFILES):
                chosen_file = INFILES[idx - 1]
                infile = f"extracted_letter_sequences/text_{chosen_file}.json"
                outfile = f"gemini_translations/{chosen_file}.json"
                return chosen_file, infile, outfile
        except ValueError:
            pass
        print(f"Please only enter an integer in the range 1-{len(INFILES)}.")


def choose_model():
    """Prompts the user to select the Gemini model to use."""
    print("\nChoose your model:")
    for i, m in enumerate(MODELS):
        print(f"\t{i + 1}: {m}")

    while True:
        user_choice = input(f"Choice (1-{len(MODELS)}): ")
        try:
            idx = int(user_choice) - 1
            if 0 <= idx < len(MODELS):
                selected_model = MODELS[idx]
                confirm = input(
                    f'You are choosing "{selected_model}" are you sure (Y/N): '
                )
                if confirm.lower() == "y":
                    return selected_model
                if confirm.lower() == "n":
                    continue
        except ValueError:
            pass
        print(f"Only enter an integer from 1-{len(MODELS)}")


def handle_resume_logic(outfile_path, chunk_size):
    """Manages file tracking persistence and returns the starting index position."""
    start_index = 0
    master_english_dict = {}

    if os.path.exists(outfile_path) and os.path.getsize(outfile_path) > 0:
        with open(outfile_path, "r", encoding="utf-8") as fp:
            master_english_dict = json.load(fp)
            start_index = len(master_english_dict)
            prev_iters = int(start_index / chunk_size) + 1

            if start_index > 0:
                print(f"\nFound Progress: {start_index} (Iteration {prev_iters})")
                while True:
                    choice = input("1. Resume\n2. Start Over\nChoice: ")
                    if choice == "1":
                        break
                    if choice == "2":
                        start_index = 0
                        master_english_dict = {}
                        with open(outfile_path, "w", encoding="utf-8") as wipe_fp:
                            wipe_fp.write("{}")
                        break
                    print("Only enter '1' or '2'")
    return start_index, master_english_dict


# pylint: disable=inconsistent-return-statements
def process_chunk_with_retry(client, model, chunk_string, system_prompt):
    """Queries the Gemini API with a retry block on structural or API faults."""
    max_retries = 30
    attempt = 0

    while attempt <= max_retries:
        try:
            print("Querying Gemini...")
            response = client.models.generate_content(
                model=model,
                contents=chunk_string,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            translated_chunk = json.loads(response.text)
            if not isinstance(translated_chunk, dict):
                raise ValueError("Model did not return a dictionary")
            return translated_chunk

        except (APIError, json.JSONDecodeError, ValueError) as e:
            attempt += 1
            print(f"API or Parse error on attempt {attempt}: {e}")
            if attempt <= max_retries:
                time.sleep(5)
            else:
                raise e

# pylint: disable=too-many-locals
def translate_json(chosen_file, input_json_path, outfile_path, api_key, model):
    """Iterates through JSON chunks and translates them using the Gemini API."""
    client = genai.Client(api_key=api_key)

    with open(input_json_path, "r", encoding="utf-8") as fp:
        all_data = json.load(fp)
        print(f"\nLoaded Data from {input_json_path}")

    address_list = list(all_data.items())
    chunk_size = 600
    duration_history = []

    if chosen_file == "UI":
        print("\nUI File detected. Filtering out non-Japanese engine data...")
        japanese_regex = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]")
        address_list = [
            (k, v) for k, v in address_list if japanese_regex.search(v.get("text", ""))
        ]
        print(f"Reduced to {len(address_list)} Japanese lines!")

    num_iterations = math.ceil(len(address_list) / chunk_size)
    start_index, master_english_dict = handle_resume_logic(outfile_path, chunk_size)

    sys_instruction = """
        You are the lead localization engineer translating 'Kingdom Ikkitousen no Tsurugi'.
        CRITICAL LORE RULES: Use Japanese Romaji names (Shin, Ei Sei, Ouki).
        CRITICAL TECHNICAL RULES:
        1. I am providing a JSON dictionary.
        2. Translate to natural English.
        3. DO NOT change the JSON keys.
        4. Preserve engine control codes exactly.
        5. Return ONLY a single JSON Object.
    """

    for i in range(start_index, len(address_list), chunk_size):
        iter_num = int((i / chunk_size) + 1)
        print(f"\n---STARTING ITERATION {iter_num}/{num_iterations}---")
        iteration_start = time.time()

        chunk_slice = address_list[i : i + chunk_size]
        chunk_string = json.dumps(dict(chunk_slice), ensure_ascii=False)

        translated_chunk = process_chunk_with_retry(
            client, model, chunk_string, sys_instruction
        )

        master_english_dict.update(translated_chunk)
        with open(outfile_path, "w", encoding="utf-8") as fp:
            json.dump(master_english_dict, fp, indent=4, ensure_ascii=False)

        duration = time.time() - iteration_start
        duration_history.append(duration)
        avg_duration = sum(duration_history) / len(duration_history)
        remaining = num_iterations - iter_num
        percent = (iter_num / num_iterations) * 100
        eta_m, eta_s = divmod(int(remaining * avg_duration), 60)

        bar_fill = int(20 * iter_num // num_iterations)
        progress_bar = "█" * bar_fill + "-" * (20 - bar_fill)
        print(f"\rProgress: [{progress_bar}] {percent:.1f}% | ETA: {eta_m}m {eta_s}s")


if __name__ == "__main__":
    load_dotenv()
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("Error: GEMINI_API_KEY not found in .env")
    else:
        target_name, infile_path, outfile_dest = find_infile()
        selected_engine = choose_model()
        translate_json(
            target_name, infile_path, outfile_dest, gemini_api_key, selected_engine
        )
