
#!/usr/bin/env python3
"""
Simple TCP-based UNO server.
Protocol: JSON messages delimited by newline.
Message from server:
  {"type":"welcome","player_id":int}
  {"type":"state","state":{...}}  # full game state snapshot (dict)
  {"type":"prompt","player_id":int} # whose turn
  {"type":"info","text":"..."}
Message from client:
  {"type":"action","action":"play","card_index":int,"new_color":null}
  {"type":"action","action":"draw"}
  {"type":"action","action":"join"}
This is a minimal reference implementation to integrate into the provided uno.py game logic.
"""
import socket
import threading
import json
import traceback
import time
from uno import UnoGame, UnoPlayer, UnoCard

HOST = "0.0.0.0"
PORT = 10000
MIN_PLAYERS = 2
MAX_PLAYERS = 6
ACCEPT_TIMEOUT = 60  # seconds to wait for players

clients = []
client_locks = {}
client_names = {}

def send_json(conn, obj):
    data = json.dumps(obj, default=str) + "\n"
    conn.sendall(data.encode())

def recv_json(conn):
    buf = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        buf += chunk
        if b"\n" in buf:
            line, rest = buf.split(b"\n",1)
            return json.loads(line.decode())

def broadcast(obj):
    to_remove = []
    for c in clients:
        try:
            send_json(c, obj)
        except Exception:
            to_remove.append(c)
    for r in to_remove:
        try:
            clients.remove(r)
        except: pass

def handle_client(conn, addr, player_index):
    try:
        send_json(conn, {"type":"welcome","player_index":player_index})
        # simple loop: wait for actions sent by main thread handling turns.
        while True:
            msg = recv_json(conn)
            if msg is None:
                print("Client disconnected", addr)
                break
            # put message into a per-client queue stored in client_locks
            with client_locks[conn]["lock"]:
               client_locks[conn]["msg"] = msg

    except Exception as e:
        print("Client handler error:", e)
        traceback.print_exc()
    finally:
        conn.close()
        if conn in clients:
            clients.remove(conn)

def accept_clients(server_sock, timeout=ACCEPT_TIMEOUT):
    server_sock.settimeout(timeout)
    start = time.time()
    while True:
        try:
            conn, addr = server_sock.accept()
            print("Accepted", addr)
            clients.append(conn)
            client_locks[conn] = {"lock": threading.Lock(), "msg": None}
            idx = len(clients)-1
            client_names[conn] = f"Player{idx}"
            threading.Thread(target=handle_client, args=(conn,addr,idx), daemon=True).start()
            if len(clients) >= MAX_PLAYERS:
                break
        except socket.timeout:
            break
    return len(clients)


def snapshot_game(game, player_index=None):
    # produce a JSON-serializable snapshot
    state = {
        "players": [
            {"id": p.player_id or idx, "hand_count": len(p.hand)}
            for idx, p in enumerate(game.players)
        ],
        "current_card": str(game.current_card),
        "current_player_index": game.players.index(game.current_player),
        "is_active": game.is_active
    }

    # if a player index is given, also include their hand
    if player_index is not None:
        state["your_hand"] = [str(card) for card in game.players[player_index].hand]

    return state

def main():
    print("UNO TCP Server starting on port", PORT)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print("Listening. Waiting for players (min {}, max {})...".format(MIN_PLAYERS, MAX_PLAYERS))
        accept_clients(s)
        n = len(clients)
        if n < MIN_PLAYERS:
            print("Not enough players connected. Exiting.")
            return
        # create game
        game = UnoGame(n)
        # assign player ids to connected clients
        for i, conn in enumerate(clients):
            try:
                send_json(conn, {"type":"info","text":f"Game starting. You are Player {i}"})
            except:
                pass

        # main game loop
        while game.is_active:
            # broadcast state
            # Send tailored state to each player
            for i, conn in enumerate(clients):
               try:
                   state = snapshot_game(game, player_index=i)
                   send_json(conn, {"type":"state", "state":state})
               except:
                  pass

            current_idx = game.players.index(game.current_player)
            broadcast({"type":"prompt","player_index":current_idx})
            # find connection for this player (simple mapping by index)
            if current_idx >= len(clients):
                # AI: if no network client for this player, auto-play
                # choose first playable or draw
                player = game.current_player
                if player.can_play(game.current_card):
                    for i,card in enumerate(player.hand):
                        if game.current_card.playable(card):
                            game.play(player=player.player_id, card=i, new_color=(None if card.color!='black' else None))
                            break
                else:
                    game.play(player=player.player_id, card=None)
                continue
            conn = clients[current_idx]
            # wait for client's action (with timeout)
            waited = 0
            action = None
            while waited < 60:
               with client_locks[conn]["lock"]:
                  msg = client_locks[conn]["msg"]
                  client_locks[conn]["msg"] = None
               if msg:
                   action = msg
                   break
               time.sleep(0.5)
               waited += 0.5

            if not action:
                # timeout -> treat as draw
                send_json(conn, {"type":"info","text":"Turn timed out, drawing a card."})
                game.play(player=current_idx, card=None)
            else:
                try:
                    if action.get("type")=="action":
                        act = action.get("action")
                        if act=="play":
                            card_index = action.get("card_index")
                            new_color = action.get("new_color")
                            try:
                                chosen_card = game.players[current_idx].hand[card_index]
                            except Exception:
                                chosen_card = None
                            print(f"[server] Player {current_idx} attempting to play index {card_index}: {chosen_card}")
                            game.play(player=current_idx, card=card_index, new_color=new_color)
                        elif act=="draw":
                            game.play(player=current_idx, card=None)
                except Exception as e:
                    send_json(conn, {"type":"info","text":f"Error processing action: {e}"})
        # final state
        broadcast({"type":"state","state":snapshot_game(game)})
        broadcast({"type":"info","text":"Game finished."})
        print("Game finished.")

if __name__=="__main__":
    main()
