import os
import random
import sys
import pygame

# Original Flappy Bird sprite/audio recreation using the assets in this folder.
pygame.init()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITE_DIR = os.path.join(BASE_DIR, "sprites")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")

WIDTH, HEIGHT = 400, 600
FPS = 60
GROUND_HEIGHT = 90
GROUND_Y = HEIGHT - GROUND_HEIGHT
BIRD_X = int(WIDTH * 0.28)
GRAVITY = 0.42
FLAP_VELOCITY = -7.4
PIPE_SPEED = 3.0
PIPE_GAP = 155
PIPE_INTERVAL = 1450

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Flappy Bird")
clock = pygame.time.Clock()


def load_image(filename, alpha=True):
    path = os.path.join(SPRITE_DIR, filename)
    image = pygame.image.load(path)
    return image.convert_alpha() if alpha else image.convert()


def load_sound(filename):
    path = os.path.join(AUDIO_DIR, filename)
    try:
        return pygame.mixer.Sound(path)
    except (pygame.error, FileNotFoundError):
        return None


# Sprites
background = pygame.transform.smoothscale(load_image("background-day.png", False), (WIDTH, HEIGHT))
base_image = load_image("base.png")
pipe_image = load_image("pipe-green.png")
pipe_top_image = pygame.transform.flip(pipe_image, False, True)
bird_frames = [
    load_image("yellowbird-upflap.png"),
    load_image("yellowbird-midflap.png"),
    load_image("yellowbird-downflap.png"),
]
message_image = load_image("message.png")
gameover_image = load_image("gameover.png")
digits = [load_image(f"{n}.png") for n in range(10)]

# Sounds (OGG files included in the uploaded archive)
wing_sound = load_sound("wing.ogg")
point_sound = load_sound("point.ogg")
hit_sound = load_sound("hit.ogg")
die_sound = load_sound("die.ogg")
swoosh_sound = load_sound("swoosh.ogg")

# Scale the ground strip to the window width while preserving its appearance.
base_image = pygame.transform.scale(base_image, (WIDTH, GROUND_HEIGHT))


def play(sound):
    if sound is not None:
        sound.play()


def new_pipe():
    # gap_y is the bottom edge of the upper pipe and the top of the opening.
    min_gap_y = 115
    max_gap_y = GROUND_Y - PIPE_GAP - 75
    gap_y = random.randint(min_gap_y, max_gap_y)
    return {"x": float(WIDTH + 10), "gap_y": gap_y, "scored": False}


def reset_game():
    now = pygame.time.get_ticks()
    return {
        "bird_y": HEIGHT * 0.42,
        "velocity": 0.0,
        "bird_frame": 1,
        "frame_timer": 0.0,
        "pipes": [],
        "score": 0,
        "started": False,
        "game_over": False,
        "last_pipe_time": now,
        "ground_offset": 0.0,
        "hit_sound_played": False,
        "die_sound_played": False,
    }


def draw_center(image, center_x, center_y):
    rect = image.get_rect(center=(int(center_x), int(center_y)))
    screen.blit(image, rect)
    return rect


def draw_score(score):
    text_images = [digits[int(char)] for char in str(score)]
    spacing = 3
    total_width = sum(img.get_width() for img in text_images) + spacing * (len(text_images) - 1)
    x = (WIDTH - total_width) // 2
    y = 48
    for image in text_images:
        screen.blit(image, (x, y))
        x += image.get_width() + spacing


def bird_rect(game):
    image = bird_frames[game["bird_frame"]]
    rect = image.get_rect(center=(BIRD_X, int(game["bird_y"])))
    # A slightly forgiving hitbox is typical for this kind of game.
    return rect.inflate(-5, -4)


def pipe_collision_rects(pipe):
    x = int(pipe["x"])
    gap_y = pipe["gap_y"]
    bottom_y = gap_y + PIPE_GAP
    pipe_w = pipe_image.get_width()
    return (
        pygame.Rect(x, -pipe_image.get_height() + gap_y, pipe_w, pipe_image.get_height()),
        pygame.Rect(x, bottom_y, pipe_w, GROUND_Y - bottom_y),
    )


def draw_pipe(pipe):
    x = int(pipe["x"])
    gap_y = pipe["gap_y"]
    bottom_y = gap_y + PIPE_GAP
    # The source pipe sprite points down; flip vertically for the upper pipe.
    screen.blit(pipe_top_image, (x, gap_y - pipe_top_image.get_height()))
    screen.blit(pipe_image, (x, bottom_y))


