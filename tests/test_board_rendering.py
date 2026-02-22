import pytest
from PIL import Image
from app.game.state import TeamState, GameState
from app.game.board import render_board, render_all_public_boards, boards_to_bytes


class TestBoardRendering:
    def test_render_empty_board(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        
        img = render_board(team, show_private=True)
        
        assert isinstance(img, Image.Image)
        assert img.size[0] > 0
        assert img.size[1] > 0
    
    def test_render_board_with_ships(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")
        
        img = render_board(team, show_private=True)
        
        assert isinstance(img, Image.Image)
    
    def test_render_public_board(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")
        team.receive_bomb(0, 0, "blue")
        
        img = render_board(team, show_private=False)
        
        assert isinstance(img, Image.Image)
    
    def test_render_all_boards(self):
        state = GameState()
        state.handle_team_joined({
            "name": "Team A", "color": "red", "chat_id": 123, "bombs": 3
        })
        state.handle_team_joined({
            "name": "Team B", "color": "blue", "chat_id": 456, "bombs": 3
        })
        
        img = render_all_public_boards(state)
        
        assert isinstance(img, Image.Image)
    
    def test_boards_to_bytes(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        img = render_board(team, show_private=True)
        
        img_bytes = boards_to_bytes(img)
        
        assert isinstance(img_bytes, bytes)
        assert len(img_bytes) > 0
