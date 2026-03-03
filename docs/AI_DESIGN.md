# 重力四子棋 - 人机对战设计文档

## 一、项目架构分析

### 1.1 游戏规则
- **棋盘**: 5×5 的方格
- **落子规则**: 点击列上方，棋子会落到该列最底部（重力下落）
- **胜利条件**: 横、竖、斜任意方向连成4子
- **玩家**: 2人对战，玩家1（粉色 #FF69B4）先手，玩家2（蓝色 #87CEEB）后手

### 1.2 现有架构
- **后端**: FastAPI + WebSocket，支持房间管理、游戏状态同步
- **前端**: uni-app 框架，支持H5/APP/小程序多端
- **通信**: WebSocket实时双向通信

---

## 二、人机对战需求分析

### 2.1 功能需求
1. 当房间只有1个玩家时，可以：
   - 分享连接邀请其他玩家（人人对战）
   - 点击对面空白头像添加人机（人机对战）
2. 难度分级：
    - 简单模式：常放水，适合新手
    - 中等模式：偶尔放水，适合普通玩家
    - 困难模式：几乎不放水，适合高手
3. 人机特性：
   - 人机总是后手（玩家1先手，人机为玩家2）
   - 人机保持每局能够平局或胜利
   - 根据难度级别动态调整防水概率

### 2.2 技术需求
- 人机决策延迟 0.5-1.5 秒（模拟思考）
- 人机落子通过WebSocket广播，前端无感知差异
- 支持人机对战时重新开始游戏
- 人机断线自动重连

---

## 三、AI算法设计

### 3.1 核心策略：Minimax + Alpha-Beta剪枝 + 评估函数

由于棋盘只有5×5=25格，搜索空间可控，可以使用博弈树搜索。

### 3.2 重力规则适配
```python
def get_valid_moves(board):
    """返回所有可落子的列（考虑重力规则）"""
    valid_cols = []
    for x in range(5):
        if board[0][x] == 0:  # 该列最上方为空，即可落子
            valid_cols.append(x)
    return valid_cols

def make_move(board, col, player):
    """在指定列执行落子（重力下落）"""
    for y in range(4, -1, -1):
        if board[y][col] == 0:
            board[y][col] = player
            return (col, y)  # 返回实际落子位置
    return None
```

### 3.3 评估函数设计

```python
# 位置权重表（中心位置更有价值）
POSITION_WEIGHTS = [
    [1, 2, 3, 2, 1],
    [2, 3, 4, 3, 2],
    [3, 4, 5, 4, 3],
    [2, 3, 4, 3, 2],
    [1, 2, 3, 2, 1]
]

# 棋型评分表（新增棋型评估）
SCORE_TABLE = {
    'WIN': 100000,           # 连成4子获胜
    'BLOCK_WIN': 50000,      # 阻止对手获胜
    'FOUR': 10000,           # 活四（差一步获胜）
    'THREE_OPEN': 1000,      # 开放三连（两端都空）
    'THREE_BLOCKED': 300,    # 封闭三连（一端被堵）
    'TWO_OPEN': 100,         # 开放两连
    'TWO_BLOCKED': 30,       # 封闭两连
    'POSITION': 1            # 位置权重
}

def evaluate_line(line):
    """评估一条线上的棋型"""
    score = 0
    length = len(line)
    
    # 检查所有长度为4的连续子序列
    for i in range(length - 3):
        segment = line[i:i+4]
        ai_count = segment.count(AI_PLAYER)
        human_count = segment.count(HUMAN_PLAYER)
        empty_count = segment.count(0)
        
        # AI获胜
        if ai_count == 4:
            score += SCORE_TABLE['WIN']
        # 玩家获胜（AI需要阻止）
        elif human_count == 4:
            score -= SCORE_TABLE['WIN']
        # AI活三或冲四
        elif ai_count == 3 and empty_count == 1:
            score += SCORE_TABLE['FOUR']
        elif ai_count == 3 and human_count == 0:
            score += SCORE_TABLE['THREE_OPEN']
        # 玩家活三（AI需要重点防范）
        elif human_count == 3 and empty_count == 1:
            score -= SCORE_TABLE['FOUR'] * 0.8
        elif human_count == 3 and ai_count == 0:
            score -= SCORE_TABLE['THREE_OPEN'] * 0.8
        # 活二
        elif ai_count == 2 and empty_count == 2:
            score += SCORE_TABLE['TWO_OPEN']
        elif human_count == 2 and empty_count == 2:
            score -= SCORE_TABLE['TWO_OPEN'] * 0.6
    
    return score
```

### 3.4 搜索深度

