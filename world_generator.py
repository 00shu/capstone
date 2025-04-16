import json
import requests
import networkx as nx
from typing import Dict, List, Any
from pydantic import BaseModel, Field, field_validator

class NPCModel(BaseModel):
    id: str = Field(description="Unique identifier for the NPC")
    name: str = Field(description="NPC's name")
    description: str = Field(description="Physical appearance and notable features")
    personality: str = Field(description="Key personality traits and behavior")

class LocationThemeModel(BaseModel):
    main_plot: str = Field(description="Main plot or theme of this location")
    side_quests: List[str] = Field(description="Potential side quests or subplots")
    secrets: List[str] = Field(description="Hidden secrets or mysteries of this location")
    atmosphere: str = Field(description="General atmosphere and mood of the location")
    key_events: List[str] = Field(description="Important events that could happen here")

class LocationPlot(BaseModel):
    title: str = Field(description="Title of the primary plot")
    description: str = Field(description="Detailed description of the plot")
    key_npcs: List[str] = Field(description="IDs of NPCs crucial to this plot")
    status: str = Field(description="Current status of the plot (active/inactive/completed)")

class LocationModel(BaseModel):
    id: str = Field(description="Unique identifier for the location")
    name: str = Field(description="Location name")
    type: str = Field(description="Type of location (city/dungeon/forest/etc)")
    description: str = Field(description="Detailed description for image generation")
    connected_to: List[str] = Field(description="List of connected location IDs")
    primary_npcs: List[str] = Field(description="List of important NPC IDs for this location")
    secondary_npcs: List[str] = Field(description="List of background NPC IDs")
    plot: LocationPlot = Field(description="Primary plot associated with this location")


class PlayerCharacterModel(BaseModel):
    name: str = Field(description="Character's name (must be a male name)")
    description: str = Field(description="Physical appearance and notable features")
    personality: str = Field(description="Key personality traits and behavior")

class WorldModel(BaseModel):
    # world_name: str = Field(description="Name of the world")
    # locations: List[LocationModel]
    # npcs: List[NPCModel]
    # player_character: PlayerCharacterModel
    world_name: str = Field(description="Name of the world")
    locations: List[LocationModel] = Field(description="List of all locations in the world")
    npcs: List[NPCModel] = Field(description="List of all NPCs in the world")
    player_character: PlayerCharacterModel = Field(description="The main player character in the world")

class WorldState(BaseModel):
    """Class to track the dynamic state of the world"""
    known_npcs: Dict[str, NPCModel] = Field(description="Dictionary of all known NPCs")
    npc_attitudes: Dict[str, Dict[str, str]] = Field(description="NPC attitudes towards other characters")
    location_states: Dict[str, Dict[str, Any]] = Field(description="Current state of each location")
    active_plots: List[str] = Field(description="Currently active plot threads")
    completed_plots: List[str] = Field(description="Completed plot threads")

class WorldGenerator:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model = "rolandroland/llama3.1-uncensored"

    def _query_llm(self, prompt: str, format_schema: dict) -> str:
        """Send a query to the Ollama LLM and get the response."""
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "format": format_schema,  # Pass the schema to the LLM
                "stream": False
            }
        )
        return response.json()["response"]

    def generate_world(self, setting_prompt: str = "fantasy medieval world") -> WorldModel:
        """Generate a complete world including map, locations, NPCs, and player character."""
        world_prompt = f"""
        Create a D&D world with the following setting: {setting_prompt}
        Include a detailed player character that will be the protagonist of this adventure.
        
        IMPORTANT RULES:
        1. The player character MUST be male, with a masculine name
        2. Each location must have:
           - A primary plot with clear objectives
           - Key NPCs who are essential to that plot
           - Additional background NPCs
        3. NPCs should have clear personalities that relate to their location's plot
        4. Locations must be physical places (towns, dungeons, forests, etc.)
        5. The player character should NOT be included as a location
        6. Each location must connect to at least one other location
        
        The response must strictly follow the provided JSON schema format.
        """
        
        try:
            format_schema = WorldModel.model_json_schema()
            print("\n=== Schema sent to LLM ===")
            print(json.dumps(format_schema, indent=2))
            
            response = self._query_llm(world_prompt, format_schema)
            print("\n=== Raw LLM Response ===")
            print("Response type:", type(response))
            print(response)
            
            print("\n=== Attempting to parse response ===")
            world_data = WorldModel.model_validate_json(response)
            
            print("\n=== Successfully created WorldModel ===")
            print(f"Type of world_data: {type(world_data)}")
            print(f"Number of locations: {len(world_data.locations)}")
            print(f"Number of NPCs: {len(world_data.npcs)}")
            
            return world_data
        except Exception as e:
            print("\n=== Error in generate_world ===")
            print(f"Error type: {type(e)}")
            print(f"Error message: {str(e)}")
            raise

    def create_world_graph(self, world_data: WorldModel) -> nx.Graph:
        """Create a networkx graph representation of the world."""
        G = nx.Graph()
        
        # Add locations as nodes
        for location in world_data.locations:
            G.add_node(location.id, 
                      type="location",
                      name=location.name,
                      description=location.description)
            
        # Add connections between locations
        for location in world_data.locations:
            for connected_id in location.connected_to:
                G.add_edge(location.id, connected_id)
                
        # Add NPCs as nodes and connect them to their locations
        for npc in world_data.npcs:
            G.add_node(npc.id,
                      type="npc",
                      name=npc.name,
                      description=npc.description)
            G.add_edge(npc.id, npc.id)
            
        return G

    def save_world(self, world_data: WorldModel, filename: str = "saved_world.json"):
        """Save the generated world to a JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(world_data.model_dump(), f, indent=2)
            print(f"\n=== World saved successfully to {filename} ===")
        except Exception as e:
            print(f"\n=== Error saving world: {str(e)} ===")
            raise

    def load_world(self, filename: str = "saved_world.json") -> WorldModel:
        """Load a previously generated world from a JSON file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                world_data = json.load(f)
            print(f"\n=== World loaded successfully from {filename} ===")
            return WorldModel.model_validate(world_data)
        except FileNotFoundError:
            print(f"\n=== No saved world found at {filename} ===")
            return None
        except Exception as e:
            print(f"\n=== Error loading world: {str(e)} ===")
            raise

if __name__ == "__main__":
    # Test the world generator
    generator = WorldGenerator()
    world = generator.generate_world("A small fantasy kingdom with a mysterious forest")
    print(world.model_dump_json(indent=2))
    graph = generator.create_world_graph(world)
    print(f"World graph has {len(graph.nodes)} nodes and {len(graph.edges)} edges") 