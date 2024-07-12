import os
import json
import re
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ProgressBar, Log, Static
from textual import work

class ImageProcessingApp(App):
    CSS = """
    ProgressBar {
        width: 100%;
        height: 1;
    }
    #progress_container {
        layout: vertical;
        background: $boost;
        padding: 1;
    }
    .progress_label {
        padding-left: 1;
    }
    Log {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Static(id="progress_container"):
            yield Static("Overall Progress:", classes="progress_label")
            yield ProgressBar(id="overall_progress", show_percentage=True)
            yield Static("Image Conversion:", classes="progress_label")
            yield ProgressBar(id="convert_progress", show_percentage=True)
            yield Static("Thumbnail Creation:", classes="progress_label")
            yield ProgressBar(id="thumbnail_progress", show_percentage=True)
        yield Log()
        yield Footer()

    def on_mount(self):
        self.run_processor()

    @work(thread=True)
    def run_processor(self):
        self.process_images()

    def generate_filename(self, prompt):
        short_prompt = re.sub(r'[^\w\s-]', '', prompt.lower())
        short_prompt = re.sub(r'[-\s]+', '-', short_prompt).strip('-')[:50]
        return short_prompt

    def convert_to_webp(self, image_path, output_path):
        if os.path.exists(output_path):
            return output_path, True
        with Image.open(image_path) as img:
            img.save(output_path, 'WEBP')
        return output_path, False

    def create_thumbnail(self, prompt_entry, thumbnail_dir, output_json):
        if not prompt_entry["images"]:
            return prompt_entry

        thumbnail_path = os.path.join(thumbnail_dir, f"{self.generate_filename(prompt_entry['prompt'])}_thumbnail.webp")
        
        if os.path.exists(thumbnail_path):
            prompt_entry["thumbnail"] = os.path.relpath(thumbnail_path, os.path.dirname(output_json))
            return prompt_entry

        images = [img["original_path"] for img in prompt_entry["images"]]
        num_images = len(images)
        if num_images <= 3:
            cols, rows = num_images, 1
        elif num_images <= 6:
            cols, rows = 3, 2
        else:
            cols, rows = 3, 3

        max_size = (300, 300)
        size = (min(max_size[0], cols * 100), min(max_size[1], rows * 100))
        
        thumbnail = Image.new('RGB', size, (0, 0, 0))
        
        for i, image_path in enumerate(images[:9]):
            with Image.open(image_path) as img:
                img.thumbnail((size[0]//cols, size[1]//rows))
                x = (i % cols) * (size[0] // cols)
                y = (i // cols) * (size[1] // rows)
                thumbnail.paste(img, (x, y))
        
        thumbnail.save(thumbnail_path, 'WEBP')
        prompt_entry["thumbnail"] = os.path.relpath(thumbnail_path, os.path.dirname(output_json))
        
        self.call_from_thread(self.query_one(Log).write, f"Created thumbnail for prompt: {prompt_entry['prompt']}\n")
        return prompt_entry

    def process_image(self, image_path, webp_dir):
        relative_path = os.path.relpath(image_path, self.image_root_dir)
        subfolder = os.path.dirname(relative_path)
        file_name = os.path.basename(image_path)
        webp_name = f"{os.path.splitext(file_name)[0]}.webp"
        webp_subfolder = os.path.join(webp_dir, subfolder)
        os.makedirs(webp_subfolder, exist_ok=True)
        webp_path = os.path.join(webp_subfolder, webp_name)
        webp_path, existed = self.convert_to_webp(image_path, webp_path)
        
        with Image.open(image_path) as img:
            width, height = img.size
        
        return webp_path, image_path, width, height, existed

    def process_images(self):
        prompts_file = "prompts.txt"
        self.image_root_dir = "images"
        output_json = "image_data.json"
        webp_dir = "webp_images"
        thumbnail_dir = "thumbnails"

        os.makedirs(webp_dir, exist_ok=True)
        os.makedirs(thumbnail_dir, exist_ok=True)

        with open(prompts_file, 'r') as f:
            prompts = [line.strip() for line in f if line.strip()]

        data = []
        prompt_prefixes = {self.generate_filename(prompt): prompt for prompt in prompts}

        self.call_from_thread(self.query_one("#overall_progress").update, total=len(prompts))

        with ThreadPoolExecutor() as executor:
            futures = []
            for root, _, files in os.walk(self.image_root_dir):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        file_prefix = file.split('.')[0].lower()
                        if file_prefix in prompt_prefixes:
                            image_path = os.path.join(root, file)
                            futures.append(executor.submit(self.process_image, image_path, webp_dir))

            self.call_from_thread(self.query_one("#convert_progress").update, total=len(futures))
            
            for future in as_completed(futures):
                webp_path, original_path, width, height, existed = future.result()
                if not existed:
                    self.call_from_thread(self.query_one(Log).write, f"Converted {original_path} to {webp_path}\n")
                self.call_from_thread(self.query_one("#convert_progress").advance, 1)
                
                relative_webp_path = os.path.relpath(webp_path, webp_dir)
                relative_original_path = os.path.relpath(original_path, self.image_root_dir)
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

        self.call_from_thread(self.query_one("#thumbnail_progress").update, total=len(data))

        # Define the desired order of subfolders
        subfolder_order = ["auraflow_llm", "auraflow", "StableCascade", "kolors", "sd3_upsampled", "hghd_play_enh_hd", "hunyuandit", "ideogram", "dalle3", "midjourney"]

        # Sort images within each prompt entry
        for prompt_entry in data:
            prompt_entry["images"].sort(key=lambda x: (
                subfolder_order.index(x["subfolder"]) if x["subfolder"] in subfolder_order else len(subfolder_order),
                x["webp_path"]
            ))

        # Threaded thumbnail creation
        with ThreadPoolExecutor() as thumbnail_executor:
            thumbnail_futures = [
                thumbnail_executor.submit(self.create_thumbnail, prompt_entry, thumbnail_dir, output_json)
                for prompt_entry in data
            ]
            
            for future in as_completed(thumbnail_futures):
                updated_prompt_entry = future.result()
                self.call_from_thread(self.query_one("#thumbnail_progress").advance, 1)
                self.call_from_thread(self.query_one("#overall_progress").advance, 1)

        data.sort(key=lambda x: prompts.index(x["prompt"]))

        with open(output_json, 'w') as f:
            json.dump(data, f, indent=2)

        self.call_from_thread(self.query_one(Log).write, f"Data has been written to {output_json}")
        self.call_from_thread(self.exit)

if __name__ == "__main__":
    app = ImageProcessingApp()
    app.run()