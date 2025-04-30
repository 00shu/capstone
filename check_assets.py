import os
import json

def check_assets():
    # Check if assets directory exists
    if not os.path.exists('assets'):
        print("Creating assets directory...")
        os.makedirs('assets')
    
    # Check if location and npc subdirectories exist
    for subdir in ['location', 'npc']:
        path = os.path.join('assets', subdir)
        if not os.path.exists(path):
            print(f"Creating {subdir} directory...")
            os.makedirs(path)
    
    # Load world content
    try:
        with open("world_content.json", "r", encoding="utf-8") as f:
            world_content = json.load(f)
    except FileNotFoundError:
        print("Error: world_content.json not found!")
        return
    except json.JSONDecodeError:
        print("Error: world_content.json is not valid JSON!")
        return
    
    # Check location images
    print("\nChecking location images...")
    for location in world_content.get('locations', []):
        location_name = location['name']
        image_path = os.path.join('assets', 'location', f"{location_name}.png")
        if not os.path.exists(image_path):
            print(f"Missing: {image_path}")
    
    # Check NPC images
    print("\nChecking NPC images...")
    for location in world_content.get('locations', []):
        for npc in location.get('npcs', []):
            npc_name = npc['name']
            image_path = os.path.join('assets', 'npc', f"{npc_name}.png")
            if not os.path.exists(image_path):
                print(f"Missing: {image_path}")
    
    # Check default images
    default_images = [
        os.path.join('assets', 'location', 'default.png'),
        os.path.join('assets', 'npc', 'default.png')
    ]
    print("\nChecking default images...")
    for image_path in default_images:
        if not os.path.exists(image_path):
            print(f"Missing: {image_path}")

if __name__ == '__main__':
    check_assets() 