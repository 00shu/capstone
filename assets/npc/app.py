from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO, emit
import json
import os
from main import GameEngine, PlayerCharacter

app = Flask(__name__, static_folder='assets')
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app)

# Initialize game engine
with open("world_content.json", "r", encoding="utf-8") as f:
    world_content = json.load(f)

# Global game state
game_engine = None
llm_status = {"is_processing": False, "last_response": None}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

@app.route('/start_game', methods=['POST'])
def start_game():
    global game_engine
    data = request.json
    player_name = data.get('player_name')
    player_role = data.get('player_role')
    
    player = PlayerCharacter(player_name, player_role)
    game_engine = GameEngine(world_content, player)
    game_engine.start_game()
    
    # Get initial game state
    game_state = {
        'current_location': {
            'name': game_engine.current_location['name'],
            'visual_description': game_engine.current_location['visual_description'],
            'connections': game_engine.current_location.get('connections', []),
            'npcs': game_engine.current_location.get('npcs', [])
        },
        'event_summary': game_engine.event_summary,
        'player': {
            'name': player.name,
            'role': player.role
        },
        'narrative': f"Welcome to {game_engine.current_location['name']}. {game_engine.current_location['visual_description']}",
        'available_npcs': game_engine.current_location.get('npcs', []),
        'default_choices': game_engine.generate_default_choices("Start game")
    }
    
    return jsonify(game_state)

@app.route('/process_input', methods=['POST'])
def process_input():
    data = request.json
    player_input = data.get('input')
    
    if not game_engine:
        return jsonify({'error': 'Game not started'}), 400
    
    try:
        llm_status["is_processing"] = True
        output = game_engine.process_player_input(player_input)
        return jsonify(output)
    except Exception as e:
        print(f"Error processing input: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        llm_status["is_processing"] = False
        llm_status["last_response"] = output if 'output' in locals() else None

@app.route('/handle_talk', methods=['POST'])
def handle_talk():
    data = request.json
    npc_index = data.get('npc_index')
    dialogue = data.get('dialogue')
    player_choice = data.get('player_choice')
    
    if not game_engine:
        return jsonify({'error': 'Game not started'}), 400
    
    try:
        llm_status["is_processing"] = True
        available_npcs = game_engine.current_location.get('npcs', [])
        output = game_engine.handle_talk_option(available_npcs, npc_index, dialogue, player_choice)
        return jsonify(output)
    except Exception as e:
        print(f"Error handling talk: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        llm_status["is_processing"] = False
        llm_status["last_response"] = output if 'output' in locals() else None

@app.route('/handle_move', methods=['POST'])
def handle_move():
    data = request.json
    connections = data.get('connections', [])
    
    if not game_engine:
        return jsonify({'error': 'Game not started'}), 400
    
    try:
        llm_status["is_processing"] = True
        output = game_engine.handle_move_option(connections)
        return jsonify(output)
    except Exception as e:
        print(f"Error handling move: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        llm_status["is_processing"] = False
        llm_status["last_response"] = output if 'output' in locals() else None

@app.route('/get_llm_status', methods=['GET'])
def get_llm_status():
    return jsonify(llm_status)

if __name__ == '__main__':
    # Create assets directory if it doesn't exist
    os.makedirs('assets/location', exist_ok=True)
    os.makedirs('assets/npc', exist_ok=True)
    socketio.run(app, debug=True) 