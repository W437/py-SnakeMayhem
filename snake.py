import pygame
import random
import sys
import numpy as np

# --- Game Constants ---
CELL_SIZE    = 20
GRID_WIDTH   = 50
GRID_HEIGHT  = 50
BOARD_WIDTH  = GRID_WIDTH * CELL_SIZE      # 1000 px
BOARD_HEIGHT = GRID_HEIGHT * CELL_SIZE     # 1000 px
SLIDER_HEIGHT = 40                        # Extra UI space at bottom
WINDOW_WIDTH  = BOARD_WIDTH
WINDOW_HEIGHT = BOARD_HEIGHT + SLIDER_HEIGHT

FOOD_COUNT = 5  # How many food pieces are concurrently on board

# --- Colors ---
BLACK      = (0, 0, 0)
WHITE      = (255, 255, 255)
RED        = (220, 20, 60)       # Crimson
GREEN      = (50, 205, 50)       # Lime Green
BLUE       = (65, 105, 225)      # Royal Blue
YELLOW     = (255, 215, 0)       # Gold
PURPLE     = (128, 0, 128)       # Aggressive powerup & snake color
CYAN       = (0, 255, 255)       # Shield (also snake color option)
ORANGE     = (255, 140, 0)       # Obstacles
MAGENTA    = (255, 0, 255)       # Multiplier powerup
DARK_GREY  = (50, 50, 50)

# Background gradient colors.
BG_TOP     = (10, 10, 30)
BG_BOTTOM  = (30, 30, 60)

# --- Initialize Pygame ---
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Snake Mayhem: NPC Snakes!")
clock = pygame.time.Clock()

# --- Initialize Mixer and Create Sounds (generated on the fly) ---
pygame.mixer.init()

def create_sound(frequency=440, duration_ms=200, volume=0.5):
    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, n_samples, endpoint=False)
    wave = np.sin(2 * np.pi * frequency * t) * (32767 * volume)
    wave = wave.astype(np.int16)
    mixer_init = pygame.mixer.get_init()  # (frequency, format, channels)
    if mixer_init is not None and mixer_init[2] == 2:
        wave = np.column_stack((wave, wave))
    return pygame.sndarray.make_sound(wave)

sound_eat    = create_sound(frequency=600, duration_ms=150, volume=0.5)
sound_cut    = create_sound(frequency=300, duration_ms=150, volume=0.5)
sound_dead   = create_sound(frequency=100, duration_ms=300, volume=0.5)
sound_boost  = create_sound(frequency=800, duration_ms=150, volume=0.5)

# --- Global Effects & Screen Shake ---
effects = []  # List to store particle effects.
screen_shake_timer = 0
screen_shake_intensity = 0

def add_effect(board_surf, board_pos, effect_type):
    # effect_type: "eat", "powerup", "death", "spawn"
    if effect_type == "eat":
        color = YELLOW
    elif effect_type == "powerup":
        color = MAGENTA
    elif effect_type == "death":
        color = RED
    elif effect_type == "spawn":
        color = GREEN
    else:
        color = WHITE
    effect = {
        'pos': board_pos,  # board cell (x,y) coordinate (not pixels)
        'timer': 30,
        'max_timer': 30,
        'color': color,
    }
    effects.append(effect)

def update_and_draw_effects(surface):
    # Draw effects on the given surface (which should be the game board surface).
    for effect in effects[:]:
        effect['timer'] -= 1
        if effect['timer'] <= 0:
            effects.remove(effect)
            continue
        progress = 1 - effect['timer'] / effect['max_timer']
        radius = int(5 + progress * 15)  # from 5 to 20 pixels radius
        alpha = int(255 * (1 - progress))
        # Create a temporary surface for the effect.
        eff_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(eff_surf, effect['color'] + (alpha,), (radius, radius), radius)
        # Convert board cell coordinate to pixels.
        pos_px = (int(effect['pos'][0]*CELL_SIZE + CELL_SIZE/2 - radius),
                  int(effect['pos'][1]*CELL_SIZE + CELL_SIZE/2 - radius))
        surface.blit(eff_surf, pos_px)

# --- Utility Functions ---
def lerp_color(color1, color2, t):
    return tuple(int(c1 + (c2 - c1) * t) for c1, c2 in zip(color1, color2))

