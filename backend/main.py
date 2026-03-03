from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
import uuid
from dataclasses import dataclass, field
from enum import Enum

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlayerStatus(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    WATCHING = "watching"
    DISCONNECTED = "disconnected"


@dataclass
class Player:
    id: str
    name: str
    color: str
    status: PlayerStatus = PlayerStatus.WAITING
    websocket: Optional[WebSocket] = None


@dataclass
class Room:
    id: str
    players: List[Player] = field(default_factory=list)
    board: List[List[int]] = field(default_factory=list)
    current_turn: int = 0
    game_status: str = "waiting"
    winner: Optional[str] = None

    def __post_init__(self):
        if not self.board:
            self.board = [[0 for _ in range(5)] for _ in range(5)]


rooms: Dict[str, Room] = {}
player_connections: Dict[str, WebSocket] = {}


def generate_room_id() -> str:
    return str(uuid.uuid4())[:8].upper()


def get_player_color(player_index: int) -> str:
    return "#FF69B4" if player_index == 0 else "#87CEEB"


def check_winner(board, last_move) -> Optional[int]:
    if not last_move:
        return None
    
    x, y = last_move
    player = board[y][x]
    if player == 0:
        return None

    # 水平方向
    count = 1
    for i in range(1, 4):
        if x + i < 5 and board[y][x + i] == player:
            count += 1
        else:
            break
    for i in range(1, 4):
        if x - i >= 0 and board[y][x - i] == player:
            count += 1
        else:
            break
    if count >= 4:
        return player

    # 垂直方向
    count = 1
    for i in range(1, 4):
        if y + i < 5 and board[y + i][x] == player:
            count += 1
        else:
            break
    for i in range(1, 4):
        if y - i >= 0 and board[y - i][x] == player:
            count += 1
        else:
            break
    if count >= 4:
        return player

    # 对角线方向（左上到右下）
    count = 1
    for i in range(1, 4):
        if x + i < 5 and y + i < 5 and board[y + i][x + i] == player:
            count += 1
        else:
            break
    for i in range(1, 4):
        if x - i >= 0 and y - i >= 0 and board[y - i][x - i] == player:
            count += 1
        else:
            break
    if count >= 4:
        return player

    # 对角线方向（右上到左下）
    count = 1
    for i in range(1, 4):
        if x - i >= 0 and y + i < 5 and board[y + i][x - i] == player:
            count += 1
        else:
            break
    for i in range(1, 4):
        if x + i < 5 and y - i >= 0 and board[y - i][x + i] == player:
            count += 1
        else:
            break
    if count >= 4:
        return player

    return None


def is_board_full(board) -> bool:
    for row in board:
        for cell in row:
            if cell == 0:
                return False
    return True


def get_next_empty_row(board, col) -> Optional[int]:
    for i in range(4, -1, -1):
        if board[i][col] == 0:
            return i
    return None


async def broadcast_to_room(room_id: str, message: dict):
    if room_id in rooms:
        room = rooms[room_id]
        for player in room.players:
            if player.websocket:
                try:
                    await player.websocket.send_json(message)
                except:
                    pass


async def send_to_player(player_id: str, message: dict):
    if player_id in player_connections:
        try:
            await player_connections[player_id].send_json(message)
        except:
            pass


def get_room_state(room_id: str) -> dict:
    if room_id not in rooms:
        return {}
    
    room = rooms[room_id]
    players_data = []
    for i, player in enumerate(room.players):
        players_data.append({
            "id": player.id,
            "name": player.name,
            "color": player.color,
            "status": player.status.value,
            "is_current_turn": i == room.current_turn and room.game_status == "playing"
        })
    
    return {
        "room_id": room.id,
        "players": players_data,
        "board": room.board,
        "current_turn": room.current_turn,
        "game_status": room.game_status,
        "winner": room.winner
    }


@app.websocket("/ws/{room_id}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_name: str):
    await websocket.accept()
    
    player_id = str(uuid.uuid4())
    player = Player(
        id=player_id,
        name=player_name or f"Player_{player_id[:4]}",
        color="",
        websocket=websocket
    )
    player_connections[player_id] = websocket

    try:
        if room_id not in rooms:
            room = Room(id=room_id)
            room.players.append(player)
            room.players[0].color = get_player_color(0)
            room.players[0].status = PlayerStatus.WAITING
            rooms[room_id] = room
        else:
            room = rooms[room_id]
            playing_players = [p for p in room.players if p.status != PlayerStatus.WATCHING and p.status != PlayerStatus.DISCONNECTED]
            
            if len(playing_players) >= 2:
                player.status = PlayerStatus.WATCHING
                player.color = "#FFD700"
                room.players.append(player)
            else:
                player.color = get_player_color(len(playing_players))
                player.status = PlayerStatus.PLAYING
                room.players.append(player)
                
                if len(playing_players) == 1:
                    room.game_status = "playing"
                    room.current_turn = 0

        await websocket.send_json({
            "type": "init",
            "player_id": player_id,
            "player_color": player.color,
            "room_state": get_room_state(room_id)
        })

        await broadcast_to_room(room_id, {
            "type": "room_update",
            "room_state": get_room_state(room_id)
        })

        while True:
            data = await websocket.receive_json()
            await handle_message(room_id, player_id, data)

    except WebSocketDisconnect:
        await handle_disconnect(room_id, player_id)
    except Exception as e:
        print(f"Error: {e}")
        await handle_disconnect(room_id, player_id)
    finally:
        if player_id in player_connections:
            del player_connections[player_id]


async def handle_message(room_id: str, player_id: str, data: dict):
    if room_id not in rooms:
        return
    
    room = rooms[room_id]
    message_type = data.get("type")

    if message_type == "update_name":
        # 处理昵称更新
        new_name = data.get("name")
        if new_name:
            # 找到对应的玩家并更新昵称
            for player in room.players:
                if player.id == player_id:
                    player.name = new_name
                    break
            
            # 向房间内所有玩家广播房间状态更新
            await broadcast_to_room(room_id, {
                "type": "room_update",
                "room_state": get_room_state(room_id)
            })
        return

    if message_type == "place_piece":
        if room.game_status != "playing":
            return
        
        player_idx = None
        for i, p in enumerate(room.players):
            if p.id == player_id and p.status != PlayerStatus.WATCHING:
                player_idx = i
                break
        
        if player_idx is None or player_idx != room.current_turn:
            return

        x = data.get("x")
        y = data.get("y")

        if not (0 <= x < 5):
            return
        
        # 实现重力下落，找到该列的最底部空位
        empty_row = get_next_empty_row(room.board, x)
        if empty_row is None:
            return
        
        y = empty_row
        player_num = player_idx + 1
        room.board[y][x] = player_num

        winner = check_winner(room.board, (x, y))
        
        if winner:
            room.game_status = "ended"
            room.winner = winner
            await broadcast_to_room(room_id, {
                "type": "game_over",
                "winner": winner,
                "room_state": get_room_state(room_id)
            })
        elif is_board_full(room.board):
            room.game_status = "ended"
            room.winner = 0
            await broadcast_to_room(room_id, {
                "type": "game_over",
                "winner": 0,
                "room_state": get_room_state(room_id)
            })
        else:
            room.current_turn = 1 - room.current_turn
            await broadcast_to_room(room_id, {
                "type": "piece_placed",
                "position": {"x": x, "y": y},
                "player": player_num,
                "next_turn": room.current_turn,
                "room_state": get_room_state(room_id)
            })

    elif message_type == "restart_game":
        playing_players = [p for p in room.players if p.status != PlayerStatus.WATCHING]
        if len(playing_players) == 2:
            room.board = [[0 for _ in range(5)] for _ in range(5)]
            room.current_turn = 0
            room.game_status = "playing"
            room.winner = None
            
            await broadcast_to_room(room_id, {
                "type": "game_restarted",
                "room_state": get_room_state(room_id)
            })


async def handle_disconnect(room_id: str, player_id: str):
    if room_id not in rooms:
        return
    
    room = rooms[room_id]
    player = None
    player_idx = None
    
    for i, p in enumerate(room.players):
        if p.id == player_id:
            player = p
            player_idx = i
            break
    
    if player:
        player.status = PlayerStatus.DISCONNECTED
        
        await broadcast_to_room(room_id, {
            "type": "player_disconnected",
            "player_id": player_id,
            "room_state": get_room_state(room_id)
        })
        
        if player_idx is not None and player.status != PlayerStatus.WATCHING:
            playing_players = [p for p in room.players if p.status != PlayerStatus.WATCHING and p.status != PlayerStatus.DISCONNECTED]
            if len(playing_players) < 2:
                room.game_status = "waiting"


@app.get("/")
async def root():
    return {"message": "Gravity Chess API"}


@app.get("/room/{room_id}")
async def get_room(room_id: str):
    if room_id not in rooms:
        return {"error": "Room not found", "exists": False}
    
    room = rooms[room_id]
    return {
        "exists": True,
        "room_state": get_room_state(room_id)
    }


@app.post("/room")
async def create_room():
    room_id = generate_room_id()
    room = Room(id=room_id)
    rooms[room_id] = room
    
    return {
        "room_id": room_id,
        "room_state": get_room_state(room_id)
    }