剩余空格数	搜索深度	适用场景
>15	         3层	开局，快速响应
10-15	     4层	中局，平衡性能
5-9	         5层	残局，精确计算
<5	         6层	终局，决胜

### 3.5 难度分级与放水机制设计

**核心思想**: 根据玩家选择的难度级别，动态调整放水概率和搜索深度。困难级别人机需要基本确保只有1种获胜方式。

#### 3.5.1 难度参数配置
```python
@dataclass
class AIDifficultyConfig:
    name: str
    weakness_probability: float  # 放水概率
    search_depth: int            # 基础搜索深度
    mistake_probability: float   # 失误概率

AI_DIFFICULTY_CONFIGS = {
    'easy': AIDifficultyConfig(
        name='简单',
        weakness_probability=0.7,   # 70%概率放水
        search_depth=3,              # 浅层搜索
        mistake_probability=0.3      # 30%概率走明显劣着
    ),
    'medium': AIDifficultyConfig(
        name='中等',
        weakness_probability=0.3,    # 30%概率放水
        search_depth=4,              # 标准搜索
        mistake_probability=0.1      # 10%概率失误
    ),
    'hard': AIDifficultyConfig(
        name='困难',
        weakness_probability=0.05,   # 5%概率放水
        search_depth=5,              # 深度搜索
        mistake_probability=0.02     # 2%概率失误
    )
}
```
#### 3.5.2 核心决策算法
```python
def get_ai_move(board, difficulty='medium'):
    """根据难度获取AI落子位置"""
    config = AI_DIFFICULTY_CONFIGS[difficulty]
    
    # 1. 如果能直接赢，必定赢（所有难度都一样）
    winning_move = find_winning_move(board, AI_PLAYER)
    if winning_move:
        return winning_move
    
    # 2. 如果玩家下一步能赢，必须阻止
    blocking_move = find_winning_move(board, HUMAN_PLAYER)
    if blocking_move:
        # 困难模式：完美阻挡
        if difficulty == 'hard':
            return blocking_move
        # 简单/中等：小概率失误（故意不挡）
        elif random.random() < config.mistake_probability:
            # 故意不挡，让玩家赢
            pass
        else:
            return blocking_move
    
    # 3. 获取所有合法走法及其评估分数
    moves_with_scores = evaluate_all_moves(board, config.search_depth)
    
    # 4. 根据难度选择走法
    if not moves_with_scores:
        return None
    
    # 按分数降序排序
    moves_with_scores.sort(key=lambda x: x[1], reverse=True)
    
    # 难度决策
    if difficulty == 'easy':
        # 简单：大概率选中等偏下的走法
        if random.random() < config.weakness_probability:
            # 从后50%的走法中随机选一个
            weak_moves = moves_with_scores[len(moves_with_scores)//2:]
            return random.choice(weak_moves)[0] if weak_moves else moves_with_scores[0][0]
    
    elif difficulty == 'medium':
        # 中等：适度放水
        if random.random() < config.weakness_probability:
            # 选择第2或第3好的走法
            candidates = moves_with_scores[1:3]
            return random.choice(candidates)[0] if candidates else moves_with_scores[0][0]
    
    # 困难或未触发放水：选择最优走法
    return moves_with_scores[0][0]
```
#### 3.5.3 连胜调整机制
```python
class AIPlayer:
    def __init__(self, player_id, difficulty='medium'):
        self.id = player_id
        self.difficulty = difficulty
        self.consecutive_wins = 0
        self.base_weakness_prob = AI_DIFFICULTY_CONFIGS[difficulty].weakness_probability
    
    def get_adjusted_weakness_probability(self):
        """根据连胜次数调整放水概率"""
        if self.consecutive_wins >= 2:
            # 连胜2局后，必放水
            return 1.0
        elif self.consecutive_wins == 1:
            # 连胜1局后，放水概率提升50%
            return min(self.base_weakness_prob * 1.5, 1.0)
        else:
            return self.base_weakness_prob
    
    def record_game_result(self, is_win):
        """记录游戏结果，用于动态难度调整"""
        if is_win:
            self.consecutive_wins += 1
        else:
            self.consecutive_wins = 0
```