def get_gradient_color(base_color, index, total):
    if total <= 1:
        return base_color
    factor = (index / (total - 1)) * 0.4
    return tuple(max(0, int(c * (1 - factor))) for c in base_color)

def draw_background(surface):
    for y in range(BOARD_HEIGHT):
        t = y / BOARD_HEIGHT
        color = lerp_color(BG_TOP, BG_BOTTOM, t)
        pygame.draw.line(surface, color, (0, y), (BOARD_WIDTH, y))
    for x in range(0, BOARD_WIDTH, CELL_SIZE):
        pygame.draw.line(surface, DARK_GREY, (x, 0), (x, BOARD_HEIGHT))
    for y in range(0, BOARD_HEIGHT, CELL_SIZE):
        pygame.draw.line(surface, DARK_GREY, (0, y), (BOARD_WIDTH, y))

def is_in_bounds(pos):
    return 0 <= pos[0] < GRID_WIDTH and 0 <= pos[1] < GRID_HEIGHT

def collides_with_other(new_head, current_snake, snakes):
    for snake in snakes:
        if snake != current_snake and new_head in snake.segments:
            return True
    return False

# --- Obstacles ---
obstacles = []
MAX_OBSTACLES = 10

def update_obstacles():
    for obs in obstacles[:]:
        obs['timer'] -= 1
        if obs['timer'] <= 0:
            obstacles.remove(obs)
    if len(obstacles) < MAX_OBSTACLES and random.random() < 0.02:
        spawn_obstacle()

def spawn_obstacle():
    occupied = set()
    for snake in snakes:
        occupied.update(snake.segments)
    for f in foods:
        occupied.add(f)
    for obs in obstacles:
        occupied.add(obs['pos'])
    for pu in powerups:
        occupied.add(pu['pos'])
    available = [(x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT) if (x, y) not in occupied]
    if available:
        pos = random.choice(available)
        timer = random.randint(50, 150)
        obstacles.append({'pos': pos, 'timer': timer})

