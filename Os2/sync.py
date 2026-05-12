from offline_queue import fetch_messages, has_pending_messages
from encryption import decrypt_message, SHARED_KEY
import threading
import time

def sync_on_connect(client_instance):
    """
    Called when a user comes online.
    Retrieves offline messages and displays them.
    """
    username = client_instance.username
    if has_pending_messages(username):
        print(f"\n[📦] You have pending offline messages!")
        messages = fetch_messages(username)
        for msg in messages:
            plaintext = decrypt_message(msg['text'], SHARED_KEY)
            print(f"[📨 Offline from {msg['from']} at {msg['timestamp']}]: {plaintext}")
        print("\n[You] Continue chatting...")
    else:
        print("[✓] No pending offline messages.")

def periodic_sync_check(client_instance, interval=30):
    """
    Periodically check for new offline messages while online.
    Runs in a background thread.
    """
    def check_loop():
        while client_instance.running:
            time.sleep(interval)
            if has_pending_messages(client_instance.username):
                # We don't auto-fetch to avoid interrupting; just notify
                print(f"\n[🔔] New offline messages arrived! Type '/sync' to retrieve.")
                print("[You] ", end='', flush=True)
    thread = threading.Thread(target=check_loop, daemon=True)
    thread.start()
    return thread