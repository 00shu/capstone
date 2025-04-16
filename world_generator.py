import json
import re
import requests
from typing import List
from pydantic import BaseModel, ValidationError


# -----------------------------
# Pydantic Models for World JSON Schema
# -----------------------------
class NPC(BaseModel):
    name: str
    visual_description: str


class Location(BaseModel):
    name: str
    visual_description: str
    connections: List[str]
    npcs: List[NPC]
    plot: str


class WorldContent(BaseModel):
    locations: List[Location]


# -----------------------------
# LLM Client for API Integration via Ollama
# -----------------------------
class LLMClient:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model = "rolandroland/llama3.1-uncensored"

    def call_llm(self, prompt: str, format_schema: dict = None) -> str:
        """
        Sends a query to the Ollama LLM API and returns the generated response.
        This function attempts to extract a valid JSON snippet even if the response includes additional text or markdown formatting.
        """
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

        # Attempt to extract JSON enclosed in triple backticks with optional "json" marker
        json_match = re.search(r"```json\s*({.*})\s*```", raw_response, re.DOTALL)
        if json_match:
            extracted = json_match.group(1)
        else:
            # Fallback: extract from the first '{' to the last '}'
            start_index = raw_response.find('{')
            end_index = raw_response.rfind('}')
            if start_index != -1 and end_index != -1:
                extracted = raw_response[start_index:end_index + 1]
            else:
                extracted = raw_response  # If all fails, return the raw response

        return extracted


# -----------------------------
# World Content Generator Functions
# -----------------------------
def validate_world_json(data: dict) -> WorldContent:
    """
    Validates the provided world JSON data against the defined Pydantic models.
    
    Args:
        data (dict): World content JSON data.
    
    Returns:
        WorldContent: Validated world content.
    
    Raises:
        ValidationError: If the data does not meet the schema.
    """
    try:
        world_content = WorldContent(**data)
    except ValidationError as e:
        raise e
    return world_content


def generate_world_content() -> WorldContent:
    """
    Generates the game world's content by constructing a detailed prompt and calling the local LLM API.
    It then validates the returned JSON against the expected schema.
    
    Returns:
        WorldContent: The generated and validated world content.
    
    Raises:
        ValueError: If the LLM response cannot be parsed as valid JSON.
    """
    prompt = (
        "Generate a creative and rich JSON structure for a fantasy game world. "
        "The JSON should have the following format:\n\n"
        "{\n"
        '  "locations": [\n'
        "    {\n"
        '      "name": string,\n'
        '      "visual_description": string,\n'
        '      "connections": [string, string, ...],\n'
        '      "npcs": [\n'
        "        {\n"
        '          "name": string,\n'
        '          "visual_description": string\n'
        "        }\n"
        "      ],\n"
        '      "plot": string\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Ensure the output is strictly in JSON format without additional explanation or formatting."
    )

    llm_client = LLMClient()  # Use default ollama_url ("http://localhost:11434")
    llm_response = llm_client.call_llm(prompt)

    try:
        data = json.loads(llm_response)
    except json.JSONDecodeError as e:
        raise ValueError("LLM response is not valid JSON.") from e

    validated_world = validate_world_json(data)
    return validated_world

def save_world_content(world: WorldContent, filename: str = "world_content.json") -> None:
    """
    Saves the generated world content to a JSON file.
    
    Args:
        world (WorldContent): The validated world content.
        filename (str): The filename where the content will be saved.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            # For Pydantic V2, model_dump_json replaces the old json() method.
            f.write(world.model_dump_json(indent=2))
        print(f"World content saved to {filename}")
    except Exception as e:
        print(f"Error saving world content: {e}")

# -----------------------------
# Main Execution Block
# -----------------------------
if __name__ == "__main__":
    try:
        world = generate_world_content()
        # For Pydantic V2, use model_dump_json instead of json()
        print(world.model_dump_json(indent=2))
        save_world_content(world)
    except Exception as e:
        print(f"Error generating world content: {e}")