### 3.6 Minimax算法实现（带Alpha-Beta剪枝）
```python
def minimax(board, depth, alpha, beta, is_maximizing, ai_player, human_player):
    """
    Minimax算法实现
    is_maximizing: True表示AI回合，False表示玩家回合
    """
    # 检查游戏是否结束
    winner = check_winner_from_board(board)
    if winner == ai_player:
        return 1000000
    elif winner == human_player:
        return -1000000
    elif is_board_full(board) or depth == 0:
        return evaluate_board(board, ai_player, human_player)
    
    if is_maximizing:
        max_eval = -float('inf')
        for col in get_valid_moves(board):
            # 模拟AI落子
            new_board = [row[:] for row in board]
            make_move(new_board, col, ai_player)
            
            eval = minimax(new_board, depth - 1, alpha, beta, False, 
                          ai_player, human_player)
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            
            if beta <= alpha:
                break  # Alpha-Beta剪枝
        return max_eval
    else:
        min_eval = float('inf')
        for col in get_valid_moves(board):
            # 模拟玩家落子
            new_board = [row[:] for row in board]
            make_move(new_board, col, human_player)
            
            eval = minimax(new_board, depth - 1, alpha, beta, True,
                          ai_player, human_player)
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            
            if beta <= alpha:
                break  # Alpha-Beta剪枝
        return min_eval
```

---

## 四、后端接口设计

### 4.0 数据模型扩展
```python
@dataclass
class Player:
    id: str
    name: str
    color: str
    status: PlayerStatus = PlayerStatus.WAITING
    websocket: Optional[WebSocket] = None
    is_ai: bool = False  # 是否为人机
    ai_difficulty: str = "medium"  # 人机难度
    consecutive_wins: int = 0  # 连胜次数

@dataclass
class Room:
    id: str
    players: List[Player] = field(default_factory=list)
    board: List[List[int]] = field(default_factory=list)
    current_turn: int = 0
    game_status: str = "waiting"
    winner: Optional[str] = None
    game_mode: str = "pvp"  # "pvp" 或 "pve"
```

### 4.1 WebSocket消息类型

```python
# 前端 -> 后端
MESSAGE_TYPES = {
    "add_ai_player": "add_ai_player",           # 添加人机玩家
    "set_ai_difficulty": "set_ai_difficulty",   # 设置人机难度
    "place_piece": "place_piece",                # 落子
    "restart_game": "restart_game",              # 重新开始
    "update_name": "update_name"                 # 更新昵称
}

# 后端 -> 前端
{
    "type": "ai_player_added",
    "player": { ... },  # 人机玩家信息
    "difficulty": "medium",
    "room_state": { ... }
}

{
    "type": "ai_move_made",
    "position": {"x": x, "y": y},
    "player": 2,
    "next_turn": 0,
    "room_state": { ... }
}
```

### 4.2 人机落子流程

```python
async def handle_ai_turn(room_id: str):
    """处理人机回合"""
    room = rooms[room_id]
    
    # 延迟0.5-1.5秒模拟思考
    delay = random.uniform(0.5, 1.5)
    await asyncio.sleep(delay)
    
    # 找到人机玩家
    ai_player = next((p for p in room.players if p.is_ai), None)
    if not ai_player:
        return
    
    # AI计算落子
    col = get_ai_move(room.board, ai_player.ai_difficulty)
    if col is not None:
        # 执行落子
        y = get_next_empty_row(room.board, col)
        player_num = 2  # AI总是玩家2
        room.board[y][col] = player_num
        
        # 检查游戏结果
        winner = check_winner(room.board, (col, y))
        if winner:
            room.game_status = "ended"
            room.winner = winner
            # 记录AI胜负
            if winner == 2:
                ai_player.consecutive_wins += 1
            else:
                ai_player.consecutive_wins = 0
                
            await broadcast_to_room(room_id, {
                "type": "game_over",
                "winner": winner,
                "room_state": get_room_state(room_id)
            })
        else:
            room.current_turn = 0  # 切换回玩家回合
            await broadcast_to_room(room_id, {
                "type": "ai_move_made",
                "position": {"x": col, "y": y},
                "player": player_num,
                "next_turn": room.current_turn,
                "room_state": get_room_state(room_id)
            })
```
### 4.3 人机断线重连

```python
async def check_ai_connection(room_id: str):
    """定期检查人机状态，断线自动重连"""
    if room_id in rooms:
        room = rooms[room_id]
        for player in room.players:
            if player.is_ai and player.status == PlayerStatus.DISCONNECTED:
                # 自动重连
                player.status = PlayerStatus.PLAYING
                await broadcast_to_room(room_id, {
                    "type": "ai_reconnected",
                    "room_state": get_room_state(room_id)
                })
```

---

## 五、前端交互设计

### 5.1 UI修改

**右侧玩家区域**（当前显示"等待玩家..."）：
- 当房间只有1个玩家时，显示"点击添加人机"提示
- 点击添加人机后弹窗提示选择难度

