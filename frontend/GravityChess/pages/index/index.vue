<template>
	<view class="container">
		<!-- 自定义导航栏 -->
		<view class="custom-nav-bar">
			<view class="nav-left"></view>
			<text class="nav-title">重力四子棋</text>
			<button class="nav-share-btn" @click="shareGame">
				<uni-icons type="paperplane" size="30" color="#fff"></uni-icons>
			</button>
		</view>
		
		<view class="top-bar">
			<view class="room-info" v-if="roomId">
				<text class="room-label">房间号:</text>
				<text class="room-id">{{ roomId }}</text>
				<button class="copy-btn" @click="copyRoomId">复制</button>
			</view>
			<view class="join-room">
				<input 
					class="room-input" 
					type="text" 
					v-model="joinRoomId" 
					placeholder="输入房间号"
					@confirm="joinRoom"
				/>
				<button class="join-btn" @click="joinRoom">加入房间</button>
			</view>
		</view>

		<view class="game-area">
			<view class="board-section">
				<!-- 左侧玩家 -->
				<view class="player-info left-player" :class="{ active: currentTurn === 0 && gameStatus === 'playing' }">
					<view class="player-avatar" :style="{ backgroundColor: players[0]?.color || '#999' }"></view>
					<view class="player-name-container">
						<input 
							v-if="players[0]?.id === playerId && editingName"
							class="player-name-input"
							v-model="tempName"
							@blur="saveName"
							@confirm="saveName"
							focus
						/>
						<text 
							v-else 
							class="player-name"
							@click="startEditName(0)"
						>{{ players[0]?.name || '等待玩家...' }}</text>
					</view>
					<text class="player-status" v-if="players[0]?.status === 'watching'">(观战中)</text>
				</view>

				<!-- 棋盘 -->
				<view class="board-container">
					<view v-if="gameStatus === 'ended'" class="result-overlay">
						<text class="result-text">{{ winner === 0 ? '平局!' : (getWinnerName() + ' 获胜!') }}</text>
						<button class="restart-btn" @click="restartGame" v-if="!isWatching">再来一局</button>
					</view>
					
					<view class="board-wrapper">
						<view class="board">
							<view class="row" v-for="(row, y) in displayBoard" :key="y">
								<view 
									class="cell" 
									v-for="(cell, x) in row" 
									:key="x"
									:class="{ 
										'player1': cell === 1, 
										'player2': cell === 2,
										'last-move': isLastMove(x, y)
									}"
									:style="{ backgroundColor: getCellColor(cell) }"
									@click="handleCellClick(x, y)"
								>
									<view v-if="cell !== 0" class="piece-inner"></view>
								</view>
							</view>
							
							<view 
								v-if="animatingPiece" 
								class="animating-piece"
								:style="animatingPieceStyle"
							>
								<view class="piece-inner"></view>
							</view>
						</view>
					</view>
				</view>

				<!-- 右侧玩家 -->
				<view class="player-info right-player" :class="{ active: currentTurn === 1 && gameStatus === 'playing' }">
					<view class="player-avatar" :style="{ backgroundColor: players[1]?.color || '#999' }"></view>
					<view class="player-name-container">
						<input 
							v-if="players[1]?.id === playerId && editingName"
							class="player-name-input"
							v-model="tempName"
							@blur="saveName"
							@confirm="saveName"
							focus
						/>
						<text 
							v-else 
							class="player-name"
							@click="startEditName(1)"
						>{{ players[1]?.name || '等待玩家...' }}</text>
					</view>
					<text class="player-status" v-if="players[1]?.status === 'watching'">(观战中)</text>
				</view>
			</view>
			
			<!-- 规则说明区域 -->
			<view class="rules-section">
				<text class="rules-title">游戏规则</text>
				<text class="rules-text">点击列上方落子，棋子会落到该列最底部。率先在横、竖、斜任意方向连成4子者获胜！</text>
			</view>
		</view>

		<view class="status-bar">
			<text class="game-status-text">{{ statusText }}</text>
			<text v-if="isWatching" class="watching-tip">您正在观战</text>
		</view>

		<view v-if="!connected" class="connecting-overlay">
			<text>正在连接...</text>
		</view>
	</view>
</template>

