import os
import json
import argparse
from flask import Flask, jsonify, abort

app = Flask(__name__)


@app.route('/<app_name>',methods=['GET'])
def get_schema(app_name):
    # 1. Construct the file path
    file_name= f"{app_name}.schema.json"
    file_path = os.path.join(app.config['SCHEMA_DIR'], file_name)

    # 2. Handle 404 if file doesn't exist
    if not os.path.exists(file_path):
        abort(404, description="Schema file not found")

    # 3. Read and return the JSON
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except json.JSONDecodeError:
        abort(500, description="Error parsing JSON file")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple Schema Server")
    
    # Define the arguments
    parser.add_argument("--schema-dir", type=str, default="/data/schemas", help="Directory containing JSON schemas")
    parser.add_argument("--listen", type=str, default="0.0.0.0:5001", help="host:port to listen on")
    
    args = parser.parse_args()

    # Store the directory in a way the route can access it
    app.config['SCHEMA_DIR'] = args.schema_dir
    # Split the listen argument into host and port
    try:
        host, port = args.listen.split(":")
        app.run(host=host, port=int(port))
    except ValueError:
        print("Error: --listen must be in format host:port (e.g., 127.0.0.1:8000)")