import os
import re
from openai import OpenAI

def read_prompts(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def extract_number(prompt):
    match = re.match(r'^(\d+)\s*-\s*(.*)$', prompt)
    if match:
        return match.group(1), match.group(2)
    return None, prompt

def process_prompt(client, prompt):
    history = [
        {"role": "system", "content": "You are an intelligent assistant. You always provide well-reasoned answers that are both correct and helpful."},
        {"role": "user", "content": """A caption is a way that a person would describe an image separated by commas when necessary. All in lower case. Expand the input below into a more detailed caption without changing the original relative positions or interactions between objects, colors or any other specific attributes if they are disclosed in the original prompt. Clarify positional information, colors, counts of objects, other visual aspects and features. Make sure to include as much detail as possible. Make sure to describe the spatial relationships seen in the image. You can use words like left/right, above/below, front/behind, far/near/adjacent, inside/outside. Make sure to include object interactions like "a table is in front of the kitchen pot" and "there are baskets on the table". Also describe relative sizes of objects seen in the image. Make sure to include counts of prominent objects in the image, especially when there is humans in the image. When its a photograph, include photographic details like bokeh, large field of view etc but dont just say it to say something, do it only when it makes sense. When its art, include details about the style like minimalist, impressionist, oil painting etc. Include world and period knowledge if it makes sense to, like 1950s chevrolet etc. """ + prompt + "\n only output the enhanced prompt in a single paragraph, nothing else."},
    ]

    completion = client.chat.completions.create(
        model="NousResearch/Hermes-2-Theta-Llama-3-8B-GGUF",
        messages=history,
        temperature=0.7,
    )

    return completion.choices[0].message.content

def main():
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    input_file = "numbered_prompts.txt"
    output_file = "enhanced_prompts2.txt"

    prompts = read_prompts(input_file)

    with open(output_file, 'w') as out_file:
        for prompt in prompts:
            number, clean_prompt = extract_number(prompt)
            print(f"Processing: {prompt}")
            
            enhanced_prompt = process_prompt(client, clean_prompt)
            
            if number:
                output = f"{number} - {enhanced_prompt}\n"
            else:
                output = f"{enhanced_prompt}\n"
            
            print(f"Original: {prompt}")
            print(f"Enhanced: {output}")
            out_file.write(output)
            out_file.flush()  # Ensure the output is written immediately
            
            print("Done\n")

    print(f"Enhanced prompts have been written to {output_file}")

if __name__ == "__main__":
    main()