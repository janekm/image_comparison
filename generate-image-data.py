import os
import json
import re
from collections import defaultdict

def generate_filename(prompt):
    short_prompt = re.sub(r'[^\w\s-]', '', prompt.lower())
    short_prompt = re.sub(r'[-\s]+', '-', short_prompt).strip('-')[:50]
    return short_prompt

def generate_image_data(prompts_file, image_root_dir, output_json):
    with open(prompts_file, 'r') as f:
        prompts = [line.strip() for line in f if line.strip()]

    data = []
    prompt_prefixes = {generate_filename(prompt): prompt for prompt in prompts}

    for prompt in prompts:
        prompt_entry = {"prompt": prompt, "images": []}
        prompt_prefix = generate_filename(prompt)

        for root, _, files in os.walk(image_root_dir):
            subfolder = os.path.relpath(root, image_root_dir)
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    file_prefix = file.split('.')[0].lower()
                    if file_prefix == prompt_prefix:
                        image_path = os.path.join(subfolder, file)
                        prompt_entry["images"].append({
                            "path": image_path,
                            "subfolder": subfolder
                        })

        if prompt_entry["images"]:
            prompt_entry["images"].sort(key=lambda x: (x["subfolder"], x["path"]))
            data.append(prompt_entry)

    with open(output_json, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Data has been written to {output_json}")

# Usage
prompts_file = "prompts.txt"
image_root_dir = "."
output_json = "image_data.json"

generate_image_data(prompts_file, image_root_dir, output_json)
