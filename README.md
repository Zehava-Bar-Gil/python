# Snake

A two-player Snake game written in Python. Both players share one keyboard. Each player eats apples, earns points, and grows. A player who crashes is eliminated, and the other player wins.

**Author:** Zehava Bar-Gil 

## Requirements

- Python 3 with `tkinter` (included in the standard Windows and macOS installers)
- No additional packages are required.

## How to Run

```bash
python snake.py
```

## Controls

Each snake moves on its own at all times. The player only changes its direction: up, down, left, or right.

| Direction | Player 1 | Player 2 |
|---|---|---|
| Up | Up arrow | W |
| Down | Down arrow | S |
| Left | Left arrow | A |
| Right | Right arrow | D |
| **Starting position** | Center of the board, facing right | Bottom right, facing left |

- A snake cannot reverse direction in a single move, so it cannot run into itself.
- Up to three direction changes can be pressed quickly in a row, and the snake performs them in order.
- Player 2's keys also work when the keyboard is set to Hebrew.
- To change the keys, edit `DIRS` for Player 1 and `P2_KEYS` for Player 2.

**Other keys**

| Key | Action |
|---|---|
| P or Space | Pause |
| Enter, Space, or mouse click | Start a game |
| Esc | Menu or quit |
| L | Switch language |

## Scoring and Food

Every item eaten is worth its points multiplied by the current level, so points add up faster as the game progresses. Every item eaten makes the snake one cell longer.

| Item | Player 1 | Player 2 | Where it appears |
|---|---|---|---|
| Red apple | 25 × level | 10 × level | Always in the same cell: column 20, row 10 |
| Gold star (bonus) | 100 × level | 50 × level | In a random cell |

- **Fixed apple position:** after the apple is eaten, it returns to the same cell. If a wall falls on that exact cell, the apple appears in a random cell for that level. To change the position, edit `FOOD_SPOT`.
- **Bonus stars:** after each apple eaten by Player 1, there is a 30% chance that a star appears. It stays for 45 moves, spins, and blinks before it disappears.
- **Score display:** each player's score is shown at the top of the board. Every time a snake eats, the points earned float above it (for example, +25).
- **High score:** Player 1's highest score is saved, even after the game is closed.

## Speed and Levels

Every 5 apples (eaten by both players together), the game advances one level. On each level the snake moves a little faster and more walls appear. The snake starts slowly and reaches its top speed only at level 14.

| Level | Time between moves (ms) | Walls |
|---|---|---|
| 1 | 220 | None |
| 2 | 210 | 2 horizontal bars |
| 3 | 200 | 2 more vertical bars |
| 4 | 190 | 5 more scattered blocks |
| 5–13 | 10 less on each level | 5 more blocks on each level (up to 40) |
| 14 and up | 90 (fastest) | Same as level 13 |

- **Speed settings:** a smaller number means a faster snake. Edit `BASE_TICK_MS` (starting speed, 220), `TICK_STEP_MS` (speed-up per level, 10), and `MIN_TICK_MS` (top speed, 90).
- **Level up:** a large title with the level number appears, with the message "Faster snake - new walls!" below it.
- **Progress bar:** a purple bar under the score shows how close the players are to the next level.
- A new wall never appears on top of a snake or directly in front of its head.

## Walls, Elimination, and Game Over

When a snake hits something it should not, it is eliminated and the game ends. The other player wins.

| Collision with... | Player 1 | Player 2 |
|---|---|---|
| Edge of the board | Not eliminated; wraps to the opposite side | Not eliminated; wraps to the opposite side |
| Inner wall (from level 2) | Eliminated | Not eliminated; passes through |
| Its own body | Eliminated | Eliminated |
| The other player's snake | Eliminated | Eliminated |
| Head-on collision | Draw | Draw |

**The Game Over screen shows:**

- The winner (or a draw), in a large title in the winner's color
- Player 1's score, the level, and the snake's length
- "NEW RECORD!" if Player 1 set a new high score
- How to play again: Enter or a mouse click

At the moment of elimination, a burst of red sparks appears.

## Instructions and Languages

The instructions appear on the start screen, and the game can switch between English and Hebrew at any time.

**Start screen:**

- The game title
- "Eat - Grow - Level up"
- How to move
- Pause and quit keys
- The high score
- "Press ENTER or click to start" (blinking)

**Pause screen:** explains how to resume or return to the menu.

**Languages:**

- The game opens in English.
- A purple button at the top, next to the score, reads "עברית" or "English". Clicking it or pressing L switches all the text.
- Translated text includes: score, level, high score, instructions, pause, game over, new record, level up, each player's score, and the winner. The window title changes too.
- To translate additional text, add a pair to the `PAIRS` list: the English text and its Hebrew translation.

## Visual Design

A black background with pink and purple snakes that stand out against it.

| Element | Color |
|---|---|
| Background | Black, with barely visible cells (`#050505`, cells `#121212` and `#171717`) |
| Player 1's snake | Pink at the head (`#f472b6`) fading to purple at the tail (`#7c3aed`) |
| Player 2's snake | The same colors: pink to purple |
| Apple | Red with a green leaf |
| Bonus star | Gold |
| Walls | Blue-gray |
| Buttons and frames | Purple |

- **Snake gradient:** the color shifts gradually from the head color to the tail color. For Player 1, edit `snake_head` and `snake_tail`. For Player 2, edit `P2_HEAD_COLOR` and `P2_TAIL_COLOR`.
- **Background colors:** edit `bg`, `panel`, `cell_a`, `cell_b`, and `border`.

**Sharpness**

- Everything is drawn in code rather than from images, so it stays sharp at any size.
- On Windows, the game supports high-resolution displays without blurring.
- Text stays readable and scales with the window.
- **Window size:** opens at 960×760 and can be resized down to 520×440. Everything adjusts automatically.

**Eye-catching details**

- The snakes have eyes that look in the direction they are moving.
- The apple pulses, and the star spins.
- Sparks fly whenever a snake eats, levels up, or is eliminated.
- Points float above the snake's head and fade away.
- Cards have shadows and colored frames, and the start prompt blinks.
- Smooth motion at 60 frames per second.

## Known Issues and To-Do

Items I found while reviewing the current code:

- [ ] Both snakes use the same colors (pink to purple), so it is hard to tell them apart. One of them should be changed.
- [ ] Player 2 earns fewer points (10 and 50 instead of 25 and 100). To make it fair, change `pts = 10` to `25` and `pts = 50` to `100` in Player 2's block.
- [ ] Player 1 is eliminated by inner walls, but Player 2 is not. Decide on the intended behavior. To eliminate both, set `P2_WALLS_KILL = True`.
- [ ] The start screen says "Arrows / WASD", but WASD now belongs to Player 2.
- [ ] The Game Over screen shows only Player 1's score, and only Player 1's high score is saved.
- [ ] A bonus star appears only after Player 1 eats an apple, not after Player 2.
- [ ] The R key for restarting is not implemented yet. Currently, a new game starts with Enter, Space, or a mouse click.



