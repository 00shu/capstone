import json
import re
import requests
from typing import Dict, Any, List, Optional

# -----------------------------
# Player Character Definition
# -----------------------------
class PlayerCharacter:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    def __str__(self):
        return f"{self.name} ({self.role})"


# -----------------------------
# LLM Client for API Integration via Ollama
# -----------------------------
class LLMClient:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model = "rolandroland/llama3.1-uncensored"

    def call_llm(self, prompt: str, format_schema: dict = None) -> str:
        request_data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        if format_schema:
            request_data["format"] = format_schema
        response = requests.post(f"{self.ollama_url}/api/generate", json=request_data)
        response.raise_for_status()
        raw_response = response.json()["response"]
        json_match = re.search(r"```json\s*({.*})\s*```", raw_response, re.DOTALL)
        if json_match:
            extracted = json_match.group(1)
        else:
            start_index = raw_response.find('{')
            end_index = raw_response.rfind('}')
            if start_index != -1 and end_index != -1:
                extracted = raw_response[start_index:end_index + 1]
            else:
                extracted = raw_response
        return extracted


# -----------------------------
# Narrative Manager
# -----------------------------
class NarrativeManager:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def generate_narrative_segment(self, game_state: Dict[str, Any], player_input: str) -> str:
        available_npcs = game_state['location'].get('npcs', [])
        npc_context = ""
        if available_npcs:
            npc_context = "Available NPCs (for context only):\n"
            for npc in available_npcs:
                motive_text = f" | Motive: {npc.get('motive')}" if npc.get("motive") else ""
                npc_context += f"- {npc.get('name')}: {npc.get('visual_description', '')}{motive_text}\n"
        player_info = f"Player Character: {game_state['player'].name} ({game_state['player'].role})"
        plot_info = f"Plot: {game_state['location'].get('plot', 'No plot info provided')}\n"
        prompt = (
            "You are a creative Dungeon Master for a murder mystery game. Generate a concise and immersive narrative segment "
            "based solely on the following details. Do NOT include explicit dialogue or detailed NPC actions; only set the scene, "
            "and do not echo the player's dialogue.\n"
            f"{npc_context}\n"
            f"Location Description: {game_state['location'].get('visual_description', '')}\n"
            f"{plot_info}"
            f"Event Summary: {game_state.get('summary', '')}\n"
            f"{player_info}\n"
            f"Player Action (paraphrase if needed): {player_input}\n"
            "Keep it short and focused on advancing the scene, while subtly hinting at NPC motives."
        )
        llm_response = self.llm_client.call_llm(prompt)
        return f"Narrative: {llm_response}"

    def update_event_summary(self, event_summary: str, new_event: str) -> str:
        # Increase the maximum length to 2000 characters.
        updated_summary = new_event if not event_summary else f"{event_summary} | {new_event}"
        max_length = 2000
        if len(updated_summary) > max_length:
            updated_summary = updated_summary[-max_length:]
        return updated_summary

    def generate_followup_narrative(self, npc_responses: List[Dict[str, str]], previous_summary: str) -> str:
        prompt = (
            "Based on the following NPC interactions and the previous event summary, generate a concise follow-up narrative that updates "
            "the scene and reflects the characters' motives:\n"
            f"NPC Interactions: {npc_responses}\n"
            f"Event Summary: {previous_summary}\n"
            "Keep it short and focused on current developments.\n"
            "Don't repeat the original dialouges on the NPCs, and should focus on narrative of the NPCs reaction to each others dialouges"
        )
        llm_response = self.llm_client.call_llm(prompt)
        return f"Update: {llm_response}"

    def generate_dynamic_choices(self, game_state: Dict[str, Any], player_input: str) -> List[str]:
        plot_info = f"Plot: {game_state['location'].get('plot', '')}\n"
        prompt = (
            "Based on the following context, generate three distinct, concise, and creative action choices for the player. "
            "Output must be a valid JSON array of strings with no additional text.\n"
            f"Location Description: {game_state['location'].get('visual_description', '')}\n"
            f"{plot_info}"
            f"Event Summary: {game_state.get('summary', '')}\n"
            f"Player Action: {player_input}\n"
            "Example: [\"Explore the area\", \"Talk to someone\", \"Move to a new location\"]"
        )
        llm_response = self.llm_client.call_llm(prompt)
        try:
            choices = json.loads(llm_response)
            if isinstance(choices, list) and all(isinstance(choice, str) for choice in choices):
                return choices
            else:
                return []
        except Exception:
            return []

