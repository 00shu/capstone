import json
import requests
import networkx as nx
from typing import Dict, List, Any, Optional # Added Optional
from pydantic import BaseModel, Field # Removed field_validator as it wasn't used

# --- Models --- (WorldState and LocationThemeModel removed)
class NPCModel(BaseModel):
    id: str = Field(description="Unique identifier for the NPC, e.g., 'elara_the_wise'")
    name: str = Field(description="NPC's full name")
    description: str = Field(description="Physical appearance and notable features")
    personality: str = Field(description="Key personality traits and behavior (e.g., 'Gruff, Loyal, Secretive')")

class LocationPlot(BaseModel):
    title: str = Field(description="Concise title of the primary plot or situation at this location")
    description: str = Field(description="Detailed description of the plot/situation")
    key_npcs: List[str] = Field(description="List of NPC IDs crucial to this plot")
    status: str = Field("Active", description="Current status (e.g., Active, Inactive, Completed)") # Added default

class LocationModel(BaseModel):
    id: str = Field(description="Unique identifier for the location, e.g., 'whispering_caves'")
    name: str = Field(description="Location name")
    type: str = Field(description="Type of location (e.g., 'City', 'Dungeon', 'Forest', 'Tavern')")
    description: str = Field(description="Detailed description suitable for setting a scene")
    connected_to: List[str] = Field(description="List of connected location IDs")
    primary_npcs: List[str] = Field(description="List of important NPC IDs usually found here")
    secondary_npcs: List[str] = Field(description="List of background NPC IDs sometimes found here")
    plot: LocationPlot = Field(description="Primary plot associated with this location")

class PlayerCharacterModel(BaseModel):
    name: str = Field(description="Character's name (must be a conventionally male name)")
    description: str = Field(description="Physical appearance and notable features")
    personality: str = Field(description="Key personality traits and behavior")

class WorldModel(BaseModel):
    world_name: str = Field(description="Name of the world")
    locations: List[LocationModel] = Field(description="List of all locations in the world")
    npcs: List[NPCModel] = Field(description="List of all NPCs in the world")
    player_character: PlayerCharacterModel = Field(description="The main player character in the world")

