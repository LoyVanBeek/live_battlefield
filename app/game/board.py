from app.game.state import TeamState, GameState
from app.game.ships import COLS, BOARD_SIZE
from PIL import Image, ImageDraw, ImageFont
from typing import Optional
import io


COLOR_MAP = {
    "red": (220, 60, 60),
    "blue": (60, 100, 220),
    "green": (60, 180, 80),
    "purple": (160, 60, 180),
    "orange": (255, 150, 50),
    "yellow": (220, 200, 60),
}

CELL_SIZE = 30
HEADER_SIZE = 30
GRID_SIZE = CELL_SIZE * BOARD_SIZE + HEADER_SIZE


def render_board(
    team: TeamState,
    show_private: bool = False,
    viewer_team: Optional[TeamState] = None
) -> Image.Image:
    img = Image.new("RGB", (GRID_SIZE, GRID_SIZE), "white")
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except:
        font = ImageFont.load_default()
    
    for i in range(BOARD_SIZE):
        x = HEADER_SIZE + i * CELL_SIZE
        draw.text((x + 8, 5), COLS[i], fill="black", font=font)
    
    for i in range(1, BOARD_SIZE + 1):
        y = HEADER_SIZE + (i - 1) * CELL_SIZE
        draw.text((5, y + 8), str(i), fill="black", font=font)
    
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            x1 = HEADER_SIZE + col * CELL_SIZE
            y1 = HEADER_SIZE + row * CELL_SIZE
            x2 = x1 + CELL_SIZE
            y2 = y1 + CELL_SIZE
            
            draw.rectangle((x1, y1, x2, y2), outline="gray", width=1)
            
            if show_private and team.private_board[row][col]:
                ship = team.get_ship_at(row, col)
                if ship and ship.is_sunk():
                    draw.rectangle((x1 + 2, y1 + 2, x2 - 2, y2 - 2), fill="darkred")
                else:
                    draw.rectangle((x1 + 2, y1 + 2, x2 - 2, y2 - 2), fill="black")
            
            cell = team.public_board[row][col]
            if cell:
                color_name, is_hit = cell
                rgb = COLOR_MAP.get(color_name, (128, 128, 128))
                
                if is_hit:
                    draw.ellipse((x1 + 4, y1 + 4, x2 - 4, y2 - 4), fill=rgb)
                else:
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    draw.line((x1 + 4, y1 + 4, x2 - 4, y2 - 4), fill=rgb, width=2)
                    draw.line((x2 - 4, y1 + 4, x1 + 4, y2 - 4), fill=rgb, width=2)
    
    return img


def render_all_public_boards(state, show_titles: bool = True) -> Image.Image:
    if not state.teams:
        img = Image.new("RGB", (GRID_SIZE + 40, GRID_SIZE + 40), "white")
        return img
    
    team_count = len(state.teams)
    cols = min(3, team_count)
    rows = (team_count + cols - 1) // cols
    
    board_width = GRID_SIZE + (60 if show_titles else 20)
    board_height = GRID_SIZE + (40 if show_titles else 20)
    
    total_width = board_width * cols
    total_height = board_height * rows
    
    img = Image.new("RGB", (total_width, total_height), "white")
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except:
        title_font = ImageFont.load_default()
    
    for idx, (color, team) in enumerate(state.teams.items()):
        col_idx = idx % cols
        row_idx = idx // cols
        
        offset_x = col_idx * board_width
        offset_y = row_idx * board_height
        
        if show_titles:
            rgb = COLOR_MAP.get(color, (128, 128, 128))
            draw.text((offset_x + 30, offset_y + 5), f"{team.name} ({color})", fill=rgb, font=title_font)
        
        board_img = render_board(team, show_private=False)
        img.paste(board_img, (offset_x + (10 if show_titles else 10), offset_y + (30 if show_titles else 10)))
    
    return img


def boards_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def render_private_board(team: TeamState) -> Image.Image:
    return render_board(team, show_private=True)


def create_public_board_gif(events: list, team_color: str) -> bytes:
    from app.events.factory import create_events

    typed_events = create_events(events)
    frames = []
    prev_board_repr = None

    state = GameState()
    for event in typed_events:
        state, _ = event.apply(state)
        if team_color in state.teams:
            team = state.teams[team_color]
            board_repr = str(team.public_board)
            if board_repr != prev_board_repr:
                prev_board_repr = board_repr
                frame = render_board(team, show_private=False)
                frames.append(frame)

    if not frames:
        return b""

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=500,
        loop=0,
        optimize=True,
    )
    buf.seek(0)
    return buf.getvalue()