<script>
export default {
	data() {
		return {
			roomId: '',
			joinRoomId: '',
			playerId: '',
			playerColor: '',
			players: [],
			board: [],
			currentTurn: 0,
			gameStatus: 'waiting',
			winner: null,
			lastMove: null,
			connected: false,
			isWatching: false,
			animatingPiece: null,
			animatingPieceStyle: {},
			editingName: false,
			tempName: ''
		}
	},
	computed: {
		displayBoard() {
			if (!this.board || this.board.length === 0) {
				return [[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]
			}
			return this.board
		},
		statusText() {
			if (this.gameStatus === 'ended') {
				if (this.winner === 0) return '游戏平局!'
				return this.winner === this.getMyPlayerNum() ? '恭喜你获胜!' : '对手获胜!'
			}
			if (this.isWatching) return '您正在观战'
			if (this.gameStatus !== 'playing') return '等待对手加入...'
			if (this.currentTurn === this.getMyPlayerNum() - 1) return '轮到你下棋'
			return '对手下棋中...'
		}
	},
	onLoad(options) {
		// 检查URL参数中是否有房间号
		const roomFromQuery = options?.room || this.getRoomFromUrl()
		
		if (roomFromQuery) {
			// 从分享链接进入，加入已有房间
			this.joinRoomId = roomFromQuery.toUpperCase()
			this.joinRoom()
		} else {
			// 创建新房间
			this.createRoom()
		}
		
		// 监听导航栏分享按钮点击
		// #ifdef APP-PLUS
		const webView = this.$scope.$getAppWebview()
		webView.setStyle({
			titleNView: {
				buttons: [{
					text: '分享',
					fontSize: '16px',
					color: '#ffffff',
					float: 'right',
					onclick: () => {
						this.shareGame()
					}
				}]
			}
		})
		// #endif
	},
	onUnload() {
		this.closeWebSocket()
	},
	onNavigationBarButtonTap() {
		this.shareGame()
	},
	methods: {
		createRoom() {
			this.roomId = this.generateRoomId()
			this.connectWebSocket(this.roomId, 'Player1')
		},
		
		joinRoom() {
			if (!this.joinRoomId) {
				uni.showToast({ title: '请输入房间号', icon: 'none' })
				return
			}
			this.roomId = this.joinRoomId.toUpperCase()
			this.closeWebSocket()
			this.connectWebSocket(this.roomId, 'Player2')
			this.joinRoomId = ''
		},
		
		generateRoomId() {
			return Math.random().toString(36).substring(2, 10).toUpperCase()
		},
		
		getRoomFromUrl() {
			// #ifdef H5
			const urlParams = new URLSearchParams(window.location.search)
			return urlParams.get('room')
			// #endif
			
			// #ifndef H5
			return null
			// #endif
		},
		
		getWinnerName() {
			if (this.winner === 0) return ''
			const winnerIndex = this.winner - 1
			if (this.players && this.players[winnerIndex]) {
				return this.players[winnerIndex].name
			}
			return winnerIndex === 0 ? '红方' : '蓝方'
		},
		
		connectWebSocket(roomId, defaultName) {
			// 使用wss协议，域名替换localhost
			const wsUrl = `wss://siziqi.notos.space/ws/${roomId}/${defaultName}`
			
			uni.connectSocket({ url: wsUrl })
			
			uni.onSocketOpen(() => {
				this.connected = true
				console.log('WebSocket connected')
			})
			
			uni.onSocketMessage((res) => {
				const data = JSON.parse(res.data)
				this.handleMessage(data)
			})
			
			uni.onSocketClose(() => {
				this.connected = false
				console.log('WebSocket closed')
			})
			
			uni.onSocketError((err) => {
				console.error('WebSocket error:', err)
				this.connected = false
			})
		},
		
		closeWebSocket() {
			uni.closeSocket()
		},
		
		handleMessage(data) {
			switch(data.type) {
				case 'init':
					this.playerId = data.player_id
					this.playerColor = data.player_color
					this.updateRoomState(data.room_state)
					break
				case 'room_update':
					this.updateRoomState(data.room_state)
					break
				case 'piece_placed':
					this.board = data.room_state.board
					this.currentTurn = data.next_turn
					this.lastMove = data.position
					this.animatingPiece = null
					this.updateRoomState(data.room_state)
					break
				case 'game_over':
					this.board = data.room_state.board
					this.winner = data.winner
					this.gameStatus = 'ended'
					this.animatingPiece = null
					this.updateRoomState(data.room_state)
					break
				case 'game_restarted':
					this.board = data.room_state.board
					this.currentTurn = data.room_state.current_turn
					this.gameStatus = 'playing'
					this.winner = null
					this.lastMove = null
					this.animatingPiece = null
					break
				case 'player_disconnected':
					this.updateRoomState(data.room_state)
					break
			}
		},
		
		updateRoomState(state) {
			if (!state) return
			this.roomId = state.room_id
			
			// 只保留当前用户自己修改的昵称，其他玩家的昵称使用服务器数据
			const newPlayers = state.players || []
			if (this.players.length > 0) {
				newPlayers.forEach((newPlayer) => {
					// 只处理当前用户自己的昵称
					if (newPlayer.id === this.playerId) {
						const oldPlayer = this.players.find(p => p.id === newPlayer.id)
						// 如果本地有修改且与服务器不同，保留本地昵称
						if (oldPlayer && oldPlayer.name !== newPlayer.name) {
							newPlayer.name = oldPlayer.name
						}
					}
					// 其他玩家的昵称直接使用服务器数据
				})
			}
			this.players = newPlayers
			
			this.board = state.board || []
			this.currentTurn = state.current_turn
			this.gameStatus = state.game_status
			this.winner = state.winner
			
			const myPlayer = this.players.find(p => p.id === this.playerId)
			this.isWatching = myPlayer?.status === 'watching'
		},
		
		getMyPlayerNum() {
			const myPlayer = this.players.find(p => p.id === this.playerId)
			if (!myPlayer) return 0
			const playingPlayers = this.players.filter(p => p.status !== 'watching')
			const idx = playingPlayers.findIndex(p => p.id === this.playerId)
			return idx + 1
		},
		
		handleCellClick(x, y) {
			if (this.isWatching || this.gameStatus !== 'playing') return
			if (this.currentTurn !== this.getMyPlayerNum() - 1) return
			
			// 检查该列是否已满
			if (this.board[0][x] !== 0) return
			
			// 找到最终落点
			let finalY = 4
			for (let i = 0; i < 5; i++) {
				if (this.board[i][x] !== 0) {
					finalY = i - 1
					break
				}
			}
			
			// 开始动画
			this.startPieceAnimation(x, finalY)
			
			// 发送消息到后端
			uni.sendSocketMessage({
				data: JSON.stringify({
					type: 'place_piece',
					x: x,
					y: 0,
					z: 0
				})
			})
		},
		
		startPieceAnimation(x, finalY) {
			const cellSize = this.getCellSize()
			const gap = this.getGap()
			const myPlayerNum = this.getMyPlayerNum()
			const pieceColor = myPlayerNum === 1 ? '#FF69B4' : '#87CEEB'
			
			this.animatingPiece = {
				x: x,
				finalY: finalY,
				color: pieceColor
			}
			
			// 计算位置（相对于board）
			const boardRect = uni.createSelectorQuery().select('.board').boundingClientRect()
			boardRect.exec((res) => {
				if (res[0]) {
					const boardTop = res[0].top
					const boardLeft = res[0].left
					// 从点击处的格子位置开始
					const startTop = boardTop + 8 // 从棋盘顶部开始
					const endTop = boardTop + 8 + finalY * (cellSize + gap)
					const left = boardLeft + 8 + x * (cellSize + gap)
					
					// 初始位置（点击处）
					this.animatingPieceStyle = {
						left: `${left}px`,
						top: `${startTop}px`,
						backgroundColor: pieceColor,
						width: `${cellSize}px`,
						height: `${cellSize}px`,
						transition: 'none',
						position: 'fixed',
						zIndex: 9999
					}
					
					// 确保样式先应用
					this.$nextTick(() => {
						requestAnimationFrame(() => {
							// 重力下落效果，使用更自然的缓动函数，动画更慢
							this.animatingPieceStyle = {
								...this.animatingPieceStyle,
								top: `${endTop}px`,
								transition: 'top 1.2s cubic-bezier(0.25, 0.1, 0.25, 1.0)'
							}
							
							// 等待动画完成后再清除
							setTimeout(() => {
								this.animatingPiece = null
							}, 1200)
						})
					})
				}
			})
		},
		
		getCellSize() {
			const systemInfo = uni.getSystemInfoSync()
			const windowWidth = systemInfo.windowWidth
			const windowHeight = systemInfo.windowHeight
			const isLandscape = windowWidth > windowHeight
			const isDesktop = windowWidth >= 1024
			
			// 桌面端更大的棋盘
			if (isDesktop) {
				if (windowWidth <= 1200) return 110
				return 120
			}
			
			// 移动端横屏和小屏幕平板
			if (isLandscape) {
				if (windowHeight <= 375) return 40
				if (windowHeight <= 430) return 45
				if (windowHeight <= 500) return 50
				if (windowHeight <= 768) return 60
				return 70
			}
			
			// 竖屏
			if (windowWidth <= 375) return 65
			if (windowWidth <= 414) return 70
			if (windowWidth <= 768) return 75
			return 90
		},
		
		getGap() {
			const systemInfo = uni.getSystemInfoSync()
			const windowWidth = systemInfo.windowWidth
			const windowHeight = systemInfo.windowHeight
			const isLandscape = windowWidth > windowHeight
			
			if (isLandscape) return 6
			return 4
		},
		
		getCellColor(cell) {
			if (cell === 0) return 'rgba(255,255,255,0.1)'
			if (cell === 1) return this.players[0]?.color || '#FF69B4'
			if (cell === 2) return this.players[1]?.color || '#87CEEB'
			return 'rgba(255,255,255,0.1)'
		},
		
		isLastMove(x, y) {
			if (!this.lastMove) return false
			return this.lastMove.x === x && this.lastMove.y === y
		},
		
		restartGame() {
			uni.sendSocketMessage({
				data: JSON.stringify({
					type: 'restart_game'
				})
			})
		},
		
		copyRoomId() {
			uni.setClipboardData({
				data: this.roomId,
				success: () => {
					uni.showToast({ title: '房间号已复制', icon: 'success' })
				}
			})
		},
		
		startEditName(playerIndex) {
			if (this.players[playerIndex]?.id !== this.playerId) return
			this.tempName = this.players[playerIndex].name
			this.editingName = true
		},
		
		saveName() {
			if (this.tempName.trim()) {
				const myPlayer = this.players.find(p => p.id === this.playerId)
				if (myPlayer) {
					const newName = this.tempName.trim()
					myPlayer.name = newName
					
					// 向后台发送昵称更新消息
					uni.sendSocketMessage({
						data: JSON.stringify({
							type: 'update_name',
							name: newName
						})
					})
				}
			}
			this.editingName = false
			this.tempName = ''
		},
		
		shareGame() {
			const shareUrl = `https://siziqi.notos.space/?room=${this.roomId}`
			// 或者使用房间号直接加入的方式
			// const shareUrl = `https://siziqi.notos.space/#/join/${this.roomId}`
			const shareTitle = '重力四子棋 - 快来挑战我吧！'
			const shareDesc = `房间号：${this.roomId}，点击加入游戏！`
			
			// #ifdef H5
			if (navigator.share) {
				navigator.share({
					title: shareTitle,
					text: shareDesc,
					url: shareUrl
				}).catch(err => {
					console.log('分享取消:', err)
				})
			} else {
				// 复制到剪贴板
				uni.setClipboardData({
					data: shareUrl,
					success: () => {
						uni.showToast({ title: '链接已复制到剪贴板', icon: 'success' })
					}
				})
			}
			// #endif
			
			// #ifdef APP-PLUS
			uni.share({
				provider: 'weixin',
				scene: 'WXSceneSession',
				type: 0,
				title: shareTitle,
				summary: shareDesc,
				href: shareUrl,
				imageUrl: '/static/logo.png',
				success: (res) => {
					console.log('分享成功:', res)
				},
				fail: (err) => {
					console.log('分享失败:', err)
				}
			})
			// #endif
		},
		
		// #ifdef MP-WEIXIN
		uni.showShareMenu({
			withShareTicket: true,
			menus: ['shareAppMessage', 'shareTimeline']
		})
		// #endif
	}
}
</script>

<style>
* {
	box-sizing: border-box;
	margin: 0;
	padding: 0;
}

page {
	min-height: 90vh;
	background-color: #263238;
}

.container {
	min-height: 100vh;
	background-color: #263238;
	padding: 0;
	display: flex;
	flex-direction: column;
}

/* 自定义导航栏 */
.custom-nav-bar {
	height: 44px;
	background-color: #263238;
	display: flex;
	align-items: center;
	padding: 0 20rpx;
	border-bottom: 1rpx solid rgba(255,255,255,0.1);
	position: sticky;
	top: 0;
	z-index: 100;
}

.nav-left {
	width: 80rpx;
}

.nav-title {
	color: #fff;
	font-size: 24px;
	font-weight: bold;
	flex: 1;
	text-align: center;
}

.nav-share-btn {
	background: transparent;
	border: none;
	padding: 8rpx;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 80rpx;
}

.top-bar {
	display: flex;
	justify-content: space-between;
	align-items: center;
	min-height: 160rpx;
	padding: 10rpx 20rpx;
	flex-shrink: 0;
	flex-wrap: nowrap;
	gap: 20rpx;
}

.room-info {
	display: flex;
	align-items: center;
	gap: 10rpx;
	flex-shrink: 0;
}

.room-label {
	color: #aaa;
	font-size: 32rpx;
	white-space: nowrap;
}

.room-id {
	color: #fff;
	font-size: 36rpx;
	font-weight: bold;
	white-space: nowrap;
}

.copy-btn {
	background-color: #1a237e;
	color: #fff;
	font-size: 24rpx;
	padding: 6rpx 16rpx;
	border-radius: 6rpx;
	margin-left: 10rpx;
	line-height: 1.4;
	white-space: nowrap;
}

.join-room {
	display: flex;
	align-items: center;
	gap: 10rpx;
	flex-shrink: 0;
}

.room-input {
	background-color: rgba(255,255,255,0.1);
	border: 1px solid rgba(255,255,255,0.2);
	border-radius: 8rpx;
	padding: 8rpx 15rpx;
	color: #fff;
	font-size: 36rpx;
	width: 180rpx;
	white-space: nowrap;
}

.join-btn {
	background-color: #1a237e;
	color: #fff;
	font-size: 26rpx;
	padding: 10rpx 24rpx;
	border-radius: 8rpx;
	line-height: 1.5;
	white-space: nowrap;
	flex-shrink: 0;
}

.share-icon {
	font-size: 28rpx;
}

/* 竖屏适配 */
@media screen and (orientation: portrait) {
	.top-bar {
		padding: 10rpx 15rpx;
		gap: 15rpx;
	}
	
	.room-input {
		width: 160rpx;
	}
	
	.room-info {
		font-size: 16rpx;
	}
	
	.join-btn {
		padding: 8rpx 20rpx;
	}
	
	.result-overlay {
		padding: 40rpx 60rpx;
		min-width: 320rpx;
	}
	
	.result-text {
		font-size: 40rpx;
	}
	
	.restart-btn {
		font-size: 28rpx;
		padding: 15rpx 35rpx;
		min-width: 160rpx;
		height: auto;
		line-height: 1.2;
	}
}

.game-area {
	display: flex;
	flex-direction: column;
	align-items: center;
	flex: 1;
	padding: 10rpx;
	gap: 15rpx;
	min-height: 0;
	justify-content: center;
}

.board-section {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 10rpx;
	flex: 1;
	width: 100%;
	max-width: 800rpx;
}

.player-info {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 10rpx;
	border-radius: 12rpx;
	background-color: rgba(255,255,255,0.05);
	min-width: 100rpx;
	flex-shrink: 0;
}

.player-info.active {
	background-color: rgba(255,215,0,0.2);
	border: 2rpx solid #FFD700;
}

.player-avatar {
	width: 60rpx;
	height: 60rpx;
	border-radius: 50%;
	margin-bottom: 8rpx;
}

.player-name-container {
	display: flex;
	align-items: center;
	justify-content: center;
}

.player-name {
	color: #fff;
	font-size: 26rpx;
	text-align: center;
	word-break: break-all;
	max-width: 100rpx;
}

.player-name-input {
	background-color: rgba(255,255,255,0.2);
	border: 1px solid rgba(255,255,255,0.3);
	border-radius: 6rpx;
	padding: 4rpx 8rpx;
	color: #fff;
	font-size: 24rpx;
	width: 100rpx;
	text-align: center;
}

.player-status {
	color: #FFD700;
	font-size: 20rpx;
	margin-top: 4rpx;
}

.board-container {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 10rpx;
	position: relative;
	justify-content: center;
}

.board-wrapper {
	display: flex;
	align-items: center;
	justify-content: center;
}

.board {
	display: flex;
	flex-direction: column;
	gap: 6rpx;
	padding: 12rpx;
	background-color: rgba(255,255,255,0.05);
	border-radius: 12rpx;
	position: relative;
}

.row {
	display: flex;
	gap: 6rpx;
}

.cell {
	width: 55rpx;
	height: 55rpx;
	border-radius: 8rpx;
	display: flex;
	align-items: center;
	justify-content: center;
	cursor: pointer;
	transition: all 0.2s;
}

.cell:hover {
	transform: scale(1.05);
}

.cell.player1 {
	background-color: #FF69B4;
}

.cell.player2 {
	background-color: #87CEEB;
}

.cell.last-move {
	box-shadow: 0 0 10rpx #FFD700;
}

.piece-inner {
	width: 70%;
	height: 70%;
	background-color: rgba(255,255,255,0.3);
	border-radius: 50%;
}

.animating-piece {
	position: absolute;
	border-radius: 6rpx;
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 10;
	pointer-events: none;
}

.animating-piece .piece-inner {
	width: 70%;
	height: 70%;
	background-color: rgba(255,255,255,0.3);
	border-radius: 50%;
}

.result-overlay {
	position: absolute;
	top: 50%;
	left: 50%;
	transform: translate(-50%, -50%);
	background-color: rgba(0,0,0,0.9);
	padding: 40rpx 60rpx;
	border-radius: 16rpx;
	display: flex;
	flex-direction: column;
	align-items: center;
	z-index: 100;
	min-width: 300rpx;
	max-width: 80%;
	white-space: nowrap;
}

.result-text {
	color: #FFD700;
	font-size: 36rpx;
	font-weight: bold;
	margin-bottom: 20rpx;
	white-space: nowrap;
}

.restart-btn {
	background-color: #1a237e;
	color: #fff;
	font-size: 28rpx;
	padding: 15rpx 35rpx;
	border-radius: 10rpx;
	white-space: nowrap;
	min-width: 160rpx;
	height: auto;
	line-height: 1.2;
}

.status-bar {
	padding: 15rpx 20rpx;
	text-align: center;
	flex-shrink: 0;
	background-color: rgba(255,255,255,0.05);
	border-radius: 12rpx;
	margin-top: 10rpx;
	max-width: 600rpx;
	align-self: center;
}

.game-status-text {
	color: #fff;
	font-size: 36rpx;
	font-weight: bold;
}

.watching-tip {
	display: block;
	color: #FFD700;
	font-size: 26rpx;
	margin-top: 8rpx;
}

.rules-section {
	background-color: rgba(255,255,255,0.05);
	border-radius: 12rpx;
	padding: 15rpx 20rpx;
	margin-top: 10rpx;
	text-align: center;
	max-width: 600rpx;
}

.rules-title {
	color: #FFD700;
	font-size: 28rpx;
	font-weight: bold;
	display: block;
	margin-bottom: 8rpx;
}

.rules-text {
	color: #aaa;
	font-size: 22rpx;
	line-height: 1.5;
	display: block;
}

.connecting-overlay {
	position: fixed;
	top: 0;
	left: 0;
	right: 0;
	bottom: 0;
	background-color: rgba(0,0,0,0.7);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1000;
}

.connecting-overlay text {
	color: #fff;
	font-size: 32rpx;
}

/* 横屏适配 - 基础 */
@media screen and (orientation: landscape) {
	.container {
		padding: 5rpx 15rpx;
		min-height: 100vh;
	}
	
	.top-bar {
		padding: 5rpx 15rpx;
		gap: 20rpx;
		min-height: 100rpx;
	}
	
	.room-label {
		font-size: 28rpx;
	}
	
	.room-id {
		font-size: 32rpx;
	}
	
	.copy-btn {
		font-size: 22rpx;
		padding: 5rpx 12rpx;
	}
	
	.room-input {
		font-size: 24rpx;
		width: 140rpx;
	}
	
	.join-btn {
		font-size: 24rpx;
		padding: 8rpx 20rpx;
	}
	
	.share-icon {
		font-size: 24rpx;
	}
	
	.game-area {
		gap: 15rpx;
		padding: 5rpx 10rpx;
		flex: 1;
		min-height: 0;
	}
	
	.player-info {
		padding: 8rpx;
		min-width: 80rpx;
	}
	
	.player-avatar {
		width: 50rpx;
		height: 50rpx;
		margin-bottom: 4rpx;
	}
	
	.player-name {
		font-size: 20rpx;
		max-width: 70rpx;
	}
	
	.player-name-input {
		font-size: 18rpx;
		width: 70rpx;
	}
	
	.player-status {
		font-size: 16rpx;
	}
	
	.cell {
		width: 45rpx;
		height: 45rpx;
	}
	
	.board {
		padding: 8rpx;
		gap: 4rpx;
	}
	
	.row {
		gap: 4rpx;
	}
	
	.status-bar {
		padding: 8rpx;
		margin-top: 5rpx;
	}
	
	.game-status-text {
		font-size: 24rpx;
	}
	
	.rules-section {
		padding: 10rpx 15rpx;
		margin-top: 5rpx;
	}
	
	.rules-title {
		font-size: 24rpx;
	}
	
	.rules-text {
		font-size: 18rpx;
	}
}

/* 移动端横屏适配 */
@media screen and (orientation: landscape) and (max-height: 500px) {
	.container {
		padding: 2rpx 10rpx;
	}
	
	.top-bar {
		padding: 2rpx 10rpx;
		gap: 10rpx;
		min-height: 80rpx;
	}
	
	.room-label {
		font-size: 24rpx;
	}
	
	.room-id {
		font-size: 28rpx;
	}
	
	.copy-btn {
		font-size: 20rpx;
		padding: 4rpx 10rpx;
	}
	
	.room-input {
		font-size: 22rpx;
		width: 120rpx;
		padding: 4rpx 8rpx;
	}
	
	.join-btn {
		font-size: 22rpx;
		padding: 6rpx 16rpx;
	}
	
	.game-area {
		gap: 10rpx;
		padding: 2rpx 5rpx;
	}
	
	.player-info {
		padding: 6rpx;
		min-width: 70rpx;
	}
	
	.player-avatar {
		width: 40rpx;
		height: 40rpx;
		margin-bottom: 3rpx;
	}
	
	.player-name {
		font-size: 18rpx;
		max-width: 60rpx;
	}
	
	.player-name-input {
		font-size: 16rpx;
		width: 60rpx;
	}
	
	.player-status {
		font-size: 14rpx;
	}
	
	.cell {
		width: 40rpx;
		height: 40rpx;
	}
	
	.board {
		padding: 6rpx;
		gap: 3rpx;
	}
	
	.row {
		gap: 3rpx;
	}
	
	.status-bar {
		padding: 6rpx;
	}
	
	.game-status-text {
		font-size: 20rpx;
	}
	
	.watching-tip {
		font-size: 18rpx;
		margin-top: 4rpx;
	}
	
	.rules-section {
		padding: 8rpx 12rpx;
	}
	
	.rules-title {
		font-size: 22rpx;
		margin-bottom: 4rpx;
	}
	
	.rules-text {
		font-size: 16rpx;
		line-height: 1.4;
	}
	
	.result-overlay {
		padding: 25rpx 40rpx;
		min-width: 220rpx;
	}
	
	.result-text {
		font-size: 26rpx;
	}
	
	.restart-btn {
		font-size: 20rpx;
		padding: 8rpx 20rpx;
		min-width: 100rpx;
		height: auto;
		line-height: 1.2;
	}
}

/* 横屏适配 - 中等屏幕 (800-960px) */
@media screen and (orientation: landscape) and (min-width: 800px) and (max-width: 960px) {
	.container {
		padding: 5rpx 10rpx;
	}
	
	.top-bar {
		padding: 5rpx 15rpx;
		gap: 15rpx;
		min-height: 80rpx;
	}
	
	.room-label {
		font-size: 24rpx;
	}
	
	.room-id {
		font-size: 26rpx;
	}
	
	.copy-btn {
		font-size: 16rpx;
		padding: 4rpx 12rpx;
	}
	
	.room-input {
		font-size: 20rpx;
		width: 140rpx;
		padding: 4rpx 12rpx;
	}
	
	.join-btn {
		font-size: 16rpx;
		padding: 6rpx 16rpx;
	}
	
	.share-icon {
		font-size: 24rpx;
	}
	
	.game-area {
		gap: 10rpx;
		padding: 5rpx;
	}
	
	.board-section {
		max-width: 600rpx;
		gap: 10rpx;
	}
	
	.player-info {
		padding: 8rpx;
		min-width: 90rpx;
	}
	
	.player-avatar {
		width: 50rpx;
		height: 50rpx;
		margin-bottom: 4rpx;
	}
	
	.player-name {
		font-size: 20rpx;
		max-width: 80rpx;
	}
	
	.player-name-input {
		font-size: 18rpx;
		width: 80rpx;
	}
	
	.player-status {
		font-size: 16rpx;
	}
	
	.cell {
		width: 50rpx;
		height: 50rpx;
	}
	
	.board {
		padding: 8rpx;
		gap: 4rpx;
	}
	
	.row {
		gap: 4rpx;
	}
	
	.status-bar {
		padding: 8rpx 12rpx;
		margin-top: 5rpx;
	}
	
	.game-status-text {
		font-size: 22rpx;
	}
	
	.watching-tip {
		font-size: 18rpx;
		margin-top: 4rpx;
	}
	
	.rules-section {
		padding: 8rpx 12rpx;
		margin-top: 5rpx;
	}
	
	.rules-title {
		font-size: 22rpx;
		margin-bottom: 4rpx;
	}
	
	.rules-text {
		font-size: 16rpx;
		line-height: 1.4;
	}
	
	.result-overlay {
		padding: 30rpx 50rpx;
		min-width: 260rpx;
	}
	
	.result-text {
		font-size: 30rpx;
	}
	
	.restart-btn {
		font-size: 22rpx;
		padding: 12rpx 25rpx;
		min-width: 130rpx;
		height: auto;
		line-height: 1.2;
	}
}

/* 横屏适配 - 大屏幕 (960px+) */
@media screen and (orientation: landscape) and (min-width: 960px) {
	.top-bar {
		padding: 15rpx 50rpx;
		gap: 40rpx;
		max-width: 1600px;
		margin: 0 auto;
	}
	
	.room-label {
		font-size: 40rpx;
	}
	
	.room-id {
		font-size: 44rpx;
	}
	
	.copy-btn {
		font-size: 32rpx;
		padding: 10rpx 24rpx;
	}
	
	.room-input {
		font-size: 36rpx;
		padding: 12rpx 24rpx;
		width: 260rpx;
		min-width: 260rpx;
	}
	
	.join-btn {
		font-size: 34rpx;
		padding: 14rpx 32rpx;
	}
	
	.share-icon {
		font-size: 32rpx;
	}

	.rules-section {
		margin-top: -100rpx;
		min-width: 400rpx;
		min-height: 160rpx;
	}

	.rules-title {
		font-size: 32rpx;
		margin-bottom: 4rpx;
	}
	
	.rules-text {
		font-size: 26rpx;
		line-height: 1.6;
	}

	.game-area {
		max-height: 900rpx;
	}
	
	.board-section {
		max-width: 1200rpx;
		max-height: 800rpx;
		gap: 20rpx;
	}
	
	.board-container {
		min-width: 800rpx;
	}
	
	.board-wrapper {
		min-width: 800rpx;
	}
	
	.player-info {
		padding: 15rpx;
		min-width: 160rpx;
	}
	
	.player-avatar {
		width: 80rpx;
		height: 80rpx;
	}
	
	.player-name {
		font-size: 28rpx;
		max-width: 160rpx;
	}
	
	.cell {
		width: 75rpx;
		height: 75rpx;
	}
	
	.board {
		padding: 15rpx;
		gap: 8rpx;
	}
	
	.row {
		gap: 8rpx;
	}
	
	.result-overlay {
		padding: 40rpx 70rpx;
		min-width: 350rpx;
	}
	
	.result-text {
		font-size: 44rpx;
	}
	
	.restart-btn {
		font-size: 32rpx;
		padding: 16rpx 35rpx;
		min-width: 160rpx;
		height: auto;
		line-height: 1.2;
	}
}


</style>
