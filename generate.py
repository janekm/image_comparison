import requests
import json
from generate_signature import generate_signature
import hashlib
import time
import os
import re
import argparse
import urllib.request
import traceback
import sys
import asyncio
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window, ScrollablePane
from prompt_toolkit.widgets import Frame
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from collections import deque
import threading
import queue
import signal
import sys

url_pre = "https://" + "ap-east-1.tensorart.cloud"
app_id = "CvQtR6nFx"
private_key_path = "private_key.pem"
url_job = "/v1/jobs"

running_tasks = []
completed_tasks = []
tasks = []
max_parallel = 1
ui = None
task_queue = queue.Queue()
ui_queue = queue.Queue()
job_semaphore = threading.Semaphore(1)  # Control API call rate

class UIMessage:
    def __init__(self, type, **kwargs):
        self.type = type
        self.data = kwargs

class PromptToolkitUI:
    def __init__(self, total_tasks):
        self.total_tasks = total_tasks
        self.completed_tasks = 0
        self.total_credits = 0
        self.running_tasks = 0
        self.waiting_tasks = 0
        self.job_statuses = {}
        self.log_messages = deque(maxlen=100)

        self.status_area = FormattedTextControl(text=self.get_status_text)
        self.log_area = FormattedTextControl(text=self.get_log_text)

        root_container = HSplit([
            Frame(ScrollablePane(Window(content=self.status_area)), 
                  height=Dimension(preferred=10, weight=1),
                  title="Job Status"),
            Frame(ScrollablePane(Window(content=self.log_area)), 
                  height=Dimension(preferred=10, weight=1),
                  title="Log Messages")
        ])

        self.layout = Layout(root_container)
        
        style = Style.from_dict({
            'status.running': 'bold',
            'status.success': '#00ff00',
            'status.error': '#ff0000',
        })

        kb = KeyBindings()

        @kb.add('c-c')
        @kb.add('q')
        def _(event):
            event.app.exit()

        self.app = Application(layout=self.layout, full_screen=True, style=style, key_bindings=kb)

    def get_status_text(self):
        status_lines = [
            ('', f"Progress: {self.completed_tasks}/{self.total_tasks} | "
                f"Running: {self.running_tasks} | Waiting: {self.waiting_tasks} | "
                f"Credits: {self.total_credits:.2f}\n")
        ]
        # Sort jobs: running first, then waiting, then others
        sorted_jobs = sorted(self.job_statuses.items(), 
                             key=lambda x: (x[1]['status'] != 'RUNNING', x[1]['status'] != 'WAITING', x[0]))
        
        for job_id, info in sorted_jobs:
            status = info["status"]
            prompt = info["prompt"]
            if status == 'RUNNING':
                status_lines.append(('class:status.running', f"{job_id[:8]}: {status} - {prompt[:50]}...\n"))
            elif status == 'SUCCESS':
                status_lines.append(('class:status.success', f"{job_id[:8]}: {status} - {prompt[:50]}...\n"))
            elif status == 'WAITING':
                status_lines.append(('', f"{job_id[:8]}: {status} - {prompt[:50]}...\n"))
            else:
                status_lines.append(('', f"{job_id[:8]}: {status} - {prompt[:50]}...\n"))
        
        return status_lines

    def get_log_text(self):
        return [('', f"{level}: {message}\n") for level, message in self.log_messages]

    def log_info(self, message):
        self.log_messages.append(("INFO", message))
        self.app.invalidate()

    def log_error(self, message):
        self.log_messages.append(("ERROR", message))
        self.app.invalidate()

    def update_progress(self, completed=0, credits=0):
        self.completed_tasks = completed
        self.total_credits += credits
        self.app.invalidate()

    def set_running_tasks(self, count):
        self.running_tasks = count
        self.app.invalidate()

    def set_waiting_tasks(self, count):
        self.waiting_tasks = count
        self.app.invalidate()

    def update_job_status(self, job_id, status, prompt, credits=None):
        if status == 'SUCCESS' and len(self.job_statuses) >= 20:
            # Remove the oldest successful job if we have more than 20 jobs
            oldest_success = min((job for job in self.job_statuses.items() if job[1]['status'] == 'SUCCESS'), 
                                 key=lambda x: x[0], default=None)
            if oldest_success:
                del self.job_statuses[oldest_success[0]]
        
        self.job_statuses[job_id] = {"status": status, "prompt": prompt}
        if credits is not None:
            self.total_credits += credits
        
        # Update running and waiting task counts
        self.running_tasks = sum(1 for job in self.job_statuses.values() if job['status'] == 'RUNNING')
        self.waiting_tasks = sum(1 for job in self.job_statuses.values() if job['status'] == 'WAITING')
        
        self.app.invalidate()

