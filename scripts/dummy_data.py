#!/usr/bin/env python3
"""
Dummy data script to insert test events into the database.
Run with: python scripts/dummy_data.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import async_session_maker, init_db
from app.models import add_event, create_location, create_game
from app.database import EventType


async def main():
    await init_db()
    
    async with async_session_maker() as db:
        print("Creating dummy data...")
        
        # Create a game
        game = await create_game(db, name="Dummy Game", gm_token="dummy_token")
        game_id = game.id

        # Add locations
        locations = [
            (1, 52.3676, 4.9041, "ABCD"),
            (2, 52.3702, 4.8952, "EFGH"),
            (3, 52.3725, 4.8890, "IJKL"),
        ]

        for num, lat, lon, code in locations:
            await create_location(db, game_id, num, lat, lon, code)
            print(f"Created location {num}")
        
        # Add game events
        events = [
            (EventType.TEAM_JOINED, {
                "name": "Red Team",
                "color": "red",
                "chat_id": 111111,
                "bombs": 3
            }),
            (EventType.TEAM_JOINED, {
                "name": "Blue Team", 
                "color": "blue",
                "chat_id": 222222,
                "bombs": 3
            }),
            (EventType.TEAM_JOINED, {
                "name": "Green Team",
                "color": "green",
                "chat_id": 333333,
                "bombs": 3
            }),
            # Red team ships
            (EventType.SHIP_PLACED, {
                "color": "red",
                "ship_type": "airplane_carrier",
                "row": 0,
                "col": 0,
                "direction": "horizontal"
            }),
            (EventType.SHIP_PLACED, {
                "color": "red",
                "ship_type": "battleship",
                "row": 2,
                "col": 0,
                "direction": "vertical"
            }),
            (EventType.SHIP_PLACED, {
                "color": "red",
                "ship_type": "battleship",
                "row": 5,
                "col": 0,
                "direction": "horizontal"
            }),
            # Blue team ships
            (EventType.SHIP_PLACED, {
                "color": "blue",
                "ship_type": "airplane_carrier",
                "row": 0,
                "col": 0,
                "direction": "vertical"
            }),
            (EventType.SHIP_PLACED, {
                "color": "blue",
                "ship_type": "battleship",
                "row": 7,
                "col": 5,
                "direction": "horizontal"
            }),
            # Red bombs Blue
            (EventType.BOMB_THROWN, {
                "attacker_color": "red",
                "target_color": "blue",
                "row": 0,
                "col": 0,
                "result": "hit"
            }),
            (EventType.BOMB_THROWN, {
                "attacker_color": "red",
                "target_color": "blue",
                "row": 1,
                "col": 0,
                "result": "hit"
            }),
            (EventType.BOMB_THROWN, {
                "attacker_color": "red",
                "target_color": "blue",
                "row": 5,
                "col": 5,
                "result": "miss"
            }),
            # Code redemption
            (EventType.CODE_REDEEMED, {
                "color": "red",
                "location_number": 1,
                "code": "ABCD",
                "success": True
            }),
        ]
        
        for event_type, payload in events:
            await add_event(db, event_type, payload)
            print(f"Added event: {event_type.value}")
        
        print("Dummy data created successfully!")


if __name__ == "__main__":
    asyncio.run(main())
