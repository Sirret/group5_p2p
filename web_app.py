from flask import Flask, render_template, request, jsonify, session
import threading
import time
import secrets
import uuid
import os
from werkzeug.utils import secure_filename
from client import MessengerClient

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

active_clients = {}
client_locks = {}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit


# File upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'doc', 'docx', 'zip'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if file and allowed_file(file.filename):
        original_name = secure_filename(file.filename)
        # Keep original name but add timestamp to avoid collision
        name_parts = original_name.rsplit('.', 1)
        unique_name = f"{int(time.time())}_{name_parts[0]}.{name_parts[1]}" if len(name_parts) > 1 else f"{int(time.time())}_{original_name}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        file.save(filepath)
        file_url = f"/api/download/{unique_name}"
        return jsonify({'fileUrl': file_url, 'filename': original_name})
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/api/download/<filename>')
def download_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)

def get_or_create_client():
    if 'client_id' not in session:
        session['client_id'] = str(uuid.uuid4())
    client_id = session['client_id']
    return active_clients.get(client_id)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    registry_ip = data.get('registry_ip', '127.0.0.1')
    registry_port = data.get('registry_port', 5555)

    client_id = session.get('client_id')
    if not client_id:
        client_id = str(uuid.uuid4())
        session['client_id'] = client_id

    # Clean up old client if exists
    if client_id in active_clients:
        old = active_clients[client_id]
        old.running = False
        old.unregister()
        del active_clients[client_id]
        if client_id in client_locks:
            del client_locks[client_id]

    # Create new client
    client = MessengerClient(username, registry_host=registry_ip, registry_port=registry_port)
    active_clients[client_id] = client
    client_locks[client_id] = threading.Lock()

    # Start the client in web mode (no terminal input loop)
    # Use an event so we wait until registration actually completes
    registered_event = threading.Event()

    def start_web_client():
        try:
            client.register()
            registered_event.set()  # Signal that registration is done
            # Start listener thread
            listener = threading.Thread(target=client.start_listener, daemon=True)
            listener.start()
            # Start auto-refresh thread
            refresher = threading.Thread(target=client.auto_refresh_users, daemon=True)
            refresher.start()
            # Sync offline messages on startup
            client.sync_offline_messages()
            # Keep the thread alive (client.running controls exit)
            while client.running:
                time.sleep(1)
        except Exception as e:
            registered_event.set()  # Unblock even on failure
            print(f"Web client error for {username}: {e}")

    thread = threading.Thread(target=start_web_client, daemon=True)
    thread.start()
    registered_event.wait(timeout=5)  # Wait up to 5 seconds for real registration

    return jsonify({'status': 'connected', 'username': username})

@app.route('/api/users', methods=['GET'])
def get_users():
    client = get_or_create_client()
    if client:
        with client_locks.get(session.get('client_id'), threading.Lock()):
            online = list(client.online_users.keys())
            offline_known = [u for u in client.get_seen_users() if u not in online]
        return jsonify({'online': online, 'offline_known': offline_known})
    return jsonify({'online': [], 'offline_known': []})

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    client = get_or_create_client()
    if client:
        client_id = session.get('client_id')
        with client_locks.get(client_id, threading.Lock()):
            client.graceful_exit()
        # Clean up
        if client_id in active_clients:
            del active_clients[client_id]
        if client_id in client_locks:
            del client_locks[client_id]
        return jsonify({'status': 'disconnected'})
    return jsonify({'error': 'No client'}), 400

@app.route('/api/send', methods=['POST'])
def send():
    client = get_or_create_client()
    if not client:
        return jsonify({'error': 'Not registered'}), 400

    data = request.json
    to_user = data.get('to')
    text = data.get('message')

    with client_locks.get(session.get('client_id'), threading.Lock()):
        success = client.send_message(to_user, text)
    # Optionally detect if recipient was offline (client.send_message returns True even when stored)
    return jsonify({'success': success})

@app.route('/api/messages', methods=['GET'])
def get_messages():
    client = get_or_create_client()
    if client:
        with client_locks.get(session.get('client_id'), threading.Lock()):
            msgs = client.get_web_messages()
        return jsonify({'messages': msgs})
    return jsonify({'messages': []})

@app.route('/api/sync', methods=['POST'])
def sync():
    client = get_or_create_client()
    if client:
        with client_locks.get(session.get('client_id'), threading.Lock()):
            synced_msgs = client.sync_offline_messages()
        # The messages are already added to web_message_buffer,
        # but we can also return them directly for immediate display
        return jsonify({'status': 'synced', 'messages': synced_msgs})
    return jsonify({'error': 'No client'}), 400

@app.route('/api/status', methods=['GET'])
def status():
    client = get_or_create_client()
    return jsonify({'connected': client is not None, 'running': client.running if client else False})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)