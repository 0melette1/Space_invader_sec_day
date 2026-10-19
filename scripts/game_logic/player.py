import pygame
import os
import time

class Player:
    def __init__(self, game):
        # Apply game scale factor to player size
        scaled_size = int(50 * game.scale_factor)
        self.image = self.load_and_scale_image("player.png", (scaled_size, scaled_size))
        self.width, self.height = self.image.get_size()
        self.x = (game.screen_width - self.width) // 2
        self.y = game.screen_height - self.height - 10
        self.speed = int(5 * game.scale_factor)
        self.lives = 3
        self.game = game
        self.invulnerable = False  
        self.invulnerable_timer = 0
        self.invulnerable_duration = 5  # Duration in seconds for invulnerability
        self.shield_outline = self.create_shield_outline()

    def load_and_scale_image(self, filename, size):
        try:
            return pygame.transform.scale(pygame.image.load(os.path.join("assets", "sprites", filename)).convert_alpha(), size)
        except pygame.error as e:
            print(f"Error loading or scaling image '{filename}': {e}")
            pygame.quit()
            quit()

    def create_shield_outline(self):
        outline_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        player_mask = pygame.mask.from_surface(self.image)
        dark_blue = (60, 60 , 180, 255)  # Darker blue for the outline

        for x in range(self.width):
            for y in range(self.height):
                if player_mask.get_at((x, y)):
                    # Check if this pixel is on or near the edge of the shape
                    for dx in range(-2, 3):  # Check 2 pixels in each direction
                        for dy in range(-2, 3):
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height and not player_mask.get_at((nx, ny)):
                                # Set color for a thicker outline
                                outline_surface.set_at((x, y), dark_blue)
                                for i in range(-1, 2):
                                    for j in range(-1, 2):
                                        nx2, ny2 = x + i, y + j
                                        if 0 <= nx2 < self.width and 0 <= ny2 < self.height:
                                            outline_surface.set_at((nx2, ny2), dark_blue)
                                break  # Break after setting one outline pixel to prevent overwriting
                        else:
                            continue
                        break

        return outline_surface    

    def move(self, keys):
        if keys[pygame.K_LEFT]:
            self.x -= self.speed
        if keys[pygame.K_RIGHT]:
            self.x += self.speed
        self.x = max(0, min(self.x, self.game.screen_width - self.width))

    def shoot(self, keys):
        current_time = time.time()
        if keys[pygame.K_SPACE] and current_time - self.game.bullet_manager.last_shot_time >= self.game.bullet_manager.player_shoot_interval:
            self.game.bullet_manager.add_player_bullet(self.x + self.width // 2, self.y)
            self.game.bullet_manager.last_shot_time = current_time
            self.game.shoot_sound.play()

    def draw(self):
        self.game.screen.blit(self.image, (self.x, self.y))
        
        if self.invulnerable:
            if int(time.time() * 5) % 2 == 0:  # Flash every 0.2 seconds
                self.game.screen.blit(self.shield_outline, (self.x, self.y))
                
    def set_invulnerable(self, duration=None):
        self.invulnerable = True
        self.invulnerable_timer = time.time()
        if duration:
            self.invulnerable_duration = duration
            
    def check_invulnerability(self):
        if self.invulnerable:
            current_time = time.time()
            if current_time - self.invulnerable_timer >= self.invulnerable_duration:
                self.invulnerable = False


