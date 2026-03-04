"""
重力四子棋 AI 引擎
使用 Minimax + Alpha-Beta 剪枝算法
"""
import random
from typing import List, Optional

# AI 常量
AI_PLAYER = 2
HUMAN_PLAYER = 1

# 位置权重表（中心位置更有价值）
POSITION_WEIGHTS = [
    [1, 2, 3, 2, 1],
    [2, 3, 4, 3, 2],
    [3, 4, 5, 4, 3],
    [2, 3, 4, 3, 2],
    [1, 2, 3, 2, 1]
]

# 棋型评分表
SCORE_TABLE = {
    'WIN': 100000,           # 连成4子获胜
    'BLOCK_WIN': 50000,      # 阻止对手获胜
    'THREE_OPEN': 1000,      # 开放三连（两端都空）
    'THREE_BLOCKED': 100,    # 封闭三连
    'TWO_OPEN': 50,          # 开放两连
    'POSITION': 1            # 位置权重
}

# 方向定义
DIRECTIONS = [
    (0, 1),   # 水平
    (1, 0),   # 垂直
    (1, 1),   # 对角线1
    (1, -1)   # 对角线2
]

# AI 连胜记录
ai_win_streak = {}


def get_next_empty_row(board: List[List[int]], col: int) -> Optional[int]:
    """获取指定列的下一个空行（从下往上）"""
    for i in range(4, -1, -1):
        if board[i][col] == 0:
            return i
    return None


def get_valid_moves(board: List[List[int]]) -> List[int]:
    """获取所有有效的落子位置（有空间的列）"""
    moves = []
    for col in range(5):
        if get_next_empty_row(board, col) is not None:
            moves.append(col)
    return moves


def check_winner(board: List[List[int]], last_move) -> Optional[int]:
    """检查获胜者"""
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


def is_board_full(board: List[List[int]]) -> bool:
    """检查棋盘是否已满"""
    for row in board:
        for cell in row:
            if cell == 0:
                return False
    return True


def evaluate_line(line: List[int]) -> int:
    """评估一行（4个格子）的得分"""
    ai_count = line.count(AI_PLAYER)
    human_count = line.count(HUMAN_PLAYER)
    empty_count = line.count(0)
    
    if ai_count == 4:
        return SCORE_TABLE['WIN']
    if human_count == 4:
        return -SCORE_TABLE['WIN']
    
    if ai_count == 3 and empty_count == 1:
        return SCORE_TABLE['THREE_OPEN']
    if human_count == 3 and empty_count == 1:
        return -SCORE_TABLE['BLOCK_WIN']
    
    if ai_count == 2 and empty_count == 2:
        return SCORE_TABLE['TWO_OPEN']
    if human_count == 2 and empty_count == 2:
        return -SCORE_TABLE['BLOCK_WIN'] # 阻止对手2连权重提高，避免出现开局必胜走法
    
    return 0


def evaluate(board: List[List[int]]) -> int:
    """评估棋盘状态"""
    score = 0
    
    # 检查所有可能的4连线路
    for y in range(5):
        for x in range(5):
            for dy, dx in DIRECTIONS:
                if y + 3*dy < 5 and x + 3*dx < 5 and x + 3*dx >= 0:
                    line = [
                        board[y][x],
                        board[y+dy][x+dx],
                        board[y+2*dy][x+2*dx],
                        board[y+3*dy][x+3*dx]
                    ]
                    score += evaluate_line(line)
    
    # 加上位置权重
    for y in range(5):
        for x in range(5):
            if board[y][x] == AI_PLAYER:
                score += POSITION_WEIGHTS[y][x]
            elif board[y][x] == HUMAN_PLAYER:
                score -= POSITION_WEIGHTS[y][x]
    
    return score


def minimax(board: List[List[int]], depth: int, alpha: float, beta: float, is_maximizing: bool) -> float:
    """Minimax 算法 + Alpha-Beta 剪枝"""
    valid_moves = get_valid_moves(board)
    
    # 终止状态
    if depth == 0 or not valid_moves:
        return evaluate(board)
    
    if is_maximizing:
        max_eval = -float('inf')
        for move in valid_moves:
            row = get_next_empty_row(board, move)
            if row is not None:
                board[row][move] = AI_PLAYER
                eval = minimax(board, depth-1, alpha, beta, False)
                board[row][move] = 0
                max_eval = max(max_eval, eval)
                alpha = max(alpha, eval)
                if beta <= alpha:
                    break
        return max_eval
    else:
        min_eval = float('inf')
        for move in valid_moves:
            row = get_next_empty_row(board, move)
            if row is not None:
                board[row][move] = HUMAN_PLAYER
                eval = minimax(board, depth-1, alpha, beta, True)
                board[row][move] = 0
                min_eval = min(min_eval, eval)
                beta = min(beta, eval)
                if beta <= alpha:
                    break
        return min_eval