```vue
<view v-if="showDifficultyModal" class="difficulty-modal" @touchmove.stop.prevent>
    <view class="difficulty-content">
      <text class="difficulty-title">选择难度</text>
      <button 
        class="difficulty-btn easy" 
        @click="addAIPlayer('easy')">
        <text class="difficulty-name">简单</text>
        <text class="difficulty-desc">适合新手，经常放水</text>
      </button>
      <button 
        class="difficulty-btn medium" 
        @click="addAIPlayer('medium')">
        <text class="difficulty-name">中等</text>
        <text class="difficulty-desc">适合普通玩家，偶尔放水</text>
      </button>
      <button 
        class="difficulty-btn hard" 
        @click="addAIPlayer('hard')">
        <text class="difficulty-name">困难</text>
        <text class="difficulty-desc">适合高手，很少放水</text>
      </button>
      <button class="difficulty-cancel" @click="showDifficultyModal = false">取消</button>
    </view>
  </view>
```

- 点击后发送 `add_ai_player` 消息
- 人机加入后显示为"电脑"或"AI"

### 5.2 状态管理

```javascript
data() {
    return {
        // ... 现有数据
        isAiGame: false,
        aiPlayerId: null,
        aiDifficulty: 'medium',
        showDifficultyModal: false
    }
},

methods: {
    showAIOptions() {
        // 只有没有玩家2且不是观战时显示难度选择
        if (!this.players[1] && !this.isWatching) {
            this.showDifficultyModal = true
        }
    },
    
    addAIPlayer(difficulty) {
        this.showDifficultyModal = false
        this.aiDifficulty = difficulty
        
        uni.sendSocketMessage({
            data: JSON.stringify({
                type: 'add_ai_player',
                difficulty: difficulty
            })
        })
    },
    
    getDifficultyText(difficulty) {
        const map = {
            'easy': '简单',
            'medium': '中等',
            'hard': '困难'
        }
        return map[difficulty] || '中等'
    },
    
    // 重写落子方法，人机对战时特殊处理
    handleCellClick(x, y) {
        if (this.isWatching || this.gameStatus !== 'playing') return
        if (this.currentTurn !== this.getMyPlayerNum() - 1) return
        
        // 检查该列是否已满
        if (this.board[0][x] !== 0) return
        
        // 玩家落子
        this.playerMove(x)
    },
    
    playerMove(x) {
        // 开始动画
        const finalY = this.getFinalY(x)
        this.startPieceAnimation(x, finalY)
        
        // 发送消息到后端
        uni.sendSocketMessage({
            data: JSON.stringify({
                type: 'place_piece',
                x: x
            })
        })
    },
    
    getFinalY(x) {
        for (let i = 4; i >= 0; i--) {
            if (this.board[i][x] === 0) {
                return i
            }
        }
        return 0
    }
}
```

### 5.3 交互流程

```
玩家创建房间
    ↓
显示"等待玩家..." + "点击添加人机"提示
    ↓
玩家点击右侧头像区域
    ↓
发送 add_ai_player 消息
    ↓
后端创建人机玩家，广播 room_update
    ↓
前端更新显示，游戏开始
```

---

## 六、实现计划

### Phase 1: 后端AI核心
1. 实现评估函数
2. 实现Minimax搜索
3. 实现Alpha-Beta剪枝
4. 实现放水机制

### Phase 2: 后端集成
1. 添加AI玩家类型
2. 实现AI落子逻辑
3. 添加WebSocket消息处理

### Phase 3: 前端集成
1. 修改玩家区域UI
2. 添加人机添加交互
3. 处理人机对战状态

---

## 七、关键算法伪代码

### 7.1 Minimax算法

```python
def minimax(board, depth, alpha, beta, is_maximizing):
    if depth == 0 or game_over(board):
        return evaluate(board)
    
    if is_maximizing:
        max_eval = -infinity
        for move in get_valid_moves(board):
            make_move(board, move, AI_PLAYER)
            eval = minimax(board, depth - 1, alpha, beta, False)
            undo_move(board, move)
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = +infinity
        for move in get_valid_moves(board):
            make_move(board, move, HUMAN_PLAYER)
            eval = minimax(board, depth - 1, alpha, beta, True)
            undo_move(board, move)
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha:
                break
        return min_eval
```

### 7.2 评估函数

```python
def evaluate(board):
    score = 0
    
    # 检查所有方向的连线
    for direction in [HORIZONTAL, VERTICAL, DIAGONAL1, DIAGONAL2]:
        lines = extract_lines(board, direction)
        for line in lines:
            score += evaluate_line(line)
    
    # 加上位置权重
    for y in range(5):
        for x in range(5):
            if board[y][x] == AI_PLAYER:
                score += POSITION_WEIGHTS[y][x]
            elif board[y][x] == HUMAN_PLAYER:
                score -= POSITION_WEIGHTS[y][x]
    
    return score
```
