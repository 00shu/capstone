# story_engine.py
import requests
import json # Keep json import here for potential use within the engine
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

# Import the models defined above (or from models.py)
from models import (
    WorldModel, WorldState, LocationModel, NPCModel, PlayerCharacterModel,
    NPCReactionModel, GameMasterBeatModel, DirectNPCResponseModel
)
# Assuming WorldGenerator is in a separate file
# from world_generator import WorldGenerator

# --- Constants ---
MAX_HISTORY_EVENTS_BEFORE_SUMMARY = 5
MAX_SUMMARY_TOKENS = 300 # Adjust based on LLM context window and desired summary length

class StoryEngine:
    def __init__(self, world_data: WorldModel, ollama_url: str = "http://localhost:11434", model: str = "rolandroland/llama3.1-uncensored"):
        self.world_data = world_data
        self.ollama_url = ollama_url
        self.model = model
        self.current_location: Optional[LocationModel] = None
        self.player = world_data.player_character

        # --- MODIFIED WorldState Initialization ---
        # 1. Initialize WorldState *without* passing known_npcs initially.
        #    It will use the default {} from the model definition.
        #    Also fix the f-string access for world_name.
        self.world_state = WorldState(
            # known_npcs field will use its default {}
            npc_attitudes={}, # Initialize attitudes later if needed
            location_states={loc.id: {
                "visited": False,
                "plot_status": loc.plot.status
            } for loc in world_data.locations},
            current_summary=f"The adventure begins in the world of {world_data.world_name}.", # Corrected world_name access
            full_event_log=[]
        )

        # 2. Now, directly assign the correctly typed dictionary to the field.
        #    This bypasses the validation issue during the initial WorldState instantiation.
        self.world_state.known_npcs = {npc.id: npc for npc in world_data.npcs}
        # --- End of Modification ---


        # Initialize attitudes (optional: start neutral) - Keep this part
        for npc_id in self.world_state.known_npcs:
             # Ensure the npc_id entry exists before adding the target
             if npc_id not in self.world_state.npc_attitudes:
                  self.world_state.npc_attitudes[npc_id] = {}
             self.world_state.npc_attitudes[npc_id][self.player.name] = "neutral"


    def _query_llm(self, prompt: str, json_model_class: Optional[type[BaseModel]] = None) -> Any:
        """Send a query to the Ollama LLM. Returns structured JSON if json_model_class is provided, otherwise raw string."""
        request_data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
             "options": { # Example options, adjust as needed
                "temperature": 0.7,
                "top_p": 0.9,
            }
        }
        if json_model_class:
            request_data["format"] = "json"
            # Add schema context to prompt for better adherence (optional but recommended)
            schema_json = json.dumps(json_model_class.model_json_schema(), indent=2)
            prompt += f"\n\nIMPORTANT: Respond STRICTLY in the following JSON format:\n```json\n{schema_json}\n```"
            request_data["prompt"] = prompt # Update prompt in request data

        print(f"\n--- Sending Prompt to LLM ({'JSON Mode' if json_model_class else 'Text Mode'}) ---\n{prompt}\n---------------------------\n")

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=request_data,
                #timeout=120 # Add a timeout
            )
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            raw_response_data = response.json()

            if json_model_class:
                 # Ollama often returns JSON as a string within the 'response' field
                try:
                    json_response_str = raw_response_data["response"]
                    # Basic cleaning (sometimes helpful)
                    json_response_str = json_response_str.strip().lstrip('```json').rstrip('```')
                    parsed_json = json.loads(json_response_str)
                    # Validate with Pydantic
                    validated_data = json_model_class.model_validate(parsed_json)
                    print(f"\n--- Received Validated JSON from LLM ---\n{validated_data.model_dump_json(indent=2)}\n-----------------------------------\n")
                    return validated_data
                except json.JSONDecodeError as json_err:
                    print(f"\n--- LLM JSON Parsing Error ---")
                    print(f"Raw Response: {raw_response_data.get('response', 'N/A')}")
                    print(f"Error: {json_err}")
                    raise ValueError(f"LLM response was not valid JSON: {json_err}") from json_err
                except Exception as pyd_err: # Catch Pydantic validation errors too
                     print(f"\n--- LLM JSON Validation Error ---")
                     print(f"Parsed JSON attempt: {parsed_json}")
                     print(f"Error: {pyd_err}")
                     raise ValueError(f"LLM JSON did not match schema: {pyd_err}") from pyd_err
            else:
                # Return raw text response
                text_response = raw_response_data.get("response", "").strip()
                print(f"\n--- Received Text from LLM ---\n{text_response}\n---------------------------\n")
                return text_response

        except requests.exceptions.RequestException as req_err:
            print(f"Error connecting to Ollama: {req_err}")
            raise ConnectionError(f"Failed to connect to Ollama at {self.ollama_url}") from req_err
        except Exception as e:
            print(f"An unexpected error occurred during LLM query: {e}")
            raise

    def _update_and_summarize_history(self, player_action: Optional[str], result_data: Any):
        """Adds the latest turn to the log and triggers summarization if needed."""
        event = {
            "location_id": self.current_location.id if self.current_location else "None",
            "player_action": player_action,
            "outcome": result_data.model_dump() if isinstance(result_data, BaseModel) else str(result_data) # Store Pydantic data or string
        }
        self.world_state.full_event_log.append(event)

        # Summarize if log is long enough
        if len(self.world_state.full_event_log) % MAX_HISTORY_EVENTS_BEFORE_SUMMARY == 0:
            print("\n--- Summarizing History ---")
            recent_events_text = "\n".join([
                f"Player: {ev['player_action']}\nResult: {json.dumps(ev['outcome'])}"
                for ev in self.world_state.full_event_log[-MAX_HISTORY_EVENTS_BEFORE_SUMMARY:]
            ])

            prompt = f"""
            Current Story Summary:
            {self.world_state.current_summary}

            Recent Events:
            {recent_events_text}

            Based on the current summary and recent events, provide an updated, concise summary of the story so far.
            Focus on key plot points, character interactions, player goals, and location changes.
            Keep the summary under {MAX_SUMMARY_TOKENS} words.
            """
            try:
                self.world_state.current_summary = self._query_llm(prompt, json_model_class=None) # Get text summary
                print(f"--- New Summary ---\n{self.world_state.current_summary}\n-------------------")
            except Exception as e:
                print(f"Failed to summarize history: {e}. Continuing with old summary.")


    def _get_location_context(self) -> str:
        """Generates context string for the current location."""
        if not self.current_location:
            return "Player is not currently in a known location."

        loc = self.current_location
        loc_state = self.world_state.location_states.get(loc.id, {})
        visited_str = "You have been here before." if loc_state.get("visited") else "This is your first time here."

        present_npcs = loc.primary_npcs + loc.secondary_npcs
        npc_details = []
        for npc_id in present_npcs:
            npc = self.world_state.known_npcs.get(npc_id)
            if npc:
                 attitude = self.world_state.npc_attitudes.get(npc_id, {}).get(self.player.name, "neutral")
                 npc_details.append(f"- {npc.name} ({npc.description}, Personality: {npc.personality}, Attitude towards {self.player.name}: {attitude})")

        return f"""
        Current Location: {loc.name} ({loc.type}) - {visited_str}
        Description: {loc.description}
        Current Plot: '{loc.plot.title}' ({loc.plot.status}) - {loc.plot.description}
        Key Plot NPCs: {', '.join(loc.plot.key_npcs)}
        Other NPCs Present:
        {chr(10).join(npc_details) if npc_details else "- None"}
        Connected Locations: {', '.join([l.name for l_id in loc.connected_to for l in self.world_data.locations if l.id == l_id])}
        """

    def start_story(self, starting_location_id: str) -> GameMasterBeatModel:
        """Initializes the story at a specific location."""
        found_location = next((loc for loc in self.world_data.locations if loc.id == starting_location_id), None)

        if not found_location:
            raise ValueError(f"Invalid starting location ID: '{starting_location_id}'")

        self.current_location = found_location
        self.world_state.location_states[found_location.id]["visited"] = True # Mark as visited

        print(f"\n=== Starting Story at {self.current_location.name} ===")

        # Generate the very first beat using the GM function with no initial player action
        initial_beat = self.generate_story_beat(player_action="look around and observe the surroundings") # Give a default starting action
        # Reset the summary to something more fitting *after* the first beat is generated if needed
        # self.world_state.current_summary = f"The adventure started for {self.player.name} in {self.current_location.name}."
        # self._update_and_summarize_history(None, initial_beat) # Log the start

        return initial_beat


    def generate_story_beat(self, player_action: Optional[str]) -> GameMasterBeatModel:
        """
        Acts as the Game Master. Takes player action, queries LLM, and returns the next story beat.
        """
        if not self.current_location:
            raise RuntimeError("Cannot generate beat, player is not in a location.")

        location_context = self._get_location_context()

        prompt = f"""
        You are the Game Master (GM) for a text-based fantasy adventure game.
        Your role is to narrate the story, describe the world, control NPC reactions, and guide the player ({self.player.name}, {self.player.description}, Personality: {self.player.personality}).

        Current World State Summary:
        {self.world_state.current_summary}

        Current Scene Details:
        {location_context}

        Player's Action: {player_action if player_action else "(No action specified, describe the current scene and offer choices)"}

        Instructions:
        1.  **Narrate:** Describe what happens as a result of the player's action. Update the scene description based on the action and location context. If no action was given, describe the initial scene vividly.
        2.  **NPC Reactions:** Determine which NPCs present would realistically react to the player's action or the situation. Generate their reactions (dialogue and non-verbal descriptions) considering their personality, attitude towards the player, and the location's plot. Only include reactions if relevant and impactful. Ensure `npc_id` is correct.
        3.  **Environment:** Note any significant changes or details in the environment.
        4.  **Plot:** Mention any progress or changes related to the location's plot ('{self.current_location.plot.title}'). Provide a brief `plot_update` description if something significant changes.
        5.  **Location Change:** If the action plausibly leads to a connected location, set `location_change` to the *ID* of the new location. Otherwise, keep it null.
        6.  **Suggest Actions:** Provide 2-4 diverse and engaging suggested actions the player could take next based on the current situation, narrative, and plot.
        7.  **Be Creative:** Make the story engaging, consistent, and responsive.

        Response Format: Generate a JSON object strictly adhering to the GameMasterBeatModel schema.
        """

        # Query the LLM, expecting a GameMasterBeatModel object
        try:
             beat_result = self._query_llm(prompt, json_model_class=GameMasterBeatModel)
        except (ValueError, ConnectionError) as e:
             # Handle LLM errors gracefully, maybe return a default error beat
             print(f"Error generating story beat: {e}")
             # You might want to return a cached state or a generic error message beat
             # For simplicity, we re-raise here, but a real game might handle it differently
             raise RuntimeError("Failed to generate the next story beat from the LLM.") from e


        # --- Post-processing the result ---
        # Fill in NPC names for reactions
        present_npc_ids = set(self.current_location.primary_npcs + self.current_location.secondary_npcs)
        valid_reactions = []
        for reaction in beat_result.npc_reactions:
            if reaction.npc_id in self.world_state.known_npcs and reaction.npc_id in present_npc_ids:
                 reaction.npc_name = self.world_state.known_npcs[reaction.npc_id].name
                 valid_reactions.append(reaction)
            else:
                 print(f"Warning: LLM generated reaction for unknown or absent NPC ID: {reaction.npc_id}. Ignoring.")
        beat_result.npc_reactions = valid_reactions


        # Update world state based on the beat
        if beat_result.location_change:
            new_location = next((loc for loc in self.world_data.locations if loc.id == beat_result.location_change), None)
            if new_location and new_location.id in [l.id for l in self.world_data.locations if l.id in self.current_location.connected_to]:
                print(f"Changing location from {self.current_location.name} to {new_location.name}")
                self.current_location = new_location
                self.world_state.location_states[new_location.id]["visited"] = True
                 # Reset summary slightly on location change? Optional.
                 # self.world_state.current_summary += f"\n{self.player.name} has arrived in {self.current_location.name}."
            else:
                 print(f"Warning: LLM suggested invalid location change to '{beat_result.location_change}'. Ignoring.")
                 beat_result.location_change = None # Correct the beat data

        if beat_result.plot_update:
            # You might want more sophisticated plot state tracking here
             self.world_state.location_states[self.current_location.id]["plot_status"] = beat_result.plot_update # Simplistic update


        # Update attitudes based on reactions (simplified example)
        for reaction in beat_result.npc_reactions:
             # Simple check: if message sounds negative/positive, adjust attitude slightly
             # A more robust method would involve another LLM call or sentiment analysis
             if any(neg in reaction.message.lower() for neg in ["stop", "idiot", "threat", "leave"]):
                 current_attitude = self.world_state.npc_attitudes.get(reaction.npc_id, {}).get(self.player.name, "neutral")
                 # Simple transition: friendly -> neutral -> hostile
                 new_attitude = "hostile" if current_attitude == "neutral" else "neutral"
                 self.world_state.npc_attitudes[reaction.npc_id][self.player.name] = new_attitude
             elif any(pos in reaction.message.lower() for pos in ["thank", "friend", "help", "welcome"]):
                  current_attitude = self.world_state.npc_attitudes.get(reaction.npc_id, {}).get(self.player.name, "neutral")
                  new_attitude = "friendly" if current_attitude == "neutral" else current_attitude # Stay friendly/hostile if already set
                  self.world_state.npc_attitudes[reaction.npc_id][self.player.name] = new_attitude


        # Update history *after* processing the beat
        self._update_and_summarize_history(player_action, beat_result)

        # Filter present NPCs based on current location *after* potential move
        beat_result.present_npc_ids = [npc_id for npc_id in (self.current_location.primary_npcs + self.current_location.secondary_npcs) if npc_id in self.world_state.known_npcs]


        return beat_result


    def get_direct_npc_response(self, npc_id: str, player_dialogue: str) -> DirectNPCResponseModel:
        """Generates a direct response from a specific NPC."""
        npc = self.world_state.known_npcs.get(npc_id)
        if not npc:
            raise ValueError(f"Invalid NPC ID: {npc_id}")

        if npc_id not in (self.current_location.primary_npcs + self.current_location.secondary_npcs):
             raise ValueError(f"{npc.name} is not present here.")


        current_attitude = self.world_state.npc_attitudes.get(npc.id, {}).get(self.player.name, "neutral")

        prompt = f"""
        You are playing the role of the NPC: {npc.name}.
        Your Description: {npc.description}
        Your Personality: {npc.personality}
        Your Current Attitude towards {self.player.name}: {current_attitude}

        Story Context Summary:
        {self.world_state.current_summary}

        Current Location: {self.current_location.name}
        Location Plot: {self.current_location.plot.title} ({self.current_location.plot.status})

        {self.player.name} ({self.player.personality}) says to you: "{player_dialogue}"

        Instructions:
        Generate your response based on your personality, attitude, the context, and what the player said.
        Provide your spoken dialogue, an optional non-verbal action, and update your attitude if the interaction changes it.

        Response Format: Generate a JSON object strictly adhering to the DirectNPCResponseModel schema.
        """
        try:
             response_data = self._query_llm(prompt, json_model_class=DirectNPCResponseModel)
             # Update attitude in world state based on response
             if response_data.attitude != current_attitude:
                 self.world_state.npc_attitudes[npc.id][self.player.name] = response_data.attitude
                 print(f"Note: {npc.name}'s attitude changed to {response_data.attitude}")

             # Log this interaction
             self._update_and_summarize_history(f"Talk to {npc.name}: {player_dialogue}", response_data)

             return response_data
        except (ValueError, ConnectionError) as e:
             print(f"Error getting NPC response: {e}")
             raise RuntimeError("Failed to get NPC response from the LLM.") from e