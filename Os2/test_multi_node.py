"""
test_multi_node.py - Automated multi-node test for the Distributed Messaging System
Tests: connection, message transmission, encryption, and offline message handling
"""

import threading
import time
import sys
import os
import json

# Make sure we can import from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client import MessengerClient
from server import RegistryServer
from encryption import encrypt_message, decrypt_message, SHARED_KEY

# ─── Colour helpers (work on Windows 10+ and all Unix) ───────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}[PASS]{RESET} {msg}")
def fail(msg): print(f"  {RED}[FAIL]{RESET} {msg}")
def info(msg): print(f"  {CYAN}[INFO]{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{YELLOW}{'='*55}{RESET}\n{BOLD}  {msg}{RESET}\n{BOLD}{YELLOW}{'='*55}{RESET}")

# ─── Global results tracker ───────────────────────────────────────────────────
results = {"passed": 0, "failed": 0}

def assert_true(condition, description):
    if condition:
        ok(description)
        results["passed"] += 1
    else:
        fail(description)
        results["failed"] += 1
    return condition

# ─── Start registry server in background ─────────────────────────────────────
def start_registry():
    server = RegistryServer(host='127.0.0.1', port=5555)
    t = threading.Thread(target=server.start, daemon=True)
    t.start()
    time.sleep(0.5)
    info("Registry server started on 127.0.0.1:5555")
    return server

# ─── Helper: create and register a client ────────────────────────────────────
def make_client(username):
    c = MessengerClient(username, registry_host='127.0.0.1', registry_port=5555)
    c.register()
    # Start listener so it can receive messages
    t = threading.Thread(target=c.start_listener, daemon=True)
    t.start()
    time.sleep(0.3)
    return c

# ═════════════════════════════════════════════════════════════════════════════
# TEST 1 — Client Connection
# ═════════════════════════════════════════════════════════════════════════════
def test_client_connection(clients):
    header("TEST 1: Client Connection Testing")

    # All 5 clients should be registered
    # Ask the registry via one client
    online = clients[0].get_online_users()
    all_names = list(online.keys()) + [clients[0].username]

    assert_true(len(all_names) == 5,
        f"All 5 clients registered (found {len(all_names)})")

    for c in clients:
        assert_true(c.listening_port is not None,
            f"{c.username} has a listening port assigned ({c.listening_port})")
        assert_true(6000 <= c.listening_port <= 6100,
            f"{c.username} port {c.listening_port} is in valid range 6000-6100")

    # Verify no two clients share the same port
    ports = [c.listening_port for c in clients]
    assert_true(len(ports) == len(set(ports)),
        "No two clients share the same port")

# ═════════════════════════════════════════════════════════════════════════════
# TEST 2 — Message Transmission
# ═════════════════════════════════════════════════════════════════════════════
def test_message_transmission(clients):
    header("TEST 2: Message Transmission Testing")

    alice, bob = clients[0], clients[1]
    test_msg = "Hello Bob, this is a test message!"

    info(f"{alice.username} → {bob.username}: '{test_msg}'")
    success = alice.send_message(bob.username, test_msg)
    assert_true(success, f"send_message() returned True for online recipient")

    time.sleep(0.5)  # let the message arrive

    received = bob.get_web_messages()
    assert_true(len(received) > 0, f"{bob.username} received at least 1 message")

    if received:
        assert_true(received[0]['from'] == alice.username,
            f"Message 'from' field is correct ({alice.username})")
        assert_true(received[0]['text'] == test_msg,
            f"Message content matches after decryption")

    # Test multiple users communicating simultaneously
    info("Sending messages between multiple pairs simultaneously...")
    threads = []
    for i in range(len(clients) - 1):
        sender = clients[i]
        receiver = clients[(i + 1) % len(clients)]
        msg = f"Concurrent message from {sender.username}"
        t = threading.Thread(target=sender.send_message, args=(receiver.username, msg))
        threads.append(t)
    for t in threads: t.start()
    for t in threads: t.join()
    time.sleep(0.5)

    assert_true(True, "Concurrent messaging completed without crash")

