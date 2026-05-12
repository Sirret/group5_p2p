import socket
import threading
import json
import time
import signal
import sys
import encryption
# Import encryption and offline modules
from encryption import encrypt_message, decrypt_message
from offline_queue import store_message, fetch_messages, has_pending_messages

class MessengerClient:
    def __init__(self, username, registry_host='127.0.0.1', registry_port=5555):
        self.username = username
        self.registry_host = registry_host
        self.registry_port = registry_port
        self.online_users = {}  # {username: {'ip': ip, 'port': port}}
        self.listening_port = None
        self.running = True
        self.seen_users = set()  # To track users we've seen before
        self.web_message_buffer = []

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return '127.0.0.1'
    
    def find_available_port(self):
        for port in range(6000, 6100):  # Start at 6000 to avoid Flask (5000) and registry (5555)
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.bind(('0.0.0.0', port))
                test_sock.close()
                return port
            except:
                continue
        return 6000
    
    def register(self):
        self.listening_port = self.find_available_port()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.registry_host, self.registry_port))
        
        request = {
            'type': 'register',
            'username': self.username,
            'client_port': self.listening_port
        }
        sock.send(json.dumps(request).encode())
        
        response = json.loads(sock.recv(4096).decode())
        self.online_users = response['users']
        sock.close()
        
        print(f"[+] Registered as {self.username}")
        print(f"[+] Listening on port {self.listening_port}")
        print(f"[+] Online users: {list(self.online_users.keys())}")
    
    def unregister(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.registry_host, self.registry_port))
            request = {'type': 'unregister', 'username': self.username}
            sock.send(json.dumps(request).encode())
            sock.close()
            print(f"[✓] Unregistered {self.username}")
        except:
            pass
    
    def graceful_exit(self, signum=None, frame=None):
        print("\n[!] Shutting down...")
        self.unregister()
        self.running = False
        sys.exit(0)
    
    def start_listener(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', self.listening_port))
        server.listen(5)
        
        while self.running:
            try:
                server.settimeout(1.0)
                conn, addr = server.accept()
                data = conn.recv(4096).decode()
                message = json.loads(data)
                # Decrypt the message
                plaintext = decrypt_message(message['text'], encryption.SHARED_KEY)
                self.web_message_buffer.append({
                    'from': message['from'],
                    'text': plaintext,
                    'timestamp': time.time()
                })
                print(f"\n[📨 Message from {message['from']}]: {plaintext}")
                print(f"\n[You] (send: recipient: message) or /users: ", end='')
                conn.close()
            except socket.timeout:
                continue
            except Exception as e:
                pass
    # Add a method to fetch and clear buffer atomically
    def get_web_messages(self):
        msgs = self.web_message_buffer[:]
        del self.web_message_buffer[:]
        return msgs


    def send_message(self, to_user, text):
        # Refresh online users list (also updates seen_users)
        self.get_online_users()
        
        # Case 1: Recipient is currently online → send directly
        if to_user in self.online_users:
            recipient_ip = self.online_users[to_user]['ip']
            recipient_port = self.online_users[to_user]['port']
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((recipient_ip, recipient_port))
                encrypted = encrypt_message(text, encryption.SHARED_KEY)
                message = {'from': self.username, 'text': encrypted}
                sock.send(json.dumps(message).encode())
                sock.close()
                print(f"[✓] Message sent to {to_user}: {text}")
                return True
            except Exception as e:
                print(f"[!] Error sending to {to_user}: {e}")
                return False
        
        # Case 2: Recipient is known (was online before) but currently offline → store
        elif to_user in self.seen_users:
            encrypted = encrypt_message(text, encryption.SHARED_KEY)
            store_message(to_user, self.username, encrypted)
            print(f"[📦] {to_user} is offline. Message saved for later delivery.")
            return True
        
        # Case 3: Recipient has never been seen (never registered) → reject
        else:
            print(f"[!] User '{to_user}' does not exist or has never registered. Message not saved.")
            return False
    
    def get_online_users(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.registry_host, self.registry_port))
            request = {'type': 'get_users'}
            sock.send(json.dumps(request).encode())
            response = json.loads(sock.recv(4096).decode())
            self.online_users = response['users']
            sock.close()
        except:
            pass
        for user in self.online_users:
            self.seen_users.add(user)
        return self.online_users
    
    def get_seen_users(self):
        return list(self.seen_users)

    def sync_offline_messages(self):
        """Retrieve pending offline messages and add to web buffer"""
        if has_pending_messages(self.username):
            messages = fetch_messages(self.username)
            print(f"\n[📦] Retrieved {len(messages)} offline message(s):")
            delivered = []
            for msg in messages:
                plaintext = decrypt_message(msg['text'], encryption.SHARED_KEY)
                self.web_message_buffer.append({
                    'from': msg['from'],
                    'text': plaintext,
                    'timestamp': msg.get('timestamp', time.time()),
                    'offline': True
                })
                print(f"  From {msg['from']} at {msg['timestamp']}: {plaintext}")
                delivered.append({
                    'from': msg['from'],
                    'text': plaintext,
                    'timestamp': msg.get('timestamp', time.time())
                })
            print()
            return delivered
        else:
            print("[✓] No pending offline messages.")
            return []
    
    def auto_refresh_users(self):
        while self.running:
            time.sleep(10)
            self.get_online_users()
    
    def run(self):
        self.register()
        
        # Setup signal handlers for graceful exit
        signal.signal(signal.SIGINT, self.graceful_exit)
        signal.signal(signal.SIGTERM, self.graceful_exit)
        
        # Start listener thread
        listener_thread = threading.Thread(target=self.start_listener, daemon=True)
        listener_thread.start()
        
        # Start auto-refresh thread
        refresh_thread = threading.Thread(target=self.auto_refresh_users, daemon=True)
        refresh_thread.start()
        
        # Check for offline messages on startup
        self.sync_offline_messages()
        
        print("\n" + "="*50)
        print(f"Welcome {self.username} to UTG Messenger")
        print("Commands:")
        print("  /users      - Show online users")
        print("  /sync       - Fetch offline messages")
        print("  /quit       - Exit")
        print("  recipient: message - Send message")
        print("="*50 + "\n")
        
        while self.running:
            user_input = input("[You] ")
            
            if user_input.lower() == '/users':
                users = self.get_online_users()
                print(f"[+] Online users: {list(users.keys())}")
            elif user_input.lower() == '/sync':
                self.sync_offline_messages()
            elif user_input.lower() == '/quit':
                self.graceful_exit()
            elif ':' in user_input:
                recipient, message = user_input.split(':', 1)
                recipient = recipient.strip()
                message = message.strip()
                if recipient and message:
                    self.send_message(recipient, message)
                else:
                    print("[!] Both recipient and message required")
            else:
                print("[!] Format: recipient: message")

if __name__ == '__main__':
    username = input("Enter your username: ")
    client = MessengerClient(username)
    try:
        client.run()
    except KeyboardInterrupt:
        client.graceful_exit()