class UIManager:
    def __init__(self, total_tasks):
        self.ui = PromptToolkitUI(total_tasks)
        self.queue = queue.Queue()
        self.exit_event = threading.Event()

    def start(self):
        def run_ui():
            self.ui.app.run(pre_run=self.pre_run)
            self.exit_event.set()  # Signal that the UI has exited

        ui_thread = threading.Thread(target=run_ui)
        ui_thread.start()

        while not self.exit_event.is_set():
            try:
                message = self.queue.get(timeout=0.1)
                self.process_message(message)
            except queue.Empty:
                continue

        ui_thread.join()

    def pre_run(self):
        def set_exit():
            self.exit_event.set()
            self.ui.app.exit()
        self.ui.app.on_exit = set_exit

    def process_message(self, message):
        if message.type == "EXIT":
            self.ui.app.exit()
        elif message.type == "LOG_INFO":
            self.ui.log_info(message.data['message'])
        elif message.type == "LOG_ERROR":
            self.ui.log_error(message.data['message'])
        elif message.type == "UPDATE_PROGRESS":
            self.ui.update_progress(**message.data)
        elif message.type == "SET_RUNNING_TASKS":
            self.ui.set_running_tasks(message.data['count'])
        elif message.type == "SET_WAITING_TASKS":
            self.ui.set_waiting_tasks(message.data['count'])
        elif message.type == "UPDATE_JOB_STATUS":
            self.ui.update_job_status(**message.data)

    def put_message(self, message):
        self.queue.put(message)

def ui_thread(total_tasks):
    global ui
    ui = PromptToolkitUI(total_tasks)
    
    def ui_update():
        while True:
            try:
                message = ui_queue.get(block=False)
                if message.type == "EXIT":
                    break
                elif message.type == "LOG_INFO":
                    ui.log_info(message.data['message'])
                elif message.type == "LOG_ERROR":
                    ui.log_error(message.data['message'])
                elif message.type == "UPDATE_PROGRESS":
                    ui.update_progress(**message.data)
                elif message.type == "SET_RUNNING_TASKS":
                    ui.set_running_tasks(message.data['count'])
                elif message.type == "UPDATE_JOB_STATUS":
                    ui.update_job_status(**message.data)
            except queue.Empty:
                break
        return False  # Return False to keep the application running

    ui.app.run(pre_run=ui_update)

def log_info(message):
    ui_manager.put_message(UIMessage("LOG_INFO", message=message))

def log_error(message):
    ui_manager.put_message(UIMessage("LOG_ERROR", message=message))

def update_progress(completed=0, credits=0):
    ui_manager.put_message(UIMessage("UPDATE_PROGRESS", completed=completed, credits=credits))

def set_running_tasks(count):
    ui_manager.put_message(UIMessage("SET_RUNNING_TASKS", count=count))

def update_job_status(job_id, status, prompt, credits=None):
    ui_manager.put_message(UIMessage("UPDATE_JOB_STATUS", job_id=job_id, status=status, prompt=prompt, credits=credits))

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

