import json
import os
from datetime import datetime
import threading

# File to store offline messages
OFFLINE_FILE = "offline_messages.json"
FILE_LOCK = threading.Lock()

def init_storage():
    """Initialize the JSON file if it doesn't exist"""
    if not os.path.exists(OFFLINE_FILE):
        with open(OFFLINE_FILE, 'w') as f:
            json.dump({}, f)

def store_message(to_user, from_user, encrypted_text):
    """
    Store an encrypted message for an offline user.
    Structure: { "recipient": [{"from": "sender", "text": "...", "timestamp": "..."}] }
    """
    init_storage()
    with FILE_LOCK:
        with open(OFFLINE_FILE, 'r+') as f:
            data = json.load(f)
            if to_user not in data:
                data[to_user] = []
            data[to_user].append({
                "from": from_user,
                "text": encrypted_text,
                "timestamp": datetime.now().isoformat()
            })
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
    print(f"[📦] Stored offline message for {to_user}")

def fetch_messages(username):
    """
    Retrieve and remove all pending messages for a user.
    Returns list of messages (each is a dict with 'from', 'text', 'timestamp')
    """
    init_storage()
    with FILE_LOCK:
        with open(OFFLINE_FILE, 'r') as f:
            data = json.load(f)
        
        messages = data.pop(username, [])
        
        with open(OFFLINE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        return messages

def has_pending_messages(username):
    """Check if user has any offline messages"""
    init_storage()
    with FILE_LOCK:
        with open(OFFLINE_FILE, 'r') as f:
            data = json.load(f)
            return username in data and len(data[username]) > 0

def delete_all_for_user(username):
    """Utility: delete all messages for a user (if needed)"""
    init_storage()
    with FILE_LOCK:
        with open(OFFLINE_FILE, 'r') as f:
            data = json.load(f)
        if username in data:
            del data[username]
        with open(OFFLINE_FILE, 'w') as f:
            json.dump(data, f, indent=2)

# For quick testing (run standalone)
if __name__ == "__main__":
    # Test the offline queue
    store_message("bob", "alice", "encrypted_hello")
    store_message("bob", "carol", "encrypted_hi_there")
    print("Pending for bob:", fetch_messages("bob"))
    print("Pending for bob again (should be empty):", fetch_messages("bob"))