# -----------------------------
# Choice Manager
# -----------------------------
class ChoiceManager:
    def display_choices(self, choices: List[str]) -> None:
        print("\nYour choices:")
        for idx, choice in enumerate(choices, start=1):
            print(f"  {idx}. {choice}")

    def capture_player_choice(self, choices: List[str]) -> str:
        user_input = input("Enter your choice (number or custom option): ").strip()
        if user_input.isdigit():
            selection = int(user_input)
            if 1 <= selection <= len(choices):
                return choices[selection - 1]
            else:
                print("Choice number out of range; using your text as custom option.")
                return user_input
        else:
            return user_input if user_input else (choices[0] if choices else "")

# -----------------------------
# NPC Interaction Module
# -----------------------------
class NPCInteractionModule:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def determine_active_npcs(self, npcs: List[Dict[str, str]], narrative: str, player_action: str) -> List[Dict[str, str]]:
        # First try: direct reference.
        direct_matches = []
        for npc in npcs:
            npc_first = npc.get("name", "").split()[0].lower()
            if npc_first in player_action.lower():
                direct_matches.append(npc)
        if len(direct_matches) == 1:
            return direct_matches
        elif len(direct_matches) > 1:
            return direct_matches

        # Next: match using the narrative.
        active = []
        for npc in npcs:
            npc_first = npc.get("name", "").split()[0].lower()
            if npc_first in narrative.lower():
                active.append(npc)
        if active:
            filtered = []
            for npc in active:
                prompt = (
                    f"Based on the narrative context below, determine if the NPC '{npc.get('name')}' is still actively present for conversation "
                    "or is leaving/disengaged. Answer only with 'true' or 'false'.\n"
                    f"Narrative: {narrative}"
                )
                response = self.llm_client.call_llm(prompt)
                if "true" in response.lower():
                    filtered.append(npc)
            return filtered if filtered else active

        # Fallback: use LLM query.
        prompt = (
            "Based on the context below, decide which NPCs from the following list should interact with the player. "
            "Return a valid JSON array of NPC objects (each with 'name' and 'visual_description').\n\n"
            "Available NPCs:\n"
        )
        for npc in npcs:
            prompt += f"- {npc.get('name')}: {npc.get('visual_description')}\n"
        prompt += (
            f"\nNarrative: {narrative}\n"
            f"Player Action: {player_action}\n"
            "If no NPC should interact, return []."
        )
        llm_response = self.llm_client.call_llm(prompt)
        try:
            active_npcs = json.loads(llm_response)
            if isinstance(active_npcs, list):
                return active_npcs
            else:
                return []
        except Exception:
            return []

    def generate_npc_response(self, npc: Dict[str, str], dialogue: str, event_summary: str) -> Dict[str, str]:
        motive_text = ""
        if npc.get("motive"):
            motive_text = f"Motive: {npc.get('motive')}\n"
        # Now include the event summary in the prompt for deeper context.
        prompt = (
            "You are role-playing as an NPC in a murder mystery. The player has addressed you with the following dialogue:\n"
            f"'{dialogue}'\n"
            "Additionally, consider the current event summary in your response.\n"
            f"Current Event Summary: {event_summary}\n"
            "Based on your personality, visual description, and motive (if applicable), generate a structured JSON response with these keys:\n"
            "- name: Your full name.\n"
            "- action: A brief description of your physical behavior or gesture.\n"
            "- speech: Your spoken response addressing the player's dialogue, subtly reflecting your inner motive.\n"
            "Include the motive in your context if applicable. Output only a valid JSON object with these keys and no additional text.\n"
            f"NPC Name: {npc.get('name')}\n"
            f"Visual Description: {npc.get('visual_description', '')}\n"
            f"{motive_text}"
            "Example: {\"name\": \"Elara the Woodland Spirit\", \"action\": \"smiles mysteriously\", \"speech\": \"There are secrets I must keep...\"}"
        )
        llm_response = self.llm_client.call_llm(prompt)
        try:
            npc_reply = json.loads(llm_response)
            for key in ["name", "action", "speech"]:
                if key not in npc_reply:
                    npc_reply[key] = ""
            return npc_reply
        except Exception:
            return {
                "name": npc.get("name"),
                "action": "remains silent",
                "speech": "I have nothing to say at this moment."
            }

