import os
import json
import re
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

def generate_filename(prompt):
    short_prompt = re.sub(r'[^\w\s-]', '', prompt.lower())
    short_prompt = re.sub(r'[-\s]+', '-', short_prompt).strip('-')[:50]
    return short_prompt

def convert_to_webp(image_path, output_path):
    if os.path.exists(output_path):
        return output_path
    with Image.open(image_path) as img:
        img.save(output_path, 'WEBP')
    return output_path

def create_thumbnail(images, output_path, max_size=(300, 300)):
    if os.path.exists(output_path):
        return output_path
    
    num_images = len(images)
    if num_images <= 3:
        cols, rows = num_images, 1
    elif num_images <= 6:
        cols, rows = 3, 2
    else:
        cols, rows = 3, 3

    size = (min(max_size[0], cols * 100), min(max_size[1], rows * 100))
    
    thumbnail = Image.new('RGB', size, (255, 255, 255))
    
    for i, image_path in enumerate(images[:9]):
        with Image.open(image_path) as img:
            img.thumbnail((size[0]//cols, size[1]//rows))
            x = (i % cols) * (size[0] // cols)
            y = (i // cols) * (size[1] // rows)
            thumbnail.paste(img, (x, y))
    
    thumbnail.save(output_path, 'WEBP')
    return output_path

def process_image(image_path, webp_dir):
    relative_path = os.path.relpath(image_path, image_root_dir)
    subfolder = os.path.dirname(relative_path)
    file_name = os.path.basename(image_path)
    webp_name = f"{os.path.splitext(file_name)[0]}.webp"
    webp_subfolder = os.path.join(webp_dir, subfolder)
    os.makedirs(webp_subfolder, exist_ok=True)
    webp_path = os.path.join(webp_subfolder, webp_name)
    webp_path = convert_to_webp(image_path, webp_path)
    
    with Image.open(image_path) as img:
        width, height = img.size
    
    return webp_path, image_path, width, height

def generate_image_data(prompts_file, image_root_dir, output_json, webp_dir, thumbnail_dir):
    os.makedirs(webp_dir, exist_ok=True)
    os.makedirs(thumbnail_dir, exist_ok=True)

    with open(prompts_file, 'r') as f:
        prompts = [line.strip() for line in f if line.strip()]

    data = []
    prompt_prefixes = {generate_filename(prompt): prompt for prompt in prompts}
    print(prompt_prefixes)

    with ThreadPoolExecutor() as executor:
        futures = []
        for root, _, files in os.walk(image_root_dir):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    file_prefix = file.split('.')[0].lower()
                    if file_prefix in prompt_prefixes:
                        image_path = os.path.join(root, file)
                        futures.append(executor.submit(process_image, image_path, webp_dir))

        for future in as_completed(futures):
            webp_path, original_path, width, height = future.result()
            print(f"Converted {original_path} to {webp_path}")
            relative_webp_path = os.path.relpath(webp_path, webp_dir)
            relative_original_path = os.path.relpath(original_path, image_root_dir)
            file_prefix = os.path.basename(webp_path).split('.')[0].lower()
            prompt = prompt_prefixes[file_prefix]
            
            prompt_entry = next((item for item in data if item["prompt"] == prompt), None)
            if prompt_entry is None:
                prompt_entry = {"prompt": prompt, "images": [], "thumbnail": ""}
                data.append(prompt_entry)
            
            prompt_entry["images"].append({
                "webp_path": os.path.join("webp_images", relative_webp_path),
                "original_path": os.path.join("images", relative_original_path),
                "subfolder": os.path.dirname(relative_webp_path),
                "width": width,
                "height": height
            })

    for prompt_entry in data:
        if prompt_entry["images"]:
            thumbnail_path = os.path.join(thumbnail_dir, f"{generate_filename(prompt_entry['prompt'])}_thumbnail.webp")
            prompt_entry["thumbnail"] = create_thumbnail([img["original_path"] for img in prompt_entry["images"]], thumbnail_path)
            prompt_entry["thumbnail"] = os.path.relpath(thumbnail_path, os.path.dirname(output_json))
            prompt_entry["images"].sort(key=lambda x: (x["subfolder"], x["webp_path"]))

    data.sort(key=lambda x: prompts.index(x["prompt"]))

    with open(output_json, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Data has been written to {output_json}")

# Usage
prompts_file = "prompts.txt"
image_root_dir = "images"
output_json = "image_data.json"
webp_dir = "webp_images"
thumbnail_dir = "thumbnails"

generate_image_data(prompts_file, image_root_dir, output_json, webp_dir, thumbnail_dir)