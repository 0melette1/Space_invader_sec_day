import pygame
import math
import random
import time
import os
from scripts.game_logic.minigame import HackingMiniGame

class Boss:
    def __init__(self, game):
        self.game = game

        # Load assets
        self.base_image = self.load_and_scale_image("boss.png", (150, 150))
        self.rage_image = self.load_and_scale_image("boss_rage.png", (150, 150))
        # Secret skin: used when the player is named "Horox"
        self.skins = {
            "VIRUS": (self.base_image, self.rage_image),
            "HOROX": (self.load_and_scale_image("boss_horox.png", (150, 150)),
                      self.load_and_scale_image("boss_horox_rage.png", (150, 150))),
        }
        # Load the virus bullet asset
        self.virus_bullet_image = self.load_and_scale_image("virus.png", (20, 20))

        self.current_image = self.base_image
        self.width, self.height = self.base_image.get_size()
        self.x = (game.screen_width - self.width) // 2
        self.y = 100
        self.speed = 3  # used as a base speed for movement
        self.health = 100
        self.max_health = 100
        self.last_shot_time = 0
        self.animation_interval = 0.5
        self.last_animation_time = 0
        self.animation_toggle = False
        
        # Save initial positions/stats so you can reset if needed
        self.initial_x = self.x
        self.initial_y = self.y
        self.initial_speed = self.speed
        self.initial_shoot_interval = 0.1
        self.initial_animation_interval = self.animation_interval

        self.rage_mode = False
        self.name = "VIRUS"
        self.minigame_triggered = False

        # For movement that needs a stored horizontal velocity
        self.dx = self.speed

        # For erratic (phase 5) movement: target position and time
        self.target_pos = (self.x, self.y)
        self.last_target_update = pygame.time.get_ticks()

        # New attributes for the multi–phase AI:
        self.phase = 1  # Phases 1 to 5
        # Adjustable shooting intervals (in seconds) for each phase:
        self.phase1_shoot_interval = 0.15  # Phase 1: Line attack (100%-81%)
        self.phase2_shoot_interval = 0.1  # Phase 2: Spread attack (80%-61%)
        self.phase3_shoot_interval = 0.5  # Phase 3: Aimed attack (60%-41%)
        self.phase4_shoot_interval = 0.07  # Phase 4: Circle attack (40%-21%)
        self.phase5_shoot_interval = 1 # Phase 5: Virus explosion attack (20%-0%)
        
        # Variables for Virus Bullets
        self.virus_bullet_speed = 4
        self.min_explosion_dist = 300
        self.max_explosion_dist = 700
        self.player_explode_threshold = 250

    def load_and_scale_image(self, filename, size):
        try:
            return pygame.transform.scale(
                pygame.image.load(os.path.join("assets", "sprites", filename)).convert_alpha(), size
            )
        except pygame.error as e:
            print(f"Error loading or scaling image '{filename}': {e}")
            pygame.quit()
            quit()

    def update(self):
        # Update phase according to current health.
        self.update_phase()
        # Update movement based on phase.
        self.perform_movement()
        # Fire attacks based on phase.
        self.attack_pattern()
        # Update virus bullets (if any) so they can explode.
        self.update_virus_bullets()
        # Check for collisions with player bullets.
        self.check_hit_by_player()
        # Draw the boss and its health bar.
        self.draw()

    def update_phase(self):
        """Determine the current phase based on the percentage of remaining health."""
        health_percent = (self.health / self.max_health) * 100
        if health_percent > 80:
            self.phase = 1
        elif health_percent > 60:
            self.phase = 2
        elif health_percent > 40:
            self.phase = 3
        elif health_percent > 20:
            self.phase = 4
        else:
            self.phase = 5

    # ─── MOVEMENT PATTERNS ─────────────────────────────────────────────
    def perform_movement(self):
        """Call the movement routine for the current phase."""
        if self.phase == 1:
            self.movement_phase1()
        elif self.phase == 2:
            self.movement_phase2()
        elif self.phase == 3:
            self.movement_phase3()
        elif self.phase == 4:
            self.movement_phase4()
        elif self.phase == 5:
            self.movement_phase5()

    def movement_phase1(self):
        # Simple horizontal movement between preset boundaries.
        x_min = 50
        x_max = self.game.screen_width - self.width - 50
        self.x += self.dx
        if self.x < x_min or self.x > x_max:
            self.dx = -self.dx
            self.x += self.dx

    def movement_phase2(self):
        # Horizontal movement similar to phase 1 with a sine-based vertical oscillation.
        x_min = 50
        x_max = self.game.screen_width - self.width - 50
        self.x += self.dx
        if self.x < x_min or self.x > x_max:
            self.dx = -self.dx
            self.x += self.dx
        base_y = 100
        amplitude = 20
        self.y = base_y + amplitude * math.sin(pygame.time.get_ticks() / 1000.0)

    def movement_phase3(self):
        # Boss “aims” at the player but with smoothing.
        target_x = self.game.player.x + self.game.player.width/2 - self.width/2
        # Calculate a fraction of the difference to move smoothly.
        dx = (target_x - self.x) * 0.05
        # Limit the maximum movement per update.
        if dx > self.speed:
            dx = self.speed
        elif dx < -self.speed:
            dx = -self.speed
        self.x += dx
        # Vertical oscillation (set movement, not pure reaction).
        base_y = 100
        amplitude = 20
        self.y = base_y + amplitude * math.sin(pygame.time.get_ticks() / 1000.0)

    def movement_phase4(self):
        # Zigzag movement: use time–based sine functions for both x and y.
        period = 3000  # period in milliseconds
        t = pygame.time.get_ticks() % period
        x_min = 50
        x_max = self.game.screen_width - self.width - 50
        sine_val = math.sin(2 * math.pi * t / period)
        self.x = x_min + (x_max - x_min) * (sine_val + 1) / 2
        # Vertical oscillation between 50 and 150.
        self.y = 50 + (150 - 50) * ((math.sin(2 * math.pi * t / period + math.pi/4) + 1) / 2)

    def movement_phase5(self):
        # Erratic movement: update a target position every 2 seconds, then smoothly move toward it.
        current_time = pygame.time.get_ticks()
        if current_time - self.last_target_update > 2000:
            x_min = 50
            x_max = self.game.screen_width - self.width - 50
            y_min = 50
            y_max = self.game.screen_height // 3
            self.target_pos = (random.randint(x_min, x_max), random.randint(y_min, y_max))
            self.last_target_update = current_time
        target_x, target_y = self.target_pos
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.hypot(dx, dy)
        if distance != 0:
            dx = (dx / distance) * self.speed
            dy = (dy / distance) * self.speed
        self.x += dx
        self.y += dy

    # ─── ATTACK PATTERNS ─────────────────────────────────────────────
    def attack_pattern(self):
        """Select and execute an attack based on the current phase."""
        if self.phase == 1:
            self.speed = 6
            self.phase1_attack()
        elif self.phase == 2:
            self.speed = 3
            self.phase2_attack()
        elif self.phase == 3:
            self.speed = 5
            self.phase3_attack()
        elif self.phase == 4:
            self.speed = 3
            self.phase4_attack()
        elif self.phase == 5:
            self.phase5_attack()

    def phase1_attack(self):
        """Phase 1: Fire a bullet straight down."""
        current_time = time.time()
        if current_time - self.last_shot_time < self.phase1_shoot_interval:
            return
        self.last_shot_time = current_time
        self.game.bullet_manager.add_boss_bullet(
            self.x + self.width // 2, self.y + self.height, dx=0, dy=3
        )

    def phase2_attack(self):
        """Phase 2: Spread attack – continuously fire a single bullet with a random angle in a 45° cone (relative to straight down)."""
        current_time = time.time()
        if current_time - self.last_shot_time < self.phase2_shoot_interval:
            return
        self.last_shot_time = current_time

        # Compute the boss's firing point (center-bottom of the boss image)
        boss_center_x = self.x + self.width / 2
        boss_bottom_y = self.y + self.height

        # Choose a random angle between -22.5° and +22.5° (relative to straight down)
        angle = random.uniform(-90, 90)
        rad = math.radians(angle)
    
        # Calculate bullet velocity components; when angle=0, bullet goes straight down
        dx = math.sin(rad) * 3  # Horizontal component
        dy = math.cos(rad) * 3  # Vertical component

        # Fire a single bullet
        self.game.bullet_manager.add_boss_bullet(boss_center_x, boss_bottom_y, dx, dy)

    def phase3_attack(self):
        
        current_time = time.time()
        if current_time - self.last_shot_time < self.phase3_shoot_interval:
            return
        self.last_shot_time = current_time
        player_center_x = self.game.player.x + self.game.player.width / 2
        player_center_y = self.game.player.y + self.game.player.height / 2
        boss_center_x = self.x + self.width / 2
        boss_center_y = self.y + self.height / 2
        dx = (player_center_x - boss_center_x) / 50.0
        dy = (player_center_y - boss_center_y) / 50.0
        # Add slight inaccuracy
        dx += dx * random.uniform(-0.02, 0.02)
        dy += dy * random.uniform(-0.02, 0.02)
        self.game.bullet_manager.add_boss_bullet(
            self.x + self.width // 2, self.y + self.height, dx, dy
        )

    def phase4_attack(self):
        """Phase 4: Circle attack firing a bullet in a random direction."""
        current_time = time.time()
        if current_time - self.last_shot_time < self.phase4_shoot_interval:
            return
        self.last_shot_time = current_time
        angle = random.randint(0, 360)
        rad = math.radians(angle)
        dx = math.cos(rad) * 3
        dy = math.sin(rad) * 3
        self.game.bullet_manager.add_boss_bullet(
            self.x + self.width // 2, self.y + self.height, dx, dy
        )

    def phase5_attack(self):
        current_time = time.time()
        if current_time - self.last_shot_time < self.phase5_shoot_interval:
            return
        self.last_shot_time = current_time

        # Calculate direction to player
        px = self.game.player.x + self.game.player.width//2
        py = self.game.player.y + self.game.player.height//2
        bx = self.x + self.width//2
        by = self.y + self.height

        dx = px - bx
        dy = py - by
        dist = math.hypot(dx, dy)
        if dist == 0:
            dx, dy = 0, 1
        else:
            dx /= dist
            dy /= dist

        dx *= self.virus_bullet_speed
        dy *= self.virus_bullet_speed

        # Create virus bullet with explosion params
        virus_bullet = {
            "x": bx, "y": by, "dx": dx, "dy": dy, 
            "type": "virus", "image": self.virus_bullet_image,
            "start_x": bx, "start_y": by,
            "explode_dist": random.uniform(self.min_explosion_dist, self.max_explosion_dist)
        }
        self.game.bullet_manager.boss_bullets.append(virus_bullet)

    def update_virus_bullets(self):
        """Update virus bullets and trigger their explosion when they reach the threshold."""

        explosion_threshold = (5000)

        for bullet in self.game.bullet_manager.boss_bullets[:]:
            if isinstance(bullet, dict) and bullet.get("type") == "virus":
                # Update its position
                bullet["y"] += bullet["dy"]

                if bullet["y"] >= (500):
                    self.explode_virus(bullet)
                    self.game.bullet_manager.boss_bullets.remove(bullet)

    def explode_virus(self, bullet):
        """Explode the virus bullet into several bullets in a circular pattern."""
        x, y = bullet["x"], bullet["y"]
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            dx = math.cos(rad) * 4
            dy = math.sin(rad) * 4
            self.game.bullet_manager.add_boss_bullet(x, y, dx, dy)

    # ─── RAGE MODE ─────────────────────────────────────────────
    def enable_rage_mode(self):
        """
        When called (for example, if the player loses the minigame),
        the boss goes into rage mode:
         - Movement speed increases by 15%
         - Shooting intervals decrease by 15% (i.e. shooting faster)
         - The health bar displays a red "(Rage Mode)" next to its name.
        """
        if not self.rage_mode:
            self.rage_mode = True
            self.speed *= 1.5  # Increase base movement speed
            self.phase1_shoot_interval *= 0.5
            self.phase2_shoot_interval *= 0.5
            self.phase3_shoot_interval *= 0.5
            self.phase4_shoot_interval *= 0.5
            self.phase5_shoot_interval *= 0.5

    # ─── DRAWING METHODS ─────────────────────────────────────────────
    def draw(self):
        # Handle image animation (flip periodically)
        current_time = time.time()
        if current_time - self.last_animation_time >= self.animation_interval:
            self.animation_toggle = not self.animation_toggle
            base = self.rage_image if self.rage_mode else self.base_image
            self.current_image = (pygame.transform.flip(base, True, False)
                                  if self.animation_toggle else base)
            self.last_animation_time = current_time

        self.game.screen.blit(self.current_image, (self.x, self.y))
        self.draw_health_bar()

    def draw_health_bar(self):
        bar_width = 200
        health_width = int(bar_width * (self.health / self.max_health))
        bar_x = self.game.screen_width // 2 - bar_width // 2

        # Draw health bar background (red) and current health (green)
        pygame.draw.rect(self.game.screen, self.game.RED, (bar_x, 40, bar_width, 20))
        pygame.draw.rect(self.game.screen, self.game.GREEN, (bar_x, 40, health_width, 20))

        # Render "VIRUS" text
        name_text = self.game.font.render(self.name, True, self.game.YELLOW)
    
        # If in rage mode, render "(Rage Mode)" text
        if self.rage_mode:
            rage_text = self.game.font.render(self.game.lang.get_string("boss_rage_mode", "(Rage Mode)"), True,
                                              self.game.RED)

            # Calculate total width of "VIRUS (Rage Mode)" combined
            total_width = name_text.get_width() + 10 + rage_text.get_width()

            # Center the full text combo above the health bar
            name_x = self.game.screen_width // 2 - total_width // 2
            rage_x = name_x + name_text.get_width() + 10  # Place "(Rage Mode)" after "VIRUS"

            # Draw both texts
            self.game.screen.blit(name_text, (name_x, 10))
            self.game.screen.blit(rage_text, (rage_x, 10))
        else:
            # Just center "VIRUS" normally if not in rage mode
            name_x = self.game.screen_width // 2 - name_text.get_width() // 2
            self.game.screen.blit(name_text, (name_x, 10))


    def check_hit_by_player(self):
        """Check for collision with player bullets and update health."""
        for bullet in self.game.bullet_manager.player_bullets[:]:
            if (self.x < bullet[0] < self.x + self.width and 
                self.y < bullet[1] < self.y + self.height):
                self.game.bullet_manager.player_bullets.remove(bullet)
                self.health -= 1
                self.game.adjust_score(self.game.SCORE_BOSS_HIT, show=False)
                if self.health <= 0:
                    self.game.change_music(self.game.boss_defeated_music)
                    self.game.display_feedback(
                        self.game.lang.get_string("feedback_boss_defeated", "Boss Defeated!"), self.game.GREEN)
                    self.game.end_game_screen()
                    return
                # Once at half health: winning the minigame weakens the boss, losing it enrages the boss
                elif self.health <= self.max_health // 2 and not self.minigame_triggered:
                    self.minigame_triggered = True
                    if HackingMiniGame(self.game).run():
                        self.health = max(1, self.health - HackingMiniGame.BOSS_DAMAGE)
                    else:
                        self.enable_rage_mode()
                    # Don't drop the player back into bullets fired before the minigame
                    self.game.clear_bullets()
                    return

    def reset_boss(self):
        self.x = self.initial_x
        self.y = self.initial_y
        self.health = 100
        self.max_health = 100
        self.speed = self.initial_speed
        self.animation_interval = self.initial_animation_interval
        self.name = "HOROX" if self.game.player_name.strip().lower() == "horox" else "VIRUS"
        self.base_image, self.rage_image = self.skins[self.name]
        self.last_shot_time = 0
        self.last_animation_time = 0
        self.current_image = self.base_image
        self.direction = 1
        self.rage_mode = False
        self.minigame_triggered = False
        self.phase1_shoot_interval = 0.15  
        self.phase2_shoot_interval = 0.1  
        self.phase3_shoot_interval = 0.5  
        self.phase4_shoot_interval = 0.07  
        self.phase5_shoot_interval = 1 
        