# -----------------------------
# Game Engine (Game Master)
# -----------------------------
class GameEngine:
    def __init__(self, world: Dict[str, Any], player: PlayerCharacter, ollama_url: str = "http://localhost:11434"):
        self.world = world
        self.current_location = None
        self.event_summary = ""
        self.player = player
        self.llm_client = LLMClient(ollama_url)
        self.narrative_manager = NarrativeManager(self.llm_client)
        self.choice_manager = ChoiceManager()
        self.npc_interaction = NPCInteractionModule(self.llm_client)

    def get_state_json(self) -> Dict[str, Any]:
        return {
            "current_location": {
                "name": self.current_location.get("name"),
                "visual_description": self.current_location.get("visual_description")
            },
            "event_summary": self.event_summary,
            "player": {
                "name": self.player.name,
                "role": self.player.role
            }
        }

    def start_game(self):
        if self.world.get("locations"):
            self.current_location = self.world["locations"][0]
            self.event_summary = f"Game started at {self.current_location['name']}."
            print(f"Starting game at: {self.current_location['name']}")
            print(f"Location description: {self.current_location['visual_description']}")
            print(f"Player Character: {self.player}")
        else:
            print("World content is empty. Unable to start the game.")

    def update_game_state(self, new_location_name: str = None, event: str = None):
        if new_location_name:
            for loc in self.world.get("locations", []):
                if loc["name"] == new_location_name:
                    self.current_location = loc
                    print(f"Location updated to: {new_location_name}")
                    break
        if event:
            self.event_summary = self.narrative_manager.update_event_summary(self.event_summary, event)
            print(f"Event summary updated: {self.event_summary}")

    def handle_talk_option(self, active_npcs: List[Dict[str, str]], npc_index: int, dialogue: str, player_choice: str) -> Dict[str, Any]:
        """
        Now receives:
        - active_npcs (the possible NPCs),
        - npc_index (which NPC the user chose in the main loop),
        - dialogue (what the user typed in the main loop).

        Returns NPC response data but does not prompt the user.
        """
        output = {}
        if not active_npcs:
            output["npc_responses"] = []
            output["followup"] = ""
            return output

        # Safely pick the user's selection
        if 0 <= npc_index < len(active_npcs):
            chosen_npc = active_npcs[npc_index]
        else:
            chosen_npc = active_npcs[0]

        # Generate NPC's response
        npc_reply = self.npc_interaction.generate_npc_response(chosen_npc, dialogue, self.event_summary)
        self.event_summary = self.narrative_manager.update_event_summary(
            self.event_summary, f"Player talked to {chosen_npc.get('name')}: {dialogue}"
        )
        followup = self.narrative_manager.generate_followup_narrative([npc_reply], self.event_summary)
        self.event_summary = self.narrative_manager.update_event_summary(
            self.event_summary, "Scene updated after NPC interaction."
        )

        output["npc_responses"] = [npc_reply]
        available_npcs = self.current_location.get("npcs", [])
        output["available_npcs"] = available_npcs
        output["followup"] = followup
        default_options = engine.generate_default_choices(player_choice)
        output["default_choices"] = default_options
        output["current_location"] = {
            "name": self.current_location.get("name"),
            "visual_description": self.current_location.get("visual_description")
        }
        print(json.dumps(output, indent=2))
        #engine.choice_manager.display_choices(default_options)
        next_choice = self.choice_manager.capture_player_choice(default_options)
        print(f"\nYou chose: {next_choice}")
        self.event_summary = self.narrative_manager.update_event_summary(self.event_summary, f"Player chose: {next_choice}")
        output["player_choice"] = next_choice
        output["event_summary"] = self.event_summary
        return output

    def handle_move_option(self, connections: List[str]) -> Dict[str, Any]:
        output = {}
        available_places = ""
        if not connections:
            print("No connected locations available.")
            output["narrative"] = ""
            return output

        #print("\nChoose a destination:")
        for idx, loc in enumerate(connections, start=1):
            available_places += f"  {idx}. {loc}\n"
        output["available_places"]= available_places
        print(json.dumps(output, indent=2))
        selection = input("Enter the number corresponding to your destination: ").strip()
        try:
            selected_index = int(selection) - 1
            if 0 <= selected_index < len(connections):
                chosen_location = connections[selected_index]
            else:
                print("Invalid selection. Defaulting to the first option.")
                chosen_location = connections[0]
        except ValueError:
            print("Invalid input. Defaulting to the first option.")
            chosen_location = connections[0]
        self.update_game_state(new_location_name=chosen_location, event=f"Moved to {chosen_location}")
        print(f"\nNew location: {chosen_location}")
        print(f"Location description: {self.current_location['visual_description']}")
        game_state = {"location": self.current_location, "summary": self.event_summary, "player": self.player}
        narrative = self.narrative_manager.generate_narrative_segment(game_state, "Arrived at new location")
        print("\n" + narrative)
        
        
        output = {}
        output["current_location"] = {
            "name": self.current_location.get("name"),
            "visual_description": self.current_location.get("visual_description")
        }
        output["narrative"] = narrative
        available_npcs = self.current_location.get("npcs", [])
        output["available_npcs"] = available_npcs
        default_options = engine.generate_default_choices(f"Move to {chosen_location}")
        output["default_choices"] = default_options
        print(json.dumps(output, indent=2))
        
        next_choice = self.choice_manager.capture_player_choice(default_options)
        print(f"\nYou chose: {next_choice}")
        self.event_summary = self.narrative_manager.update_event_summary(self.event_summary, f"Player chose: {next_choice}")
        output["player_choice"] = next_choice
        output["event_summary"] = self.event_summary
        
        
        return output
    def process_player_input(self, player_input: str) -> Dict[str, Any]:
        output = {}
        # Build the game state to pass into the narrative generator.
        game_state = {
            "location": self.current_location,
            "summary": self.event_summary,
            "player": self.player
        }
        
        # 1. Generate the narrative first
        narrative = self.narrative_manager.generate_narrative_segment(game_state, player_input)
        print("\nNarrative:")
        print(narrative)
        
        # (Optionally, if you want NPCs to respond automatically when NOT doing a talk/move command:)
        npc_responses = []
        followup = ""
        available_npcs = self.current_location.get("npcs", [])
        if not player_input.lower().startswith("talk to") and not player_input.lower().startswith("move to"):
            active_npcs = self.npc_interaction.determine_active_npcs(available_npcs, narrative, player_input)
            if active_npcs:
                for npc in active_npcs:
                    response = self.npc_interaction.generate_npc_response(npc, player_input, self.event_summary)
                    npc_responses.append(response)
                    print("\nNPC Response:")
                    print(f"  Name   : {response.get('name')}")
                    print(f"  Action : {response.get('action')}")
                    print(f"  Speech : {response.get('speech')}")
                followup = self.narrative_manager.generate_followup_narrative(npc_responses, self.event_summary)
                print("\nFollow-up:")
                print(followup)
                self.event_summary = self.narrative_manager.update_event_summary(self.event_summary, "Scene updated after NPC interaction.")
            else:
                print("\nNo NPC interacts at this moment.")
        else:
            # For commands like "talk to" or "move to", any additional actions (e.g. a detailed dialogue or NPC selection)
            # can be handled afterward (see main loop example below).
            pass

        # 2. Build default options list (always show choices after the narrative)
        default_options = ["Explore the area"]
        
        # If there are NPCs in the current location, add the talk option.
        if available_npcs:
            npc_names = ", ".join(npc.get("name", "Unknown") for npc in available_npcs)
            default_options.append(f"Talk to someone ({npc_names})")
        
        # If there are connected locations, add the move option.
        connections = self.current_location.get("connections", [])
        if connections:
            connected_str = ", ".join(connections)
            default_options.append(f"Move to a new location ({connected_str})")
        else:
            default_options.append("Move to a new location")
        
        # Add any dynamic choices from the LLM.
        dynamic_choices = self.narrative_manager.generate_dynamic_choices(game_state, player_input)
        for choice in dynamic_choices:
            if choice not in default_options:
                default_options.append(choice)

        # 3. Display the choices and capture one user input.
        
        
        # Return the complete cycle output.
        output["narrative"] = narrative
        output["npc_responses"] = npc_responses
        output["available_npcs"] = available_npcs
        output["followup"] = followup
        #output["active_npcs"] = active_npcs
        output["default_choices"] = default_options
        output["current_location"] = {
            "name": self.current_location.get("name"),
            "visual_description": self.current_location.get("visual_description")
        }
        self.choice_manager.display_choices(default_options)
        print(json.dumps(output, indent=2))
        next_choice = self.choice_manager.capture_player_choice(default_options)
        print(f"\nYou chose: {next_choice}")
        self.event_summary = self.narrative_manager.update_event_summary(self.event_summary, f"Player chose: {next_choice}")
        output["player_choice"] = next_choice
        output["event_summary"] = self.event_summary
        
        print(json.dumps(output, indent=2))
        return output
    
    def generate_default_choices(self, player_input: str) -> List[str]:
        """Generate a list of default choices based on the current location and event summary."""
        game_state = {"location": self.current_location,
                    "summary": self.event_summary,
                    "player": self.player}
        default_options = ["Explore the area"]
        
        # Add a talk option if there are NPCs in the current location.
        available_npcs = self.current_location.get("npcs", [])
        if available_npcs:
            npc_names = ", ".join(npc.get("name", "Unknown") for npc in available_npcs)
            default_options.append(f"Talk to someone ({npc_names})")
        
        # Add a move option for connected locations.
        connections = self.current_location.get("connections", [])
        if connections:
            connected_str = ", ".join(connections)
            default_options.append(f"Move to a new location ({connected_str})")
        else:
            default_options.append("Move to a new location")
        
        # Optionally include dynamic choices.
        dynamic_choices = self.narrative_manager.generate_dynamic_choices(game_state, player_input)
        for choice in dynamic_choices:
            if choice not in default_options:
                default_options.append(choice)
        
        return default_options