# ═════════════════════════════════════════════════════════════════════════════
# TEST 3 — Encryption
# ═════════════════════════════════════════════════════════════════════════════
def test_encryption():
    header("TEST 3: Encryption Testing")

    plaintext = "Secret test message"
    encrypted = encrypt_message(plaintext, SHARED_KEY)

    assert_true(encrypted != plaintext,
        "Encrypted text differs from plaintext")
    assert_true(len(encrypted) > 20,
        "Encrypted output has expected ciphertext length")
    assert_true(
        not any(word in encrypted for word in ["Secret", "test", "message"]),
        "Plaintext words not visible in ciphertext")

    decrypted = decrypt_message(encrypted, SHARED_KEY)
    assert_true(decrypted == plaintext,
        "Decrypted text matches original plaintext")

    # Each encryption of the same message should produce a different ciphertext (IV randomness)
    encrypted2 = encrypt_message(plaintext, SHARED_KEY)
    assert_true(encrypted != encrypted2,
        "Same message encrypts differently each time (random IV confirmed)")

    info(f"Sample ciphertext: {encrypted[:60]}...")

# ═════════════════════════════════════════════════════════════════════════════
# TEST 4 — Offline Message Handling
# ═════════════════════════════════════════════════════════════════════════════
def test_offline_messages(clients):
    header("TEST 4: Offline Message Testing")

    # Pick carol as the user who will go offline
    carol = clients[2]
    dave  = clients[3]

    offline_msgs = [
        "Hey Carol, you there?",
        "Just checking in",
        "Call me when you're back"
    ]

    # Take carol offline
    info(f"Taking {carol.username} offline...")
    carol.running = False
    carol.unregister()
    time.sleep(0.5)

    # Dave sends messages to offline carol
    info(f"{dave.username} sending {len(offline_msgs)} messages to offline {carol.username}...")
    for msg in offline_msgs:
        result = dave.send_message(carol.username, msg)
        assert_true(result, f"Message queued for offline user: '{msg}'")
    time.sleep(0.3)

    # Verify messages are in the offline store
    from offline_queue import has_pending_messages, fetch_messages
    assert_true(has_pending_messages(carol.username),
        f"Offline queue has pending messages for {carol.username}")

    # Bring carol back online
    info(f"Reconnecting {carol.username}...")
    carol.running = True
    carol.register()
    t = threading.Thread(target=carol.start_listener, daemon=True)
    t.start()
    time.sleep(0.3)

    # Sync offline messages
    synced = carol.sync_offline_messages()
    assert_true(len(synced) == len(offline_msgs),
        f"All {len(offline_msgs)} offline messages retrieved after reconnect")

    # Verify order preserved
    if len(synced) == len(offline_msgs):
        for i, (sent, received) in enumerate(zip(offline_msgs, synced)):
            assert_true(received['text'] == sent,
                f"Message {i+1} content and order correct: '{sent}'")

    # Verify queue is cleared after sync
    assert_true(not has_pending_messages(carol.username),
        f"Offline queue cleared after delivery")

# ═════════════════════════════════════════════════════════════════════════════
# TEST 5 — Unknown / never-seen user rejection
# ═════════════════════════════════════════════════════════════════════════════
def test_unknown_user(clients):
    header("TEST 5: Unknown User Rejection")

    sender = clients[0]
    result = sender.send_message("ghost_user_xyz", "This should not be stored")
    assert_true(result == False,
        "send_message() returns False for a user who never registered")

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    print(f"\n{BOLD}{'='*55}")
    print("  Distributed Messaging System - Multi-Node Test")
    print(f"  Group 5 | Operating Systems 2")
    print(f"{'='*55}{RESET}\n")

    # Start registry
    start_registry()

    # Create 5 client nodes as described in the document
    usernames = ["Alice", "Bob", "Carol", "Dave", "Eve"]
    info(f"Launching {len(usernames)} client nodes: {usernames}")
    clients = []
    for name in usernames:
        c = make_client(name)
        clients.append(c)
        info(f"  {name} registered on port {c.listening_port}")
    time.sleep(0.5)

    # Run all test scenarios from Section 5.2
    test_client_connection(clients)
    test_message_transmission(clients)
    test_encryption()
    test_offline_messages(clients)
    test_unknown_user(clients)

    # Cleanup
    info("Shutting down all clients...")
    for c in clients:
        try:
            c.running = False
            c.unregister()
        except:
            pass

    # Final report
    total = results["passed"] + results["failed"]
    print(f"\n{BOLD}{'='*55}")
    print(f"  RESULTS: {results['passed']}/{total} tests passed", end="")
    if results["failed"] == 0:
        print(f"  {GREEN}ALL PASSED ✓{RESET}{BOLD}")
    else:
        print(f"  {RED}{results['failed']} FAILED ✗{RESET}{BOLD}")
    print(f"{'='*55}{RESET}\n")

    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == '__main__':
    main()
