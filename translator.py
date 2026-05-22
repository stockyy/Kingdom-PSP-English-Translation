import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json
import time
import math
import re

INFILES = ["MSN", "DAT", "UI"]
MODEL = ""
MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.1-pro-preview"]

def find_infile():
    global INFILE, CHOSEN_FILE, OUTFILE

    options = "\n".join(f"\t{i}. {file}" for i, file in enumerate(INFILES, start=1))
    print(f"Which of the following files would you like to translate?")
    os.makedirs("gemini_translations", exist_ok=True)
    
    while True:
        # print options & get user input
        user_choice = input(f"{options}\nChoice: ")

        # validate user input
        try:
            user_choice = int(user_choice)
        except: 
            print(f"Please only enter an integer in the range 1-{len(INFILES)}.")
            
        # validate input is in range & save user choice of infile
        if user_choice in range (1, len(INFILES)+1):
            CHOSEN_FILE = INFILES[user_choice-1]
            INFILE = f"extracted_letter_sequences/text_{CHOSEN_FILE}.json"
            OUTFILE = f"gemini_translations/{CHOSEN_FILE}.json"
            break

        else:
            print(f"Please only enter an integer in the range 1-{len(INFILES)}.")

def choose_model():
    global MODELS
    global MODEL

    # print model option
    print("\nChoose your model:")
    for i, model in enumerate(MODELS):
        print(f"\t{i + 1}: {model}")

    try:
        # Get User Model Choice
        while True:
            user_choice = input("Choice (1-5): ")
            possible_choices = range(len(MODELS))

            if int(user_choice) - 1 in range(len(possible_choices)):
                MODEL = MODELS[int(user_choice) - 1]

                # confirm choice
                confirm = input(f'You are choosing "{MODEL}" are you sure (Y/N): ')
                try:
                    if confirm == 'Y' or confirm == 'y':
                        break
                    elif confirm == 'N' or confirm == 'n':
                        continue
                    else:
                        print("Only enter 'Y' or 'N'")
                except:
                    print("Only enter 'Y' or 'N'")
            else:
                print("Only enter an integer from ")
    
    except ValueError:
        print(f"Only enter an integer from {possible_choices[0]+1}-{possible_choices[-1]+1}")