def draw_obstacles(surface):
    for obs in obstacles:
        rect = pygame.Rect(obs['pos'][0]*CELL_SIZE, obs['pos'][1]*CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(surface, ORANGE, rect)

# --- Power-Ups ---
powerups = []
MAX_POWERUPS = 5

def update_powerups():
    for pu in powerups[:]:
        pu['timer'] -= 1
        if pu['timer'] <= 0:
            powerups.remove(pu)
    if len(powerups) < MAX_POWERUPS and random.random() < 0.01:
        spawn_powerup()

def spawn_powerup():
    occupied = set()
    for snake in snakes:
        occupied.update(snake.segments)
    for f in foods:
        occupied.add(f)
    for obs in obstacles:
        occupied.add(obs['pos'])
    available = [(x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT) if (x, y) not in occupied]
    if available:
        pos = random.choice(available)
        timer = random.randint(100, 200)
        pu_type = random.choice(["aggressive", "shield", "multiplier"])
        powerups.append({'pos': pos, 'timer': timer, 'type': pu_type})

def draw_powerups(surface):
    for pu in powerups:
        rect = pygame.Rect(pu['pos'][0]*CELL_SIZE, pu['pos'][1]*CELL_SIZE, CELL_SIZE, CELL_SIZE)
        if pu['type'] == "aggressive":
            color = PURPLE
        elif pu['type'] == "shield":
            color = CYAN
        elif pu['type'] == "multiplier":
            color = MAGENTA
        else:
            color = YELLOW
        pygame.draw.rect(surface, color, rect)

# --- Food (Multiple) ---
foods = []  # List of food coordinates

def spawn_food():
    # Spawn a food piece in a free cell.
    occupied = set()
    for snake in snakes:
        occupied.update(snake.segments)
    for f in foods:
        occupied.add(f)
    for obs in obstacles:
        occupied.add(obs['pos'])
    for pu in powerups:
        occupied.add(pu['pos'])
    available = [(x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT) if (x, y) not in occupied]
    if available:
        return random.choice(available)
    return None

# --- Snake Class ---
class Snake:
    def __init__(self, base_color, init_pos, direction):
        self.base_color = base_color
        self.segments = [init_pos]
        self.direction = direction
        self.score = 0
        self.alive = True
        self.respawn_timer = 0
        self.respawn_flash_timer = 0
        self.aggressive_timer = 0
        self.shield_timer = 0
        self.multiplier_timer = 0

    def head(self):
        return self.segments[0]

    def draw(self, surface):
        total = len(self.segments)
        for i, seg in enumerate(self.segments):
            color = get_gradient_color(self.base_color, i, total)
            rect = pygame.Rect(seg[0]*CELL_SIZE, seg[1]*CELL_SIZE, CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(surface, color, rect)
        # Glowing border if power-up active or on respawn.
        if self.aggressive_timer > 0 or self.respawn_flash_timer > 0:
            head_rect = pygame.Rect(self.head()[0]*CELL_SIZE, self.head()[1]*CELL_SIZE, CELL_SIZE, CELL_SIZE)
            glow_color = YELLOW if self.aggressive_timer > 0 else WHITE
            pygame.draw.rect(surface, glow_color, head_rect, 3)
        # Small icons above head for active power-ups.
        font = pygame.font.SysFont(None, 16)
        x, y = self.head()[0]*CELL_SIZE, self.head()[1]*CELL_SIZE
        status_text = ""
        if self.aggressive_timer > 0:
            status_text += "A"
        if self.shield_timer > 0:
            status_text += "S"
        if self.multiplier_timer > 0:
            status_text += "M"
        if status_text:
            txt = font.render(status_text, True, WHITE)
            surface.blit(txt, (x, y - 15))

# --- Enhanced AI Function ---
def get_direction_for_snake(snake, foods, powerups, snakes):
    head = snake.head()
    moves = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    candidate_moves = []
    obstacle_positions = {obs['pos'] for obs in obstacles}
    
    for move in moves:
        # Avoid immediate reversal.
        if len(snake.segments) > 1:
            if (head[0] + move[0], head[1] + move[1]) == snake.segments[1]:
                continue
        new_head = (head[0] + move[0], head[1] + move[1])
        if not is_in_bounds(new_head) or new_head in obstacle_positions:
            continue
        
        enemy_collision = False
        attack_bonus = 0
        for other in snakes:
            if other == snake:
                continue
            if new_head == other.head():
                if snake.aggressive_timer > 0 or len(snake.segments) > len(other.segments):
                    attack_bonus = 20
                else:
                    enemy_collision = True
                    break
            elif new_head in other.segments:
                enemy_collision = True
                break
        if enemy_collision:
            continue
        
        # Compute cost to target: choose the closer of food vs. powerup (if no powerup active)
        food_cost = min([abs(new_head[0]-f[0]) + abs(new_head[1]-f[1]) for f in foods]) if foods else 1000
        if (snake.aggressive_timer == 0 and snake.shield_timer == 0 and snake.multiplier_timer == 0
                and powerups):
            pu_cost = min([abs(new_head[0]-pu['pos'][0]) + abs(new_head[1]-pu['pos'][1]) for pu in powerups])
            target_cost = min(food_cost, pu_cost * 0.7)  # weight powerup distance lower
        else:
            target_cost = food_cost
        
        # Bonus for blocking enemy paths.
        for other in snakes:
            if other == snake:
                continue
            if foods:
                enemy_to_food = abs(other.head()[0]-foods[0][0]) + abs(other.head()[1]-foods[0][1])
                if enemy_to_food < target_cost and abs(new_head[0]-other.head()[0]) + abs(new_head[1]-other.head()[1]) == 1:
                    target_cost -= 5
        if new_head in snake.segments:
            target_cost += 10
        total_cost = target_cost - attack_bonus
        candidate_moves.append((move, total_cost))
    
    if candidate_moves:
        candidate_moves.sort(key=lambda x: x[1])
        return candidate_moves[0][0]
    return None

# --- Slider UI Functions ---
slider_rect = pygame.Rect(50, BOARD_HEIGHT + 10, BOARD_WIDTH - 100, 20)
slider_handle_radius = 10
speed_multiplier = 1

def draw_slider(surface, multiplier):
    pygame.draw.rect(surface, DARK_GREY, slider_rect)
    pygame.draw.rect(surface, WHITE, slider_rect, 2)
    ratio = (multiplier - 1) / 9.0
    handle_x = slider_rect.x + int(ratio * slider_rect.width)
    handle_y = slider_rect.y + slider_rect.height // 2
    pygame.draw.circle(surface, YELLOW, (handle_x, handle_y), slider_handle_radius)
    font = pygame.font.SysFont(None, 24)
    text = font.render(f"Speed: {multiplier}x", True, WHITE)
    surface.blit(text, (slider_rect.right + 10, slider_rect.y))

def update_slider(pos):
    global speed_multiplier
    if slider_rect.collidepoint(pos):
        rel = pos[0] - slider_rect.x
        ratio = rel / slider_rect.width
        new_mult = 1 + int(ratio * 9)
        speed_multiplier = max(1, min(10, new_mult))

# --- Respawn Function ---
def respawn_snake(snake):
    occupied = set()
    for other in snakes:
        occupied.update(other.segments)
    for f in foods:
        occupied.add(f)
    for obs in obstacles:
        occupied.add(obs['pos'])
    for pu in powerups:
        occupied.add(pu['pos'])
    available = [(x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT) if (x, y) not in occupied]
    if available:
        pos = random.choice(available)
    else:
        pos = (random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1))
    snake.segments = [pos]
    snake.direction = random.choice([(1,0), (-1,0), (0,1), (0,-1)])
    snake.alive = True
    snake.respawn_flash_timer = 30
    add_effect(game_board, pos, "spawn")

# --- Create Game Board Surface ---
game_board = pygame.Surface((BOARD_WIDTH, BOARD_HEIGHT))

# --- Create Snakes ---
# Define six snakes with distinct colors.
snake_colors = [RED, GREEN, BLUE, YELLOW, PURPLE, CYAN]
snakes = []
for i, color in enumerate(snake_colors):
    # Place them at random positions in the upper-left quadrant.
    pos = (random.randint(0, GRID_WIDTH//3), random.randint(0, GRID_HEIGHT//3))
    direction = random.choice([(1,0), (-1,0), (0,1), (0,-1)])
    snakes.append(Snake(color, pos, direction))

# --- Initialize Foods ---
foods = []
while len(foods) < FOOD_COUNT:
    new_food = spawn_food()
    if new_food is not None:
        foods.append(new_food)

# --- Header UI ---
def draw_header(surface):
    font_large = pygame.font.SysFont(None, 36)
    font_small = pygame.font.SysFont(None, 24)
    title = font_large.render("Snake Mayhem: NPC Snakes!", True, YELLOW)
    instructions = font_small.render("Snakes chase food & powerups! And, try to kill each other.", True, WHITE)
    surface.blit(title, ((BOARD_WIDTH - title.get_width()) // 2, 5))
    surface.blit(instructions, ((BOARD_WIDTH - instructions.get_width()) // 2, 40))

# --- Main Game Loop ---
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                update_slider(event.pos)
        elif event.type == pygame.MOUSEMOTION:
            if event.buttons[0]:
                update_slider(event.pos)
    
    update_obstacles()
    update_powerups()
    
    # Maintain constant food count.
    while len(foods) < FOOD_COUNT:
        new_food = spawn_food()
        if new_food is not None:
            foods.append(new_food)
    
    # Run game logic based on speed multiplier.
    for _ in range(speed_multiplier):
        for snake in snakes:
            if snake.alive:
                dir_choice = get_direction_for_snake(snake, foods, powerups, snakes)
                if dir_choice is None:
                    snake.alive = False
                    snake.respawn_timer = 50
                    sound_dead.play()
                    add_effect(game_board, snake.head(), "death")
                    screen_shake_timer = 10
                    screen_shake_intensity = 10
                    continue
                new_head = (snake.head()[0] + dir_choice[0], snake.head()[1] + dir_choice[1])
                if not is_in_bounds(new_head):
                    snake.alive = False
                    snake.respawn_timer = 50
                    sound_dead.play()
                    add_effect(game_board, snake.head(), "death")
                    screen_shake_timer = 10
                    screen_shake_intensity = 10
                    continue
                if new_head in {obs['pos'] for obs in obstacles}:
                    snake.alive = False
                    snake.respawn_timer = 50
                    sound_dead.play()
                    add_effect(game_board, snake.head(), "death")
                    screen_shake_timer = 10
                    screen_shake_intensity = 10
                    continue
                
                # Check enemy collisions.
                for other in snakes:
                    if other == snake:
                        continue
                    if new_head == other.head():
                        if snake.aggressive_timer > 0 or len(snake.segments) > len(other.segments):
                            if other.shield_timer > 0:
                                other.shield_timer = 0
                            else:
                                other.alive = False
                                other.respawn_timer = 50
                                sound_dead.play()
                                add_effect(game_board, other.head(), "death")
                                screen_shake_timer = 10
                                screen_shake_intensity = 10
                            snake.score += 2
                        else:
                            if snake.shield_timer > 0:
                                snake.shield_timer = 0
                            else:
                                snake.alive = False
                                snake.respawn_timer = 50
                                sound_dead.play()
                                add_effect(game_board, snake.head(), "death")
                                screen_shake_timer = 10
                                screen_shake_intensity = 10
                            break
                if not snake.alive:
                    continue

                snake.segments.insert(0, new_head)
                # Check if snake eats food.
                if new_head in foods:
                    if snake.multiplier_timer > 0:
                        snake.score += 2
                    else:
                        snake.score += 1
                    sound_eat.play()
                    add_effect(game_board, new_head, "eat")
                    foods.remove(new_head)
                else:
                    snake.segments.pop()
                
                # Self-collision: cut tail.
                if new_head in snake.segments[1:]:
                    idx = snake.segments.index(new_head, 1)
                    snake.segments = snake.segments[:idx]
                    sound_cut.play()
                
                # Check for powerup pickup.
                for pu in powerups[:]:
                    if new_head == pu['pos']:
                        if pu['type'] == "aggressive":
                            snake.aggressive_timer = 50
                        elif pu['type'] == "shield":
                            snake.shield_timer = 50
                        elif pu['type'] == "multiplier":
                            snake.multiplier_timer = 50
                        sound_boost.play()
                        add_effect(game_board, new_head, "powerup")
                        powerups.remove(pu)
                
                # Decrement timers.
                if snake.aggressive_timer > 0:
                    snake.aggressive_timer -= 1
                if snake.shield_timer > 0:
                    snake.shield_timer -= 1
                if snake.multiplier_timer > 0:
                    snake.multiplier_timer -= 1
                if snake.respawn_flash_timer > 0:
                    snake.respawn_flash_timer -= 1
            else:
                snake.respawn_timer -= 1
                if snake.respawn_timer <= 0:
                    respawn_snake(snake)
    
    # --- Drawing ---
    # Draw game board on its own surface.
    game_board.fill(BLACK)
    draw_background(game_board)
    draw_obstacles(game_board)
    draw_powerups(game_board)
    # Draw foods.
    for f in foods:
        rect = pygame.Rect(f[0]*CELL_SIZE, f[1]*CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(game_board, WHITE, rect)
    # Draw snakes.
    for snake in snakes:
        snake.draw(game_board)
    # Draw particle effects.
    update_and_draw_effects(game_board)
    
    # Screen shake: if active, choose a random offset.
    offset_x, offset_y = 0, 0
    if screen_shake_timer > 0:
        offset_x = random.randint(-screen_shake_intensity, screen_shake_intensity)
        offset_y = random.randint(-screen_shake_intensity, screen_shake_intensity)
        screen_shake_timer -= 1
    
    # Blit the game board (with offset if shaking) onto the main screen.
    screen.fill(BLACK)
    screen.blit(game_board, (offset_x, offset_y))
    
    # Draw header and slider on top.
    draw_header(screen)
    draw_slider(screen, speed_multiplier)
    
    # Scoreboard.
    font = pygame.font.SysFont(None, 24)
    y_off = BOARD_HEIGHT - 20 if BOARD_HEIGHT < WINDOW_HEIGHT - SLIDER_HEIGHT else WINDOW_HEIGHT - 20
    for i, snake in enumerate(snakes):
        status = "Alive" if snake.alive else "Respawning"
        pu_status = ""
        if snake.aggressive_timer > 0:
            pu_status += f" A:{snake.aggressive_timer}"
        if snake.shield_timer > 0:
            pu_status += f" S:{snake.shield_timer}"
        if snake.multiplier_timer > 0:
            pu_status += f" M:{snake.multiplier_timer}"
        txt = font.render(f"Snake {i+1}: {snake.score} ({status}){pu_status}", True, snake.base_color)
        screen.blit(txt, (5, y_off))
        y_off -= 20

    pygame.display.flip()
    clock.tick(10)

pygame.quit()
sys.exit()
