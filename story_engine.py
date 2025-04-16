import json
import requests
from typing import Dict, List, Any, Optional
from world_generator import WorldGenerator, WorldModel, WorldState, LocationModel, NPCModel
from pydantic import BaseModel, Field

class SceneModel(BaseModel):
    narrative: str = Field(description="Detailed description of the opening scene")
    available_actions: List[str] = Field(description="List of possible actions")
    active_npcs: List[str] = Field(description="List of present NPC IDs")

class NPCReactionModel(BaseModel):
    id: str = Field(description="ID of the NPC")
    message: str = Field(description="What the NPC says")
    reaction: str = Field(description="How the NPC reacts")

class StoryBeatModel(BaseModel):
    narrative: str = Field(description="Detailed description of what happens next")
    available_actions: List[str] = Field(description="List of possible actions")
    active_npcs: List[str] = Field(description="List of present NPC IDs")
    location_change: Optional[str] = Field(None, description="ID of new location if changed")
    npc_reactions: List[NPCReactionModel] = Field(description="List of NPC reactions")

class NPCResponseModel(BaseModel):
    dialogue: str = Field(description="NPC's spoken response")
    action: Optional[str] = Field(None, description="NPC's action if any")
    attitude: str = Field(description="NPC's current attitude toward player")

class StoryEngine:
    def __init__(self, world_data: WorldModel, ollama_url: str = "http://localhost:11434"):
        self.world_data = world_data
        self.ollama_url = ollama_url
        self.model = "rolandroland/llama3.1-uncensored"
        self.current_location = None
        self.story_context = []
        # Initialize world state with simplified location states
        self.world_state = WorldState(
            known_npcs={npc.id: npc for npc in world_data.npcs},
            npc_attitudes={},
            location_states={loc.id: {
                "visited": False,
                "plot_status": loc.plot.status  # Changed from theme to plot_status
            } for loc in world_data.locations},
            active_plots=[],
            completed_plots=[]
        )
        
    def _query_llm(self, prompt: str, format_schema: dict = None) -> str:
        """Send a query to the Ollama LLM and get the response."""
        request_data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        if format_schema:
            request_data["format"] = format_schema
            
        response = requests.post(
            f"{self.ollama_url}/api/generate",
            json=request_data
        )
        return response.json()["response"]
    
    def start_story(self, starting_location_id: str) -> SceneModel:
        """Initialize the story at a specific location."""
        print("\n=== Starting Story ===")
        print(f"Looking for location ID: {starting_location_id}")
        print(f"Available locations:")
        for loc in self.world_data.locations:
            print(f"- ID: '{loc.id}' (type: {type(loc.id)})")
        
        self.current_location = next(
            (loc for loc in self.world_data.locations 
             if loc.id == starting_location_id),
            None
        )
        
        if not self.current_location:
            print("\n=== Location Not Found ===")
            print(f"Input ID: '{starting_location_id}' (type: {type(starting_location_id)})")
            print("Available IDs:", [f"'{loc.id}'" for loc in self.world_data.locations])
            raise ValueError("Invalid starting location ID")
            
        scene_schema = SceneModel.model_json_schema()
        
        prompt = f"""
        Create an engaging opening scene for a D&D adventure that takes place in {self.current_location.name}.
        Location Description: {self.current_location.description}
        
        Current Plot: {self.current_location.plot.title}
        Plot Description: {self.current_location.plot.description}
        
        Primary NPCs Present:
        {self._format_npcs(self.current_location.primary_npcs)}
        
        Background NPCs:
        {self._format_npcs(self.current_location.secondary_npcs)}
        
        The response must strictly follow the provided JSON schema format.
        Focus on introducing the location's primary plot and key NPCs.
        """
        
        response = self._query_llm(prompt, scene_schema)
        print("\n=== Raw Scene Response ===")
        print(response)
        
        try:
            scene_data = SceneModel.model_validate_json(response)
            # Filter out player character from active NPCs
            scene_data.active_npcs = [
                npc_id for npc_id in scene_data.active_npcs 
                if npc_id != self.world_data.player_character.name
            ]
            self.story_context.append({
                "location": self.current_location.id,
                "scene": scene_data.model_dump()
            })
            return scene_data
        except Exception as e:
            print("\n=== Scene Parsing Error ===")
            print(f"Error type: {type(e)}")
            print(f"Error message: {str(e)}")
            raise
    
    def _format_npcs(self, npc_ids: List[str]) -> str:
        """Format NPC information for prompts"""
        npc_info = []
        for npc_id in npc_ids:
            npc = self.world_state.known_npcs.get(npc_id)
            if npc:
                npc_info.append(f"- {npc.name}: {npc.description}\n  Personality: {npc.personality}")
        return "\n".join(npc_info)

    def add_new_npc(self, npc_data: NPCModel):
        """Add a new NPC to the world state"""
        self.world_state.known_npcs[npc_data.id] = npc_data
        print(f"\n=== New NPC Added: {npc_data.name} ===")

    def update_npc_attitude(self, npc_id: str, target_id: str, attitude: str):
        """Update an NPC's attitude towards another character"""
        if npc_id not in self.world_state.npc_attitudes:
            self.world_state.npc_attitudes[npc_id] = {}
        self.world_state.npc_attitudes[npc_id][target_id] = attitude

    def get_relevant_npcs(self, action: str, location: LocationModel) -> List[NPCModel]:
        """Determine which NPCs would realistically react to an action"""
        relevant_npcs = []
        # Combine both primary and secondary NPCs
        all_npcs = location.primary_npcs + location.secondary_npcs
        for npc_id in all_npcs:
            npc = self.world_state.known_npcs.get(npc_id)
            if npc:
                # Check if NPC would care about this action based on their personality
                if any(keyword in action.lower() for keyword in npc.personality.lower().split()):
                    relevant_npcs.append(npc)
                # Add NPCs who are mentioned in the action
                if npc.name.lower() in action.lower():
                    relevant_npcs.append(npc)
        return relevant_npcs

    def process_action(self, player_action: str) -> StoryBeatModel:
        """Process a player's action and generate the next story beat."""
        relevant_npcs = self.get_relevant_npcs(player_action, self.current_location)
        
        prompt = f"""
        Story Context:
        {self._build_context(relevant_npcs)}
        
        Current Location: {self.current_location.name}
        Active Plot: {self.current_location.plot.title}
        Plot Status: {self.current_location.plot.status}
        
        Key NPCs Present:
        {self._format_npcs(self.current_location.primary_npcs)}
        
        NPCs who would notice this action:
        {self._format_relevant_npcs(relevant_npcs)}
        
        Player Action: {player_action}
        
        Generate the next story beat following the provided JSON schema format.
        IMPORTANT FORMAT RULES:
        1. 'available_actions' should only include possible actions the player can take next
        2. NPC dialogue and reactions should go in 'npc_reactions', not in 'available_actions'
        3. 'narrative' should describe what happens, not include direct NPC speech
        
        Example available actions:
        - "Examine the ancient ruins"
        - "Follow the path deeper into the forest"
        - "Search for clues about the missing artifact"
        
        Consider:
        1. How this action affects the location's primary plot
        2. Reactions from plot-relevant NPCs
        3. The current plot status
        """
        
        story_beat_schema = StoryBeatModel.model_json_schema()
        
        try:
            response = self._query_llm(prompt, story_beat_schema)
            print("\n=== Raw Story Beat Response ===")
            print(response)
            
            result = StoryBeatModel.model_validate_json(response)
            
            # Filter out player character from active NPCs
            result.active_npcs = [
                npc_id for npc_id in result.active_npcs 
                if npc_id != self.world_data.player_character.name
            ]
            
            # Filter out player character from NPC reactions
            result.npc_reactions = [
                reaction for reaction in result.npc_reactions 
                if reaction.id != self.world_data.player_character.name
            ]
            
            # Update current location if changed
            if result.location_change:
                self.current_location = next(
                    (loc for loc in self.world_data.locations if loc.id == result.location_change),
                    self.current_location
                )
            
            self.story_context.append({
                "location": self.current_location.id,
                "scene": result.model_dump()
            })
            
            return result
        except Exception as e:
            print("\n=== Story Beat Parsing Error ===")
            print(f"Error type: {type(e)}")
            print(f"Error message: {str(e)}")
            raise
    
    def _build_context(self, relevant_npcs: List[NPCModel]) -> str:
        """Build detailed context for the story generation"""
        recent_events = "\n".join([
            f"Location: {event['location']}"
            f"\nScene: {event['scene']['narrative']}"
            for event in self.story_context[-3:]
        ])
        
        npc_attitudes = "\n".join([
            f"{npc.name}'s attitude: {self.world_state.npc_attitudes.get(npc.id, {}).get('player', 'neutral')}"
            for npc in relevant_npcs
        ])
        
        return f"""
        Recent Events:
        {recent_events}
        
        NPC Attitudes:
        {npc_attitudes}
        """

    def get_npc_response(self, npc_id: str, player_action: str) -> NPCResponseModel:
        """Generate an NPC's response to a player's action."""
        npc = next((npc for npc in self.world_data.npcs if npc.id == npc_id), None)
        if not npc:
            raise ValueError("Invalid NPC ID")
            
        npc_response_schema = NPCResponseModel.model_json_schema()
        
        prompt = f"""
        NPC Information:
        Name: {npc.name}
        Description: {npc.description}
        Personality: {npc.personality}
        Current Attitude: {self.world_state.npc_attitudes.get(npc.id, {}).get('player', 'neutral')}
        
        Player action/question: {player_action}
        
        The response must strictly follow the provided JSON schema format.
        """
        
        try:
            response = self._query_llm(prompt, npc_response_schema)
            print("\n=== Raw NPC Response ===")
            print(response)
            
            # Use Pydantic validation
            return NPCResponseModel.model_validate_json(response)
        except Exception as e:
            print("\n=== NPC Response Parsing Error ===")
            print(f"Error type: {type(e)}")
            print(f"Error message: {str(e)}")
            raise

    def _format_relevant_npcs(self, npcs: List[NPCModel]) -> str:
        """Format relevant NPC information for prompts"""
        npc_info = []
        for npc in npcs:
            npc_info.append(
                f"- {npc.name}: {npc.description}\n"
                f"  Personality: {npc.personality}\n"
                f"  Current Attitude: {self.world_state.npc_attitudes.get(npc.id, {}).get('player', 'neutral')}"
            )
        return "\n".join(npc_info)

if __name__ == "__main__":
    # Test the story engine
    generator = WorldGenerator()
    world = generator.generate_world("A small fantasy kingdom with a mysterious forest")
    engine = StoryEngine(world)
    
    # Start the story at the first location
    first_location = world.locations[0].id
    opening_scene = engine.start_story(first_location)
    print(json.dumps(opening_scene, indent=2)) 