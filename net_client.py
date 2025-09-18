
#!/usr/bin/env python3
"""
Simple TCP client for the UNO server.
Run: python3 net_client.py --host HOST --port PORT
Interact via terminal prompts when it's your turn.
"""
import socket, argparse, json, threading, sys

def recv_loop(sock):
    buf = b""
    while True:
        data = sock.recv(4096)
        if not data:
            print("Server closed connection.")
            sys.exit(0)
        buf += data
        while b"\n" in buf:
            line, buf = buf.split(b"\n",1)
            try:
                msg = json.loads(line.decode())
            except Exception as e:
                print("Failed to parse:", e)
                continue
            handle(msg, sock)

my_index = None

def handle(msg, sock):
    global my_index
    t = msg.get("type")
    if t=="welcome":
        my_index = msg.get("player_index")
        print("Welcome! Your player index:", my_index)

    elif t=="state":
        state = msg.get("state")
        print("=== Game State ===")
        print("Current card:", state.get("current_card"))

    #  Show your hand if the server sent it
        if "your_hand" in state:
           print("Your hand:")
           for i, card in enumerate(state["your_hand"]):
              print(f"  {i}: {card}")


        print("Players:")
        for p in state.get("players",[]):
            print(" -", p.get("id"), "cards:", p.get("hand_count"))
        print("==================")

    elif t=="prompt":
      idx = msg.get("player_index")
      print(f"It's player {idx}'s turn.")

      # Only ask for input if this client is the current player
      if idx == my_index:
          me = input("Your action ([p]lay [d]raw): ").strip().lower()
          if me.startswith('p'):
            card_idx = int(input("Card index to play (0-based): ").strip())
            new_color = input("If wild, new color (red/yellow/green/blue) or blank: ").strip() or None
            print(f"[client] Sending play request for index {card_idx}")
            send(sock, {"type":"action","action":"play",
                "card_index":card_idx,"new_color":new_color})

          else:
              send(sock, {"type":"action","action":"draw"})
    elif t=="info":
        print("[info]", msg.get("text"))
    else:
        print("Unknown message", msg)

def send(sock, obj):
    data = json.dumps(obj) + "\n"
    sock.sendall(data.encode())

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=10000, type=int)
    args = parser.parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((args.host, args.port))
        print("Connected to server", args.host, args.port)
        recv_thread = threading.Thread(target=recv_loop, args=(s,), daemon=True)
        recv_thread.start()
        recv_thread.join()
