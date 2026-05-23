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
BORDER_SIZE = 2
TOTAL_SIZE = GRID_SIZE + BORDER_SIZE * 2
BORDER_COLOR = (51, 51, 51)
HEADER_BG = (224, 224, 224)
HEADER_FG = (51, 51, 51)
GRID_LINE_COLOR = (204, 204, 204)


def _blend(color, alpha, bg=(255, 255, 255)):
    return tuple(int(c * alpha + bg[i] * (1 - alpha)) for i, c in enumerate(color))


def render_board(
    team: TeamState,
    show_private: bool = False,
    viewer_team: Optional[TeamState] = None
) -> Image.Image:
    img = Image.new("RGB", (TOTAL_SIZE, TOTAL_SIZE), BORDER_COLOR)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except:
        font = ImageFont.load_default()

    draw.rectangle((BORDER_SIZE, BORDER_SIZE, TOTAL_SIZE - BORDER_SIZE - 1, TOTAL_SIZE - BORDER_SIZE - 1), fill="white")

    for i in range(BOARD_SIZE):
        x = BORDER_SIZE + HEADER_SIZE + i * CELL_SIZE
        draw.rectangle((x, BORDER_SIZE, x + CELL_SIZE, BORDER_SIZE + HEADER_SIZE), fill=HEADER_BG, outline=GRID_LINE_COLOR)
        draw.text((x + 8, BORDER_SIZE + 5), COLS[i], fill=HEADER_FG, font=font)

    for i in range(1, BOARD_SIZE + 1):
        y = BORDER_SIZE + HEADER_SIZE + (i - 1) * CELL_SIZE
        draw.rectangle((BORDER_SIZE, y, BORDER_SIZE + HEADER_SIZE, y + CELL_SIZE), fill=HEADER_BG, outline=GRID_LINE_COLOR)
        draw.text((BORDER_SIZE + 5, y + 8), str(i), fill=HEADER_FG, font=font)

    draw.rectangle(
        (BORDER_SIZE, BORDER_SIZE, BORDER_SIZE + HEADER_SIZE, BORDER_SIZE + HEADER_SIZE),
        fill=HEADER_BG, outline=GRID_LINE_COLOR
    )

    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE):
            x1 = BORDER_SIZE + HEADER_SIZE + col * CELL_SIZE
            y1 = BORDER_SIZE + HEADER_SIZE + row * CELL_SIZE
            x2 = x1 + CELL_SIZE
            y2 = y1 + CELL_SIZE

            draw.rectangle((x1, y1, x2, y2), outline=GRID_LINE_COLOR, width=1)

            if show_private and team.private_board[row][col]:
                ship = team.get_ship_at(row, col)
                if ship and ship.is_sunk():
                    draw.rectangle((x1 + 2, y1 + 2, x2 - 2, y2 - 2), fill="darkred")
                else:
                    draw.rectangle((x1 + 2, y1 + 2, x2 - 2, y2 - 2), fill="black")

            cell = team.public_board[row][col]
            if cell:
                attacker_color_name, is_hit = cell
                attacker_rgb = COLOR_MAP.get(attacker_color_name, (128, 128, 128))

                if is_hit:
                    board_color = COLOR_MAP.get(team.color)
                    if board_color:
                        fill = _blend(board_color, 0.4)
                        draw.rectangle((x1 + 1, y1 + 1, x2 - 1, y2 - 1), fill=fill)
                    draw.line((x1 + 4, y1 + 4, x2 - 4, y2 - 4), fill=attacker_rgb, width=2)
                    draw.line((x2 - 4, y1 + 4, x1 + 4, y2 - 4), fill=attacker_rgb, width=2)
                else:
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=attacker_rgb)

    return img


def render_all_public_boards(state, show_titles: bool = True) -> Image.Image:
    if not state.teams:
        img = Image.new("RGB", (TOTAL_SIZE + 40, TOTAL_SIZE + 40), "white")
        return img

    team_count = len(state.teams)
    cols = min(3, team_count)
    rows = (team_count + cols - 1) // cols

    board_width = TOTAL_SIZE + (60 if show_titles else 20)
    board_height = TOTAL_SIZE + (40 if show_titles else 20)

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
    final_state = None

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
        final_state = state

    if not frames:
        return b""

    if final_state and final_state.status.value == "ended":
        winner = final_state.get_winner()
        if winner:
            last = frames[-1].copy()
            draw = ImageDraw.Draw(last)
            bar_h = 36
            draw.rectangle((0, last.height - bar_h, last.width, last.height), fill=(0, 0, 0))
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
            except:
                font = ImageFont.load_default()
            text = f"{winner.name} ({winner.color}) wins!"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text(((last.width - tw) // 2, last.height - bar_h + (bar_h - th) // 2), text, fill="white", font=font)
            frames[-1] = last

    buf = io.BytesIO()
    durations = [500] * (len(frames) - 1) + [3000]
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    buf.seek(0)
    return buf.getvalue()
