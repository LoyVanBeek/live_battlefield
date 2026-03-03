# TODO

## Completed Items
- [x] Only start game once all ships are placed 
- [x] only start game once all locations are set. 
- [x] Equally divide bombs over locations,  with total bomb count being equal to board size
- [x] Do not allow new joins once game is started
- [x] Add an overview of all locations on a map
- [x] of each team with locations not yet redeemed 
- [x] add an overview of all codes
- [x] Accept `[Enter]` as button press on admin panel
- [x] Receive a message when you are hit by a bomb
- [x] Let `/locations` show an overview of all locations, not a list of URLs.  --> Not possible in a single view. Can send many location pin message, but that is unwiedly with many locations but not a map view. 
- [x] Re-order test-panel web UI: Show a row with the game status, buttons to start or stop if applicable. Then all the public boards, then below for each team a column with basic stats and their private board. Below the other buttons to reset stuff. 
- [x] Add the 'create locations' to the locations-secret page. 
- [x] Add 'Remove location' button+API
- [x] Add a page for each team via which they can play the game: See the other teams' public boards, a function to throw bombs, redeem codes, see their own private board and place ships. In that order. 
- [x] Add Telegram menu so you don't have to type the full commands https://core.telegram.org/bots/features#commands 
- [x] These send the command directly, so not able to add extra arguments
- [x] Create a nice-looking web-app for users/players
- [x] Write tests first! Make them first, have the fail, then add code to make the tests pass
- [x] Start with different Event types that have a Event-specific structure and parameters
- [x] Add tests for the web-API as well. 
- [x] Make the front-end (Telegram, an API, a web app, WhatsApp, admin panel) all produce `Events`.
- [x] Each event is handled by a specific handler that takes a current `GameState` + an `Event` and produces a new `GameState`.
- [x] The total `GameState` is thus the product of subsequent `Events`
- [x] Logging in console for each event
- [x] AI players, that throw bombs at roughly the same pace as the humans
- [x] Test this!
- [x] Adding+5 bombs doesn't work anymore
- [x] start/end game should be events as well 
- [x] Add scripts to play a bit of a game
- [x] Add script to finish a whole game
- [x] Fix "Add all ships" 
- [x] Add a command to add all ships for users in Telegram as well
- [x] BUG: Show correct column and row labels in html rendering
- [x] Show event timestamps in timeline
- [x] Bug: game can start before all ships are placed and without locations
- [ ] variable board size, with matching ships
## Remaining Items

| # | Item | Plan |
|---|------|------|
| 6 | bonus: animation of game state after game ended | [docs/plans/todo-6-animation.md](docs/plans/todo-6-animation.md) |
| 13 | Disable buttons that don't apply | [docs/plans/todo-13-disable-buttons.md](docs/plans/todo-13-disable-buttons.md) |
| 21 | Protect admin panel with HTTP basic auth or a session token | [docs/plans/todo-21-admin-auth.md](docs/plans/todo-21-admin-auth.md) |
| 22 | Draw game state to console on each event | [docs/plans/todo-22-console-renderer.md](docs/plans/todo-22-console-renderer.md) |
| 28 | Separate the front-end from the back-end cleanly | [docs/plans/todo-28-separate-frontend.md](docs/plans/todo-28-separate-frontend.md) |
| 31 | Each `Event` is associated with a `GameId` | [docs/plans/todo-31-multiple-games.md](docs/plans/todo-31-multiple-games.md) |
| 41 | Allows questions and answers for each location | [docs/plans/todo-41-location-qa.md](docs/plans/todo-41-location-qa.md) |
| 45 | AI doesn't go on it's own, needs to be triggered | [docs/plans/todo-45-ai-auto-trigger.md](docs/plans/todo-45-ai-auto-trigger.md) |
| 46 | Make clear on admin page that someone won | [docs/plans/todo-46-winner-display.md](docs/plans/todo-46-winner-display.md) |
| 47 | Add some CI | [docs/plans/todo-47-ci.md](docs/plans/todo-47-ci.md) |
| 48 | Figure out deployment | [docs/plans/todo-48-deployment.md](docs/plans/todo-48-deployment.md) |
