
# Networked UNO integration (added files)

I added two new files to integrate network play:

- `server.py` — a simple TCP server that hosts an UnoGame and accepts multiple clients.
- `net_client.py` — a minimal terminal client that connects to the server and allows simple interaction.

How it works (prototype):
1. Start the server: `python3 server.py`
2. Connect two or more clients: `python3 net_client.py --host 127.0.0.1 --port 10000`
3. The server will start a local UnoGame with number of connected clients and drive turns.
4. Clients receive state snapshots and are prompted on their turn to play or draw.

Notes & next steps:
- This is a minimal prototype to demonstrate server/client integration. The original `uno.py` game logic is reused on the server side.
- Security, robustness, and full rule-validation on the client are intentionally simple; you may want to:
  - Use authentication and TLS.
  - Use a WebSocket or HTTP API for browser clients.
  - Send full player hand info only to the owning client (currently server only sends hand counts).
  - Improve serialization of cards and state.
- If you want, I can now:
  - Push these changes into the repository and run a basic smoke test.
  - Convert the protocol to WebSockets for browser-based clients.
  - Create a simple web UI (React) that connects via WebSocket.

