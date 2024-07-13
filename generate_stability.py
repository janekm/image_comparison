import asyncio
import os
import re
import sys
from pathlib import Path
import aiohttp
from aiohttp import MultipartWriter

class ImageGenerator:
    def __init__(self, prompts, output_dir, num_parallel):
        self.prompts = prompts
        self.output_dir = output_dir
        self.num_parallel = num_parallel
        self.total_prompts = len(prompts)
        self.completed_prompts = 0
        self.api_key = os.environ.get('STABILITY_API_KEY')
        if not self.api_key:
            raise ValueError("STABILITY_API_KEY environment variable is not set")

    async def run_generation(self):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i in range(0, len(self.prompts), self.num_parallel):
                batch = self.prompts[i:i+self.num_parallel]
                tasks.extend([self.generate_image(session, prompt) for prompt in batch])
                await asyncio.gather(*tasks)
                tasks.clear()
        
        print("\nAll images generated successfully!")

    async def generate_image(self, session, prompt):
        try:
            url = "https://api.stability.ai/v2beta/stable-image/generate/ultra"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "image/*"
            }

            # Create multipart writer
            mpwriter = MultipartWriter('form-data')
            
            # Add prompt part
            part = mpwriter.append(prompt)
            part.set_content_disposition('form-data', name='prompt')
            
            # Add output_format part
            part = mpwriter.append('webp')
            part.set_content_disposition('form-data', name='output_format')

            async with session.post(url, headers=headers, data=mpwriter) as response:
                if response.status == 200:
                    content = await response.read()
                    filename = self.generate_filename(prompt, self.output_dir)
                    filepath = os.path.join(self.output_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    self.completed_prompts += 1
                    self.print_progress()
                    print(f"\nSaved image: {filepath}")
                else:
                    error_msg = await response.text()
                    raise Exception(f"API request failed with status {response.status}: {error_msg}")
        except Exception as e:
            print(f"\nError processing prompt '{prompt}': {str(e)}")

    def generate_filename(self, prompt, output_dir):
        short_prompt = re.sub(r'[^\w\s-]', '', prompt.lower())
        short_prompt = re.sub(r'[-\s]+', '-', short_prompt).strip('-')[:50]
        base_filename = f"{short_prompt}.webp"
        filename = base_filename
        counter = 1
        while os.path.exists(os.path.join(output_dir, filename)):
            filename = f"{short_prompt}_{counter}.webp"
            counter += 1
        return filename

    def print_progress(self):
        percent = (self.completed_prompts / self.total_prompts) * 100
        bar_length = 50
        filled_length = int(bar_length * self.completed_prompts // self.total_prompts)
        bar = '=' * filled_length + '-' * (bar_length - filled_length)
        print(f'\rProgress: [{bar}] {percent:.1f}% ({self.completed_prompts}/{self.total_prompts})', end='', flush=True)

async def main():
    if len(sys.argv) != 4:
        print("Usage: python script.py <prompt_file> <output_dir> <num_parallel>")
        sys.exit(1)

    prompt_file = sys.argv[1]
    output_dir = sys.argv[2]
    num_parallel = int(sys.argv[3])

    with open(prompt_file, 'r') as f:
        prompts = [line.strip() for line in f if line.strip()]

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    generator = ImageGenerator(prompts, output_dir, num_parallel)
    print(f"Starting image generation for {len(prompts)} prompts...")
    await generator.run_generation()

if __name__ == "__main__":
    asyncio.run(main())