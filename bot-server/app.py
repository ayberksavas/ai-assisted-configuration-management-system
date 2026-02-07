import requests
import jsonschema
import argparse
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Endpoints for internal services (Docker service names)
SCHEMA_URL = "http://schema-server:5001"
VALUES_URL = "http://values-server:5002"
OLLAMA_URL = "http://ollama:11434/api/generate"

def ask_ollama(prompt):
    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False,
        "options": {
              "num_ctx": 16384,
              "num_predict": -1  
        }
    }
    response = requests.post(OLLAMA_URL, json=payload)
    return response.json().get("response", "").strip()

@app.route('/message', methods=['POST'])
def handle_message():
    user_input = request.json.get("input")
    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    # 1. Identify the App
    app_prompt = (
        f"User request: '{user_input}'\n\n"
        "Which application is the user referring to?\n"
        "Options: chat, matchmaking, tournament\n"
        "Reply with ONLY ONE WORD - the application name, nothing else."
    )
    app_name = ask_ollama(app_prompt).lower()
    print(f"Stage 1 - LLM returned app_name: {app_name}", flush=True)
    for name in ["chat", "matchmaking", "tournament"]:
        if name in app_name:
            app_name = name
            break

    # 2. Fetch Schema and Current Values
    try:
        schema_res = requests.get(f"{SCHEMA_URL}/{app_name}")
        values_res = requests.get(f"{VALUES_URL}/{app_name}")
        
        if schema_res.status_code != 200 or values_res.status_code != 200:
            return jsonify({"error": f"Could not find data for app: {app_name}"}), 404
            
        schema = schema_res.json()
        current_values = values_res.json()
    except Exception as e:
        return jsonify({"error": f"Internal service error: {str(e)}"}), 500

    # 3. Modify Config
    # Note: Schema is fetched for validation but not sent to LLM to avoid context overflow.
    # Full schema (~1500 lines) caused unreliable outputs; validation happens post-generation.
    modify_prompt = (
        f"User request: {user_input}\n\n"
        f"Current configuration JSON:\n{json.dumps(current_values, indent=2)}\n\n"
        "Based on the user request, determine:\n"
        "1. Which field needs to be changed (as a dot-separated path)\n"
        "2. What the new value should be (extract from user request)\n\n"
        "Return ONLY a JSON object with 'path' and 'value' fields.\n"
        "Example: {\"path\": \"workloads.deployments.chat.containers.chat.resources.memory.limitMiB\", \"value\": 1024}\n"
        "Output:"
    )
    modified_json_str = ask_ollama(modify_prompt)
    modified_json_str = modified_json_str.strip()
    if modified_json_str.startswith("```"):
        lines = modified_json_str.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        modified_json_str = "\n".join(lines)

    print(f"Stage 2 - LLM returned: {modified_json_str}", flush=True)

    # Parse the change instruction
    try:
        change = json.loads(modified_json_str)
        path = change["path"]
        value = change["value"]
        # Convert string numbers to int/float
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        elif isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                pass  # Keep as string if not a number


        # Apply the change to current_values
        keys = path.split(".")
        obj = current_values
        for key in keys[:-1]:
            obj = obj[key]
        obj[keys[-1]] = value

        # Validate and return
        jsonschema.validate(instance=current_values, schema=schema)
        return jsonify(current_values)

    except jsonschema.exceptions.ValidationError as ve:
        return jsonify({"error": "Modified config failed schema validation", "details": ve.message}), 422
    except Exception as e:
        print(f"Error: {e}", flush=True)
        return jsonify({"error": "Failed to parse or apply LLM response", "details": str(e)}), 500

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot Server")
    parser.add_argument("--listen", type=str, default="0.0.0.0:5003", help="host:port to listen on")
    args = parser.parse_args()

    host, port = args.listen.split(":")
    app.run(host=host, port=int(port))