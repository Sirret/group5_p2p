# OS2 Messenger

A peer-to-peer messaging app that runs in your browser. Users connect directly to each other — no cloud, no accounts, just a local network.

## What it does

- Send and receive messages in real time through a web UI
- Messages are encrypted in transit (Fernet symmetric encryption)
- If a recipient is offline, their message is saved and delivered when they come back
- File sharing supported (images, PDFs, docs, zips — up to 16MB)

## Requirements

- Python 3.x
- Install dependencies:
  ```
  pip install flask cryptography
  ```

## How to run

**Windows** — double-click `runOs2.bat`. It opens two terminal windows (registry server + web app) and launches the browser automatically.

**Manual:**
```bash
# Terminal 1 — start the registry server
cd OS2
python server.py

# Terminal 2 — start the web app
cd OS2
python web_app.py
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

## Usage

1. Enter a username to connect
2. See who's online in the user list
3. Click a user and start chatting
4. Offline messages are delivered automatically when they reconnect

## Notes

- All users must be on the same network (or point to the same registry server IP)
- The registry runs on port `5555`, the web app on port `5000`
- The shared encryption key is hardcoded in `encryption.py` — change it before sharing with others
