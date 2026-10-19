import pygame
import random

class HackingMiniGame:
    # Health the boss loses when the player finds the word
    BOSS_DAMAGE = 15
    # Directions the hidden word can run in: right, down, diagonal down-right, diagonal up-right
    DIRECTIONS = [(0, 1), (1, 0), (1, 1), (-1, 1)]

    def __init__(self, game):
        self.game = game
        self.lang = game.lang
        self.screen = game.screen
        self.screen_width = game.screen_width
        self.screen_height = game.screen_height
        self.grid_size = 8
        self.chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        self.words = ["SECURE", "ACCESS", "SYSTEM", "DEFEND", "SHIELD"]
        self.correct_word = random.choice(self.words)
        self.selected_row = 0
        self.selected_col = 0
        # Cells picked so far, in order; together they must form one straight line
        self.selected_cells = []
        self.rejected_time = 0
        self.time_limit = 20  # Timer for game
        self.start_time = pygame.time.get_ticks() / 1000
        self.grid = []
        self.generate_grid()

    def generate_grid(self):
        """Generate the grid with the correct word hidden in a straight line."""
        self.grid = [[random.choice(self.chars) for _ in range(self.grid_size)]
                     for _ in range(self.grid_size)]

        dr, dc = random.choice(self.DIRECTIONS)
        length = len(self.correct_word)
        while True:
            row = random.randrange(self.grid_size)
            col = random.randrange(self.grid_size)
            end_row, end_col = row + dr * (length - 1), col + dc * (length - 1)
            if 0 <= end_row < self.grid_size and 0 <= end_col < self.grid_size:
                break
        for i, c in enumerate(self.correct_word):
            self.grid[row + dr * i][col + dc * i] = c

    def selected_text(self):
        return "".join(self.grid[r][c] for r, c in self.selected_cells)

    def select_current_cell(self):
        """Add the cell under the cursor if it continues the line; otherwise flash it red."""
        pos = (self.selected_row, self.selected_col)
        valid = len(self.selected_cells) < len(self.correct_word) and pos not in self.selected_cells
        if valid and self.selected_cells:
            last = self.selected_cells[-1]
            step = (pos[0] - last[0], pos[1] - last[1])
            # The next letter has to touch the previous one...
            valid = max(abs(step[0]), abs(step[1])) == 1
            # ...and keep the direction set by the first two letters
            if valid and len(self.selected_cells) >= 2:
                first, second = self.selected_cells[0], self.selected_cells[1]
                valid = step == (second[0] - first[0], second[1] - first[1])
        if valid:
            self.selected_cells.append(pos)
        else:
            self.rejected_time = pygame.time.get_ticks()

    def show_instructions(self):
        self.screen.fill(self.game.BLACK)
        title = self.game.bold_font.render(self.lang.get_string("minigame_title", "HACKING MINIGAME"), True,
                                           self.game.GREEN)
        title_rect = title.get_rect(center=(self.screen_width // 2, 100))
        self.screen.blit(title, title_rect)

        instructions = [
            [(self.lang.get_string("minigame_instr_1", "Find the hidden word in the grid"), self.game.WHITE)],
            [(self.lang.get_string("minigame_instr_2",
                                   "The letters follow each other in a straight line, even diagonally"),
              self.game.WHITE)],
            [(self.lang.get_string("minigame_instr_3", "Arrows move, ENTER selects a letter"), self.game.LIGHTBLUE)],
            [(self.lang.get_string("minigame_instr_4", "DEL or BACKSPACE removes the last letter"), self.game.RED)],
            [(self.lang.get_string("minigame_instr_5", "Time limit: {seconds} s").format(seconds=self.time_limit),
              self.game.WHITE)],
            [(self.lang.get_string("minigame_reward",
                                   "Success: the boss loses {damage} HP. Failure: rage mode.").format(
                damage=self.BOSS_DAMAGE), self.game.YELLOW)],
            [(f"{self.lang.get_string('minigame_target', 'Hidden word')}: ", self.game.WHITE),
             (self.correct_word, self.game.GREEN)],
            [(" ", self.game.WHITE)],
            [(self.lang.get_string("minigame_start", "Press any key to start..."), self.game.YELLOW)]
        ]

        y = 200
        for line in instructions:
            total_width = sum(self.game.font.size(part[0])[0] for part in line)
            start_x = (self.screen_width - total_width) // 2
            x_offset = 0
            for part_text, part_color in line:
                text_surface = self.game.font.render(part_text, True, part_color)
                self.screen.blit(text_surface, (start_x + x_offset, y))
                x_offset += text_surface.get_width()
            y += 40

        pygame.display.flip()
        self.game.wait_for_keypress()

    def draw(self, remaining_time):
        """Draw all game elements"""
        self.screen.fill(self.game.BLACK)

        # Timer
        timer_text = self.game.font.render(f"{self.lang.get_string('minigame_time', 'TIME')}: {int(remaining_time)}",
                                           True, self.game.RED if remaining_time < 5 else self.game.WHITE)
        self.screen.blit(timer_text, (self.screen_width // 2 - timer_text.get_width() // 2, 10))

        # Grid
        cell_size = 40
        start_x = (self.screen_width - (self.grid_size * cell_size)) // 2
        start_y = (self.screen_height - (self.grid_size * cell_size)) // 2
        rejected = pygame.time.get_ticks() - self.rejected_time < 300

        for row in range(self.grid_size):
            for col in range(self.grid_size):
                x = start_x + col * cell_size
                y = start_y + row * cell_size
                char = self.grid[row][col]

                # Picked letters get a filled background
                if (row, col) in self.selected_cells:
                    pygame.draw.rect(self.screen, (0, 90, 0), (x, y, cell_size, cell_size))

                # Cursor; flashes red when the letter can't continue the line
                if row == self.selected_row and col == self.selected_col:
                    cursor_color = self.game.RED if rejected else self.game.GREEN
                    pygame.draw.rect(self.screen, cursor_color, (x - 2, y - 2, cell_size + 4, cell_size + 4), 3)

                text = self.game.font.render(char, True, self.game.WHITE)
                self.screen.blit(text, (x + cell_size // 2 - text.get_width() // 2,
                                        y + cell_size // 2 - text.get_height() // 2))

        input_text = self.game.font.render(self.selected_text(), True, self.game.WHITE)
        input_rect = input_text.get_rect(center=(self.screen_width // 2, start_y + (self.grid_size * cell_size) + 50))
        self.screen.blit(input_text, input_rect)

        status_color = self.game.RED if len(self.selected_cells) >= len(self.correct_word) else self.game.WHITE
        status_text = self.game.font.render(
            f"{len(self.selected_cells)}/{len(self.correct_word)}", True, status_color)
        self.screen.blit(status_text, (self.screen_width // 2 - status_text.get_width() // 2, input_rect.bottom + 10))

        word_text = self.game.font.render(
            f"{self.lang.get_string('minigame_target', 'Hidden word')}: {self.correct_word}", True, self.game.GREEN)
        self.screen.blit(word_text, (self.screen_width // 2 - word_text.get_width() // 2, start_y - 50))
        pygame.display.flip()

    def show_result(self, success):
        """Show win/lose result screen"""
        self.screen.fill(self.game.BLACK)

        if success:
            result_text = self.lang.get_string("minigame_success", "ACCESS GRANTED!")
            effect = self.lang.get_string("minigame_success_effect", "The boss loses {damage} HP!").format(
                damage=self.BOSS_DAMAGE)
            color = self.game.GREEN
        else:
            result_text = self.lang.get_string("minigame_fail", "ACCESS DENIED!")
            effect = self.lang.get_string("minigame_fail_effect", "The boss is entering rage mode!")
            color = self.game.RED

        text = self.game.bold_font.render(result_text, True, color)
        text_rect = text.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
        self.screen.blit(text, text_rect)

        effect_text = self.game.font.render(effect, True, color)
        effect_rect = effect_text.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 50))
        self.screen.blit(effect_text, effect_rect)

        prompt = self.game.font.render(self.lang.get_string("press_any_key", "Press any key to continue"), True,
                                       self.game.WHITE)
        prompt_rect = prompt.get_rect(center=(self.screen_width // 2, self.screen_height // 2 + 100))
        self.screen.blit(prompt, prompt_rect)

        pygame.display.flip()
        self.game.wait_for_keypress()

    def run(self):
        self.show_instructions()
        # Reset timer so that it starts after the instructions are dismissed
        self.start_time = pygame.time.get_ticks() / 1000
        success = False
        running = True

        while running:
            # Calculate time remaining
            current_time = pygame.time.get_ticks() / 1000
            elapsed = current_time - self.start_time
            remaining = self.time_limit - elapsed

            if remaining <= 0:
                running = False
                success = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    quit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        self.selected_row = max(0, self.selected_row - 1)
                    elif event.key == pygame.K_DOWN:
                        self.selected_row = min(self.grid_size - 1, self.selected_row + 1)
                    elif event.key == pygame.K_LEFT:
                        self.selected_col = max(0, self.selected_col - 1)
                    elif event.key == pygame.K_RIGHT:
                        self.selected_col = min(self.grid_size - 1, self.selected_col + 1)
                    elif event.key == pygame.K_RETURN:
                        self.select_current_cell()
                    elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                        if self.selected_cells:
                            self.selected_cells.pop()

            # Check win condition
            if self.selected_text() == self.correct_word:
                running = False
                success = True

            # Draw everything
            self.draw(remaining)
            self.game.clock.tick(60)

        self.show_result(success)
        return success