def begin_or_flap(game):
    if game["game_over"]:
        return reset_game()
    if not game["started"]:
        game["started"] = True
        game["last_pipe_time"] = pygame.time.get_ticks()
        play(swoosh_sound)
    game["velocity"] = FLAP_VELOCITY
    play(wing_sound)
    return game


def main():
    game = reset_game()
    running = True

    while running:
        dt_ms = clock.tick(FPS)
        dt = min(dt_ms / (1000.0 / FPS), 2.0)  # frame units; prevents huge jumps after a pause
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    if game["game_over"]:
                        game = reset_game()
                    game = begin_or_flap(game)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if game["game_over"]:
                    game = reset_game()
                game = begin_or_flap(game)

        if game["started"] and not game["game_over"]:
            # Bird physics
            game["velocity"] += GRAVITY * dt
            game["bird_y"] += game["velocity"] * dt

            # Animate the three bird frames.
            game["frame_timer"] += dt_ms
            if game["frame_timer"] >= 90:
                game["frame_timer"] = 0
                game["bird_frame"] = (game["bird_frame"] + 1) % len(bird_frames)

            # Scroll ground
            game["ground_offset"] = (game["ground_offset"] + PIPE_SPEED * dt) % WIDTH

            # Spawn pipes by elapsed time.
            if now - game["last_pipe_time"] >= PIPE_INTERVAL:
                game["pipes"].append(new_pipe())
                game["last_pipe_time"] = now

            # Move pipes, detect collisions and award score once.
            current_bird_rect = bird_rect(game)
            for pipe in game["pipes"]:
                pipe["x"] -= PIPE_SPEED * dt
                upper_rect, lower_rect = pipe_collision_rects(pipe)
                if current_bird_rect.colliderect(upper_rect) or current_bird_rect.colliderect(lower_rect):
                    game["game_over"] = True
                    if not game["hit_sound_played"]:
                        play(hit_sound)
                        game["hit_sound_played"] = True
                    break

                if not pipe["scored"] and pipe["x"] + pipe_image.get_width() < BIRD_X:
                    pipe["scored"] = True
                    game["score"] += 1
                    play(point_sound)

            game["pipes"] = [p for p in game["pipes"] if p["x"] + pipe_image.get_width() > 0]

            # Ceiling / ground collision
            current_bird_rect = bird_rect(game)
            if current_bird_rect.top <= 0:
                game["game_over"] = True
                if not game["hit_sound_played"]:
                    play(hit_sound)
                    game["hit_sound_played"] = True
            if current_bird_rect.bottom >= GROUND_Y:
                game["game_over"] = True
                if not game["hit_sound_played"]:
                    play(hit_sound)
                    game["hit_sound_played"] = True

            if game["game_over"] and not game["die_sound_played"]:
                play(die_sound)
                game["die_sound_played"] = True

        elif not game["started"]:
            # Gentle idle bob on the title screen.
            game["bird_frame"] = (now // 180) % len(bird_frames)

        # Draw background, pipes, bird, score and ground.
        screen.blit(background, (0, 0))
        for pipe in game["pipes"]:
            draw_pipe(pipe)

        # Bird angle follows vertical movement, like the original game.
        bird = bird_frames[game["bird_frame"]]
        angle = 0
        if game["started"] and not game["game_over"]:
            angle = max(-25, min(70, -game["velocity"] * 3.2))
        elif game["game_over"]:
            angle = 70
        rotated_bird = pygame.transform.rotate(bird, angle)
        draw_center(rotated_bird, BIRD_X, game["bird_y"])

        draw_score(game["score"])

        # Ground tiles scroll horizontally.
        ground_x = -int(game["ground_offset"])
        screen.blit(base_image, (ground_x, GROUND_Y))
        screen.blit(base_image, (ground_x + WIDTH, GROUND_Y))

        if not game["started"]:
            draw_center(message_image, WIDTH // 2, HEIGHT // 2 - 25)
        elif game["game_over"]:
            draw_center(gameover_image, WIDTH // 2, HEIGHT // 2 - 80)
            # Reuse the original digit sprites for the final score.
            draw_score(game["score"])
            restart_font = pygame.font.Font(None, 25)
            restart = restart_font.render("SPACE / CLICK TO RESTART", True, (255, 255, 255))
            shadow = restart_font.render("SPACE / CLICK TO RESTART", True, (60, 60, 60))
            screen.blit(shadow, shadow.get_rect(center=(WIDTH // 2 + 1, HEIGHT // 2 + 5)))
            screen.blit(restart, restart.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 4)))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
