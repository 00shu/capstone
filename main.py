import json
from world_generator import WorldGenerator
from story_engine import StoryEngine
from story_engine import SceneModel

def print_scene(scene_data: SceneModel):
    """Pretty print the scene information."""
    print("\n" + "="*80)
    print("\nNarrative:")
    print(scene_data.narrative)
    print("\nAvailable Actions:")
    for action in scene_data.available_actions:
        print(f"- {action}")
    print("\nPresent NPCs:")
    for npc_id in scene_data.active_npcs:
        print(f"- {npc_id}")
    print("\n" + "="*80 + "\n")

def main():
    print("Welcome to the D&D Multi-Agent Adventure!")
    
    generator = WorldGenerator()
    world = None
    
    # Try to load saved world first
    try:
        world = generator.load_world()
    except Exception as e:
        print(f"Error loading saved world: {str(e)}")
    
    if world is None:
        print("Generating new world...")
        setting = input("Enter a brief description of the world setting (or press Enter for default): ").strip()
        world = generator.generate_world(setting if setting else "A small fantasy kingdom with a mysterious forest")
        
        # Save the newly generated world
        try:
            generator.save_world(world)
        except Exception as e:
            print(f"Error saving world: {str(e)}")
            print("Continuing without saving...")
    
    print(f"\nWelcome to {world.world_name}!")
    
    # Display simplified player character information
    pc = world.player_character
    print("\nYour Character:")
    print(f"Name: {pc.name}")
    print(f"Description: {pc.description}")
    print(f"Personality: {pc.personality}")
    
    print("\n=== World Generation Complete ===")
    print(f"World name: {world.world_name}")
    print("\nAvailable locations:")
    for location in world.locations:
        print(f"- {location.name} ({location.id}): {location.type}")
        print(f"  Description: {location.description}")
        print(f"  Plot: {location.plot.title}")
        print(f"  Connected to: {location.connected_to}")
        print(f"  Primary NPCs: {location.primary_npcs}")
        print(f"  Secondary NPCs: {location.secondary_npcs}")
    
    print("\n=== Initializing Story Engine ===")
    engine = StoryEngine(world)
    
    while True:
        start_loc = input("\nEnter the ID of your starting location: ").strip()
        print(f"\nAttempting to start story with location ID: '{start_loc}'")
        try:
            scene = engine.start_story(start_loc)
            print("\n=== Successfully started story ===")
            break
        except ValueError as e:
            print(f"\n=== Failed to start story ===")
            print(f"Error: {str(e)}")
            print("Please try again.")
    
    # Main game loop
    while True:
        print_scene(scene)
        
        # Get player input
        action = input("What would you like to do? (or 'quit' to exit): ").strip()
        
        if action.lower() == 'quit':
            break
            
        # Check if the player wants to talk to an NPC
        if action.lower().startswith("talk to "):
            npc_id = action[8:].strip()  # Remove "talk to " from the beginning
            try:
                npc_response = engine.get_npc_response(npc_id, input(f"What do you say to {npc_id}? "))
                print(f"\n{npc_id} says: {npc_response.dialogue}")
                if npc_response.action:  # Access action directly
                    print(f"{npc_id} {npc_response.action}")
            except ValueError:
                print(f"Cannot find NPC with ID {npc_id}")
                continue
        
        # Process the action and get the next scene
        scene = engine.process_action(action)
        
        # If location changed, announce it
        if scene.location_change:  # Access location_change directly
            print(f"\nYou have moved to {engine.current_location.name}")
        
        # Show NPC reactions if any
        if scene.npc_reactions:
            print("\nNPC Reactions:")
            for reaction in scene.npc_reactions:
                print(f"{reaction.id}: {reaction.message}")
                print(f"  {reaction.reaction}")

if __name__ == "__main__":
    main() 