import os
import re
import shutil

def generate_filename(prompt, output_dir):
    # Remove the number, dash, and space from the beginning of the prompt
    prompt = re.sub(r'^\d+\s*-\s*', '', prompt)
    
    short_prompt = re.sub(r'[^\w\s-]', '', prompt.lower())
    short_prompt = re.sub(r'[-\s]+', '-', short_prompt).strip('-')[:50]
    base_filename = f"{short_prompt}.png"
    filename = base_filename
    counter = 1
    while os.path.exists(os.path.join(output_dir, filename)):
        filename = f"{short_prompt}_{counter}.png"
        counter += 1
    return filename

def process_files(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.endswith('.txt'):
            txt_path = os.path.join(input_dir, filename)
            with open(txt_path, 'r') as file:
                content = file.read()
                prompt_match = re.search(r'Positive prompt:\s*(.*?)(?:\n|$)', content, re.DOTALL)
                if prompt_match:
                    prompt = prompt_match.group(1).strip()
                    new_filename = generate_filename(prompt, output_dir)
                    
                    # Assume the image has the same name as the text file but with .png extension
                    img_filename = os.path.splitext(filename)[0] + '.png'
                    img_path = os.path.join(input_dir, img_filename)
                    
                    if os.path.exists(img_path):
                        shutil.copy(img_path, os.path.join(output_dir, new_filename))
                        print(f"Copied {img_filename} to {new_filename}")
                    else:
                        print(f"Image file not found for {filename}")
                else:
                    print(f"No prompt found in {filename}")

# Usage
input_dir = 'images_in/StableCascade'
output_dir = 'images/StableCascade'
process_files(input_dir, output_dir)