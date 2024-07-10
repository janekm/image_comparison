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
        {"role": "user", "content": """Here are examples of enhanced text 2 image prompts:A breathtakingly detailed 8k illustration of the Goddess of Agriculture, resembling Elizabeth Hurley, standing majestically against a surreal backdrop. She wears intricately designed green armor adorned with lightning, rain, branches, leaves, fruits, flowers, and smoke. The goddess is surrounded by celestial beings, including rain nymphs and fruit spirits. The background showcases a lush, otherworldly landscape with vibrant colors, creating a coherent and immersive scene. The artwork is illuminated with cinematic lighting, reminiscent of the styles of Gediminas Pranckevicius, Pino Daeni, Moebius, Artgerm, and Esao Andrews. This remarkable piece was created by the talented artists Charlie Bowater Art, Karol Bak, and Mark Brooks, and showcases their exceptional skills
A stunning, cinematic photograph showcasing a beautiful woman emerging from a pool of vibrant, colorful liquid oil paint. The paint splashes around her, creating bold strokes of red, blue, and yellow in a dynamic, abstract pattern. The artist's name, Karol Bak, is clearly visible in the bottom corner. The lighting is dramatic and theatrical, highlighting the woman's captivating features and the mesmerizing paint.
A stunning, realistic portrayal of Lalisa Manoban from BLACKPINK wearing a summer dress. The dress is beautifully designed with vibrant colors and floral patterns, complementing her radiant smile. Her long, wavy hair is adorned with a delicate hairpin. The background features a picturesque summer scene, with sunflowers and a blue sky. The overall atmosphere is cheerful and captivating, showcasing Lalisa's natural beauty and charisma.
A stunning, close-up intimate portrait of Sasha Luss, confidently posing in a vibrant orange bandeau bikini top and a sheer cover-up wrapped around her waist. Her gaze penetrates the camera lens with a fearless intensity, evoking the essence of Solve Sundsbo's iconic subjects. The background features a tropical paradise with palm trees and a turquoise sea, adding to the alluring atmosphere.
Rewrite the following prompt in the same style: """ + prompt + "\n only output the enhanced prompt in a single paragraph, nothing else."},
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
    output_file = "enhanced_prompts.txt"

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