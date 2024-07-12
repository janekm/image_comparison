import os
import re
import shutil

MAX_NUM = 220
def read_prompts(file_path):
    prompts = {}
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split(' - ', 1)
            if len(parts) == 2:
                number, prompt = parts
                prompts[number] = prompt
    return prompts

def generate_filename(prompt, output_dir, extension):
    short_prompt = re.sub(r'[^\w\s-]', '', prompt.lower())
    short_prompt = re.sub(r'[-\s]+', '-', short_prompt).strip('-')[:50]
    base_filename = f"{short_prompt}{extension}"
    filename = base_filename
    counter = 1
    while os.path.exists(os.path.join(output_dir, filename)):
        filename = f"{short_prompt}_{counter}{extension}"
        counter += 1
    return filename

def extract_number(filename):
    # Try to match the "5-{other_text}" format
    match = re.match(r'^(\d+)-', filename)
    if match:
        return match.group(1)
    
    # Try to match the "morbuto_14_-_{other_text}" format
    match = re.match(r'^morbuto_(\d+)_-_', filename)
    if match:
        return match.group(1)
    match = re.match(r'^(\d+) - ', filename)
    if int(match.group(1)) > MAX_NUM:
        return str(int(match.group(1)) - MAX_NUM  + 1)
    if match:
        return match.group(1)
    
    return None

def rename_and_copy_files(input_dir, output_dir, prompts_file):
    prompts = read_prompts(prompts_file)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')
    
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(image_extensions):
            number = extract_number(filename)
            print(f"number: {number}")
            if number and number in prompts:
                prompt = prompts[number]
                _, extension = os.path.splitext(filename)
                new_filename = generate_filename(prompt, output_dir, extension)
                src_path = os.path.join(input_dir, filename)
                dst_path = os.path.join(output_dir, new_filename)
                shutil.copy2(src_path, dst_path)
                print(f"Copied and renamed: {filename} -> {new_filename}")
            else:
                print(f"No prompt found for file or invalid format: {filename}")
    # print(prompts)

# Usage
input_dir = 'images_in/StableCascade'
output_dir = 'images/StableCascade'
prompts_file = 'numbered_prompts.txt'

rename_and_copy_files(input_dir, output_dir, prompts_file)