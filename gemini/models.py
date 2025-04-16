# story_engine.py (or models.py)
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# --- Models from world_generator (assuming these exist) ---
class PlotModel(BaseModel):
    title: str
    description: str
    key_npcs: List[str]
    status: str # e.g., "Active", "Inactive", "Completed"

class NPCModel(BaseModel):
    id: str
    name: str
    description: str
    personality: str

class LocationModel(BaseModel):
    id: str
    name: str
    type: str
    description: str
    connected_to: List[str]
    primary_npcs: List[str]
    secondary_npcs: List[str]
    plot: PlotModel # Use the PlotModel here

class PlayerCharacterModel(BaseModel):
    name: str
    description: str
    personality: str

class WorldModel(BaseModel):
    world_name: str
    locations: List[LocationModel]
    npcs: List[NPCModel]
    player_character: PlayerCharacterModel

class WorldState(BaseModel):
    known_npcs: Dict[str, NPCModel] = {}
    npc_attitudes: Dict[str, Dict[str, str]] = {} # npc_id -> {target_id: attitude}
    location_states: Dict[str, Dict[str, Any]] = {} # loc_id -> {"visited": bool, "plot_status": str, ...}
    active_plots: List[str] = []
    completed_plots: List[str] = []
    current_summary: str = "The adventure is about to begin."
    full_event_log: List[Dict[str, Any]] = [] # Store detailed events
# --- End of assumed world_generator models ---


class NPCReactionModel(BaseModel):
    npc_id: str = Field(description="ID of the reacting NPC")
    npc_name: Optional[str] = Field(None, description="Name of the reacting NPC (filled by engine)")
    message: str = Field(description="What the NPC says or communicates")
    reaction_description: str = Field(description="How the NPC reacts non-verbally")

class GameMasterBeatModel(BaseModel):
    gm_narration: str = Field(description="The Game Master's narration of what happens and the current scene description.")
    present_npc_ids: List[str] = Field(description="List of IDs for NPCs currently present and relevant.")
    suggested_actions: List[str] = Field(description="A list of 2-4 suggested actions the player can take next.")
    npc_reactions: List[NPCReactionModel] = Field(description="List of reactions from NPCs to the player's last action or the unfolding events.")
    location_change: Optional[str] = Field(None, description="The ID of the new location if the player moved.")
    plot_update: Optional[str] = Field(None, description="A brief description of any significant change to the plot status or objectives.")
    environment_details: Optional[str] = Field(None, description="Any specific details about the environment worth noting.")

class DirectNPCResponseModel(BaseModel):
    dialogue: str = Field(description="NPC's spoken response")
    action: Optional[str] = Field(None, description="NPC's non-verbal action, if any")
    attitude: str = Field(description="NPC's current attitude toward player")