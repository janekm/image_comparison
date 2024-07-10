import os
import re
import argparse
import queue
import threading
import requests
import time
from openai import OpenAI
from openai import RateLimitError

class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls
        self.period = period
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, f):
        def wrapped(*args, **kwargs):
            with self.lock:
                now = time.time()
                self.calls = [c for c in self.calls if now - c < self.period]
                if len(self.calls) >= self.max_calls:
                    sleep_time = self.period - (now - self.calls[0])
                    time.sleep(sleep_time)
                self.calls.append(time.time())
            return f(*args, **kwargs)
        return wrapped

def generate_filename(prompt, output_dir):
    short_prompt = re.sub(r'[^\w\s-]', '', prompt.lower())
    short_prompt = re.sub(r'[-\s]+', '-', short_prompt).strip('-')[:50]
    base_filename = f"{short_prompt}.jpg"
    filename = base_filename
    counter = 1
    while os.path.exists(os.path.join(output_dir, filename)):
        filename = f"{short_prompt}_{counter}.jpg"
        counter += 1
    return filename

def image_exists(prompt, output_dir):
    short_prompt = re.sub(r'[^\w\s-]', '', prompt.lower())
    short_prompt = re.sub(r'[-\s]+', '-', short_prompt).strip('-')[:50]
    base_filename = f"{short_prompt}.jpg"
    return os.path.exists(os.path.join(output_dir, base_filename))

@RateLimiter(max_calls=5, period=60)
def call_openai_api(client, full_prompt):
    return client.images.generate(
        model="dall-e-3",
        prompt=full_prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

def process_prompt(prompt, output_dir, q):
    if image_exists(prompt, output_dir):
        print(f"Skipping existing image for prompt: {prompt[:50]}...")
        return

    client = OpenAI()
    
    full_prompt = ("The following is a test prompt for text2image systems. Please reformat it to follow OpenAI "
                   "content and safety guidelines, in particular making sure to replace all references to named "
                   "persons and trademarks with visual descriptions and making sure that all descriptions of "
                   "clothing are suitable for a mormon audience. Remove references to notorious artists." + prompt)
    
    try:
        print(f"Starting processing for prompt: {prompt[:50]}...")
        response = call_openai_api(client, full_prompt)
        print(f"OpenAI API request completed for prompt: {prompt[:50]}")
        
        image_url = response.data[0].url
        
        image_response = requests.get(image_url)
        if image_response.status_code == 200:
            filename = generate_filename(prompt, output_dir)
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(image_response.content)
            print(f"Generated and saved image: {filepath}")
        else:
            print(f"Failed to download image for prompt: {prompt}")
    except RateLimitError as e:
        print(f"Rate limit exceeded for prompt: {prompt[:50]}. Re-queuing.")
        q.put(prompt)
    except Exception as e:
        print(f"Error processing prompt: {prompt}")
        print(f"Error details: {str(e)}")
        if "rate_limit_exceeded" in str(e):
            print(f"Rate limit error. Re-queuing prompt: {prompt[:50]}")
            q.put(prompt)

def worker(q, output_dir):
    while True:
        try:
            prompt = q.get(block=False)
            process_prompt(prompt, output_dir, q)
            q.task_done()
        except queue.Empty:
            break

def main():
    parser = argparse.ArgumentParser(description="Generate images using DALLE-3 API")
    parser.add_argument("prompt_file", help="File containing prompts, one per line")
    parser.add_argument("-t", "--threads", type=int, default=4, help="Number of parallel threads")
    args = parser.parse_args()

    output_dir = "images/dalle3"
    os.makedirs(output_dir, exist_ok=True)

    q = queue.Queue()

    with open(args.prompt_file, 'r') as f:
        for line in f:
            prompt = line.strip()
            if prompt:
                q.put(prompt)

    total_prompts = q.qsize()
    print(f"Loaded {total_prompts} prompts from file.")

    threads = []
    thread_count = min(args.threads, total_prompts)
    print(f"Starting {thread_count} worker threads...")
    for _ in range(thread_count):
        t = threading.Thread(target=worker, args=(q, output_dir))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("All images generated and saved.")

if __name__ == "__main__":
    main()