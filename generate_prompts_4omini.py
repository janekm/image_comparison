import os
import random
import base64
import argparse
from openai import OpenAI
import threading
import queue
import time
from tqdm import tqdm
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_random_images(directory):
    """
    Pick 1-3 random image files from the given directory.
    """
    image_files = [f for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    num_images = random.randint(1, min(3, len(image_files)))
    return random.sample(image_files, num_images)

def encode_image(image_path):
    """
    Encode the image file to base64.
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image {image_path}: {str(e)}")
        return None

def generate_prompt(client, image_data, image_files):
    """
    Generate a prompt using the OpenAI API.
    """
    messages = [
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are a helpful assistant."}]
        },
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}
                for data in image_data if data is not None
            ] + [{
                "type": "text",
                "text": "Create a detailed visually descriptive caption of these images, which will be used as a prompt for a text to image AI system (caption only, no instructions like \"create an image\"). Give detailed visual descriptions of the character(s), including ethnicity, skin tone, expression etc. Describe the image \nstyle, e.g. any photographic or art styles / techniques utilised. Describe the composition in detail. If there is more than one image, combine the elements and characters from all of the images creatively into a single cohesive composition with a single background, inventing an interaction between the characters. The scene needs to make sense. \nAdd some short creative text (3-4 words) that complements the scene, preferably embedded naturally into the elements of the scene as a logo or writing on an element of the scene.\nYour output is only the caption itself, no comments or extra formatting. The caption is in a single long paragraph."
            }]
        }
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=1,
            max_tokens=16383,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        return response.choices[0].message.content, image_files
    except Exception as e:
        logging.error(f"Error generating prompt: {str(e)}")
        return None, image_files

def worker(input_queue, output_queue, directory, client):
    while True:
        try:
            job = input_queue.get_nowait()
            image_files = get_random_images(directory)
            image_data = [encode_image(os.path.join(directory, img)) for img in image_files]
            prompt, files = generate_prompt(client, image_data, image_files)
            if prompt:
                output_queue.put((prompt, files))
            input_queue.task_done()
        except queue.Empty:
            break
        except Exception as e:
            logging.error(f"Error in worker thread: {str(e)}")
            input_queue.task_done()

def save_prompt(queue, output_file, total_prompts):
    with open(output_file, 'a') as f, tqdm(total=total_prompts, desc="Saving Prompts", unit="prompt") as pbar:
        while True:
            prompt, image_files = queue.get()
            if prompt is None:
                break
            f.write(prompt + '\n')
            f.flush()  # Ensure the prompt is written immediately
            
            print("\n" + "="*50)
            print(f"Images processed: {', '.join(image_files)}")
            print(f"Generated prompt: {prompt[:100]}...")  # Display first 100 characters
            print("="*50 + "\n")
            
            pbar.update(1)
            queue.task_done()

def main(directory, num_prompts, output_file, num_threads):
    client = OpenAI()
    input_queue = queue.Queue()
    output_queue = queue.Queue()

    for _ in range(num_prompts):
        input_queue.put(_)

    # Start worker threads
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker, args=(input_queue, output_queue, directory, client))
        t.start()
        threads.append(t)

    # Start save thread
    save_thread = threading.Thread(target=save_prompt, args=(output_queue, output_file, num_prompts))
    save_thread.start()

    # Wait for all worker threads to complete
    for t in threads:
        t.join()

    # Signal the save thread to exit
    output_queue.put((None, None))
    save_thread.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate image prompts using OpenAI API")
    parser.add_argument("input_folder", help="Path to the directory containing images")
    parser.add_argument("num_prompts", type=int, help="Number of prompts to generate")
    parser.add_argument("output_file", help="File to store the generated prompts")
    parser.add_argument("--threads", type=int, default=4, help="Number of threads to use (default: 4)")
    
    args = parser.parse_args()
    
    main(args.input_folder, args.num_prompts, args.output_file, args.threads)