# -----------------------------
# Main Execution Block
# -----------------------------
if __name__ == "__main__":
    try:
        with open("world_content.json", "r", encoding="utf-8") as f:
            world_content = json.load(f)
    except FileNotFoundError:
        print("World content file not found. Ensure 'world_content.json' exists. Exiting game.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error loading world content: {e}")
        exit(1)

    player_name = input("Enter your character's name: ").strip()
    player_role = input("Enter your character's role (e.g., detective, journalist, etc.): ").strip()
    player = PlayerCharacter(player_name, player_role)

    engine = GameEngine(world_content, player)
    engine.start_game()

    # print("\nCurrent State:")
    # print(json.dumps(engine.get_state_json(), indent=2))

    # next_action = input("\nEnter your action (or type 'exit' to quit): ").strip()
    next_action = "Explore the area"
    while next_action.lower() != "exit":
        # Process the entered action (narrative, NPC responses, etc.)
        

        # Branch if the player chose a talk option.
        player_choice = next_action
        if player_choice.lower().startswith("talk to"):
            available_npcs = engine.current_location.get("npcs", [])
            if available_npcs:
                print("\nWho would you like to talk to?")
                for idx, npc in enumerate(available_npcs, start=1):
                    print(f"  {idx}. {npc.get('name')}")
                selection = input("Enter the number corresponding to the NPC: ").strip()
                try:
                    npc_index = int(selection) - 1
                    if not (0 <= npc_index < len(available_npcs)):
                        print("Invalid selection. Defaulting to the first NPC.")
                        npc_index = 0
                except ValueError:
                    print("Invalid input. Defaulting to the first NPC.")
                    npc_index = 0
                player_choice += f"{available_npcs[npc_index].get('name')}"
                dialogue = input(f"Enter your dialogue for {available_npcs[npc_index].get('name')}: ").strip()
                talk_result = engine.handle_talk_option(available_npcs, npc_index, dialogue, player_choice)
                # print("\nNPC Response from detailed talk:")
                # for reply in talk_result.get("npc_responses", []):
                #     print(json.dumps(reply, indent=2))
                #print("\nFollow-up:", talk_result.get("followup", ""))
                # default_options = engine.generate_default_choices(next_action)
                # engine.choice_manager.display_choices(default_options)
                next_action = talk_result.get("player_choice", "")
        
        # Branch if the player chose a move option.
        elif player_choice.lower().startswith("move to"):
            connections = engine.current_location.get("connections", [])
            if connections:
                # print("\nWhere do you want to go?")
                # for idx, loc in enumerate(connections, start=1):
                #     print(f"  {idx}. {loc}")
                # loc_choice_str = input("Enter the number corresponding to your destination: ").strip()
                # try:
                #     loc_index = int(loc_choice_str) - 1
                #     if not (0 <= loc_index < len(connections)):
                #         print("Invalid selection. Defaulting to the first option.")
                #         loc_index = 0
                # except ValueError:
                #     print("Invalid input. Defaulting to the first option.")
                #     loc_index = 0
                # chosen_location = connections[loc_index]
                output = engine.handle_move_option(connections)
                # engine.update_game_state(new_location_name=chosen_location, event=f"Moved to {chosen_location}")
                # default_options = engine.generate_default_choices(next_action)
                # engine.choice_manager.display_choices(default_options)
                # next_action = input("\nEnter your action (or type 'exit' to quit): ").strip()
                next_action = output.get("player_choice", "")
            else:
                print("No connected locations available.")
        
        # After handling any special branch, or if neither branch was taken, 
        # generate and display the default choices before the next input.
        
        else:
            #next_action = player_choice
            output = engine.process_player_input(next_action)
            next_action = output.get("player_choice", "")
            # next_action = input("\nEnter your action (or type 'exit' to quit): ").strip()


