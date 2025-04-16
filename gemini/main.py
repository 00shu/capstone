# main.py
import sys
import json # Keep json import for potential debugging, though load/save uses Pydantic methods now
from world_generator import WorldGenerator, WorldModel # Import WorldModel too
from story_engine import StoryEngine, GameMasterBeatModel, DirectNPCResponseModel
from typing import Optional

# ... (print_game_beat and print_npc_dialogue functions remain the same) ...

def main():
    print("Welcome to the LLM-Powered Adventure!")

    # Initialize generator first
    generator = WorldGenerator()
    world: Optional[WorldModel] = None # Use Optional typing
    save_file = "saved_world.json"

    # --- World Loading/Generation ---
    # Try loading first using the generator's method
    world = generator.load_world(filename=save_file)

    if world is None:
        # If loading failed (file not found, invalid JSON, validation error), generate a new one
        print(f"Could not load world from {save_file}. Generating a new world...")
        try:
            # You can customize the generation prompt here if desired
            setting = input("Enter a brief world setting (or press Enter for default 'A realm shrouded in magical mist'): ").strip()
            world_setting_prompt = setting if setting else "A realm shrouded in magical mist"

            world = generator.generate_world(world_setting_prompt)

            # Save the newly generated world if generation was successful
            if world:
                generator.save_world(world, filename=save_file)

        except (RuntimeError, ConnectionError, TimeoutError, ValueError) as e:
            # Catch specific errors from generate_world or _query_llm
            print(f"\n--- FATAL ERROR during World Generation ---")
            print(f"Error: {e}")
            print("Could not create a world to start the adventure. Exiting.")
            sys.exit(1)
        except Exception as e:
            # Catch any other unexpected errors during generation
            print(f"\n--- An unexpected FATAL ERROR occurred during World Generation ---")
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Details: {e}")
            print("Exiting.")
            sys.exit(1)

    # Ensure we have a world object before proceeding
    if world is None:
        print("FATAL: Failed to obtain world data. Exiting.")
        sys.exit(1)

    # --- Player & World Info ---
    # ... (rest of the main function remains the same as the previous version) ...
    # Make sure world is guaranteed to be non-None here due to the exit checks above
    # Display simplified player character information

    print(f"\nWelcome, {world.player_character.name}, to {world.world_name}!")
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
    # ... (display character info, locations) ...

    # --- Initialize Story Engine ---
    try:
        # StoryEngine __init__ now uses the consistent model name by default
        engine = StoryEngine(world)
    except Exception as e:
        print(f"FATAL: Failed to initialize Story Engine: {e}")
        sys.exit(1)

    # ... (Select Starting Location loop remains the same) ...
    # ... (Start the Story block remains the same) ...
    # ... (Main Game Loop remains the same) ...
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
        #print_scene(scene)
        
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