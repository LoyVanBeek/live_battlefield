# Plan: Questions and Answers for Each Location

## Overview
Add question and answer fields to locations, allowing players to answer location-specific questions to earn bombs instead of just entering codes.

## References
- Original TODO: docs/TODO.md item 41

## Current State
- Locations have: number, latitude, longitude, code, bomb_value
- Players can redeem codes to get bombs
- No question/answer capability

## Implementation Plan

### Step 1: Add question/answer to database
Create migration:
```bash
alembic revision --autogenerate -m "add_location_qa"
```

Modify migration:
```python
op.add_column('locations', sa.Column('question', sa.String(500), nullable=True))
op.add_column('locations', sa.Column('answer', sa.String(200), nullable=True))
```

### Step 2: Update Location model
Modify `app/database.py`:
```python
class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, nullable=False, unique=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    code = Column(String(20), nullable=False)
    question = Column(String(500), nullable=True)  # NEW
    answer = Column(String(200), nullable=True)    # NEW
    bomb_value = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### Step 3: Update models.py functions
Modify `app/models.py`:
```python
async def create_location(
    db: AsyncSession, 
    number: int, 
    latitude: float, 
    longitude: float, 
    code: str,
    question: Optional[str] = None,
    answer: Optional[str] = None
) -> Location:
    location = Location(
        number=number,
        latitude=latitude,
        longitude=longitude,
        code=code,
        question=question,
        answer=answer
    )
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location
```

### Step 4: Update location creation handler
Modify `app/bot/handlers.py` - handle location message parsing:
```python
async def handle_location_message(
    db, 
    message_text: str, 
    gm_chat_id: int
) -> str:
    """Parse location message with optional Q&A.
    
    Format options:
    1. Just code: /addloc lat lon code
    2. With Q&A: /addloc lat lon code | question | answer
    """
    parts = message_text.split("|")
    
    base_parts = parts[0].strip().split()
    if len(base_parts) < 3:
        return "Usage: /addloc <lat> <lon> <code> [|<question> |<answer>]"
    
    latitude = float(base_parts[0])
    longitude = float(base_parts[1])
    code = base_parts[2]
    
    question = None
    answer = None
    if len(parts) > 1:
        question = parts[1].strip()
    if len(parts) > 2:
        answer = parts[2].strip()
    
    # Create location with optional Q&A
    location = await create_location(
        db, number, latitude, longitude, code, question, answer
    )
    ...
```

### Step 5: Update code redemption to check answer
Modify `app/bot/handlers.py` - handle_code:
```python
async def handle_code(
    db, 
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    location_number: int,
    code_or_answer: str
):
    """Handle /code command - can use code OR answer."""
    # Get location
    location = await get_location_by_number(db, location_number)
    
    if not location:
        return f"Location {location_number} not found."
    
    # Check if it's a code or answer
    is_valid = False
    
    # First check the code
    if location.code.lower() == code_or_answer.lower():
        is_valid = True
    
    # Then check answer if available
    elif location.answer and location.answer.lower() == code_or_answer.lower():
        is_valid = True
    
    if is_valid:
        # Award bombs
        event = CodeRedeemedEvent(
            color=player.color,
            location_number=location_number,
            code=code_or_answer,
            success=True,
            bombs_earned=location.bomb_value
        )
        await save_event(db, event.to_game_event(), player.id)
        return f"Correct! You've earned {location.bomb_value} bomb(s)!"
    
    # Show question if available and answer wrong
    if location.question:
        return f"Wrong answer! Hint: {location.question}"
    
    return "Invalid code!"
```

### Step 6: Update locations API endpoint
Modify `app/api/routes.py`:
```python
@app.get("/api/locations")
async def get_locations():
    """Get all locations (without answers)."""
    async with async_session_maker() as session:
        locations = await get_all_locations(session)
        return [
            {
                "number": loc.number,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "question": loc.question,  # Include question (not answer!)
                "bomb_value": loc.bomb_value
            }
            for loc in locations
        ]
```

### Step 7: Update admin page for Q&A
Modify `app/templates/admin.html` or create locations management:

```html
<!-- Location creation form -->
<form id="add-location-form">
    <input type="number" name="latitude" placeholder="Latitude" required>
    <input type="number" name="longitude" placeholder="Longitude" required>
    <input type="text" name="code" placeholder="Code" required>
    <input type="number" name="bomb_value" placeholder="Bomb value" value="1">
    <input type="text" name="question" placeholder="Question (optional)">
    <input type="text" name="answer" placeholder="Answer (optional)">
    <button type="submit">Add Location</button>
</form>

<!-- Location list with Q&A -->
<table id="locations-table">
    <tr>
        <th>Number</th>
        <th>Coords</th>
        <th>Code</th>
        <th>Question</th>
        <th>Answer</th>
        <th>Bombs</th>
    </tr>
    <!-- Loop through locations -->
</table>
```

### Step 8: Update locations-secret page
Similarly update the locations admin page to show Q&A fields for management.

## Files to Modify
1. `app/database.py` - Add question/answer columns
2. `app/models.py` - Update create_location function
3. `app/bot/handlers.py` - Update location creation and code redemption
4. `app/api/routes.py` - Update locations endpoint (exclude answer)

## Files to Create
1. Migration file (via alembic)

## Usage Examples

### Creating a location with Q&A:
```
GM sends in Telegram:
/addloc 51.5074 -0.1278 SECRET123 | What year is the nearest building built? | 1890

Or just code:
/addloc 51.5074 -0.1278 SECRET123
```

### Player redeems:
```
/code 1 SECRET123   # Uses code
/code 1 1890        # Uses answer
```

### Display to players:
When using /locations, show:
- Location 1: 51.5074, -0.1278 (Question: "What year is the nearest building built?")

## Testing
1. Create location with question/answer
2. Redeem using code - should work
3. Redeem using answer - should work
4. Redeem with wrong answer - should show question hint
5. Check API doesn't leak answers