def create_job(prompt):
    sd3_data = {
        "request_id": hashlib.md5((str(int(time.time()))+prompt).encode()).hexdigest(),
        "stages": [
            {
                "type": "INPUT_INITIALIZE",
                "inputInitialize": {
                    "seed": -1,
                    "count": 1
                }
            },
            {
                "type": "DIFFUSION",
                "diffusion": {
                    "width": 1024,
                    "height": 1024,
                    "prompts": [
                        {
                            "text": prompt
                        }
                    ],
                    "sampler": "DPM++ 2M SGM Uniform",
                    "sdVae": "Automatic",
                    "steps": 35,
                    "sd_model": "738420691994573454",
                    "clip_skip": 2,
                    "cfg_scale": 7,
                    "lora": {
                    "items": [
                        {
                            "loraModel": "745836812276087995",
                            "weight": 0.5
                        }
                    ]
                }
                }
            },
            {
                "type": "IMAGE_TO_UPSCALER",
                "image_to_upscaler": {
                "hr_upscaler": "4x_foolhardy_Remacri",
                "hr_scale": 1.5,
                "hr_second_pass_steps": 15,
                "denoising_strength": 0.25
                }
            }
        ]
    }
    hunyuandit_data = {
        "request_id": hashlib.md5((str(int(time.time()))+prompt).encode()).hexdigest(),
        "stages": [
            {
                "type": "INPUT_INITIALIZE",
                "inputInitialize": {
                    "seed": -1,
                    "count": 1
                }
            },
            {
                "type": "DIFFUSION",
                "diffusion": {
                    "width": 1024,
                    "height": 1024,
                    "prompts": [
                        {
                            "text": prompt
                        }
                    ],
                    "sampler": "Heun",
                    "sdVae": "Automatic",
                    "steps": 32,
                    "sd_model": "728341924169251653",
                    "clip_skip": 2,
                    "cfg_scale": 7
                }
            }
        ]
    }
    playground25_data = {
        "request_id": hashlib.md5((str(int(time.time()))+prompt).encode()).hexdigest(),
        "stages": [
            {
                "type": "INPUT_INITIALIZE",
                "inputInitialize": {
                    "seed": -1,
                    "count": 1
                }
            },
            {
                "type": "DIFFUSION",
                "diffusion": {
                    "width": 1024,
                    "height": 1024,
                    "prompts": [
                        {
                            "text": prompt
                        }
                    ],
                    "sampler": "DPM++ 3M SDE Exponential",
                    "sdVae": "None",
                    "steps": 50,
                    "sd_model": "711820250385052892",
                    "clip_skip": 2,
                    "cfg_scale": 3
                }
            }
        ]
    }
    playground25_hd_data = {
        "request_id": hashlib.md5((str(int(time.time()))+prompt).encode()).hexdigest(),
        "stages": [
            {
                "type": "INPUT_INITIALIZE",
                "inputInitialize": {
                    "seed": -1,
                    "count": 1
                }
            },
            {
                "type": "DIFFUSION",
                "diffusion": {
                    "width": 1024,
                    "height": 1024,
                    "prompts": [
                        {
                            "text": prompt
                        }
                    ],
                    "sampler": "DPM++ 2S a",
                    "sdVae": "None",
                    "steps": 40,
                    "sd_model": "711820250385052892",
                    "clip_skip": 2,
                    "cfg_scale": 3
                }
            },
            {
                "type": "IMAGE_TO_UPSCALER",
                "image_to_upscaler": {
                "hr_upscaler": "4x_foolhardy_Remacri",
                "hr_scale": 1.5,
                "hr_second_pass_steps": 15,
                "denoising_strength": 0.25
                }
            }
        ]
    }    
    helloworld_data = {
        "request_id": hashlib.md5((str(int(time.time()))+prompt).encode()).hexdigest(),
        "stages": [
            {
                "type": "INPUT_INITIALIZE",
                "inputInitialize": {
                    "seed": -1,
                    "count": 1
                }
            },
            {
                "type": "DIFFUSION",
                "diffusion": {
                    "width": 1024,
                    "height": 1024,
                    "prompts": [
                        {
                            "text": prompt
                        }
                    ],
                    "negativePrompts": [{ "text": "hands, deviantart" }],
                    "sampler": "DPM++ 2S a Karras",
                    "sdVae": "None",
                    "steps": 40,
                    "sd_model": "666150205269367046",
                    "clip_skip": 2,
                    "cfg_scale": 7
                }
            },
            {
                "type": "IMAGE_TO_UPSCALER",
                "image_to_upscaler": {
                "hr_upscaler": "4x_foolhardy_Remacri",
                "hr_scale": 1.5,
                "hr_second_pass_steps": 15,
                "denoising_strength": 0.3
                }
            }
        ]
    }
    data = helloworld_data

    log_info(f"request_id: {data['request_id']}")
    body = json.dumps(data)
    auth_header = generate_signature("POST", url_job, body, app_id, private_key_path)
    try:
        response = requests.post(f"{url_pre}{url_job}", json=data, headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': auth_header
        })
        response.raise_for_status()
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        log_error(f"Error creating job: {str(e)}")
        return None

def get_job_status(job_id):
    try:
        response = requests.get(f"{url_pre}{url_job}/{job_id}", headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': generate_signature("GET", f"{url_job}/{job_id}", "", app_id, private_key_path)
        })
        response.raise_for_status()
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        log_error(f"Error getting job status for job ID {job_id}: {str(e)}")
        return None

def save_image(image_url, output_path):
    try:
        urllib.request.urlretrieve(image_url, output_path)
        log_info(f"Image saved: {output_path}")
    except Exception as e:
        log_error(f"Error saving image: {str(e)}")

def image_downloader(download_queue):
    while True:
        task = download_queue.get()
        if task is None:
            break
        try:
            save_image(task['image_url'], task['output_path'])
        except Exception as e:
            log_error(f"Error in image downloader: {str(e)}")
        download_queue.task_done()

