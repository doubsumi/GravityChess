from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
import uuid
from dataclasses import dataclass, field
from enum import Enum
import random
import asyncio

# 导入 AI 引擎
try:
    from backend.ai_engine import (
        get_ai_move, check_winner, is_board_full, get_next_empty_row,
        AI_PLAYER, update_win_streak, reset_win_streak
    )
except ImportError:
    from ai_engine import (
        get_ai_move, check_winner, is_board_full, get_next_empty_row,
        AI_PLAYER, update_win_streak, reset_win_streak
    )

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
    is_ai: bool = False
    difficulty: str = "medium"


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
        player_data = {
            "id": player.id,
            "name": player.name,
            "color": player.color,
            "status": player.status.value,
            "is_ai": player.is_ai,
            "is_current_turn": i == room.current_turn and room.game_status == "playing"
        }
        if player.is_ai:
            player_data["difficulty"] = player.difficulty
        players_data.append(player_data)
    
    return {
        "room_id": room.id,
        "players": players_data,
        "board": room.board,
        "current_turn": room.current_turn,
        "game_status": room.game_status,
        "winner": room.winner
    }


async def ai_make_move(room_id):
    """AI makes a move"""
    if room_id not in rooms:
        return
    
    room = rooms[room_id]
    
    # Check if it's AI's turn
    ai_player = None
    for i, player in enumerate(room.players):
        if player.is_ai and i == room.current_turn:
            ai_player = player
            break
    
    if not ai_player or room.game_status != "playing":
        return
    
    # Simulate thinking delay
    await asyncio.sleep(random.uniform(0.5, 1.5))
    
    # Get AI move with difficulty
    difficulty = getattr(ai_player, 'difficulty', 'medium')
    move = get_ai_move(room.board, room_id, difficulty)
    if move is None:
        return
    
    # Execute move
    y = get_next_empty_row(room.board, move)
    if y is None:
        return
    
    x = move
    player_num = AI_PLAYER
    room.board[y][x] = player_num
    
    # Check winner
    winner = check_winner(room.board, (x, y))
    
    if winner:
        room.game_status = "ended"
        room.winner = winner
        update_win_streak(room_id, winner)
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
        
        # Check if next turn is also AI (should not happen)
        if room.current_turn < len(room.players) and room.players[room.current_turn].is_ai:
            await ai_make_move(room_id)


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

    if message_type == "add_ai_player":
        # Check if room already has 2 players
        playing_players = [p for p in room.players if p.status != PlayerStatus.WATCHING and p.status != PlayerStatus.DISCONNECTED]
        if len(playing_players) >= 2:
            return
        
        # Get difficulty from message
        difficulty = data.get("difficulty", "medium")
        difficulty_names = {
            "easy": "电脑(简单)",
            "medium": "电脑(中等)",
            "hard": "电脑(困难)"
        }
        
        # Create AI player
        ai_id = f"AI_{str(uuid.uuid4())[:4]}"
        ai_player = Player(
            id=ai_id,
            name=difficulty_names.get(difficulty, "电脑"),
            color=get_player_color(len(playing_players)),
            status=PlayerStatus.PLAYING,
            is_ai=True
        )
        ai_player.difficulty = difficulty  # Store difficulty
        room.players.append(ai_player)
        
        # Start game if 2 players
        if len(room.players) == 2:
            room.game_status = "playing"
            room.current_turn = 0
        
        await broadcast_to_room(room_id, {
            "type": "ai_player_added",
            "player": {
                "id": ai_player.id,
                "name": ai_player.name,
                "color": ai_player.color,
                "status": ai_player.status.value,
                "is_ai": ai_player.is_ai,
                "difficulty": difficulty
            },
            "room_state": get_room_state(room_id)
        })
        
        # Check if AI should move first (should not happen since AI is always second)
        if room.current_turn < len(room.players) and room.players[room.current_turn].is_ai:
            await ai_make_move(room_id)
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
            update_win_streak(room_id, winner)
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
            
            # Check if next turn is AI
            if room.current_turn < len(room.players) and room.players[room.current_turn].is_ai:
                await ai_make_move(room_id)

    elif message_type == "restart_game":
        playing_players = [p for p in room.players if p.status != PlayerStatus.WATCHING]
        if len(playing_players) == 2:
            room.board = [[0 for _ in range(5)] for _ in range(5)]
            room.current_turn = 0
            room.game_status = "playing"
            room.winner = None
            reset_win_streak(room_id)
            
            await broadcast_to_room(room_id, {
                "type": "game_restarted",
                "room_state": get_room_state(room_id)
            })
            
            # Check if first turn is AI
            if room.current_turn < len(room.players) and room.players[room.current_turn].is_ai:
                await ai_make_move(room_id)


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


@app.get("/rooms")
async def get_rooms():
    room_list = []
    for room_id, room in rooms.items():
        room_info = {
            "room_id": room_id,
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "color": p.color,
                    "status": p.status.value,
                    "is_ai": p.is_ai
                }
                for p in room.players
            ],
            "player_count": len(room.players),
            "game_status": room.game_status,
            "current_turn": room.current_turn
        }
        room_list.append(room_info)
    
    return {
        "total_rooms": len(rooms),
        "rooms": room_list
    }


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
