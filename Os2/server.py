import socket
import threading
import json

class RegistryServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.online_users = {}  # {username: (ip, port)}
        self.lock = threading.Lock()
    
    def handle_client(self, conn, addr):
        """Handle each client connection"""
        try:
            data = conn.recv(4096).decode()
            request = json.loads(data)
            
            if request['type'] == 'register':
                username = request['username']
                client_port = request['client_port']
                client_ip = addr[0]  # Get IP from connection
                
                with self.lock:
                    self.online_users[username] = (client_ip, client_port)
                print(f"[+] {username} registered at {client_ip}:{client_port}")
                
                # Send back list of online users with their addresses
                users_info = {}
                with self.lock:
                    for user, (ip, port) in self.online_users.items():
                        if user != username:  # Don't include self
                            users_info[user] = {'ip': ip, 'port': port}
                
                response = {
                    'type': 'users',
                    'users': users_info
                }
                conn.send(json.dumps(response).encode())
                
            elif request['type'] == 'get_users':
                users_info = {}
                with self.lock:
                    for user, (ip, port) in self.online_users.items():
                        users_info[user] = {'ip': ip, 'port': port}
                
                response = {
                    'type': 'users',
                    'users': users_info
                }
                conn.send(json.dumps(response).encode())
                
            elif request['type'] == 'unregister':
                username = request['username']
                with self.lock:
                    if username in self.online_users:
                        del self.online_users[username]
                print(f"[-] {username} unregistered")
                
        except Exception as e:
            print(f"[!] Error: {e}")
        finally:
            conn.close()
    
    def start(self):
        """Start the registry server"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        print(f"[*] Registry server listening on {self.host}:{self.port}")
        
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=self.handle_client, args=(conn, addr))
            thread.start()

if __name__ == '__main__':
    server = RegistryServer()
    server.start()