def job_lifecycle(task, download_queue):
    global running_tasks, completed_tasks

    try:
        log_info(f"Starting job lifecycle for prompt: {task['prompt']}")
        
        with job_semaphore:
            response_data = create_job(task['prompt'])
        
        if response_data and 'job' in response_data:
            job_id = response_data['job']['id']
            task['job_id'] = job_id
            task['status'] = response_data['job']['status']
            update_job_status(job_id, task['status'], task['prompt'])
            log_info(f"Started new job {job_id[:8]} with status {task['status']}")

            while True:
                time.sleep(5)  # Wait for 5 seconds before checking status
                job_status = get_job_status(task['job_id'])
                if job_status and 'job' in job_status:
                    status = job_status['job']['status']
                    task['status'] = status
                    log_info(f"Job {task['job_id'][:8]} status: {status}")
                    credits = job_status['job'].get('credits')
                    
                    update_job_status(task['job_id'], status, task['prompt'])
                    
                    if status == 'WAITING':
                        waiting_info = job_status['job'].get('waitingInfo', {})
                        queue_rank = waiting_info.get('queueRank', 'N/A')
                        queue_len = waiting_info.get('queueLen', 'N/A')
                        log_info(f"Job {task['job_id'][:8]} WAITING - Queue Position: {queue_rank}/{queue_len}")
                    elif status == 'RUNNING':
                        log_info(f"Job {task['job_id'][:8]} RUNNING")
                    elif status == 'SUCCESS':
                        credits_used = job_status['job'].get('credits', 0)
                        update_job_status(task['job_id'], status, task['prompt'], credits_used)
                        if 'images' in job_status['job']['successInfo'] and job_status['job']['successInfo']['images']:
                            image_url = job_status['job']['successInfo']['images'][0]['url']
                            download_queue.put({'image_url': image_url, 'output_path': task['output_path']})
                        log_info(f"Job {task['job_id'][:8]} completed successfully.")
                        break
                    elif status == 'FAILED':
                        log_error(f"Job {task['job_id'][:8]} failed for prompt: {task['prompt']}")
                        break
                else:
                    log_error(f"Failed to get job status for job ID: {task['job_id']}")

        else:
            log_error(f"Failed to create job for prompt: {task['prompt']}")

    except Exception as e:
        log_error(f"Error in job lifecycle: {str(e)}")
        log_error(traceback.format_exc())

    finally:
        with threading.Lock():
            if task in running_tasks:
                running_tasks.remove(task)
            completed_tasks.append(task)
            update_progress(completed=len(completed_tasks))
            # set_running_tasks(len(running_tasks))

        # Signal that a new task can be started
        task_queue.put(None)

def task_manager():
    while True:
        try:
            if len(running_tasks) < max_parallel and not task_queue.empty():
                task = task_queue.get()
                if task is None:
                    break
                running_tasks.append(task)
                thread = threading.Thread(target=job_lifecycle, args=(task, download_queue))
                thread.start()
            time.sleep(0.1)  # Short sleep to prevent excessive CPU usage
        except Exception as e:
            log_error(f"Error in task manager: {str(e)}")
            log_error(traceback.format_exc())


def main_loop(_tasks, _max_parallel):
    global tasks, max_parallel, running_tasks, completed_tasks, download_queue, ui_manager
    tasks = _tasks
    max_parallel = _max_parallel
    download_queue = queue.Queue()

    ui_manager = UIManager(len(tasks))
    ui_thread = threading.Thread(target=ui_manager.start)
    ui_thread.start()

    def signal_handler(signum, frame):
        ui_manager.put_message(UIMessage("EXIT"))

    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Start the image downloader thread
        downloader_thread = threading.Thread(target=image_downloader, args=(download_queue,))
        downloader_thread.daemon = True  # Set as daemon thread
        downloader_thread.start()

        # Initialize task queue
        for task in tasks:
            task_queue.put(task)

        # Start task manager thread
        task_manager_thread = threading.Thread(target=task_manager)
        task_manager_thread.daemon = True  # Set as daemon thread
        task_manager_thread.start()

        # Wait for UI to exit
        while not ui_manager.exit_event.is_set():
            time.sleep(0.1)

    except Exception as e:
        ui_manager.put_message(UIMessage("LOG_ERROR", message=f"Error in main loop: {str(e)}"))
    finally:
        # Signal all threads to exit
        ui_manager.put_message(UIMessage("EXIT"))
        task_queue.put(None)
        download_queue.put(None)

        # Wait for threads to finish (with timeout)
        ui_thread.join(timeout=5)
        task_manager_thread.join(timeout=5)
        downloader_thread.join(timeout=5)

    return completed_tasks

def main():
    parser = argparse.ArgumentParser(description="Generate images from prompts in a file")
    parser.add_argument("prompt_file", help="File containing prompts, one per line")
    parser.add_argument("output_dir", help="Directory to save generated images")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel tasks to run")
    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    with open(args.prompt_file, 'r') as file:
        prompts = [line.strip() for line in file if line.strip()]

    tasks = []
    for prompt in prompts:
        filename = generate_filename(prompt, args.output_dir)
        output_path = os.path.join(args.output_dir, filename)
        tasks.append({
            'prompt': prompt,
            'output_path': output_path
        })

    completed_tasks = main_loop(tasks, args.parallel)
    print(f"Completed {len(completed_tasks)} tasks.")

if __name__ == '__main__':
    main()
