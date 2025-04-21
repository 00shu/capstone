from diffusers import AutoPipelineForText2Image
import torch
import json

pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16")
pipe.to("cuda")

with open('./world_content.json', 'r') as file:
    data = json.load(file)

for loc in data['locations']:
  image = pipe(loc['visual_description']+" in pixel art style", num_inference_steps=10, guidance_scale=0.0).images[0]
  image.save(f"/content/assets/locations/{loc['name']}.png")
  for npc in loc['npcs']:
    image = pipe(npc['visual_description']+"full body in pixel art style, white background just the character in frame", num_inference_steps=10, guidance_scale=0.0).images[0]
    image.save(f"/content/assets/npcs/{npc['name']}.png")
