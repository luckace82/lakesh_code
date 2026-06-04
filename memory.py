import json, os

MEMORY_FILE = '.agent_memory.json'

def load_memory():
    if os.path.exists(MEMORY_FILE):
        return json.load(open(MEMORY_FILE))
    return {}

def save_memory(data):
    existing = load_memory()
    existing.update(data)
    json.dump(existing, open(MEMORY_FILE,'w'), indent=2)
