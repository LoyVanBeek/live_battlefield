# Live Battleship
Create an app, played through the Telegram messaging app, to play the boardgame Battleship in real life, with multiple players/teams.

Players can take steps in the game via Telegram commands. There is an overview of the game state available via a website as well as via Telegram.

Each player/team has:
- An assigned color
- Chosen team name
- A private board
- A public board
- private inventory of bombs

There are also one or more game masters, that manage the game and sets up the locations with codes.

At the start of the game, each player sets up 10 ships on a **private** 10x10 playing field (with columns labeled A to J and rows labeled 1 to 10).
Only a team itself initially knows where all of it's ships are and only sees an empty **public** board of all teams. 
Using these public boards of the other teams, a team can decide which other team to bomb on a given board coordinate.

If the bombed coordinate hits one of the ships (as can be determined using the receiving teams' private board), the square (on the public board) at the coordinate is filled with the color of the team that threw the bomb
If the bombed coordinate hits nothing but just ocean (as can be determined using the receiving teams' private board), then there is a cross drown in the square (on the public board)  at the coordinate, also in the color of the team that threw the bomb. 

The aim of the game is to use bombs to destroy the ships of the other teams until one team is victorious. 

Bombs can be earned by doing quests in real life and sending pictures of the result.
These quests are places in real life locations that the players or teams must visit. 

Each location:
- has a number
- Is indicated on a map
- in real life, there is some code visible or hidden at the location, or a question must be answered there that can only be answered there to indicate the players were really at that location.
	- A code is comprised of a few alpha-numeric character that are easy for humans to enter into their phones. 

## Ship types
There are 10 ships per team:
- 1x airplane carrier (6 squares)
- 2x battleship (4 squares each)
- 3x torpedo hunter (3 squres each)
- 4x patrol shop (2 squares each)

Ships can be placed either vertical or horizontal, but not diagonally. 
Ships cannot touch each other either. 
# Game events and their commands
- Add location. This command can only be performed by game masters and is rejected when sent by other participants.
	- This is done by sending a Telegram location message with, optionally, the code as it's accompanying text. 
		- The system then assigns a number to this location and if no code is given, the system assigns a code for this location. 
- Add team:
	- This is done by sending: 
		- `/join <team name>`
		- This adds a new team to the game and assigns them a color for a fixed palette (red, blue, green, red, purple, orange). If the colors run out, the game is full and the team cannot join. 
		- The corresponding Telegram chat ID is coupled to the teams' color in the database. 
- Placing a ship
	- This is done by sending:
		- `/place <ship type> <coordinate> <direction>
		- `<ship type>` indicates the type of ship as listed under 'ship types'
		- `<coordinate>` indicates the coordinates of one end of the ship (eg. B2)
		- `<direction>` indicates the direction (horizontal or vertical)
	- The system then tries to put the given ship on the teams's private board and checks if it matches the rules (no touching, and of course the given ship must still be available and not all ships of the given ship type must be exhausted.)
	- As a result, the complete state of the teams' board is shown via Telegram.
- Throwing a bomb
	- This is done by sending:
		- `/bomb <team> <coordinate>`
		- The `<team>` indicates which team's board to bomb. This is indicated by the team's color
		- `<coordinate>` indicates the coordinates where to throw a bomb (eg. B2)
	- If the receiving team does have a ship occupying the given coordinate, there is a hit or miss and this is indicated on the teams' public board accordingly.
	- The team that was attacked is sent a message via telegram with a summary of what happened: team X bombed you at coordinate... and hit/missed a ship.
- Earning bombs
	- This can be done by visiting locations in real life. The game masters have placed codes at these locations and by visiting these location players can obtain the secret code.
	- Once a location has been visited and the secret code obtained, they can send a command. 
	- This is done by sending:
		- `/code <location number> <code>`
		- The `<location number` is one from the location list
		- The`<code>` is the code teams found at the location
	- If the code is correct, a bomb is added to the teams' inventory.
- Overview
	- Teams can get an overview of their private board and the public boards by sending the command `/overview`. 

# Technology
Write the app in Python, using the `uv` project manager. 
Use the `python-telegram-bot` library to interact with the Telegram API. 
Use the event sourcing paradigm to keep track of game events and store each event in a PostgreSQL  database.
The PostgreSQL database also has a table for players, that keeps track of their color, name and Telegram chat ID, as well as their role

The current game state (the result of all game events in sequence) is rendered to an image displaying all of the team's public boards.
Each team has a private board where it can see the location of it's own ships, which is hidden for other teams. 

Each event has some logic to update the game's state. Replaying the events and the associated logic results in the current game state that can be rendered and displayed to the players and a game master.

In the future, additional commands, events and corresponding game logic can be added to enhance the game. 

## Deployment
The whole system must be deploy-able via `Docker` containers and can be brought online via a single `docker compose` command. A Telegram API key can be supplied via the `.env` file, more configuration is not needed. 

# Steps
- [ ] Create the database schema for this application
	- [ ] Add scripts to insert dummy events
- [ ] Create the game logic, to process each event and to represent the resulting game state
	- [ ] Add tests for the logic
- [ ] Represent the game state as an image or HTML that can be rendered to an image
	- [ ] Add tests for this as well
- [ ] Create the messaging interface:
	- [ ] to create game events from Telegram commands
	- [ ] insert those into the database
	- [ ] reply with the resulting game state.