def find_winning_move(board: List[List[int]]) -> Optional[int]:
    """查找 AI 是否能直接获胜"""
    for move in get_valid_moves(board):
        row = get_next_empty_row(board, move)
        if row is not None:
            board[row][move] = AI_PLAYER
            if check_winner(board, (move, row)) == AI_PLAYER:
                board[row][move] = 0
                return move
            board[row][move] = 0
    return None


def find_blocking_move(board: List[List[int]]) -> Optional[int]:
    """查找是否需要阻止对手获胜"""
    for move in get_valid_moves(board):
        row = get_next_empty_row(board, move)
        if row is not None:
            board[row][move] = HUMAN_PLAYER
            if check_winner(board, (move, row)) == HUMAN_PLAYER:
                board[row][move] = 0
                return move
            board[row][move] = 0
    return None


def should_give_weakness(room_id: str, difficulty: str = "medium") -> bool:
    """根据难度决定是否应该放水"""
    # 根据难度设置放水概率
    weakness_chance = {
        "easy": 0.7,    # 简单：70%概率放水
        "medium": 0.4,  # 中等：40%概率放水
        "hard": 0.1     # 困难：10%概率放水
    }
    
    # 检查连胜记录
    if room_id in ai_win_streak and ai_win_streak[room_id] >= 2:
        ai_win_streak[room_id] = 0
        return True
    
    # 根据难度随机放水
    chance = weakness_chance.get(difficulty, 0.4)
    return random.random() < chance


def get_ai_move(board: List[List[int]], room_id: str, difficulty: str = "medium") -> Optional[int]:
    """
    获取 AI 的落子位置
    包含放水机制，确保玩家有获胜机会
    """
    # 1. 检查是否能直接获胜
    winning_move = find_winning_move(board)
    if winning_move is not None:
        return winning_move
    
    # 2. 检查是否需要阻止对手
    blocking_move = find_blocking_move(board)
    if blocking_move is not None:
        return blocking_move
    
    # 3. 根据难度设置搜索深度
    search_depth = {
        "easy": 2,
        "medium": 4,
        "hard": 6
    }
    depth = search_depth.get(difficulty, 4)
    
    # 4. 评估所有走法
    valid_moves = get_valid_moves(board)
    if not valid_moves:
        return None
    
    move_scores = []
    for move in valid_moves:
        row = get_next_empty_row(board, move)
        if row is not None:
            board[row][move] = AI_PLAYER
            score = minimax(board, depth, -float('inf'), float('inf'), False)
            board[row][move] = 0
            move_scores.append((score, move))
    
    # 按分数降序排序
    move_scores.sort(reverse=True, key=lambda x: x[0])
    
    # 5. 应用放水机制
    if len(move_scores) >= 3 and should_give_weakness(room_id, difficulty):
        # 根据难度选择次优走法
        if difficulty == "easy":
            # 简单：选择更差的走法
            idx = random.randint(1, min(3, len(move_scores) - 1))
        elif difficulty == "medium":
            # 中等：选择第2或第3好的走法
            idx = random.randint(1, 2)
        else:
            # 困难：偶尔选择次优
            idx = 1
        return move_scores[idx][1]
    
    # 选择最优走法
    return move_scores[0][1]


def update_win_streak(room_id: str, winner: int):
    """更新 AI 连胜记录"""
    if winner == AI_PLAYER:
        if room_id in ai_win_streak:
            ai_win_streak[room_id] += 1
        else:
            ai_win_streak[room_id] = 1
    elif winner == HUMAN_PLAYER:
        # 玩家获胜，重置连胜
        ai_win_streak[room_id] = 0


def reset_win_streak(room_id: str):
    """重置连胜记录"""
    if room_id in ai_win_streak:
        ai_win_streak[room_id] = 0
