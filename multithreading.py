import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json
import time
import math
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
INFILES = ["MSN", "DAT", "UI"]
MODEL = ""
MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.1-pro-preview"]
MAX_WORKERS = 10  # Number of simultaneous API calls. Adjust based on your rate limits.
CHUNK_SIZE = 600

# Threading lock for safe writes to the master dictionary and output file
file_lock = threading.Lock()

SYSTEM_INSTRUCTION = """
You are the lead localization engineer translating the PSP game 'Kingdom Ikkitousen no Tsurugi' (based on the anime/manga) from Japanese to English.

CRITICAL LORE RULES:
You MUST use the Japanese Romaji names for all characters, places, and ranks (e.g., use 'Shin', 'Ei Sei', 'Ouki', 'Heki'). DO NOT use the historical Chinese/Pinyin names (e.g., do not use 'Xin', 'Ying Zheng', 'Wang Qi').

CRITICAL TECHNICAL RULES:
1. I am providing a JSON dictionary of memory offsets and Japanese text.
2. Translate the text into natural, punchy English suitable for a PSP screen. Keep UI and menu terms very short.
3. DO NOT change the JSON keys (the memory offset numbers).
4. Preserve all invisible engine control codes exactly as they are at the very end of your translated string (e.g., PLY0澣a or Objectivei).
5. You MUST return ONLY a single JSON Object (Dictionary). DO NOT return a JSON List or Array.

STRICT FORMATTING TEMPLATE:
Your output must perfectly match this dictionary structure:
{
    "12345": {
        "word_length": 4,
        "text": "[Translated English Text Here]"
    },
    "67890": {
        "word_length": 8,
        "text": "[Translated English Text Here]"
    }
}
"""

def find_infile():
    global INFILE, CHOSEN_FILE, OUTFILE

    options = "\n".join(f"\t{i}. {file}" for i, file in enumerate(INFILES, start=1))
    print(f"Which of the following files would you like to translate?")
    os.makedirs("gemini_translations", exist_ok=True)
    
    while True:
        user_choice = input(f"{options}\nChoice: ")
        try:
            user_choice = int(user_choice)
            if user_choice in range(1, len(INFILES) + 1):
                CHOSEN_FILE = INFILES[user_choice - 1]
                INFILE = f"extracted_letter_sequences/text_{CHOSEN_FILE}.json"
                OUTFILE = f"gemini_translations/{CHOSEN_FILE}.json"
                break
        except ValueError:
            pass
        print(f"Please only enter an integer in the range 1-{len(INFILES)}.")

def choose_model():
    global MODEL
    print("\nChoose your model:")
    for i, m in enumerate(MODELS):
        print(f"\t{i + 1}: {m}")

    while True:
        try:
            user_choice = input(f"Choice (1-{len(MODELS)}): ")
            idx = int(user_choice) - 1
            if idx in range(len(MODELS)):
                candidate = MODELS[idx]
                confirm = input(f'You are choosing "{candidate}" are you sure (Y/N): ').lower()
                if confirm == 'y':
                    MODEL = candidate
                    break
                elif confirm == 'n':
                    continue
            print(f"Only enter an integer from 1-{len(MODELS)}")
        except ValueError:
            print(f"Only enter an integer from 1-{len(MODELS)}")

def process_chunk(client, model, chunk_slice, master_dict, outfile, iteration_id, total_iterations):
    """Worker function for a single API call."""
    chunk_string = json.dumps(dict(chunk_slice), ensure_ascii=False)
    max_retries = 30
    attempt = 0
    
    while attempt <= max_retries:
        try:
            # print(f"Querying Gemini for chunk {iteration_id}...")
            response = client.models.generate_content(
                model=model,
                contents=chunk_string,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )

            translated_chunk = json.loads(response.text)

            if not isinstance(translated_chunk, dict):
                raise ValueError(f"Model returned {type(translated_chunk).__name__} instead of dict")

            # Update master dict and save file safely
            with file_lock:
                master_dict.update(translated_chunk)
                with open(outfile, "w", encoding="utf-8") as fp:
                    json.dump(master_dict, fp, indent=4, ensure_ascii=False)
            
            return True, iteration_id
        
        except Exception as e:
            attempt += 1
            if attempt > max_retries:
                return False, iteration_id
            time.sleep(5)

def translate_json(input_json, api_key):
    client = genai.Client(api_key=api_key)
    
    # Read data
    with open(input_json, "r", encoding="utf-8") as fp:
        all_data = json.load(fp)
    
    address_list = list(all_data.items())
    
    # UI Filtering logic
    if CHOSEN_FILE == "UI":
        japanese_regex = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]')
        address_list = [(k, v) for k, v in address_list if japanese_regex.search(v.get("text", ""))]
        print(f"Filtered UI file to {len(address_list)} Japanese lines.")

    # Load existing progress
    master_english_dict = {}
    if os.path.exists(OUTFILE) and os.path.getsize(OUTFILE) > 0:
        with open(OUTFILE, "r", encoding="UTF-8") as fp:
            master_english_dict = json.load(fp)
        
        print(f"Found {len(master_english_dict)} existing translations.")
        choice = input("1. Resume (Skip existing keys)\n2. Start Over\nChoice: ")
        if choice == "2":
            master_english_dict = {}
            open(OUTFILE, 'w').close()

    # Filter out already translated keys
    remaining_list = [(k, v) for k, v in address_list if k not in master_english_dict]
    
    if not remaining_list:
        print("Everything is already translated!")
        return

    # Split into chunks
    chunks = [remaining_list[i:i + CHUNK_SIZE] for i in range(0, len(remaining_list), CHUNK_SIZE)]
    num_iterations = len(chunks)
    print(f"Processing {num_iterations} chunks with {MAX_WORKERS} workers...")

    # Statistics tracking
    completed_count = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all work
        futures = {executor.submit(process_chunk, client, MODEL, chunk, master_english_dict, OUTFILE, i+1, num_iterations): i for i, chunk in enumerate(chunks)}
        
        for future in as_completed(futures):
            success, iter_id = future.result()
            completed_count += 1
            
            # Progress calculation
            percent = (completed_count / num_iterations) * 100
            elapsed = time.time() - start_time
            avg_per_chunk = elapsed / completed_count
            remaining_chunks = num_iterations - completed_count
            eta_secs = remaining_chunks * avg_per_chunk
            mins, secs = divmod(int(eta_secs), 60)
            
            bar_length = 20
            filled = int(bar_length * completed_count // num_iterations)
            bar = '█' * filled + '-' * (bar_length - filled)
            
            print(f"\rProgress: [{bar}] {percent:.1f}% | Completed: {completed_count}/{num_iterations} | ETA: {mins}m {secs}s", end="")

    print(f"\n\n--- JAP->ENG TRANSLATION COMPLETED ---")

if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env")
        exit(1)

    find_infile()
    choose_model()
    translate_json(INFILE, api_key)
