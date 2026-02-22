from fastapi import FastAPI, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import get_all_events
from app.game.state import GameState
from app.game.board import render_all_public_boards, boards_to_bytes

app = FastAPI(title="Live Battlefield API")


@app.get("/")
async def root():
    return {"message": "Live Battlefield API"}


@app.get("/game-state.png")
async def get_game_state(db: AsyncSession = Depends(get_db)):
    events = await get_all_events(db)
    state = GameState.from_events(events)
    img = render_all_public_boards(state)
    img_bytes = boards_to_bytes(img)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/teams")
async def get_teams(db: AsyncSession = Depends(get_db)):
    events = await get_all_events(db)
    state = GameState.from_events(events)

    teams = []
    for color, team in state.teams.items():
        teams.append(
            {
                "name": team.name,
                "color": team.color,
                "bombs": team.bombs,
                "ships_placed": sum(team.placed_ship_types.values()),
                "ships_sunk": len(team.get_sunk_ships()),
                "is_destroyed": team.is_destroyed(),
            }
        )

    winner = state.get_winner()
    return {
        "teams": teams,
        "winner": {"name": winner.name, "color": winner.color} if winner else None,
    }
