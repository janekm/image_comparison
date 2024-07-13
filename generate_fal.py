import asyncio
import os
import re
import sys
from pathlib import Path
import fal_client
import aiohttp
from textual.app import App, ComposeResult
from textual.widgets import ProgressBar, RichLog
from textual.reactive import reactive

class ImageGenerationApp(App):
    BINDINGS = [("q", "quit", "Quit")]
    
    progress = reactive(0)
    total_prompts = reactive(0)

    def __init__(self, prompts, output_dir, num_parallel):
        super().__init__()
        self.prompts = prompts
        self.output_dir = output_dir
        self.num_parallel = num_parallel
        self.total_prompts = len(prompts)

    def compose(self) -> ComposeResult:
        yield ProgressBar(total=self.total_prompts, id="progress")
        yield RichLog(id="log")

    def on_mount(self) -> None:
        self.log_message(f"Total prompts to process: {self.total_prompts}")
        asyncio.create_task(self.run_generation())

    def log_message(self, message: str) -> None:
        self.query_one("#log", RichLog).write(message)

    async def run_generation(self):
        tasks = []
        for i in range(0, len(self.prompts), self.num_parallel):
            batch = self.prompts[i:i+self.num_parallel]
            tasks.extend([self.generate_image(prompt) for prompt in batch])
            await asyncio.gather(*tasks)
            tasks.clear()
        
        self.log_message("All images generated successfully!")
        await asyncio.sleep(2)
        self.exit()

    async def generate_image(self, prompt):
        try:
            handler = await fal_client.submit_async(
                # "fal-ai/aura-flow",
                "fal-ai/pixart-sigma",
                arguments={"prompt": prompt},
            )

            async for event in handler.iter_events(with_logs=True):
                if isinstance(event, fal_client.InProgress):
                    for log in event.logs:
                        self.log_message(f"[{prompt[:20]}...] {log['message']}")

            result = await handler.get()
            image_url = result['images'][0]['url']
            
            filename = self.generate_filename(prompt, self.output_dir)
            filepath = os.path.join(self.output_dir, filename)
            
            await self.download_image(image_url, filepath)
            
            self.log_message(f"Saved image: {filepath}")
            self.progress += 1
        except Exception as e:
            self.log_message(f"Error processing prompt '{prompt}': {str(e)}")

    async def download_image(self, url, filepath):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(filepath, 'wb') as f:
                        f.write(content)
                else:
                    raise Exception(f"Failed to download image. Status code: {response.status}")

    def generate_filename(self, prompt, output_dir):
        short_prompt = re.sub(r'[^\w\s-]', '', prompt.lower())
        short_prompt = re.sub(r'[-\s]+', '-', short_prompt).strip('-')[:50]
        base_filename = f"{short_prompt}.png"
        filename = base_filename
        counter = 1
        while os.path.exists(os.path.join(output_dir, filename)):
            filename = f"{short_prompt}_{counter}.png"
            counter += 1
        return filename

    def watch_progress(self, progress: int) -> None:
        """Called when progress changes."""
        self.query_one("#progress", ProgressBar).advance(1)

def main():
    if len(sys.argv) != 4:
        print("Usage: python script.py <prompt_file> <output_dir> <num_parallel>")
        sys.exit(1)

    prompt_file = sys.argv[1]
    output_dir = sys.argv[2]
    num_parallel = int(sys.argv[3])

    with open(prompt_file, 'r') as f:
        prompts = [line.strip() for line in f if line.strip()]

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    app = ImageGenerationApp(prompts, output_dir, num_parallel)
    app.run()

if __name__ == "__main__":
    main()