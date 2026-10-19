import pygame
import platform
import random
import time
import os
import json
import math
import requests
import datetime
from threading import Thread
from requests.auth import HTTPBasicAuth
from scripts.game_logic.player import Player
from scripts.game_logic.boss import Boss
from scripts.game_logic.enemy_manager import EnemyManager
from scripts.game_logic.bullet_manager import BulletManager
from scripts.game_logic.powerup_manager import PowerUpManager
from scripts.game_logic.barricade_manager import BarricadeManager


# Testing shortcuts (W = instant win). Keep False for real play, otherwise anyone can
# put an untouched score on the leaderboard with a single key press.
DEBUG_CHEATS = False


def get_asset_path(*path_parts):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", *path_parts))


class LanguageManager:
    def __init__(self):
        self.language_data = {}
        self.language = "en"

    def set_language(self, language_code):
        self.language = language_code
        try:
            path = get_asset_path("assets", "lang", f"{language_code}.json")
            with open(path, 'r', encoding='utf-8') as f:
                self.language_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading language file for {language_code}: {e}")
            if language_code != 'en':
                self.set_language('en')

    def get_string(self, key, default=""):
        return self.language_data.get(key, default)

    def get_questions(self):
        return self.language_data.get("cybersecurity_questions", [])


class Game:
    # Scoring: everything is earned, nothing is handed out at the start and time costs nothing.
    SCORE_ENEMY_KILL = 5        # x current level
    SCORE_LEVEL_CLEAR = 250     # x level just cleared
    SCORE_BOSS_HIT = 10
    SCORE_BOSS_DEFEATED = 1000
    SCORE_LIFE_LEFT = 300       # per life left when the boss is beaten
    SCORE_CORRECT_ANSWER = 200  # x question difficulty
    SCORE_POWER_UP = 50
    SCORE_HIT_PENALTY = -250    # wrong answer, or a hit after the questions ran out

    def __init__(self):
        self.lang = LanguageManager()
        self.is_raspberry_pi = platform.system() == "Linux" and "arm" in platform.machine().lower()

        # Get display info for maximum resolution
        display_info = pygame.display.Info()
        max_width = display_info.current_w
        max_height = display_info.current_h

        # Initialize display in resizable maximized window
        self.screen = pygame.display.set_mode((max_width, max_height), pygame.RESIZABLE)

        # Set window title
        pygame.display.set_caption("CYBER SECURITY INVADERS")

        # Set the window to maximized state (platform-specific)
        if platform.system() == "Windows":
            import ctypes
            ctypes.windll.user32.ShowWindow(pygame.display.get_wm_info()['window'], 3)  # 3 = SW_MAXIMIZE

        # Get actual screen dimensions
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        # 20% scale increase for maximized window
        self.scale_factor = 1.2

        print(
            f"DEBUG: Maximized resizable window - Resolution: {self.screen_width}x{self.screen_height}, Scale: {self.scale_factor}x")

        self.clock = pygame.time.Clock()
        self.game_over = False
        self.level = 1
        self.total_levels = 4
        self.boss_fight = False
        self.question_limit = 3
        self.questions_asked = 0
        self.asked_questions = []
        # Question difficulty tier: 1 = easy, 2 = medium, 3 = hard. Goes up after each correct answer.
        self.question_difficulty = 1
        self.max_question_difficulty = 3
        # Seconds of actual play (questions, pauses and splash screens don't count); breaks score ties
        self.play_time = 0.0
        self.barricade_manager = BarricadeManager(self)
        self.last_hit_time = 0
        self.hit_duration = 1.5
        self.start_time = 0
        self.hits = 0
        self.score = 0
        self.power_ups = PowerUpManager(self)
        self.paused = False
        self.current_music = None
        self.player_name = ""  # Will be set at startup
        self.init_gpio()
        self.cheat_codes = {
            "D4A52B11": "invincible",
            "C3B89A22": "infinite_ammo"
        }
        self.active_cheats = set()
        if self.is_raspberry_pi:
            self.init_rfid()

        if self.is_raspberry_pi:
            self.display_score_front = 0
            self.display_score_back = 0
            self.display_update_flag = False
            import threading
            self.display_lock = threading.Lock()
            self.start_display_thread()

            def init_rfid(self):
                from mfrc522 import SimpleMFRC522
                self.reader = SimpleMFRC522()
                self.rfid_thread = threading.Thread(target=self.check_rfid)
                self.rfid_thread.daemon = True
                self.rfid_thread.start()

            def check_rfid(self):
                while True:
                    try:
                        id, text = self.reader.read_no_block()
                        if id and str(id) in self.cheat_codes:
                            self.handle_cheat(self.cheat_codes[str(id)])
                        time.sleep(1)
                    except Exception as e:
                        print("RFID Error:", e)

            def handle_cheat(self, cheat):
                self.active_cheats.add(cheat)
                if cheat == "invincible":
                    self.player.set_invulnerable(duration=99999)
                elif cheat == "infinite_ammo":
                    self.bullet_manager.player_shoot_interval = 0.01

        # Colors
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.GREEN = (0, 255, 0)
        self.RED = (255, 0, 0)
        self.YELLOW = (255, 255, 0)
        self.BLUE = (0, 0, 128)
        self.LIGHTBLUE = (60, 60, 255)

        # Title
        self.title_image = pygame.image.load("assets/fonts/Title.png")
        # Scale title image by 20%
        title_width = int(self.title_image.get_width() * self.scale_factor)
        title_height = int(self.title_image.get_height() * self.scale_factor)
        self.title_image = pygame.transform.scale(self.title_image, (title_width, title_height))

        # Fonts - all scaled by 20%
        self.font = pygame.font.Font("assets/fonts/TextFont.ttf", int(18 * self.scale_factor))
        self.big_font = pygame.font.Font("assets/fonts/TextFont.ttf", int(23 * self.scale_factor))
        self.welcome_font = pygame.font.Font("assets/fonts/TextFont.ttf", int(32 * self.scale_factor))
        self.bold_font = pygame.font.Font("assets/fonts/TextFont.ttf", int(40 * self.scale_factor))
        self.title_font = pygame.font.Font("assets/fonts/TextFont.ttf", int(30 * self.scale_factor))

        self.player = Player(self)
        self.boss = Boss(self)
        self.enemy_manager = EnemyManager(self)
        self.bullet_manager = BulletManager(self)
        self.power_ups = PowerUpManager(self)

        # Cybersecurity questions are now empty and loaded via LanguageManager
        self.cybersecurity_questions = []

        # Sounds
        self.load_sounds()

        self.load_menu_background()

        if self.is_raspberry_pi:
            self.start_display_thread()

    def run(self):
        """Hlavný vstupný bod hry, ktorý najprv zobrazí výber jazyka."""
        self.show_language_selection()

    def show_language_selection(self):
        """Zobrazí obrazovku na výber jazyka hry."""
        options = {"en": "English", "cz": "Čeština"}
        keys = list(options.keys())
        selected_index = 0

        while True:
            self.screen.fill(self.BLACK)

            title_text = self.bold_font.render("Select Language / Zvolte jazyk", True, self.YELLOW)
            self.screen.blit(title_text,
                             (self.screen_width // 2 - title_text.get_width() // 2, self.screen_height // 3))

            for i, key in enumerate(keys):
                y = self.screen_height // 2 + i * 60
                color = self.GREEN if i == selected_index else self.WHITE
                option_text = self.big_font.render(options[key], True, color)
                self.screen.blit(option_text, (self.screen_width // 2 - option_text.get_width() // 2, y))

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        selected_index = (selected_index + 1) % len(keys)
                    elif event.key == pygame.K_UP:
                        selected_index = (selected_index - 1) % len(keys)
                    elif event.key == pygame.K_RETURN:
                        selected_language = keys[selected_index]
                        self.lang.set_language(selected_language)
                        self.cybersecurity_questions = self.lang.get_questions()
                        self.show_menu()
                        return

    def init_gpio(self):
        if self.is_raspberry_pi:
            import RPi.GPIO as GPIO, threading
            from threading import Event
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)

            GREEN_LED_PIN = 20
            RED_LED_PIN = 21

            # Define the GPIO pins connected to segments and digits
            D4 = 16
            D3 = 25
            D2 = 26
            D1 = 5

            SEGMENT_A = 4
            SEGMENT_F = 17
            SEGMENT_B = 18
            SEGMENT_E = 22
            SEGMENT_D = 23
            SEGMENT_C = 24
            SEGMENT_G = 27

            GPIO.setmode(GPIO.BCM)
            pins = [SEGMENT_A, SEGMENT_F, SEGMENT_B, SEGMENT_E, SEGMENT_D, SEGMENT_C, SEGMENT_G, D1, D2, D3, D4,
                    GREEN_LED_PIN, RED_LED_PIN]
            GPIO.setup(pins, GPIO.OUT, initial=GPIO.LOW)

            # Digit to segment mapping (0-9)
            digit_to_segments = {
                '0': [0, 0, 0, 0, 0, 0, 1],
                '1': [1, 0, 0, 1, 1, 1, 1],
                '2': [0, 0, 1, 0, 0, 1, 0],
                '3': [0, 0, 0, 0, 1, 1, 0],
                '4': [1, 0, 0, 1, 1, 0, 0],
                '5': [0, 1, 0, 0, 1, 0, 0],
                '6': [0, 1, 0, 0, 0, 0, 0],
                '7': [0, 0, 0, 1, 1, 1, 1],
                '8': [0, 0, 0, 0, 0, 0, 0],
                '9': [0, 0, 0, 0, 1, 0, 0]
            }

            # Function to display a 4-digit number on the 7-segment display
            def display_number_on_7seg(number):
                digits = str(number).zfill(4)
                start_time = time.perf_counter()
                for i, digit in enumerate(digits):

                    digit_pins = [D1, D2, D3, D4]
                    GPIO.output(digit_pins[i], GPIO.HIGH)

                    # Turn on/off the segments based on the digit
                    segments = digit_to_segments[digit]
                    GPIO.output(SEGMENT_A, GPIO.HIGH if segments[0] == 1 else GPIO.LOW)
                    GPIO.output(SEGMENT_B, GPIO.HIGH if segments[1] == 1 else GPIO.LOW)
                    GPIO.output(SEGMENT_C, GPIO.HIGH if segments[2] == 1 else GPIO.LOW)
                    GPIO.output(SEGMENT_D, GPIO.HIGH if segments[3] == 1 else GPIO.LOW)
                    GPIO.output(SEGMENT_E, GPIO.HIGH if segments[4] == 1 else GPIO.LOW)
                    GPIO.output(SEGMENT_F, GPIO.HIGH if segments[5] == 1 else GPIO.LOW)
                    GPIO.output(SEGMENT_G, GPIO.HIGH if segments[6] == 1 else GPIO.LOW)

                    for j in range(4):
                        if j != i:
                            GPIO.output(digit_pins[j], GPIO.LOW)

                    while time.perf_counter() - start_time < 0.001 * (i + 1):
                        pass

                # Turn off all digits after displaying
                GPIO.output(D1, GPIO.LOW)
                GPIO.output(D2, GPIO.LOW)
                GPIO.output(D3, GPIO.LOW)
                GPIO.output(D4, GPIO.LOW)

        else:
            print("Not running on RPi, GPIO functionality disabled.")

    def load_sounds(self):
        """Loads game sound effects and background music safely."""
        # Background Music Paths
        self.menu_music = get_asset_path("assets", "sounds", "background_music", "menu_music.wav")
        self.level_music = get_asset_path("assets", "sounds", "background_music", "level_music.wav")
        self.boss_music = get_asset_path("assets", "sounds", "background_music", "boss_music.wav")
        self.game_over_music = get_asset_path("assets", "sounds", "background_music", "game_over.wav")
        self.boss_defeated_music = get_asset_path("assets", "sounds", "background_music", "boss_defeated.wav")

        # Check if music files exist before loading them
        for music_file in [self.menu_music, self.level_music, self.boss_music, self.game_over_music,
                           self.boss_defeated_music]:
            if not os.path.exists(music_file):
                print(f"Warning: Music file missing -> {music_file}")

        # Sound Effect Paths
        self.shoot_sound = pygame.mixer.Sound(get_asset_path("assets", "sounds", "shoot.wav"))
        self.hit_sound = pygame.mixer.Sound(get_asset_path("assets", "sounds", "hit.wav"))
        self.correct_answer_sound = pygame.mixer.Sound(get_asset_path("assets", "sounds", "correct.wav"))
        self.wrong_answer_sound = pygame.mixer.Sound(get_asset_path("assets", "sounds", "wrong.wav"))
        self.level_up_sound = pygame.mixer.Sound(get_asset_path("assets", "sounds", "level_up.wav"))
        self.power_up_sound = pygame.mixer.Sound(get_asset_path("assets", "sounds", "power_up.wav"))

        # Set volume
        pygame.mixer.music.set_volume(0.3)

    def load_menu_background(self):
        # Load animated menu backgrounds
        # Load and scale menu backgrounds to fill the screen
        from PIL import Image  # Import Pillow helper

        self.menu_backgrounds = []
        for bg_file in ["menu_background1.png", "menu_background2.png", "menu_background3.png"]:
            path = f"assets/backgrounds/{bg_file}"

            # Load the image using Pillow instead of pygame
            with Image.open(path) as pil_img:
                # Ensure the image is in RGB or RGBA format for Pygame
                if pil_img.mode not in ('RGB', 'RGBA'):
                    pil_img = pil_img.convert('RGBA')

                mode = pil_img.mode
                size = pil_img.size
                data = pil_img.tobytes()

                # Convert raw bytes directly to a Pygame surface (Bypasses libjpeg-9.dll!)
                bg_image = pygame.image.fromstring(data, size, mode)

            # Scale background to fill the entire screen
            scaled_bg = pygame.transform.scale(bg_image, (self.screen_width, self.screen_height))
            self.menu_backgrounds.append(scaled_bg)

        self.menu_background_index = 0
        self.last_bg_update = time.time()
        self.bg_animation_interval = 1

    def start_display_thread(self):
        self.display_running = True
        import threading
        self.display_thread = threading.Thread(target=self.update_7seg_display)
        self.display_thread.daemon = True
        self.display_thread.start()

    def change_music(self, new_track):
        """Stops current music and plays a new track safely."""
        if not os.path.exists(new_track):
            print(f"Music file not found: {new_track}")  # Debugging info
            return

        if self.current_music != new_track:  # Avoid restarting the same track
            pygame.mixer.music.stop()
            pygame.mixer.music.load(new_track)
            pygame.mixer.music.play(-1)
            self.current_music = new_track

    def update_7seg_display(self):
        D1, D2, D3, D4 = 5, 26, 25, 16
        SEGMENT_A, SEGMENT_B, SEGMENT_C, SEGMENT_D, SEGMENT_E, SEGMENT_F, SEGMENT_G = 4, 18, 24, 23, 22, 17, 27
        digit_pins = [D1, D2, D3, D4]

        digit_to_segments = {
            '0': [0, 0, 0, 0, 0, 0, 1],
            '1': [1, 0, 0, 1, 1, 1, 1],
            '2': [0, 0, 1, 0, 0, 1, 0],
            '3': [0, 0, 0, 0, 1, 1, 0],
            '4': [1, 0, 0, 1, 1, 0, 0],
            '5': [0, 1, 0, 0, 1, 0, 0],
            '6': [0, 1, 0, 0, 0, 0, 0],
            '7': [0, 0, 0, 1, 1, 1, 1],
            '8': [0, 0, 0, 0, 0, 0, 0],
            '9': [0, 0, 0, 0, 1, 0, 0]
        }

        if self.is_raspberry_pi:
            import RPi.GPIO as GPIO
        try:
            while self.display_running:
                if self.is_raspberry_pi:
                    with self.display_lock:
                        current_score = self.display_score_front
                    digits = f"{min(current_score, 9999):04d}"

                    for i in range(4):
                        GPIO.output(digit_pins[i], GPIO.HIGH)
                        segments = digit_to_segments[digits[i]]
                        # Set each segment
                        GPIO.output(SEGMENT_A, GPIO.HIGH if segments[0] else GPIO.LOW)
                        GPIO.output(SEGMENT_B, GPIO.HIGH if segments[1] else GPIO.LOW)
                        GPIO.output(SEGMENT_C, GPIO.HIGH if segments[2] else GPIO.LOW)
                        GPIO.output(SEGMENT_D, GPIO.HIGH if segments[3] else GPIO.LOW)
                        GPIO.output(SEGMENT_E, GPIO.HIGH if segments[4] else GPIO.LOW)
                        GPIO.output(SEGMENT_F, GPIO.HIGH if segments[5] else GPIO.LOW)
                        GPIO.output(SEGMENT_G, GPIO.HIGH if segments[6] else GPIO.LOW)
                        # Hold the digit for a short time
                        time.sleep(0.001)
                        GPIO.output(digit_pins[i], GPIO.LOW)
        except KeyboardInterrupt:
            self.display_running = False
            if self.is_raspberry_pi:
                GPIO.cleanup()

    def display_changed_segments(self, number):
        # Only update what has changed
        new_digits = str(number).zfill(4)
        for i, digit in enumerate(new_digits):
            if digit != str(self.display_score).zfill(4)[i]:
                self.changed_segments.add(i)
        for i in self.changed_segments:
            self.display_digit(i, new_digits[i])
        self.changed_segments.clear()

    def display_digit(self, position, digit):
        if not self.is_raspberry_pi: return
        import RPi.GPIO as GPIO
        D1, D2, D3, D4 = 5, 26, 25, 16
        SEGMENT_A, SEGMENT_B, SEGMENT_C, SEGMENT_D, SEGMENT_E, SEGMENT_F, SEGMENT_G = 4, 18, 24, 23, 22, 17, 27
        digit_to_segments = {
            '0': [0, 0, 0, 0, 0, 0, 1], '1': [1, 0, 0, 1, 1, 1, 1], '2': [0, 0, 1, 0, 0, 1, 0],
            '3': [0, 0, 0, 0, 1, 1, 0], '4': [1, 0, 0, 1, 1, 0, 0], '5': [0, 1, 0, 0, 1, 0, 0],
            '6': [0, 1, 0, 0, 0, 0, 0], '7': [0, 0, 0, 1, 1, 1, 1], '8': [0, 0, 0, 0, 0, 0, 0],
            '9': [0, 0, 0, 0, 1, 0, 0]
        }
        digit_pins = [D1, D2, D3, D4]
        GPIO.output(digit_pins[position], GPIO.HIGH)
        segments = digit_to_segments[digit]
        for j, segment in enumerate([SEGMENT_A, SEGMENT_B, SEGMENT_C, SEGMENT_D, SEGMENT_E, SEGMENT_F, SEGMENT_G]):
            GPIO.output(segment, GPIO.HIGH if segments[j] == 1 else GPIO.LOW)
        for j in range(4):
            if j != position:
                GPIO.output(digit_pins[j], GPIO.LOW)

    def adjust_score(self, points, show=True):
        self.score = max(0, self.score + points)

        # show=False keeps frequent small gains (kills, boss hits) from flickering next to the score
        if points != 0 and show:
            self.score_adjustment = f"{points:+d}"
            self.score_adjustment_time = time.time()

            pygame.time.set_timer(pygame.USEREVENT + 1, 0)
            pygame.time.set_timer(pygame.USEREVENT + 1, 2000)

        if self.is_raspberry_pi:
            with self.display_lock:
                self.display_score_back = self.score
                self.display_update_flag = True

    def __del__(self):
        if self.is_raspberry_pi:
            self.display_running = False
            if hasattr(self, 'display_thread'):
                self.display_thread.join()
            import RPi.GPIO as GPIO
            GPIO.cleanup()

    def main_game_loop(self):
        self.change_music(self.level_music)  # Start level music
        self.game_over = False
        self.start_time = time.time()
        while not self.game_over:
            self.screen.fill(self.BLACK)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.paused = not self.paused
                    # DEBUG: Press W to instantly win (for testing)
                    if DEBUG_CHEATS and event.key == pygame.K_w:
                        print("DEBUG: WIN CHEAT ACTIVATED!")
                        self.end_game_screen()
                if event.type == pygame.USEREVENT + 1:
                    if hasattr(self, 'score_adjustment') and time.time() - self.score_adjustment_time >= 2:
                        del self.score_adjustment

            if self.paused:
                self.power_ups.pause_powerups()
                self.draw_pause_menu()
                continue

            keys = pygame.key.get_pressed()
            self.player.move(keys)
            self.player.shoot(keys)
            self.player.check_invulnerability()
            if self.boss_fight:
                self.change_music(self.boss_music)  # Start boss music
                self.boss.update()
                if self.game_over:
                    break
                if self.boss_fight:
                    player_hit = self.bullet_manager.check_player_hit_by_boss_bullet()
                else:
                    player_hit = self.bullet_manager.check_player_hit()
                if player_hit:
                    if not self.ask_cybersecurity_question():
                        self.player.lives -= 1
                        self.adjust_score(self.SCORE_HIT_PENALTY)
                        if self.player.lives <= 0:
                            self.game_over_screen()

            else:
                self.barricade_manager.update()
                self.barricade_manager.draw()
                self.enemy_manager.update()
                if self.game_over:
                    break
                self.enemy_manager.draw()
                player_hit = self.bullet_manager.check_player_hit()
                self.power_ups.update()
                if player_hit:
                    self.hit_sound.play()
                    if not self.ask_cybersecurity_question():
                        self.player.lives -= 1
                        self.adjust_score(self.SCORE_HIT_PENALTY)
                        if self.player.lives <= 0:
                            self.game_over_screen()
            self.player.draw()
            self.bullet_manager.update_player_bullets()
            self.bullet_manager.update_enemy_bullets()
            self.bullet_manager.update_boss_bullets()
            self.draw_ui()
            # Handle 7-segment display
            if self.is_raspberry_pi:
                if self.score != self.display_score_front:
                    with self.display_lock:
                        self.display_score_front = self.score
                        self.display_update_flag = True
            pygame.display.update()
            self.play_time += min(self.clock.tick(60), 100) / 1000

    def draw_pause_menu(self):
        menu_options = [
            self.lang.get_string("pause_resume", "Resume"),
            self.lang.get_string("pause_return_menu", "Return to Menu"),
            self.lang.get_string("pause_exit", "Exit Game")
        ]

        selected_option = 0
        while self.paused:
            self.screen.fill(self.BLACK)

            # Draw enemies or boss based on current game state
            if self.boss_fight:
                # Draw boss and health bar
                self.screen.blit(self.boss.current_image, (self.boss.x, self.boss.y))
                health_width = int(200 * (self.boss.health / self.boss.max_health))
                pygame.draw.rect(self.screen, self.RED, (self.screen_width // 2 - 100, 40, 200, 20))
                pygame.draw.rect(self.screen, self.GREEN, (self.screen_width // 2 - 100, 40, health_width, 20))
            else:
                self.enemy_manager.draw()

            # Draw player, enemies, bullets, and power-ups
            self.player.draw()
            self.enemy_manager.draw()
            self.bullet_manager.update_player_bullets(draw_only=True)
            self.bullet_manager.update_enemy_bullets(draw_only=True)
            self.bullet_manager.update_boss_bullets(draw_only=True)

            # Manually draw power-ups without updating them
            for power_up in self.power_ups.power_ups:
                pygame.draw.circle(self.screen, self.BLUE, (int(power_up[0]), int(power_up[1])), 10)

            # Draw pause menu overlay
            menu_background = pygame.Surface((400, 300))
            menu_background.fill(self.BLACK)
            pygame.draw.rect(menu_background, self.WHITE, menu_background.get_rect(), 2)
            self.screen.blit(menu_background, (self.screen_width // 2 - 200, 150))

            # Add PAUSED text
            paused_text = self.bold_font.render(self.lang.get_string("paused_text", "PAUSED"), True, self.WHITE)
            self.screen.blit(paused_text, (self.screen_width // 2 - paused_text.get_width() // 2, 155))

            # Draw menu items
            for i, option in enumerate(menu_options):
                y = 250 + i * 60
                color = self.GREEN if i == selected_option else self.WHITE
                option_text = self.big_font.render(option, True, color)
                self.screen.blit(option_text, (self.screen_width // 2 - option_text.get_width() // 2, y))

            pygame.display.flip()

            # Handle input
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        # Resuming with ESC must also shift the power-up timers, same as "Resume"
                        self.paused = False
                        self.power_ups.resume_powerups()
                        return
                    elif event.key == pygame.K_DOWN:
                        selected_option = (selected_option + 1) % len(menu_options)
                    elif event.key == pygame.K_UP:
                        selected_option = (selected_option - 1) % len(menu_options)
                    elif event.key == pygame.K_RETURN:
                        if selected_option == 0:
                            self.paused = False
                            self.power_ups.resume_powerups()
                            return
                        elif selected_option == 1:
                            # Ending the game loop drops back into the main menu loop
                            self.reset_game_state()
                            self.paused = False
                            self.game_over = True
                            return
                        elif selected_option == 2:
                            print("DEBUG: Exit Game selected from pause menu")
                            pygame.quit()
                            quit()

    def draw_ui(self):
        # Player name at top left
        player_text = self.font.render(f"{self.lang.get_string('ui_player', 'Player')}: {self.player_name}", True,
                                       self.GREEN)
        self.screen.blit(player_text, (10, 10))

        lives_text = self.font.render(f"{self.lang.get_string('ui_lives', 'Lives')}: {self.player.lives}", True,
                                      self.WHITE)
        self.screen.blit(lives_text, (10, 60))

        score_text = self.font.render(f"{self.lang.get_string('ui_score', 'Score')}: {self.score}", True, self.WHITE)
        self.screen.blit(score_text, (10, 110))

        level_text = self.font.render(f"{self.lang.get_string('ui_level', 'Level')}: ", True, self.WHITE)
        boss_str = self.lang.get_string('ui_boss', 'BOSS')
        boss_text = self.font.render(boss_str if self.boss_fight else str(self.level), True,
                                     self.RED if self.boss_fight else self.WHITE)
        self.screen.blit(level_text, (self.screen_width - level_text.get_width() - boss_text.get_width() - 10, 10))
        self.screen.blit(boss_text, (self.screen_width - boss_text.get_width() - 10, 10))

        # Draw power-up notification only if active
        if self.power_ups.power_up_active:
            power_up_text = self.font.render(self.lang.get_string('ui_powerup', 'Power Up!'), True, self.YELLOW)
            self.screen.blit(power_up_text, (self.screen_width // 2 - power_up_text.get_width() // 2, 10))

            # Display the name of the active power-up
            if self.power_ups.current_power_up == 'Laser':
                color = self.RED
            elif self.power_ups.current_power_up == 'Shield':
                color = self.LIGHTBLUE
            elif self.power_ups.current_power_up == 'TripleShot':
                color = self.GREEN
            elif self.power_ups.current_power_up == 'Score Multiplier':
                color = self.GREEN
            else:
                color = self.WHITE
            power_up_name = self.font.render(self.power_ups.current_power_up.capitalize(), True, color)
            self.screen.blit(power_up_name, (self.screen_width // 2 - power_up_name.get_width() // 2, 40))

        if hasattr(self, 'score_adjustment'):
            adjust_text = self.font.render(self.score_adjustment, True,
                                           self.RED if self.score_adjustment[0] == '-' else self.GREEN)
            self.screen.blit(adjust_text, (score_text.get_width() + 20, 40))

    def clear_bullets(self):
        self.bullet_manager.player_bullets.clear()
        self.bullet_manager.enemy_bullets.clear()
        self.bullet_manager.boss_bullets.clear()

    def pick_question(self):
        """Pick an unused question, preferring the player's current difficulty tier."""
        available = [q for q in self.cybersecurity_questions if q not in self.asked_questions]
        if not available:
            return None

        # Fall back to the nearest tier so a used-up tier never blocks a question
        def distance(q):
            return abs(q.get("difficulty", 1) - self.question_difficulty)

        closest = min(distance(q) for q in available)
        return random.choice([q for q in available if distance(q) == closest])

    def ask_cybersecurity_question(self):
        # Ensure there are available questions
        if self.questions_asked >= self.question_limit or not self.cybersecurity_questions:
            return False

        question_data = self.pick_question()
        if question_data is None:
            return False

        self.questions_asked += 1
        self.asked_questions.append(question_data)

        question = question_data["question"]
        options = question_data["options"]
        correct_answer = question_data["answer"]
        difficulty = question_data.get("difficulty", 1)

        # Layout: one centred column so long texts wrap instead of running off screen
        content_width = min(self.screen_width - 80, int(1000 * self.scale_factor))
        left = (self.screen_width - content_width) // 2
        padding = int(12 * self.scale_factor)
        gap = int(14 * self.scale_factor)
        line_height = self.font.get_linesize()
        big_line_height = self.big_font.get_linesize()

        question_lines = self.wrap_text(question, self.big_font, content_width)

        # Split "A) text" so wrapped lines line up under the text, not under the letter
        wrapped_options = []
        for option in options:
            prefix, body = (option[:3], option[3:]) if option[1:3] == ") " else ("", option)
            prefix_width = self.font.size(prefix)[0]
            lines = self.wrap_text(body, self.font, content_width - 2 * padding - prefix_width)
            wrapped_options.append((prefix, prefix_width, lines))

        header_height = line_height + gap
        question_height = len(question_lines) * big_line_height
        box_heights = [len(lines) * line_height + 2 * padding for _, _, lines in wrapped_options]
        total_height = (header_height + gap + question_height + 2 * gap
                        + sum(box_heights) + gap * (len(options) - 1))
        top = max(20, (self.screen_height - total_height) // 2 - line_height)

        difficulty_colors = {1: self.GREEN, 2: self.YELLOW, 3: self.RED}
        counter_text = self.font.render(
            f"{self.lang.get_string('question_counter', 'Question')} {self.questions_asked}/{self.question_limit}",
            True, self.WHITE)
        difficulty_text = self.font.render(
            f"{self.lang.get_string('difficulty_label', 'Difficulty')}: "
            f"{self.lang.get_string(f'difficulty_{difficulty}', str(difficulty))}",
            True, difficulty_colors.get(difficulty, self.WHITE))
        instruction_text = self.font.render(
            self.lang.get_string("question_instruction", "Use UP/DOWN to select, ENTER to confirm."), True,
            self.YELLOW)

        # Prepare to display the question
        selected_index = 0
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        selected_answer = chr(pygame.K_a + selected_index).upper()
                        if selected_answer == correct_answer:
                            # Correct answer -> the next question comes from a harder tier
                            self.question_difficulty = min(self.max_question_difficulty,
                                                           self.question_difficulty + 1)
                            self.adjust_score(self.SCORE_CORRECT_ANSWER * difficulty)
                            self.correct_answer_sound.play()
                            self.show_question_result(True, question_data)
                            self.clear_bullets()
                            return True
                        else:
                            self.wrong_answer_sound.play()
                            self.show_question_result(False, question_data)
                            self.clear_bullets()
                            return False
                    elif event.key == pygame.K_UP:
                        selected_index = (selected_index - 1) % len(options)
                    elif event.key == pygame.K_DOWN:
                        selected_index = (selected_index + 1) % len(options)

            self.screen.fill(self.BLACK)

            # Header: question counter on the left, difficulty on the right
            y = top
            self.screen.blit(counter_text, (left, y))
            self.screen.blit(difficulty_text, (left + content_width - difficulty_text.get_width(), y))
            y += header_height
            pygame.draw.line(self.screen, self.WHITE, (left, y), (left + content_width, y), 2)
            y += gap

            for line in question_lines:
                question_text = self.big_font.render(line, True, self.WHITE)
                self.screen.blit(question_text, (self.screen_width // 2 - question_text.get_width() // 2, y))
                y += big_line_height
            y += 2 * gap

            for i, (prefix, prefix_width, lines) in enumerate(wrapped_options):
                selected = i == selected_index
                color = self.GREEN if selected else self.WHITE
                box = pygame.Rect(left, y, content_width, box_heights[i])
                pygame.draw.rect(self.screen, color if selected else (90, 90, 90), box, 3 if selected else 1)
                if prefix:
                    self.screen.blit(self.font.render(prefix, True, color), (left + padding, y + padding))
                for j, line in enumerate(lines):
                    self.screen.blit(self.font.render(line, True, color),
                                     (left + padding + prefix_width, y + padding + j * line_height))
                y += box_heights[i] + gap

            self.screen.blit(instruction_text,
                             (self.screen_width // 2 - instruction_text.get_width() // 2, self.screen_height - 50))

            pygame.display.flip()
            self.clock.tick(60)

    def wrap_text(self, text, font, max_width):
        words = text.split(' ')
        lines = []
        current_line = ''
        for word in words:
            test_line = current_line + word + ' '
            if font.size(test_line.strip())[0] <= max_width or not current_line:
                current_line = test_line
            else:
                lines.append(current_line.strip())
                current_line = word + ' '
        lines.append(current_line.strip())
        return lines

    def show_question_result(self, correct, question_data):
        """Answer feedback with the right option and a short takeaway. Waits for a key so it can be read."""
        color = self.GREEN if correct else self.RED
        content_width = min(self.screen_width - 80, int(1000 * self.scale_factor))
        gap = int(24 * self.scale_factor)

        title = self.lang.get_string("feedback_correct", "Correct!") if correct else \
            self.lang.get_string("feedback_incorrect", "Incorrect!")
        answer_index = "ABC".find(question_data["answer"])
        correct_option = question_data["options"][answer_index] if answer_index >= 0 else ""

        # (font, colour, lines) blocks stacked top to bottom
        blocks = [(self.bold_font, color, [title])]
        if not correct and correct_option:
            label = self.lang.get_string("correct_answer_label", "Correct answer")
            blocks.append((self.font, self.WHITE, self.wrap_text(f"{label}: {correct_option}", self.font, content_width)))
        if question_data.get("explanation"):
            blocks.append((self.big_font, self.YELLOW,
                           self.wrap_text(question_data["explanation"], self.big_font, content_width)))

        total_height = sum(len(lines) * font.get_linesize() for font, _, lines in blocks) + gap * (len(blocks) - 1)
        y = max(20, (self.screen_height - total_height) // 2 - gap)

        self.screen.fill(self.BLACK)
        for font, block_color, lines in blocks:
            for line in lines:
                text = font.render(line, True, block_color)
                self.screen.blit(text, (self.screen_width // 2 - text.get_width() // 2, y))
                y += font.get_linesize()
            y += gap

        continue_text = self.font.render(
            self.lang.get_string("press_any_key", "Press any key to continue"), True, self.WHITE)
        self.screen.blit(continue_text,
                         (self.screen_width // 2 - continue_text.get_width() // 2, self.screen_height - 50))
        pygame.display.flip()

        if self.is_raspberry_pi:
            import RPi.GPIO as GPIO
            GPIO.output(20, GPIO.HIGH if correct else GPIO.LOW)  # GREEN_LED_PIN
            GPIO.output(21, GPIO.LOW if correct else GPIO.HIGH)  # RED_LED_PIN

        self.wait_for_keypress()

        if self.is_raspberry_pi:
            GPIO.output(20, GPIO.LOW)
            GPIO.output(21, GPIO.LOW)

    def display_feedback(self, message, color):
        self.screen.fill(self.BLACK)
        feedback_text = self.bold_font.render(message, True, color)
        self.screen.blit(feedback_text, (self.screen_width // 2 - feedback_text.get_width() // 2,
                                         self.screen_height // 2 - feedback_text.get_height() // 2))
        pygame.display.flip()

        if self.is_raspberry_pi:
            if color == self.GREEN:
                import RPi.GPIO as GPIO
                GPIO.output(20, GPIO.HIGH)  # GREEN_LED_PIN
                GPIO.output(21, GPIO.LOW)  # RED_LED_PIN
            else:
                import RPi.GPIO as GPIO
                GPIO.output(21, GPIO.HIGH)  # RED_LED_PIN
                GPIO.output(20, GPIO.LOW)  # GREEN_LED_PIN

        pygame.time.wait(2000)

        if self.is_raspberry_pi:
            import RPi.GPIO as GPIO
            GPIO.output(20, GPIO.LOW)
            GPIO.output(21, GPIO.LOW)

    def boss_fight_splash_screen(self):
        self.change_music(self.boss_music)  # Start boss music
        self.clear_bullets()
        self.power_ups.reset_power_up()
        self.boss.health = self.boss.max_health
        self.boss.reset_boss()
        self.boss.minigame_triggered = False

        self.screen.fill(self.BLACK)
        boss_fight_text = self.bold_font.render(self.lang.get_string("boss_fight_title", "Boss Fight!"), True, self.RED)
        self.screen.blit(boss_fight_text,
                         (self.screen_width // 2 - boss_fight_text.get_width() // 2, self.screen_height // 2 - 100))
        continue_text = self.big_font.render(self.lang.get_string("press_any_key", "Press any key to continue"), True,
                                             self.WHITE)
        self.screen.blit(continue_text,
                         (self.screen_width // 2 - continue_text.get_width() // 2, self.screen_height // 2 + 50))
        pygame.display.flip()
        self.wait_for_keypress()

    def game_over_screen(self):
        # Ends the game loop; the guard keeps one game from being saved to the leaderboard twice
        if self.game_over:
            return
        self.game_over = True
        print(f"DEBUG: game_over_screen called! player_name='{self.player_name}', score={self.score}")
        self.change_music(self.game_over_music)  # Play Game Over music
        self.screen.fill(self.RED)
        game_over_text = self.bold_font.render(self.lang.get_string("game_over_text", "GAME OVER!"), True, self.WHITE)
        self.screen.blit(game_over_text,
                         (self.screen_width // 2 - game_over_text.get_width() // 2, self.screen_height // 2 - 100))

        # Show player name and final score
        player_text = self.big_font.render(f"{self.lang.get_string('ui_player', 'Player')}: {self.player_name}", True,
                                           self.WHITE)
        self.screen.blit(player_text,
                         (self.screen_width // 2 - player_text.get_width() // 2, self.screen_height // 2 - 30))

        score_text = self.big_font.render(f"{self.lang.get_string('final_score_text', 'Final Score')}: {self.score}",
                                          True, self.YELLOW)
        self.screen.blit(score_text,
                         (self.screen_width // 2 - score_text.get_width() // 2, self.screen_height // 2 + 20))

        instruction_text = self.font.render(
            self.lang.get_string("save_and_return_prompt", "Press any key to save score and return to menu"), True,
            self.WHITE)
        self.screen.blit(instruction_text,
                         (self.screen_width // 2 - instruction_text.get_width() // 2, self.screen_height // 2 + 80))
        pygame.display.flip()

        waiting_for_input = True
        while waiting_for_input:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                if event.type == pygame.KEYDOWN:
                    waiting_for_input = False
                    # Save score before returning to menu
                    print(f"DEBUG: Saving score from game_over_screen...")
                    self.save_score(self.player_name, self.score)
                    return  # main_game_loop ends and control returns to the menu

    def wait_for_keypress(self, cooldown=1000):
        start_time = pygame.time.get_ticks()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    # I added a cooldown so user doesn't accidentally press off the splash screens
                    if pygame.time.get_ticks() - start_time >= cooldown:
                        return
            pygame.time.wait(10)

    def get_player_name(self):
        """Prompt user for their name at startup"""
        self.screen.fill(self.BLACK)

        # Welcome text - using welcome_font (32pt, 40% larger than big_font)
        welcome_text = self.welcome_font.render(
            self.lang.get_string("welcome_message", "Welcome to Cyber Security Invaders!"), True, self.GREEN)
        self.screen.blit(welcome_text,
                         (self.screen_width // 2 - welcome_text.get_width() // 2, self.screen_height // 3 - 50))

        # Name prompt
        name_prompt = self.big_font.render(self.lang.get_string("enter_name_prompt", "Enter your name:"), True,
                                           self.WHITE)
        self.screen.blit(name_prompt,
                         (self.screen_width // 2 - name_prompt.get_width() // 2, self.screen_height // 2 - 30))

        # Input Box
        input_box = pygame.Rect(self.screen_width // 2 - 150, self.screen_height // 2 + 30, 300, 32)
        color_inactive = self.LIGHTBLUE
        color_active = self.GREEN
        color = color_active
        text = ''

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        if len(text) >= 1:  # At least 1 character
                            self.player_name = text
                            return True
                    elif event.key == pygame.K_ESCAPE:
                        # Return to menu without starting game
                        self.screen.fill(self.BLACK)
                        pygame.display.flip()
                        return False
                    elif event.key == pygame.K_BACKSPACE:
                        text = text[:-1]
                    elif len(text) < 30 and event.unicode.isprintable() and event.unicode not in ['/', '\\', ':', '*',
                                                                                                  '?', '"', '<', '>',
                                                                                                  '|']:
                        text += event.unicode

            # Redraw screen
            self.screen.fill(self.BLACK)
            self.screen.blit(welcome_text,
                             (self.screen_width // 2 - welcome_text.get_width() // 2, self.screen_height // 3 - 50))
            self.screen.blit(name_prompt,
                             (self.screen_width // 2 - name_prompt.get_width() // 2, self.screen_height // 2 - 30))

            # Draw input box
            pygame.draw.rect(self.screen, color, input_box)

            # Draw text inside the box
            txt_surface = self.font.render(text, True, self.BLACK)
            width = max(300, txt_surface.get_width() + 10)
            input_box.w = width
            input_box.x = self.screen_width // 2 - width // 2
            self.screen.blit(txt_surface, (input_box.x + 5, input_box.y + 5))

            # Draw character count
            count_text = self.font.render(f"{len(text)}/30", True, self.GREEN)
            self.screen.blit(count_text,
                             (self.screen_width // 2 - count_text.get_width() // 2, self.screen_height // 2 + 70))

            pygame.display.flip()

    def show_menu(self):
        # Never prompt for name here - only in reset_game() when "New Game" is selected
        # Initialize player_name to empty string if not set, so we don't get errors
        if not hasattr(self, 'player_name'):
            self.player_name = ""

        menu_options = [
            self.lang.get_string("menu_new_game", "New Game"),
            self.lang.get_string("menu_leaderboard", "Leaderboard"),
            self.lang.get_string("menu_instructions", "Instructions"),
            self.lang.get_string("menu_exit", "Exit")
        ]
        selected_option = 0

        self.change_music(self.menu_music)  # Play menu music

        while True:
            current_time = time.time()

            # Clear the entire screen with black background
            self.screen.fill(self.BLACK)

            # Calculate vertical centering for menu
            menu_item_height = int(80 * self.scale_factor)
            total_menu_height = self.title_image.get_height() + (len(menu_options) * menu_item_height)
            start_y = (self.screen_height - total_menu_height) // 2

            # Title text - centered
            title_y = start_y
            self.screen.blit(self.title_image, (self.screen_width // 2 - self.title_image.get_width() // 2, title_y))

            # Draw menu items - centered below title
            menu_start_y = title_y + self.title_image.get_height() + int(50 * self.scale_factor)
            for i, option in enumerate(menu_options):
                y = menu_start_y + i * menu_item_height
                color = self.GREEN if i == selected_option else self.WHITE
                option_text = self.big_font.render(option, True, color)
                self.screen.blit(option_text, (self.screen_width // 2 - option_text.get_width() // 2, y))

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.VIDEORESIZE:
                    # Handle window resize
                    self.screen_width = event.w
                    self.screen_height = event.h
                    self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        selected_option = (selected_option + 1) % len(menu_options)
                    elif event.key == pygame.K_UP:
                        selected_option = (selected_option - 1) % len(menu_options)
                    elif event.key == pygame.K_RETURN:
                        # A finished game returns here, so the menu simply carries on
                        if selected_option == 0:
                            self.reset_game()
                            self.change_music(self.menu_music)
                        elif selected_option == 1:
                            self.show_leaderboard()
                        elif selected_option == 2:
                            self.show_instructions()
                        elif selected_option == 3:
                            pygame.quit()
                            quit()

    def draw(self, screen):
        for block in self.blocks:
            # You can change color based on health if desired
            pygame.draw.rect(screen, (0, 255, 0), block["rect"])

    def hit(self, pos):
        # pos is a tuple (x, y)
        for block in self.blocks:
            if block["rect"].collidepoint(pos):
                block["health"] -= 1
                if block["health"] <= 0:
                    self.blocks.remove(block)
                return True
        return False

    def check_server_availability(self):
        # Local storage is always available
        return True

    def create_loading_screen(self):
        self.screen.fill(self.BLACK)
        loading_text = self.big_font.render(self.lang.get_string("loading_text", "Loading..."), True, self.GREEN)
        self.screen.blit(loading_text, (self.screen_width // 2 - loading_text.get_width() // 2,
                                        self.screen_height // 2 - loading_text.get_height() // 2))
        pygame.display.flip()

    def show_leaderboard(self):
        self.create_loading_screen()  # Show loading screen
        self.screen.fill(self.BLACK)

        try:
            # Load local leaderboard
            leaderboard_file = 'leaderboard.json'
            leaderboard_data = []

            if os.path.exists(leaderboard_file):
                try:
                    with open(leaderboard_file, 'r') as f:
                        leaderboard_data = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    leaderboard_data = []

            # Display leaderboard
            leaderboard_title = self.bold_font.render(self.lang.get_string("leaderboard_title", "Local Leaderboard"),
                                                      True, self.YELLOW)
            self.screen.blit(leaderboard_title, (self.screen_width // 2 - leaderboard_title.get_width() // 2, 30))

            y_position = 100 + int(50 * self.scale_factor)

            if leaderboard_data:
                # Table: rank | player | score | date, one row per entry
                table_width = min(self.screen_width - 80, int(900 * self.scale_factor))
                left = (self.screen_width - table_width) // 2
                name_x = left + int(table_width * 0.08)
                score_right = left + int(table_width * 0.58)
                time_right = left + int(table_width * 0.72)
                date_right = left + table_width
                row_height = int(36 * self.scale_factor)

                headers = [
                    ("#", left, False),
                    (self.lang.get_string("ui_player", "Player"), name_x, False),
                    (self.lang.get_string("ui_score", "Score"), score_right, True),
                    (self.lang.get_string("leaderboard_time", "Time"), time_right, True),
                    (self.lang.get_string("leaderboard_date", "Date"), date_right, True),
                ]
                for text, x, right_aligned in headers:
                    header_text = self.font.render(text, True, self.GREEN)
                    self.screen.blit(header_text, (x - header_text.get_width() if right_aligned else x,
                                                   y_position + self.font.get_height() - header_text.get_height()))
                y_position += row_height
                pygame.draw.line(self.screen, self.GREEN, (left, y_position - 8), (left + table_width, y_position - 8), 2)

                for i, entry in enumerate(leaderboard_data):
                    color = self.YELLOW if i == 0 else self.WHITE
                    score_text = self.font.render(str(entry['score']), True, color)

                    # Shorten names that would run into the score column
                    name = str(entry['player'])
                    max_name_width = score_right - score_text.get_width() - name_x - 20
                    while len(name) > 1 and self.font.size(name)[0] > max_name_width:
                        name = name[:-1]

                    self.screen.blit(self.font.render(f"{i + 1}.", True, color), (left, y_position))
                    # Capital letters with accents (Ž, Č...) make the surface taller, so align by the bottom edge
                    name_text = self.font.render(name, True, color)
                    self.screen.blit(name_text,
                                     (name_x, y_position + score_text.get_height() - name_text.get_height()))
                    self.screen.blit(score_text, (score_right - score_text.get_width(), y_position))
                    if 'time' in entry:
                        seconds = int(entry['time'])
                        time_text = self.font.render(f"{seconds // 60}:{seconds % 60:02d}", True, color)
                        self.screen.blit(time_text, (time_right - time_text.get_width(), y_position))
                    if 'timestamp' in entry:
                        date_text = self.font.render(entry['timestamp'][:16], True, self.GREEN)
                        self.screen.blit(date_text, (date_right - date_text.get_width(), y_position))
                    y_position += row_height
            else:
                no_scores_text = self.font.render(
                    self.lang.get_string("no_scores_text", "No scores yet! Play a game to set a record."), True,
                    self.WHITE)
                self.screen.blit(no_scores_text, (self.screen_width // 2 - no_scores_text.get_width() // 2, y_position))

        except Exception as e:
            self.screen.fill(self.BLACK)
            error_text = self.big_font.render(f"Error loading leaderboard: {str(e)}", True, self.RED)
            self.screen.blit(error_text, (self.screen_width // 2 - error_text.get_width() // 2,
                                          self.screen_height // 2 - error_text.get_height() // 2))

        tip = self.lang.get_string("press_key_back", "Press any key to go back!")
        tip_text = self.font.render(tip, True, self.GREEN)
        self.screen.blit(tip_text, (self.screen_width // 2 - tip_text.get_width() // 2, self.screen_height - 50))

        pygame.display.flip()

        # Wait for a key press before returning to the menu. Clearing the leaderboard is hidden
        # behind CTRL+SHIFT+C here, so players at an event can't wipe it from the main menu.
        modifier_keys = (pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LSHIFT, pygame.K_RSHIFT,
                         pygame.K_LALT, pygame.K_RALT)
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                if event.type == pygame.KEYDOWN:
                    if event.key in modifier_keys:
                        continue
                    if event.key == pygame.K_c and event.mod & pygame.KMOD_CTRL and event.mod & pygame.KMOD_SHIFT:
                        self.clear_leaderboard_menu()
                        return
                    waiting = False

        # Clear screen before returning to menu
        self.screen.fill(self.BLACK)
        pygame.display.flip()

    def clear_leaderboard_menu(self):
        """Show confirmation dialog to clear the leaderboard"""
        self.screen.fill(self.BLACK)

        # Warning title
        warning_title = self.bold_font.render(self.lang.get_string("clear_leaderboard_title", "CLEAR LEADERBOARD"),
                                              True, self.RED)
        self.screen.blit(warning_title,
                         (self.screen_width // 2 - warning_title.get_width() // 2, self.screen_height // 3 - 50))

        # Confirmation text
        confirm_text = self.big_font.render(
            self.lang.get_string("confirm_clear_scores", "Are you sure you want to clear all scores?"), True,
            self.WHITE)
        self.screen.blit(confirm_text,
                         (self.screen_width // 2 - confirm_text.get_width() // 2, self.screen_height // 2 - 50))

        warning_text = self.font.render(
            self.lang.get_string("action_cannot_be_undone", "This action cannot be undone!"), True, self.YELLOW)
        self.screen.blit(warning_text,
                         (self.screen_width // 2 - warning_text.get_width() // 2, self.screen_height // 2))

        # Instructions
        yes_text = self.big_font.render(self.lang.get_string("press_y_clear", "Press Y to CLEAR"), True, self.RED)
        self.screen.blit(yes_text, (self.screen_width // 2 - yes_text.get_width() // 2, self.screen_height // 2 + 80))

        no_text = self.big_font.render(self.lang.get_string("press_n_cancel", "Press N to Cancel"), True, self.GREEN)
        self.screen.blit(no_text, (self.screen_width // 2 - no_text.get_width() // 2, self.screen_height // 2 + 130))

        pygame.display.flip()

        # Wait for user input
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_y:
                        # Clear the leaderboard
                        self.clear_leaderboard()
                        waiting = False
                    elif event.key == pygame.K_n or event.key == pygame.K_ESCAPE:
                        # Cancel and return to menu
                        waiting = False
                        # Clear screen before returning to menu
                        self.screen.fill(self.BLACK)
                        pygame.display.flip()

    def clear_leaderboard(self):
        """Clear all entries from the leaderboard"""
        print("DEBUG: Clearing leaderboard...")
        try:
            leaderboard_file = 'leaderboard.json'

            # Write empty list to file
            with open(leaderboard_file, 'w') as f:
                json.dump([], f, indent=2)

            print("DEBUG: Leaderboard cleared successfully!")

            # Show success message
            self.screen.fill(self.BLACK)
            success_text = self.bold_font.render(self.lang.get_string("leaderboard_cleared", "Leaderboard Cleared!"),
                                                 True, self.GREEN)
            self.screen.blit(success_text,
                             (self.screen_width // 2 - success_text.get_width() // 2, self.screen_height // 2))

            press_key_text = self.font.render(
                self.lang.get_string("press_key_continue", "Press any key to continue..."), True, self.WHITE)
            self.screen.blit(press_key_text,
                             (self.screen_width // 2 - press_key_text.get_width() // 2, self.screen_height // 2 + 50))

            pygame.display.flip()

            # Wait for key press
            waiting = True
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        quit()
                    if event.type == pygame.KEYDOWN:
                        waiting = False

        except Exception as e:
            print(f"DEBUG: Error clearing leaderboard: {e}")
            import traceback
            traceback.print_exc()

            # Show error message
            self.screen.fill(self.BLACK)
            error_text = self.bold_font.render(f"Error: {str(e)}", True, self.RED)
            self.screen.blit(error_text,
                             (self.screen_width // 2 - error_text.get_width() // 2, self.screen_height // 2))

            press_key_text = self.font.render(
                self.lang.get_string("press_key_continue", "Press any key to continue..."), True, self.WHITE)
            self.screen.blit(press_key_text,
                             (self.screen_width // 2 - press_key_text.get_width() // 2, self.screen_height // 2 + 50))

            pygame.display.flip()

            # Wait for key press
            waiting = True
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        quit()
                    if event.type == pygame.KEYDOWN:
                        waiting = False

        # Clear screen before returning to menu
        self.screen.fill(self.BLACK)
        pygame.display.flip()

    def clear_level(self):

        # Clear player bullets and deactivate power-ups
        self.clear_bullets()
        self.power_ups.reset_power_up()
        self.power_ups.spawn_time = time.time()
        self.power_ups.spawn_power_up()
        self.barricade_manager.reset()

    def show_instructions(self):
        instructions_pages = [
            {
                "title": self.lang.get_string("instr_title_objectives", "Objectives"),
                "text": [
                    self.lang.get_string("instr_obj_1", "Use LEFT/RIGHT arrow keys to move your firewall"),
                    self.lang.get_string("instr_obj_2", "Press SPACE to deploy security packets (shoot)"),
                    self.lang.get_string("instr_obj_3", "Destroy all incoming malware to progress"),
                    f"{self.lang.get_string('instr_obj_4', 'Survive through')} {self.total_levels} {self.lang.get_string('instr_obj_4_end', 'levels to reach the final boss')}",
                    self.lang.get_string("instr_obj_5", "Collect power-ups to enhance your defenses")
                ],
                "image": "game_image.png"
            },
            {
                "title": self.lang.get_string("instr_title_powerups", "Power-Ups"),
                "text": [
                    self.lang.get_string("instr_pow_1", "Pick up blue orbs to obtain a powerup for 5 seconds"),
                    self.lang.get_string("instr_pow_2", "Laser (Red) - Enhanced firewall throughput"),
                    self.lang.get_string("instr_pow_3", "Shield (Blue) - Temporary intrusion protection"),
                    self.lang.get_string("instr_pow_4", "TripleShot (Green) - Multi-vector defense system")
                ],
                "image": "powerups_image.png"
            },
            {
                "title": self.lang.get_string("instr_title_questions", "Cybersecurity Questions"),
                "text": [
                    self.lang.get_string("instr_qst_1", "You'll get security questions when hit"),
                    self.lang.get_string("instr_qst_2", "Correct answers restore system integrity"),
                    self.lang.get_string("instr_qst_3", "3 wrong answers compromise your network"),
                    self.lang.get_string("instr_qst_4", "Questions test real security knowledge")
                ],
                "image": "questions_image.png"
            },
            {
                "title": self.lang.get_string("instr_title_boss", "Boss Fight"),
                "text": [
                    self.lang.get_string("instr_boss_1", "Final confrontation with APT (Advanced Persistent Threat)"),
                    self.lang.get_string("instr_boss_2", "Use hacking minigame to weaken defenses"),
                    self.lang.get_string("instr_boss_3", "Prevent rage mode activation"),
                    self.lang.get_string("instr_boss_4", "Destroy core systems to win")
                ],
                "image": "boss_image.png"
            }
        ]

        current_page = 0
        running = True
        while running:
            self.screen.fill(self.BLACK)

            # Get current page data
            page = instructions_pages[current_page]

            # Draw title
            title_text = self.bold_font.render(page["title"], True, self.YELLOW)
            title_rect = title_text.get_rect(center=(self.screen_width // 2, 50))
            self.screen.blit(title_text, title_rect)

            # Load and draw image
            try:
                image_path = os.path.join("assets", "instructions", page["image"])
                image = pygame.image.load(image_path)
                image = pygame.transform.scale(image, (600, 270))
                image_rect = image.get_rect(center=(self.screen_width // 2, 225))
                self.screen.blit(image, image_rect)
            except Exception as e:
                print(f"Error loading instruction image: {e}")

            # Draw text
            text_y = 370
            for line in page["text"]:
                rendered_line = self.font.render(line, True, self.WHITE)
                self.screen.blit(rendered_line,
                                 (self.screen_width // 2 - rendered_line.get_width() // 2, text_y))
                text_y += 35

            # Draw page navigation
            page_text = self.font.render(
                f"{self.lang.get_string('page', 'Page')} {current_page + 1} {self.lang.get_string('of', 'of')} {len(instructions_pages)}",
                True, self.GREEN
            )
            self.screen.blit(page_text, (self.screen_width // 2 - page_text.get_width() // 2, 550))

            # Draw navigation help
            nav_text = self.font.render(
                self.lang.get_string("nav_help", "<-> : Navigate Pages | ESC: Return to Menu"),
                True, self.LIGHTBLUE
            )
            self.screen.blit(nav_text, (self.screen_width // 2 - nav_text.get_width() // 2, 580))

            pygame.display.flip()

            # Handle input
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        # Clear screen before returning to menu
                        self.screen.fill(self.BLACK)
                        pygame.display.flip()
                    elif event.key == pygame.K_LEFT:
                        current_page = max(0, current_page - 1)
                    elif event.key == pygame.K_RIGHT:
                        current_page = min(len(instructions_pages) - 1, current_page + 1)

    def reset_game(self):
        # Prompt for new player name at start of each new game
        print("DEBUG: Prompting for new player name...")
        if not self.get_player_name():
            return
        print(f"DEBUG: New player name set to: '{self.player_name}'")

        self.player.lives = 3
        self.player.x = (self.screen_width - self.player.width) // 2
        self.player.y = self.screen_height - self.player.height - 10
        self.player.invulnerable = False
        self.player.invulnerable_timer = 0
        self.level = 1
        self.boss_fight = False
        self.score = 0
        self.questions_asked = 0
        self.asked_questions = []
        self.question_difficulty = 1
        self.play_time = 0.0
        self.enemy_manager.create_enemies()
        self.boss.health = self.boss.max_health
        # Reset Bullets
        self.bullet_manager.player_bullets = []
        self.bullet_manager.enemy_bullets = []
        self.bullet_manager.boss_bullets = []
        # Reset Power-ups
        self.power_ups.power_up_active = False
        self.power_ups.current_power_up = None
        self.power_ups.power_ups = []
        self.power_ups.spawn_time = time.time()
        self.barricade_manager.reset()
        # Ensure game does NOT start paused
        self.paused = False
        self.main_game_loop()

    def reset_game_state(self):
        # Clear Bullets
        self.bullet_manager.player_bullets.clear()
        self.bullet_manager.enemy_bullets.clear()
        self.bullet_manager.boss_bullets.clear()
        self.barricade_manager.reset()
        # Clear Enemies
        self.enemy_manager.enemies.clear()
        # Clear Power-Ups
        self.power_ups.reset_power_up()
        self.power_ups.is_first_level = True
        # Reset Boss
        self.boss.reset_boss()
        self.boss_fight = False
        # Reset Score & Level
        self.level = 1
        self.questions_asked = 0
        self.asked_questions.clear()
        self.question_difficulty = 1
        self.play_time = 0.0
        self.score = 0
        # Reset Player
        self.player.lives = 3
        self.player.invulnerable = False
        self.player.invulnerable_timer = 0
        # Ensure UI and timers are reset
        pygame.time.set_timer(pygame.USEREVENT + 1, 0)
        if hasattr(self, 'score_adjustment'):
            del self.score_adjustment

    def end_game_screen(self):
        if self.game_over:
            return
        self.game_over = True
        self.adjust_score(self.SCORE_BOSS_DEFEATED + self.SCORE_LIFE_LEFT * self.player.lives, show=False)
        print(f"DEBUG: end_game_screen called! player_name='{self.player_name}', score={self.score}")
        self.screen.fill(self.BLACK)

        # Victory Text
        end_text = self.bold_font.render(f"{self.lang.get_string('win_text', 'YOU WIN! Your Score is:')} {self.score}",
                                         True, self.GREEN)
        self.screen.blit(end_text, (self.screen_width // 2 - end_text.get_width() // 2,
                                    self.screen_height // 3 - end_text.get_height() // 2))

        # Player name confirmation
        player_text = self.big_font.render(f"{self.lang.get_string('ui_player', 'Player')}: {self.player_name}", True,
                                           self.WHITE)
        self.screen.blit(player_text,
                         (self.screen_width // 2 - player_text.get_width() // 2, self.screen_height // 2 - 30))

        # Instruction
        instruction_text = self.font.render(
            self.lang.get_string("press_key_save_score", "Press any key to save score..."), True, self.GREEN)
        self.screen.blit(instruction_text,
                         (self.screen_width // 2 - instruction_text.get_width() // 2, self.screen_height // 2 + 30))

        pygame.display.flip()

        # Wait for key press
        print("DEBUG: Waiting for key press to save score...")
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()
                if event.type == pygame.KEYDOWN:
                    print(f"DEBUG: Key pressed, about to save score...")
                    waiting = False

        # Save score with stored player name
        print(f"DEBUG: About to call save_score with name='{self.player_name}', score={self.score}")
        self.save_score(self.player_name, self.score)
        self.power_ups.reset_power_up()

    def save_score(self, name, score):
        print(f"DEBUG: save_score called with name='{name}', score={score}")
        self.create_loading_screen()  # Show loading screen
        try:
            # Load existing leaderboard
            leaderboard_file = 'leaderboard.json'
            leaderboard_data = []

            if os.path.exists(leaderboard_file):
                print(f"DEBUG: Loading existing leaderboard from {leaderboard_file}")
                try:
                    with open(leaderboard_file, 'r') as f:
                        leaderboard_data = json.load(f)
                    print(f"DEBUG: Loaded {len(leaderboard_data)} existing entries")
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    print(f"DEBUG: Error loading leaderboard: {e}")
                    leaderboard_data = []
            else:
                print(f"DEBUG: Leaderboard file doesn't exist, creating new")

            # Add new score
            new_entry = {
                'player': name,
                'score': score,
                'time': round(self.play_time, 1),
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            leaderboard_data.append(new_entry)
            print(f"DEBUG: Added new entry: {new_entry}")

            # Sort by score (descending), equal scores by shorter play time, and keep top 10.
            # Entries from before play time was recorded rank last among equal scores.
            leaderboard_data = sorted(leaderboard_data,
                                      key=lambda x: (-x['score'], x.get('time', float('inf'))))[:10]
            print(f"DEBUG: After sorting, keeping {len(leaderboard_data)} entries")

            # Save to file
            print(f"DEBUG: Saving to {leaderboard_file}")
            with open(leaderboard_file, 'w') as f:
                json.dump(leaderboard_data, f, indent=2)
            print(f"DEBUG: Successfully saved leaderboard!")

            self.display_feedback(self.lang.get_string("score_saved_success", "Score saved successfully!"), self.GREEN)
        except Exception as e:
            print(f"DEBUG: Exception occurred: {e}")
            import traceback
            traceback.print_exc()
            self.display_feedback(f"Error saving score: {str(e)}", self.RED)

