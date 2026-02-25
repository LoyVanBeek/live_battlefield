from dataclasses import dataclass, replace
from typing import Optional, TYPE_CHECKING, Any
from app.events.types import EventType
from app.database import GameEvent

if TYPE_CHECKING:
    from app.game.state import GameState, TeamState, BombResult


@dataclass
class TeamJoinedEvent:
    event_type: EventType = EventType.TEAM_JOINED
    name: str = ""
    color: str = ""
    chat_id: int = 0
    bombs: int = 0
    quick_action: Optional[str] = None
    count: Optional[int] = None

    def apply(self, state: "GameState") -> tuple["GameState", "TeamJoinedEvent"]:
        from app.game.state import TeamState

        if self.quick_action:
            color = self.color
            if color and color in state.teams:
                new_teams = dict(state.teams)
                team = new_teams[color]

                if self.quick_action == "add_bombs":
                    count = self.count if self.count is not None else 1
                    new_teams[color] = team.with_bombs(team.bombs + count)
                elif self.quick_action == "reset_team":
                    new_teams[color] = team.with_reset()
                elif self.quick_action == "place_all_ships":
                    pass

                return replace(state, teams=new_teams), self

            return state, self

        color = self.color
        if color in state.teams:
            return state, self

        new_team = TeamState(
            name=self.name,
            color=color,
            chat_id=self.chat_id,
            bombs=self.bombs,
        )
        new_teams = {**state.teams, color: new_team}
        return replace(state, teams=new_teams), self

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.TEAM_JOINED,
            payload={
                "name": self.name,
                "color": self.color,
                "chat_id": self.chat_id,
                "bombs": self.bombs,
                "quick_action": self.quick_action,
                "count": self.count,
            },
            player_id=player_id,
        )


@dataclass
class ShipPlacedEvent:
    event_type: EventType = EventType.SHIP_PLACED
    color: str = ""
    ship_type: str = ""
    row: int = 0
    col: int = 0
    direction: str = ""
    quick_action: Optional[str] = None
    success: bool = False

    def apply(self, state: "GameState") -> tuple["GameState", "ShipPlacedEvent"]:
        from app.game.state import TeamState

        if self.quick_action:
            color = self.color
            if color and color in state.teams:
                new_teams = dict(state.teams)
                team = new_teams[color]

                if self.quick_action == "reset_team":
                    new_teams[color] = team.with_reset()
                elif self.quick_action == "place_all_ships":
                    pass

                return replace(state, teams=new_teams), self

            return state, self

        color = self.color
        if color not in state.teams:
            return state, self

        team = state.teams[color]
        success, new_team = team.place_ship(
            self.ship_type, self.row, self.col, self.direction
        )

        if not success:
            return state, replace(self, success=False)

        new_teams = {**state.teams, color: new_team}
        return replace(state, teams=new_teams), replace(self, success=True)

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.SHIP_PLACED,
            payload={
                "color": self.color,
                "ship_type": self.ship_type,
                "row": self.row,
                "col": self.col,
                "direction": self.direction,
                "quick_action": self.quick_action,
                "success": self.success,
            },
            player_id=player_id,
        )


@dataclass
class BombThrownEvent:
    event_type: EventType = EventType.BOMB_THROWN
    attacker_color: str = ""
    target_color: str = ""
    row: int = 0
    col: int = 0
    result: Optional[str] = None
    ship_type: Optional[str] = None
    ship_sunk: Optional[bool] = None

    def apply(self, state: "GameState") -> tuple["GameState", "BombThrownEvent"]:
        from app.game.state import TeamState, BombResult

        attacker_color = self.attacker_color
        target_color = self.target_color

        if attacker_color not in state.teams:
            return state, self
        if target_color not in state.teams:
            return state, self

        attacker = state.teams[attacker_color]
        target = state.teams[target_color]

        if attacker.bombs <= 0:
            return state, self

        result, ship, new_target = target.receive_bomb(
            self.row, self.col, attacker_color
        )

        new_teams = dict(state.teams)
        if target_color == attacker_color:
            new_teams[attacker_color] = new_target.with_bombs(attacker.bombs - 1)
        else:
            new_attacker = attacker.with_bombs(attacker.bombs - 1)
            new_teams[attacker_color] = new_attacker
            new_teams[target_color] = new_target

        updated_event = replace(
            self,
            result=result.value,
            ship_type=ship.ship_type if ship else None,
            ship_sunk=ship.is_sunk() if ship else None,
        )

        return replace(state, teams=new_teams), updated_event

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.BOMB_THROWN,
            payload={
                "attacker_color": self.attacker_color,
                "target_color": self.target_color,
                "row": self.row,
                "col": self.col,
                "result": self.result,
                "ship_type": self.ship_type,
                "ship_sunk": self.ship_sunk,
            },
            player_id=player_id,
        )


@dataclass
class CodeRedeemedEvent:
    event_type: EventType = EventType.CODE_REDEEMED
    color: str = ""
    location_number: int = 0
    code: str = ""
    success: bool = True
    bombs_earned: int = 1

    def apply(self, state: "GameState") -> tuple["GameState", "CodeRedeemedEvent"]:
        from app.game.state import TeamState

        color = self.color
        location_number = self.location_number
        code = self.code

        if color not in state.teams:
            return state, replace(self, success=False)

        if location_number not in state.location_codes:
            return state, replace(self, success=False)

        if state.location_codes[location_number] != code:
            return state, replace(self, success=False)

        team = state.teams[color]
        new_team = team.with_bombs(team.bombs + self.bombs_earned)

        new_teams = {**state.teams, color: new_team}
        return replace(state, teams=new_teams), replace(self, success=True)

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.CODE_REDEEMED,
            payload={
                "color": self.color,
                "location_number": self.location_number,
                "code": self.code,
                "success": self.success,
                "bombs_earned": self.bombs_earned,
            },
            player_id=player_id,
        )


@dataclass
class LocationAddedEvent:
    event_type: EventType = EventType.LOCATION_ADDED
    number: int = 0
    latitude: float = 0.0
    longitude: float = 0.0
    code: str = ""
    bomb_value: int = 1

    def apply(self, state: "GameState") -> tuple["GameState", "LocationAddedEvent"]:
        number = self.number
        code = self.code

        new_location_codes = {**state.location_codes, number: code}
        new_counter = (
            number if number > state.location_counter else state.location_counter
        )

        return (
            replace(
                state,
                location_codes=new_location_codes,
                location_counter=new_counter,
            ),
            self,
        )

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.LOCATION_ADDED,
            payload={
                "number": self.number,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "code": self.code,
                "bomb_value": self.bomb_value,
            },
            player_id=player_id,
        )
