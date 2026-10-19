# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cyber Security Invaders is an educational arcade game built with Pygame that teaches cybersecurity concepts through gameplay. It's a Space Invaders-style shooter with integrated educational Q&A, power-ups, boss battles, and optional Raspberry Pi hardware features (7-segment displays, LEDs, and RFID).

## Running the Game

```bash
# Install dependencies
pip install -r requirements.txt

# Run the game
python MAIN.py
```

**Note**: `RPi.GPIO` and `mfrc522` dependencies will fail on non-Raspberry Pi systems but the game will still run without hardware features.

## Architecture

### Entry Point
- **MAIN.py**: Simple entry point that initializes Pygame and creates a `Game` instance

### Core Game Structure

The game follows an object-oriented architecture with the main `Game` class orchestrating all components:

**scripts/game_logic/game.py** - Central game controller
- Manages game state, levels and scoring
- Handles menu systems (main menu, pause menu: Resume / Return to Menu / Exit Game)
- Orchestrates all managers (enemy, bullet, power-up, barricade)
- Implements Raspberry Pi GPIO integration (7-segment display, LEDs, RFID cheat detection)
- Manages background music and sound effects per game state
- Handles networked leaderboard via Flask API (`https://5269989.pythonanywhere.com/submit_score`)
- Platform detection for Raspberry Pi features via `platform.system()` and `platform.machine()`

### Game Component Managers

Each manager handles a specific gameplay system:

- **player.py**: Player ship movement, lives, invulnerability states, shield effects
- **enemy_manager.py**: Enemy wave spawning, movement patterns, difficulty scaling per level
- **bullet_manager.py**: Handles player and enemy projectiles, collision detection
- **boss.py**: Boss enemy with multi-phase attacks, special patterns, health system
- **powerup_manager.py**: Spawns and manages power-ups (triple shot, laser, shield)
- **barricade_manager.py**: Defensive structures that degrade when hit
- **minigame.py**: Word-search hacking mini-game at half boss health: the letters must be picked in one straight line. Success takes `HackingMiniGame.BOSS_DAMAGE` HP off the boss, failure enables rage mode

### Educational System

Questions live in the language files (`assets/lang/cz.json`, `assets/lang/en.json`) under `cybersecurity_questions` and are loaded through `LanguageManager` after the language is chosen.

- A question is asked when the player is hit; a correct answer saves the life, a wrong one costs a life and 250 points
- At most `question_limit = 3` questions per game; after that every hit costs a life
- Each question has a `difficulty` tier (1 easy, 2 medium, 3 hard). `Game.question_difficulty` starts at 1 and goes up one tier after every correct answer; `pick_question()` picks an unused question from that tier (nearest tier if it is used up)

### Raspberry Pi Hardware Integration

When `is_raspberry_pi` is True:
- **7-segment display**: Real-time score display via GPIO threading
- **LED feedback**: Green/red LEDs for correct/incorrect answers
- **RFID cheat codes**: Background thread reads RFID tags for cheats (invincibility, infinite ammo)

GPIO pins are configured in `init_gpio()` method of `Game` class.

### Player Name System

- Player enters their name (1-20 characters, printable excluding special file chars) via `get_player_name()`
- Name prompt appears ONLY when "New Game" is selected (not at startup)
- Name is stored in `self.player_name` for the current game session
- Displayed in the game UI (top-left corner in green)
- Automatically used for leaderboard entries when game ends (win or lose)
- Character counter shows current length (e.g., "5/20")
- Each new game prompts for a new player name (single prompt, only when starting game)

### Assets Organization

```
assets/
├── backgrounds/        # Menu background images (rotating animation)
├── fonts/             # TitleFont.ttf, TextFont.ttf, Title.png
├── instructions/      # Tutorial images for gameplay, boss, power-ups, questions
├── sounds/            # SFX (shoot, hit, correct, wrong, power_up, level_up)
│   └── background_music/  # Level music, boss music, menu music, game over
└── sprites/           # player.png, enemy.png, boss.png, boss_rage.png, virus.png
```

**Asset Loading**: Use `get_asset_path()` helper in game.py to build cross-platform paths.

## Game Flow

1. **Startup** → Main menu appears immediately (no name prompt)
2. **Menu** → New Game / Leaderboard / Instructions / Exit
3. **Select "New Game"** → Player prompted to enter name (1-20 characters, each new game = new player)
4. **Gameplay Loop** (per level):
   - Player name displayed in top-left corner of UI
   - Spawn enemy waves
   - Player shoots, enemies shoot back
   - Every 3 kills triggers educational Q&A
   - Power-ups spawn randomly
   - Barricades provide cover
5. **Boss Battle** (after base levels):
   - Triggered when `boss_fight = True`
   - Boss has phases with different attack patterns
   - Victory advances to next level or ends game
6. **Game End** (Victory or Game Over):
   - Shows final score with player name
   - Score automatically saved to leaderboard
   - Returns to menu (next "New Game" will prompt for new name)

## Key Constants

- **Screen**: Fullscreen mode (dynamically detects native resolution)
- **Player speed**: 5 pixels/frame
- **Lives**: 3 (starts at 3, decrements on hit)
- **Score**: starts at 0 and is only earned (kills, level clears, boss, correct answers, lives left); no time decay. Values are the `SCORE_*` constants on `Game`
- **Total levels**: 4
- **Question limit**: Every 3 enemy kills

## Display Mode

The game runs in fullscreen mode by default:
- Uses `pygame.FULLSCREEN` flag to utilize the entire screen
- Screen dimensions are detected dynamically using `screen.get_width()` and `screen.get_height()`
- All UI elements scale and position based on detected screen size
- Press ESC to exit fullscreen (via game menus)

## Leaderboard System

Scores are stored locally in `leaderboard.json`:
- Top 10 scores kept, sorted by score (descending)
- Each entry includes: player name, score, and timestamp
- File is created automatically on first score submission
- Displayed via the "Leaderboard" menu option
- Can be cleared only from the leaderboard screen with CTRL+SHIFT+C (then a Y/N confirmation), so players at an event cannot wipe it from the main menu

## Music System

Background music changes based on game state:
- Menu: `menu_music.wav`
- Levels: `level_music.wav`
- Boss: `boss_music.wav`
- Boss defeated: `boss_defeated.wav`
- Game over: `game_over.wav`

Music management via `current_music` tracking to prevent restarting same track.

## Development Notes

### Testing Without Raspberry Pi
The game auto-detects platform and disables GPIO features on non-Pi systems. All core gameplay works on any platform with Pygame.

### Adding New Questions
Add the question to `cybersecurity_questions` in **both** language files:
```json
{"difficulty": 2,
 "question": "Question text?",
 "options": ["A) Option 1", "B) Option 2", "C) Option 3"],
 "answer": "B",
 "explanation": "One or two sentences with the takeaway."}
```
`answer` is the letter of the correct option. `explanation` is shown after every answer (right or wrong) together with the correct option, until the player presses a key. Keep options short and of similar length so the correct one does not stand out.

### Modifying Difficulty
Adjust difficulty in `enemy_manager.py` (spawn rates, speed) and `game.py` (question frequency via `question_limit`).

### Clear Leaderboard
Run `scripts/clear_leaderboard.py` to reset remote leaderboard (requires auth credentials).
