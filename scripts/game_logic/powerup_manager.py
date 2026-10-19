import time
import random
import pygame

class PowerUpManager:
    def __init__(self, game):
        self.spawn_time = 0
        self.spawn_interval = 15  # seconds between power-ups
        self.power_ups = []
        self.game = game
        self.power_up_active = False
        self.power_up_timer = 0
        self.current_power_up = None
        self.last_level_check = 1
        self.is_first_level = True 
        self.paused_time = None 
        
    def update(self):
        if self.game.paused:
            return
        current_time = time.time()
        # Only update spawn time if not paused
        if not self.game.paused and not self.power_up_active:
            if not self.power_ups and current_time - self.spawn_time >= self.spawn_interval:
                self.spawn_power_up()
                self.spawn_time = current_time
        # Handling for the first level
        if self.is_first_level:
            if not self.power_ups:
                self.spawn_power_up()
                self.is_first_level = False
        # Check if a new level has started (excluding first level)
        elif self.game.level != self.last_level_check:
            self.power_ups.clear()  
            self.spawn_power_up()  
            self.spawn_time = current_time  
            self.last_level_check = self.game.level 
        # Normal spawn conditions for non-boss levels when no power-up is active
        if not self.game.boss_fight and not self.power_up_active:
            if not self.power_ups and current_time - self.spawn_time >= self.spawn_interval:
                self.spawn_power_up()
                self.spawn_time = current_time
        # Update existing power-up
        if self.power_ups:
            power_up = self.power_ups[0]
            power_up[1] += 2  # Move downwards
            if power_up[1] > self.game.screen_height:
                self.power_ups.clear()  # Remove power-up if it goes off screen
                self.power_up_timer = time.time()
            else:
                pygame.draw.circle(self.game.screen, self.game.BLUE, (int(power_up[0]), int(power_up[1])), 10)

            # Check for collision with player
            if (self.game.player.x < power_up[0] < self.game.player.x + self.game.player.width and 
                self.game.player.y < power_up[1] < self.game.player.y + self.game.player.height):
                self.power_ups.clear()
                self.apply_power_up()
        # Deactivate power-up after duration
        if self.power_up_active:
            if current_time - self.power_up_timer > 5:  # Duration of power-up
                self.reset_power_up()

    def spawn_power_up(self):
        if not self.power_ups:  # Ensure only one power-up spawns at a time
            x = random.randint(0, self.game.screen_width - 20)
            y = 0
            self.power_ups = [[x, y]]

    def apply_power_up(self):
        self.power_up_active = True
        self.power_up_timer = time.time()
        power_up_types = ['Laser', 'Shield', 'TripleShot']
        self.current_power_up = random.choice(power_up_types)
        if self.current_power_up == 'Laser':
            self.game.bullet_manager.player_bullet_height = 30
            self.game.bullet_manager.player_bullet_speed = 35
            self.game.bullet_manager.player_shoot_interval = 0.05
        elif self.current_power_up == 'Shield':
            self.game.player.set_invulnerable()  # Changed from directly setting invulnerable to using a method
        elif self.current_power_up == 'TripleShot':
            self.game.bullet_manager.triple_shot = True
        self.game.adjust_score(self.game.SCORE_POWER_UP)  
        self.game.power_up_sound.play()

    def pause_powerups(self):
        if self.paused_time is None:
            # Record the time at which the game was paused.
            self.paused_time = time.time()

    def resume_powerups(self):
        if self.paused_time is None:
            return
        # Push every running timer further by the paused duration, so a pause costs nothing
        paused_duration = time.time() - self.paused_time
        self.paused_time = None
        self.power_up_timer += paused_duration
        self.spawn_time += paused_duration
        if self.game.player.invulnerable:
            self.game.player.invulnerable_timer += paused_duration

    def reset_power_up(self):
        self.power_up_active = False
        self.paused_time = None
        self.current_power_up = None
        self.power_ups = []
        self.power_ups.clear()
        self.spawn_time = time.time()  # Reset the spawn timer
        # Reset specific power-up effects
        self.game.bullet_manager.player_bullet_height = 10  # Default bullet height
        self.game.bullet_manager.player_bullet_speed = 7    # Default bullet speed
        self.game.bullet_manager.player_shoot_interval = 0.2  # Default shoot interval
        self.game.bullet_manager.triple_shot = False  # Disable TripleShot
        self.game.player.invulnerable = False  