# --- WorldGenerator Class ---
class WorldGenerator:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "rolandroland/llama3.1-uncensored"):
        self.ollama_url = ollama_url
        self.model = model # Ensure consistency with StoryEngine

    def _query_llm(self, prompt: str, json_model_class: Optional[type[BaseModel]] = None) -> Any:
        """
        Send a query to the Ollama LLM. Returns structured JSON parsed by Pydantic
        if json_model_class is provided, otherwise returns the raw text response.
        """
        request_data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": { # Add options if needed
                "temperature": 0.7,
            }
        }

        # Modify prompt and request data if JSON format is expected
        schema_json = None
        if json_model_class:
            request_data["format"] = "json"
            try:
                schema_json = json.dumps(json_model_class.model_json_schema(), indent=2)
                # Add schema context to prompt for better adherence
                prompt += f"\n\nIMPORTANT: Respond STRICTLY in valid JSON format according to this Pydantic schema:\n```json\n{schema_json}\n```"
                request_data["prompt"] = prompt # Update prompt in request data
            except Exception as e:
                print(f"Warning: Could not generate schema for {json_model_class.__name__}: {e}")
                # Proceed without schema in prompt if generation fails, rely only on "format": "json"

        print(f"\n--- Sending Prompt to LLM ({self.model}, {'JSON Mode' if json_model_class else 'Text Mode'}) ---")
        # print(prompt) # Optionally print the full prompt for debugging
        print("---------------------------")

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=request_data,
                #timeout=180 # Increased timeout for potentially large world generation
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            raw_response_data = response.json()
            response_text = raw_response_data.get("response", "").strip()

            if not response_text:
                 raise ValueError("LLM returned an empty response.")

            if json_model_class:
                print(f"\n--- Received Raw JSON String from LLM ---\n{response_text}\n-----------------------------------\n")
                # Attempt to parse and validate the JSON response
                try:
                    # Basic cleaning (sometimes helpful for LLM outputs)
                    cleaned_response_text = response_text.strip().lstrip('```json').rstrip('```')
                    parsed_json = json.loads(cleaned_response_text)
                    validated_data = json_model_class.model_validate(parsed_json)
                    print(f"--- Successfully Validated JSON for {json_model_class.__name__} ---")
                    return validated_data
                except json.JSONDecodeError as json_err:
                    print(f"--- LLM JSON Parsing Error ---")
                    print(f"Raw Response Snippet: {response_text[:500]}...")
                    print(f"Error: {json_err}")
                    # Optionally print the expected schema for comparison during debugging
                    # if schema_json: print(f"Expected Schema:\n{schema_json}")
                    raise ValueError(f"LLM response was not valid JSON: {json_err}") from json_err
                except Exception as pyd_err: # Catch Pydantic validation errors too
                    print(f"--- LLM JSON Validation Error ({pyd_err.__class__.__name__}) ---")
                    # Print details about the validation error if possible
                    # print(f"Parsed JSON attempt: {parsed_json}") # Might be large
                    print(f"Error: {pyd_err}")
                    # if schema_json: print(f"Expected Schema:\n{schema_json}")
                    raise ValueError(f"LLM JSON did not match schema {json_model_class.__name__}: {pyd_err}") from pyd_err
            else:
                # Return raw text response if no JSON model was specified
                print(f"\n--- Received Text from LLM ---\n{response_text}\n---------------------------\n")
                return response_text

        except requests.exceptions.Timeout:
            print(f"Error: Request to Ollama timed out after 180 seconds.")
            raise TimeoutError("LLM request timed out.")
        except requests.exceptions.RequestException as req_err:
            print(f"Error connecting to Ollama or during request: {req_err}")
            raise ConnectionError(f"Failed request to Ollama at {self.ollama_url}") from req_err
        except Exception as e:
            # Catch any other unexpected errors during the process
            print(f"An unexpected error occurred during LLM query: {e.__class__.__name__} - {e}")
            raise # Re-raise the exception


    def generate_world(self, setting_prompt: str = "A small fantasy kingdom with a mysterious forest") -> WorldModel:
        """Generate a complete world including map, locations, NPCs, and player character."""
        world_prompt = f"""
        Generate a detailed Dungeons & Dragons world based on the following high-level setting: '{setting_prompt}'.

        Follow these requirements STRICTLY:
        1.  **World Structure:** Create a cohesive world with a compelling name.
        2.  **Locations:** Define 3-5 distinct locations (e.g., towns, dungeons, forests, ruins).
            * Each location needs a unique `id` (lowercase_with_underscores), `name`, `type`, and detailed `description`.
            * Each location MUST have connections (`connected_to`) to at least one other defined location ID. Ensure connections make geographical sense.
        3.  **NPCs:** Create 5-8 unique NPCs distributed across the locations.
            * Each NPC needs a unique `id` (lowercase_with_underscores), `name`, `description`, and `personality` string (3-4 descriptive words).
            * Assign NPCs to locations via `primary_npcs` (usually 1-2 per location) and `secondary_npcs` (0-2 per location) using their IDs. Ensure every NPC is listed in at least one location's list.
        4.  **Plots:** Each location MUST have a `plot` object containing:
            * A concise `title` for the plot/situation at that location.
            * A detailed `description` explaining the plot.
            * A `key_npcs` list containing IDs of NPCs essential to *that specific plot*. Ensure these IDs match NPCs defined in the main `npcs` list.
            * A `status` field, initially set to "Active".
        5.  **Player Character:** Define a `player_character` who is the protagonist.
            * The player character MUST be male, with a conventionally masculine name.
            * Provide a compelling `description` and `personality` string.
        6.  **Consistency:** Ensure all NPC IDs used in location lists (`primary_npcs`, `secondary_npcs`, `plot.key_npcs`) exist in the main `npcs` list. Ensure all location IDs in `connected_to` exist in the main `locations` list.

        Generate the output as a single JSON object conforming precisely to the WorldModel Pydantic schema provided separately.
        """

        print("\n=== Starting World Generation ===")
        try:
            # Pass the Pydantic class itself for schema generation and validation
            world_data = self._query_llm(world_prompt, json_model_class=WorldModel)

            # Perform post-generation validation/cleanup if needed
            # (e.g., ensuring all referenced IDs actually exist)
            print("\n=== LLM Response Successfully Parsed and Validated into WorldModel ===")
            print(f"Generated World: {world_data.world_name}")
            print(f"Number of locations: {len(world_data.locations)}")
            print(f"Number of NPCs: {len(world_data.npcs)}")

            return world_data
        except (ValueError, ConnectionError, TimeoutError, Exception) as e:
            print(f"\n--- FATAL ERROR during World Generation ---")
            print(f"Error Type: {type(e).__name__}")
            print(f"Error Details: {e}")
            print("---------------------------------------------")
            # Decide how to handle generation failure: raise, return None, or exit
            raise RuntimeError("Failed to generate world data from LLM.") from e


    def create_world_graph(self, world_data: WorldModel) -> Optional[nx.Graph]:
        """Create a networkx graph representation of the world. Returns None if networkx not installed."""
        try:
            import networkx as nx
        except ImportError:
            print("Warning: networkx library not installed. Cannot create world graph.")
            return None

        G = nx.Graph()
        npc_locations = {} # Track where each NPC primarily belongs

        # Add locations as nodes
        print("\nCreating world graph...")
        for location in world_data.locations:
            G.add_node(location.id,
                       label=location.name, # Use label for display names
                       type="location",
                       desc=location.description,
                       plot_title=location.plot.title)
            # Track primary NPCs for edge creation later
            for npc_id in location.primary_npcs:
                if npc_id not in npc_locations:
                    npc_locations[npc_id] = []
                npc_locations[npc_id].append(location.id)
            # Optionally track secondary NPCs too
            # for npc_id in location.secondary_npcs:
            #     if npc_id not in npc_locations: npc_locations[npc_id] = []
            #     npc_locations[npc_id].append(location.id)


        # Add connections between locations
        for location in world_data.locations:
            for connected_id in location.connected_to:
                if G.has_node(connected_id): # Ensure target node exists
                     G.add_edge(location.id, connected_id, type="connection")
                else:
                     print(f"Warning: Location '{location.name}' connects to unknown ID '{connected_id}'. Skipping edge.")


        # Add NPCs as nodes and connect them to their primary location(s)
        for npc in world_data.npcs:
            G.add_node(npc.id,
                       label=npc.name, # Use label for display names
                       type="npc",
                       desc=npc.description,
                       personality=npc.personality)
            # Connect NPC to its primary location(s) found earlier
            if npc.id in npc_locations:
                for loc_id in npc_locations[npc.id]:
                     if G.has_node(loc_id): # Ensure location node exists
                        G.add_edge(npc.id, loc_id, type="located_at")
                     else:
                          print(f"Warning: NPC '{npc.name}' assigned to unknown primary location ID '{loc_id}'. Skipping edge.")

            else:
                print(f"Warning: NPC '{npc.name}' (ID: {npc.id}) not found in any location's primary_npcs list.")

        print(f"World graph created with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
        return G

    def save_world(self, world_data: WorldModel, filename: str = "saved_world.json"):
        """Save the generated world to a JSON file using Pydantic's recommended serialization"""
        print(f"\nAttempting to save world to {filename}...")
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Use model_dump_json for direct JSON string output with Pydantic settings
                f.write(world_data.model_dump_json(indent=2))
            print(f"--- World saved successfully to {filename} ---")
        except IOError as e:
            print(f"--- Error saving world: Could not write to file {filename}. Check permissions. ---")
            print(f"Error details: {e}")
            # Optionally re-raise or handle differently
        except Exception as e:
            print(f"--- An unexpected error occurred while saving world: {e} ---")
            # Optionally re-raise


    def load_world(self, filename: str = "saved_world.json") -> Optional[WorldModel]:
        """Load a previously generated world from a JSON file"""
        print(f"\nAttempting to load world from {filename}...")
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                world_json_data = f.read() # Read the whole file
            # Use model_validate_json for direct parsing from JSON string
            world_data = WorldModel.model_validate_json(world_json_data)
            print(f"--- World loaded and validated successfully from {filename} ---")
            return world_data
        except FileNotFoundError:
            print(f"--- No saved world found at {filename} ---")
            return None
        except json.JSONDecodeError as e:
             print(f"--- Error loading world: Invalid JSON format in {filename}. ---")
             print(f"Error details: {e}")
             return None # Return None on JSON error
        except Exception as e: # Catch Pydantic validation errors and others
            print(f"--- Error loading or validating world from {filename}: {e.__class__.__name__} ---")
            print(f"Error details: {e}")
            return None # Return None on validation or other errors


if __name__ == "__main__":
    # Test the world generator
    generator = WorldGenerator()
    try:
        # Example: Generate a world if loading fails or doesn't exist
        world = generator.load_world()
        if not world:
             print("Generating a new world as loading failed or file doesn't exist.")
             world = generator.generate_world("A coastal kingdom plagued by ancient sea monsters") # Example prompt
             if world:
                  generator.save_world(world) # Save the newly generated world

        if world:
             print("\n--- World Details ---")
             print(f"World Name: {world.world_name}")
             print(f"Player: {world.player_character.name}")
             # print(world.model_dump_json(indent=2)) # Optionally print full world data

             # Test graph creation
             graph = generator.create_world_graph(world)
             if graph:
                 # You could add more graph analysis or visualization here if desired
                 pass
        else:
             print("Could not load or generate a world.")

    except (RuntimeError, ConnectionError, TimeoutError) as e:
         print(f"Terminating due to error: {e}")
    except Exception as e:
         print(f"An unexpected error occurred in the test run: {e}")