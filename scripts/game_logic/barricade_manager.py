import pygame

class BarricadeManager:
    def __init__(self, game):
        self.game = game
        self.barricades = []
        self.block_width = 15
        self.block_height = 10
        self.cols = 10
        self.rows = 4
        self.create_barricades()

    def create_barricades(self, saved_state=None):
        self.barricades = []  # Clear any old barricades
        barricade_y = self.game.screen_height - 120
        barricade_width = self.cols * self.block_width
        positions = [
            self.game.screen_width // 3 - barricade_width // 2,
            2 * self.game.screen_width // 3 - barricade_width // 2
        ]
    
        for x, saved_blocks in zip(positions, saved_state) if saved_state else [(x, None) for x in positions]:
            blocks = []
            if saved_blocks:  # Restoring from save
                for block in saved_blocks:
                    block_rect = pygame.Rect(block["x"], block["y"], self.block_width, self.block_height)
                    blocks.append({"rect": block_rect})
            else:  # Creating new barricades
                for row in range(self.rows):
                    for col in range(self.cols):
                        block_rect = pygame.Rect(
                            x + col * self.block_width,
                            barricade_y + row * self.block_height,
                            self.block_width,
                            self.block_height
                        )
                        blocks.append({"rect": block_rect})
            self.barricades.append(blocks)

    def update(self):
        for bullet in self.game.bullet_manager.enemy_bullets[:]:
            bullet_pos = (
                bullet[0] + self.game.bullet_manager.bullet_width / 2,
                bullet[1] + self.game.bullet_manager.enemy_bullet_height / 2
            )
            for barricade in self.barricades:
                for block in barricade:
                    if block["rect"].collidepoint(bullet_pos):
                        barricade.remove(block)  # Enemy bullets remove the block
                        if bullet in self.game.bullet_manager.enemy_bullets:
                            self.game.bullet_manager.enemy_bullets.remove(bullet)
                        break

        for bullet in self.game.bullet_manager.player_bullets[:]:
            bullet_pos = (bullet[0], bullet[1])
            for barricade in self.barricades:
                for block in barricade:
                    if block["rect"].collidepoint(bullet_pos):
                        if bullet in self.game.bullet_manager.player_bullets:
                            self.game.bullet_manager.player_bullets.remove(bullet)
                        break

    def draw(self):
        for barricade in self.barricades:
            for block in barricade:
                pygame.draw.rect(self.game.screen, (0, 255, 0), block["rect"])  # Always green

    def reset(self):
        self.create_barricades()