def translate_json(input_json):
    # initialise gemini API connection
    client = genai.Client(api_key=api_key)
    
    # get model
    global MODEL
    model = MODEL

    # Read json data
    with open(input_json, "r", encoding="utf-8") as fp:
        all_data = json.load(fp)
        print(f"\nLoaded Data from {input_json}")
    
    # loop variables
    master_english_dict = {}
    address_list = list(all_data.items())
    final_index = list()
    chunk_size = 600
    i = 0
    duration_history = []

    # Remove lines without japanese from huge UI file
    if CHOSEN_FILE == "UI":
        print("\nUI File detected. Filtering out non-Japanese engine data...")
        japanese_regex = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]')
        filtered_list = []
        
        for key, val in address_list:
            text = val.get("text", "")
            # Only keep the item if it actually contains Japanese characters
            if japanese_regex.search(text):
                filtered_list.append((key, val))
                
        num_lines_old = len(address_list)
        address_list = filtered_list
        print(f"Reduced to {len(address_list)} actual Japanese text lines! (from {num_lines_old})")

        num_iterations = math.ceil(len(address_list) / chunk_size)

    # Resume where we left off
    start_index = 0
    if os.path.exists(OUTFILE) and os.path.getsize(OUTFILE) > 0:
        with open(OUTFILE, "r", encoding="UTF-8") as fp:
            master_english_dict = json.load(fp)

            start_index = len(master_english_dict)
            
            previous_iterations = int((start_index / chunk_size)) + 1

            if start_index > 0:
                print(f"\nFound Existing Progress, starting from {start_index} (Iteration {previous_iterations})")
                while True:
                    print(f"Would you like to resume from iteration {previous_iterations} (1) or Start from the beginning (2)?")
                    user_choice = input("Choice: ")
                    try:
                        if int(user_choice) not in [1, 2]:
                            print("Only enter '1' or '2'")
                            continue
                        # start from beginning & wipe file
                        if int(user_choice) == 2:
                            start_index = 0
                            open(OUTFILE, 'w').close()
                        break
                    except ValueError:
                        print("Only enter '1' or '2'")
                    
                if user_choice == 2:
                    start_index = 0

    # Start iterating through the json file and get gemini to translate japanese and leave the random chars
    for i in range(start_index, len(address_list), chunk_size):
        print(f"\n---STARTING ITERATION {int((i / chunk_size) + 1)}/{num_iterations} (IN:{INFILE}, OUT:{OUTFILE})---")
        iteration_start = time.time()

        # split json data into chunks
        print("Reading from infile...")
        chunk_slice = address_list[(i):(i+chunk_size)]
        chunk_string = json.dumps(dict(chunk_slice), ensure_ascii = False)
        # print(address_list)

        max_retries = 30
        attempt = 0
        success = False
        
        while attempt <= max_retries and not success:
            try:
                # Send message to gemini
                print("Querying gemini...")
                response = client.models.generate_content(
                    model=model,
                    contents=chunk_string,
                    config=types.GenerateContentConfig(
                        system_instruction="""
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
                            """,
                        response_mime_type="application/json",
                        temperature=0.1 # Low temperature keeps the AI focused and less "creative"
                    )
                )

                # Convert the AI's text response back into a Python dictionary
                translated_chunk = json.loads(response.text)

                # If gemini didn't respond with a dict, try again
                if not isinstance(translated_chunk, dict):
                    print(f"---ERROR: {model} returned a {type(translated_chunk).__name__} instead of a dictionary ---")
                    raise ValueError

                master_english_dict.update(translated_chunk)

                # write on each iteration to save progress
                print("Writing to outfile...")
                with open (OUTFILE, "w", encoding="utf-8") as fp:
                    json.dump(master_english_dict, fp, indent=4, ensure_ascii=False)

                print(translated_chunk)

                # duration stats
                duration = time.time() - iteration_start
                duration_history.append(duration)
                avg_duration = sum(duration_history) / len(duration_history)
                completed = int(i / chunk_size ) + 1
                remaining = num_iterations - completed
                percent = (completed / num_iterations) * 100

                eta_seconds = remaining * avg_duration
                mins, secs = divmod(int(eta_seconds), 60)

                print(f"\n---FINISHED ITERATION {int((i / chunk_size) + 1)}/{num_iterations} (IN:{INFILE}, OUT:{OUTFILE})---")

                # LOADING BAR DONE BY AI
                bar_length = 20
                filled_length = int(bar_length * completed // num_iterations)
                bar = '█' * filled_length + '-' * (bar_length - filled_length)

                print(f"\rProgress: [{bar}] {percent:.1f}% | ETA: {mins}m {secs}s", end="\n")

                # NEEED IF USING FREE TIER ON GEMINI API
                # time.sleep(11) # Sleep so that we don't hit the rate limits

                # Escape the retry loop
                success = True 
            
            except Exception as e:
                attempt += 1
                print(f"API error on chunk {int((i / chunk_size) + 1)}: {e}")

                if attempt < max_retries:
                    print(f"Retrying in 5 seconds... (Attempt {attempt} of {max_retries})\n")
                    time.sleep(5)
                
                else:
                    print(f"Maximum Attempts Reached, terminating script. Current progress has been saved to {OUTFILE}")
                    raise e
    
    print(f"\n--- JAP->ENG TRANSLATION COMPLETED ---")
        

if __name__ == "__main__":
    # Load Gemini API Key
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    # Choose which game file to translate
    find_infile()

    # Choose Gemini Model
    choose_model()

    # Translate the file
    translate_json(INFILE)