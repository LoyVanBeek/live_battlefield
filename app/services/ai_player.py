import asyncio
import random
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import get_all_events, get_player_by_color
from app.game.state import GameState, GameStatusField
from app.events import BombThrownEvent, save_event
from app.game.ships import BOARD_SIZE
from app.config import settings


AI_BOMB_INTERVAL = 120  # 2 minutes between bombs
AI_MIN_BOMBS_THRESHOLD = 2  # Request bombs when at or below this
AI_BOMB_REQUEST_COOLDOWN = 60  # Seconds between bomb requests


class AIPlayer:
    def __init__(self, color: str, name: str):
        self.color = color
        self.name = name
        self.bomb_interval = AI_BOMB_INTERVAL
        self.min_bombs_threshold = AI_MIN_BOMBS_THRESHOLD
        self.last_bomb_request = 0
        self.is_paused = False

    async def is_active(self, game_state: GameState) -> bool:
        """Check if AI should be active"""
        if self.is_paused:
            return False
        if game_state.status != GameStatusField.STARTED:
            return False
        if self.color not in game_state.teams:
            return False
        return True

    async def should_request_bombs(self, team_state) -> bool:
        """Check if AI needs more bombs"""
        if team_state.bombs <= self.min_bombs_threshold:
            import time

            if time.time() - self.last_bomb_request > AI_BOMB_REQUEST_COOLDOWN:
                self.last_bomb_request = time.time()
                return True
        return False

    async def select_target(self, game_state: GameState) -> Optional[tuple[str, str]]:
        """Select target team and coordinate to bomb"""
        my_team = game_state.teams.get(self.color)
        if not my_team or my_team.bombs <= 0:
            return None

        valid_targets = []

        for color, team in game_state.teams.items():
            if color == self.color:
                continue

            if self._is_team_destroyed(team):
                continue

            valid_targets.append((color, team))

        if not valid_targets:
            return None

        target_color, target = random.choice(valid_targets)

        bomb_coord = self._select_bomb_coordinate(target, my_team)

        if bomb_coord is None:
            return None

        return target_color, bomb_coord

    def _is_team_destroyed(self, team) -> bool:
        """Check if all ships are sunk"""
        if not team.ships:
            return False
        for ship in team.ships:
            if not ship.is_sunk():
                return False
        return True

    def _select_bomb_coordinate(self, target, attacker) -> Optional[str]:
        """Select a coordinate to bomb on target's board"""
        valid_coords = []

        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if (row, col) in attacker.bombed_cells:
                    continue
                if (row, col) in target.bombed_cells:
                    continue
                valid_coords.append((row, col))

        if not valid_coords:
            return None

        row, col = random.choice(valid_coords)

        from app.game.ships import coordinate_to_string

        return coordinate_to_string(row, col)

    async def execute_bomb(self, db: AsyncSession, game_state: GameState) -> bool:
        """Execute bomb throw"""
        target_info = await self.select_target(game_state)

        if target_info is None:
            return False

        target_color, coord = target_info

        from app.game.ships import parse_coordinate, coordinate_to_string

        row, col = parse_coordinate(coord)

        event = BombThrownEvent(
            attacker_color=self.color,
            target_color=target_color,
            row=row,
            col=col,
        )

        await save_event(db, event)

        # Send notification to target player
        from app.models import get_player_by_color
        from app.config import settings

        print(f"[AI] Looking for target player: {target_color}")
        target_player = await get_player_by_color(db, target_color)
        print(
            f"[AI] Target player found: {target_player}, chat_id: {target_player.chat_id if target_player else None}"
        )

        if target_player and target_player.chat_id:
            try:
                # Check if this is a hit or miss by applying the event to game state
                from app.game.state import GameState, GameStatusField

                # Get fresh state with the new event
                events = await get_all_events(db)
                state = GameState.from_events(events)

                # Find the target team
                if target_color in state.teams:
                    target_team = state.teams[target_color]
                    target_cell = target_team.public_board[row][col]

                    coord_display = coordinate_to_string(row, col)

                    if target_cell and target_cell[1]:  # Hit
                        # Check if ship was sunk
                        ship = target_team.get_ship_at(row, col)
                        notify_msg = f"💥 HIT! {self.name} ({self.color}) bombed you at {coord_display}!"
                        if ship and ship.is_sunk():
                            notify_msg = notify_msg.replace("was hit!", "was SUNK!")
                    else:  # Miss
                        notify_msg = f"💨 MISS! {self.name} ({self.color}) missed at {coord_display}!"

                    print(
                        f"[AI] Sending notification to chat_id={target_player.chat_id}: {notify_msg}"
                    )

                    # Send telegram notification
                    from telegram import Bot

                    bot = Bot(token=settings.telegram_bot_token)
                    await bot.send_message(
                        chat_id=target_player.chat_id, text=notify_msg  # ty: ignore[invalid-argument-type]
                    )
                    print(f"[AI] Notification sent successfully!")
            except Exception as e:
                print(f"[AI] Failed to send notification: {e}")
                import traceback

                traceback.print_exc()

        return True


_ai_players: dict[str, AIPlayer] = {}
_ai_tasks: dict[str, asyncio.Task] = {}
_global_pause = False


def get_ai_player(color: str) -> Optional[AIPlayer]:
    return _ai_players.get(color)


def get_all_ai_players() -> dict[str, AIPlayer]:
    return _ai_players.copy()


def add_ai_player(color: str, name: str) -> AIPlayer:
    ai = AIPlayer(color, name)
    _ai_players[color] = ai
    return ai


def remove_ai_player(color: str) -> bool:
    if color in _ai_players:
        del _ai_players[color]
        return True
    return False


def pause_ai_player(color: str) -> bool:
    if color in _ai_players:
        _ai_players[color].is_paused = True
        return True
    return False


def resume_ai_player(color: str) -> bool:
    if color in _ai_players:
        _ai_players[color].is_paused = False
        return True
    return False


def pause_all_ai():
    global _global_pause
    _global_pause = True


def resume_all_ai():
    global _global_pause
    _global_pause = False


def is_all_ai_paused() -> bool:
    return _global_pause
