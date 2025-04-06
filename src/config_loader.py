import json

def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found. Please ensure it exists in the root directory.")
        return None
    except json.JSONDecodeError:
        print("Error: config.json is not valid JSON.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred loading config: {e}")
        return None 