#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Snake - a polished, responsive Snake game in pure Python.

Uses only the Python standard library (tkinter, json, random, time, pathlib),
so it runs on a regular Python 3 install with no pip packages.

Controls
  Arrows / WASD   move
  P / Space       pause / resume
  Enter / click   start / restart
  Esc             pause (in game) / back to menu (paused) / quit (menu)

Gameplay
  * Red apple   = 10 x level points, counts toward the next level
  * Gold star   = 50 x level points, disappears after a short time
  * Every 5 apples -> level up: the snake gets faster and new walls appear
  * Hitting a wall, an obstacle or yourself = Game Over
  * Best score is saved to ~/.snake_tk_highscore.json
"""

import json
import math
import random
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

# --------------------------------------------------------------- settings
COLS, ROWS = 28, 20
FOODS_PER_LEVEL = 5
BASE_TICK_MS = 220        # step time on level 1
TICK_STEP_MS = 10         # faster by this much every level
MIN_TICK_MS = 90          # speed cap
BONUS_CHANCE = 0.3
BONUS_LIFETIME = 45       # in snake steps
FPS = 60
SAVE_FILE = Path.home() / ".snake_tk_highscore.json"

THEME = {
    "bg": "#050505",
    "panel": "#0c0c0c",
    "shadow": "#000000",
    "cell_a": "#121212",
    "cell_b": "#171717",
    "border": "#2a2a2a",
    "text": "#e8ebf7",
    "muted": "#8a91b4",
    "accent": "#7c5cff",
    "accent_hi": "#a78bfa",
    "snake_head": "#f472b6",
    "snake_tail": "#7c3aed",
    "eye": "#ffffff",
    "pupil": "#0b0d18",
    "food": "#ff4d6d",
    "food_hi": "#ffc2cf",
    "leaf": "#22c55e",
    "stem": "#7c4a1e",
    "gold": "#fbbf24",
    "wall": "#3b4266",
    "wall_hi": "#565f8f",
    "danger": "#ff4d6d",
}

DIRS = {
    "up": (0, -1), "w": (0, -1),
    "down": (0, 1), "s": (0, 1),
    "left": (-1, 0), "a": (-1, 0),
    "right": (1, 0), "d": (1, 0),
}


# ---------------------------------------------------------------- helpers
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    ra, rb = hex_to_rgb(a), hex_to_rgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ra, rb))


def rrect(canvas, x1, y1, x2, y2, r, **kw):
    """Rounded rectangle drawn as a smoothed polygon."""
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def pick_font(root):
    available = set(tkfont.families(root))
    for fam in ("Segoe UI", "SF Pro Display", "Helvetica Neue", "Ubuntu",
                "Cantarell", "DejaVu Sans", "Arial", "Helvetica"):
        if fam in available:
            return fam
    return "Helvetica"


# ------------------------------------------------------------------- game
class SnakeGame:
    def __init__(self, root):
        self.root = root
        root.title("Snake")
        root.configure(bg=THEME["bg"])
        root.geometry("960x760")
        root.minsize(520, 440)

        self.family = pick_font(root)
        self.canvas = tk.Canvas(root, bg=THEME["bg"], highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Button-1>", self.on_click)
        root.bind("<KeyPress>", self.on_key)
        root.protocol("WM_DELETE_WINDOW", self.quit)

        # layout (recomputed on every resize)
        self.w = self.h = 1
        self.cell, self.ox, self.oy, self.hud_h, self.pad = 10, 0, 0, 60, 10

        self.best = self.load_best()
        self.state = "menu"          # menu | playing | paused | over
        self.reset()

        self.last_time = time.perf_counter()
        self.root.after(0, self.frame)

    # ----------------------------------------------------------- state
    def reset(self):
        cy = ROWS // 2
        self.snake = [(10 - i, cy) for i in range(4)]   # head first
        self.direction = (1, 0)
        self.queue = []
        self.score = 0
        self.level = 1
        self.eaten = 0
        self.acc = 0.0
        self.food = None
        self.bonus = None
        self.particles = []
        self.banner = None
        self.new_record = False
        self.build_obstacles()
        self.food = self.random_free_cell()
        self.draw_static()

    def start(self):
        self.reset()
        self.state = "playing"

    def tick_seconds(self):
        return max(MIN_TICK_MS, BASE_TICK_MS - (self.level - 1) * TICK_STEP_MS) / 1000

    def safe_zone(self):
        """Cells that must stay free of new obstacles (around the snake)."""
        safe = set(self.snake)
        hx, hy = self.snake[0]
        dx, dy = self.direction
        for k in range(1, 7):
            safe.add((hx + dx * k, hy + dy * k))
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                safe.add((hx + ox, hy + oy))
        return safe

    def build_obstacles(self):
        lv = self.level
        cells = set()
        if lv >= 2:   # two horizontal bars
            for x in range(COLS // 4, COLS - COLS // 4):
                cells.add((x, ROWS // 4))
                cells.add((x, ROWS - 1 - ROWS // 4))
        if lv >= 3:   # two vertical bars
            for y in range(ROWS // 3, ROWS - ROWS // 3):
                cells.add((3, y))
                cells.add((COLS - 4, y))
        if lv >= 4:   # scattered blocks, more each level
            rng = random.Random(lv * 7919)
            target = len(cells) + min(40, (lv - 3) * 5)
            tries = 0
            while len(cells) < target and tries < 2000:
                tries += 1
                cells.add((rng.randrange(1, COLS - 1), rng.randrange(1, ROWS - 1)))
        self.obstacles = cells - self.safe_zone()

    def random_free_cell(self):
        taken = set(self.snake) | self.obstacles
        if self.food:
            taken.add(self.food)
        if self.bonus:
            taken.add(self.bonus["pos"])
        free = [(x, y) for x in range(COLS) for y in range(ROWS) if (x, y) not in taken]
        return random.choice(free) if free else None

    # ------------------------------------------------------------ loop
    def frame(self):
        now = time.perf_counter()
        dt = min(0.1, now - self.last_time)
        self.last_time = now

        if self.state == "playing":
            self.acc += dt
            tick = self.tick_seconds()
            while self.acc >= tick and self.state == "playing":
                self.acc -= tick
                self.step(now)

        self.update_particles(dt)
        self.draw(now)
        self.root.after(int(1000 / FPS), self.frame)

    def step(self, now):
        if self.queue:
            self.direction = self.queue.pop(0)
        dx, dy = self.direction
        hx, hy = self.snake[0]
        head = ((hx + dx) % COLS, (hy + dy) % ROWS)

        eats_food = head == self.food
        eats_bonus = self.bonus is not None and head == self.bonus["pos"]
        growing = eats_food or eats_bonus
        body = self.snake if growing else self.snake[:-1]

        if (not (0 <= head[0] < COLS and 0 <= head[1] < ROWS)
                or head in self.obstacles or head in body):
            self.game_over()
            return

        self.snake.insert(0, head)
        if not growing:
            self.snake.pop()

        if self.bonus and not eats_bonus:
            self.bonus["life"] -= 1
            if self.bonus["life"] <= 0:
                self.bonus = None

        if eats_bonus:
            pts = 100 * self.level
            self.score += pts
            self.burst(head, THEME["gold"], 18)
            self.popup(head, f"+{pts}", THEME["gold"])
            self.bonus = None

        if eats_food:
            pts = 25 * self.level
            self.score += pts
            self.eaten += 1
            self.burst(head, THEME["food"], 14)
            self.popup(head, f"+{pts}", THEME["text"])
            self.food = None
            self.food = self.random_free_cell()
            if self.bonus is None and random.random() < BONUS_CHANCE:
                pos = self.random_free_cell()
                if pos:
                    self.bonus = {"pos": pos, "life": BONUS_LIFETIME}
            if self.eaten >= FOODS_PER_LEVEL:
                self.level_up(now)
            if self.food is None:      # board full - nothing left to eat
                self.game_over()

    def level_up(self, now):
        self.level += 1
        self.eaten = 0
        self.build_obstacles()
        if self.food in self.obstacles:
            self.food = None
            self.food = self.random_free_cell()
        if self.bonus and self.bonus["pos"] in self.obstacles:
            self.bonus = None
        self.banner = (f"LEVEL {self.level}", now + 1.6)
        self.burst(self.snake[0], THEME["accent_hi"], 26)
        self.draw_static()

    def game_over(self):
        self.state = "over"
        if self.score > self.best:
            self.best = self.score
            self.new_record = True
            self.save_best()
        self.burst(self.snake[0], THEME["danger"], 30)

    # ------------------------------------------------------- particles
    def burst(self, cell, color, n):
        x, y = cell[0] + 0.5, cell[1] + 0.5
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(2, 6)
            life = random.uniform(0.35, 0.8)
            self.particles.append({"x": x, "y": y, "vx": math.cos(ang) * spd,
                                   "vy": math.sin(ang) * spd, "life": life,
                                   "max": life, "color": color, "text": None})

    def popup(self, cell, text, color):
        self.particles.append({"x": cell[0] + 0.5, "y": cell[1] + 0.1, "vx": 0,
                               "vy": -1.6, "life": 0.9, "max": 0.9,
                               "color": color, "text": text})

    def update_particles(self, dt):
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["text"] is None:
                p["vy"] += 9 * dt
            p["life"] -= dt
        self.particles = [p for p in self.particles if p["life"] > 0
                          and -0.5 <= p["x"] <= COLS + 0.5
                          and -0.5 <= p["y"] <= ROWS + 0.5]

    # ----------------------------------------------------------- input
    def enqueue(self, d):
        last = self.queue[-1] if self.queue else self.direction
        if d == last or (d[0] == -last[0] and d[1] == -last[1]):
            return
        if len(self.queue) < 3:
            self.queue.append(d)

    def on_key(self, e):
        k = e.keysym.lower()
        if k in DIRS:
            if self.state == "playing":
                self.enqueue(DIRS[k])
            return
        if k in ("return", "kp_enter"):
            if self.state in ("menu", "over"):
                self.start()
            elif self.state == "paused":
                self.state = "playing"
        elif k in ("p", "space"):
            if self.state == "playing":
                self.state = "paused"
            elif self.state == "paused":
                self.state = "playing"
            elif k == "space":
                self.start()
        elif k == "escape":
            if self.state == "playing":
                self.state = "paused"
            elif self.state == "paused":
                self.reset()
                self.state = "menu"
            else:
                self.quit()

    def on_click(self, _e):
        if self.state in ("menu", "over"):
            self.start()
        elif self.state == "paused":
            self.state = "playing"

    # ----------------------------------------------------------- layout
    def on_resize(self, e):
        self.w, self.h = max(e.width, 1), max(e.height, 1)
        self.pad = max(10, min(self.w, self.h) * 0.025)
        self.hud_h = max(56, self.h * 0.1)
        avail_w = self.w - 2 * self.pad
        avail_h = self.h - self.hud_h - 2 * self.pad
        self.cell = max(6, int(min(avail_w / COLS, avail_h / ROWS)))
        bw, bh = self.cell * COLS, self.cell * ROWS
        self.ox = int((self.w - bw) / 2)
        self.oy = int(self.hud_h + self.pad + (avail_h - bh) / 2)
        self.draw_static()

    def f(self, px, weight="bold"):
        return (self.family, -max(8, int(px)), weight)

    def px(self, x, y):
        return self.ox + x * self.cell, self.oy + y * self.cell

    # ------------------------------------------------------------ draw
    def draw_static(self):
        """Board, checkerboard and obstacles - redrawn only when they change."""
        c, T = self.canvas, THEME
        c.delete("static")
        cs, ox, oy = self.cell, self.ox, self.oy
        bw, bh = cs * COLS, cs * ROWS
        m = max(4, cs * 0.35)

        rrect(c, ox - m + 3, oy - m + 5, ox + bw + m + 3, oy + bh + m + 5, m * 1.6,
              fill=T["shadow"], tags="static")
        rrect(c, ox - m, oy - m, ox + bw + m, oy + bh + m, m * 1.6,
              fill=T["border"], tags="static")
        rrect(c, ox - m + 2, oy - m + 2, ox + bw + m - 2, oy + bh + m - 2, m * 1.5,
              fill=T["panel"], tags="static")

        for y in range(ROWS):
            for x in range(COLS):
                col = T["cell_a"] if (x + y) % 2 == 0 else T["cell_b"]
                c.create_rectangle(ox + x * cs, oy + y * cs, ox + (x + 1) * cs,
                                   oy + (y + 1) * cs, fill=col, width=0, tags="static")

        r, i = cs * 0.22, cs * 0.06
        for (x, y) in self.obstacles:
            x1, y1 = ox + x * cs + i, oy + y * cs + i
            x2, y2 = x1 + cs - 2 * i, y1 + cs - 2 * i
            rrect(c, x1, y1, x2, y2, r, fill=T["wall"], tags="static")
            rrect(c, x1 + cs * 0.15, y1 + cs * 0.12, x2 - cs * 0.15, y1 + cs * 0.36,
                  r * 0.6, fill=T["wall_hi"], tags="static")
        c.tag_lower("static")

    def draw(self, now):
        self.canvas.delete("dyn")
        self.draw_hud()
        self.draw_food(now)
        self.draw_snake()
        self.draw_particles()
        self.draw_overlay(now)

    def draw_hud(self):
        c, T = self.canvas, THEME
        h = self.hud_h
        left, right = self.ox, self.ox + self.cell * COLS
        top, bottom = self.pad * 0.4, h - 12
        cy = (top + bottom) / 2
        ph = (bottom - top) * 0.92
        pw, gap = ph * 2.1, ph * 0.22

        stats = [("SCORE", self.score, T["text"]),
                 ("LEVEL", self.level, T["accent_hi"]),
                 ("BEST", self.best, T["gold"])]
        total = len(stats) * pw + (len(stats) - 1) * gap
        x = right - total
        for label, val, color in stats:
            rrect(c, x, cy - ph / 2, x + pw, cy + ph / 2, ph * 0.3, fill=T["panel"],
                  outline=T["border"], width=1, tags="dyn")
            c.create_text(x + pw / 2, cy - ph * 0.2, text=label, fill=T["muted"],
                          font=self.f(ph * 0.22), tags="dyn")
            c.create_text(x + pw / 2, cy + ph * 0.17, text=str(val), fill=color,
                          font=self.f(ph * 0.38), tags="dyn")
            x += pw + gap

        if (right - left) - total > ph * 3.2:   # title only if there is room
            dot = ph * 0.14
            c.create_oval(left, cy - dot, left + 2 * dot, cy + dot,
                          fill=T["snake_head"], width=0, tags="dyn")
            c.create_text(left + dot * 3.2, cy, text="SNAKE", anchor="w",
                          fill=T["text"], font=self.f(ph * 0.6), tags="dyn")

        # level progress bar
        by1, by2 = h - 7, h - 3
        rrect(c, left, by1, right, by2, 2, fill=T["panel"], tags="dyn")
        frac = self.eaten / FOODS_PER_LEVEL
        if frac > 0:
            rrect(c, left, by1, left + (right - left) * frac, by2, 2,
                  fill=T["accent"], tags="dyn")

    def draw_food(self, now):
        c, T, cs = self.canvas, THEME, self.cell
        if self.food:
            x, y = self.px(*self.food)
            cx, cy = x + cs / 2, y + cs / 2 + cs * 0.04
            r = cs * 0.34 * (1 + 0.08 * math.sin(now * 6))
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=T["food"], width=0, tags="dyn")
            c.create_oval(cx - r * 0.55, cy - r * 0.6, cx - r * 0.1, cy - r * 0.2,
                          fill=T["food_hi"], width=0, tags="dyn")
            c.create_line(cx, cy - r, cx + cs * 0.04, cy - r - cs * 0.14,
                          fill=T["stem"], width=max(1, cs * 0.06), tags="dyn")
            c.create_oval(cx + cs * 0.03, cy - r - cs * 0.16, cx + cs * 0.24, cy - r - cs * 0.04,
                          fill=T["leaf"], width=0, tags="dyn")

        if self.bonus:
            life = self.bonus["life"]
            if life < 10 and int(now * 6) % 2:     # blink before vanishing
                return
            x, y = self.px(*self.bonus["pos"])
            cx, cy = x + cs / 2, y + cs / 2
            R = cs * 0.38
            pts = []
            for k in range(10):
                ang = -math.pi / 2 + k * math.pi / 5 + now * 1.5
                rad = R if k % 2 == 0 else R * 0.45
                pts += [cx + math.cos(ang) * rad, cy + math.sin(ang) * rad]
            c.create_polygon(pts, fill=T["gold"], outline="", tags="dyn")
            R2 = cs * 0.48
            c.create_arc(cx - R2, cy - R2, cx + R2, cy + R2, start=90,
                         extent=min(359.9, 360 * life / BONUS_LIFETIME), style="arc",
                         outline=T["gold"], width=max(1, cs * 0.06), tags="dyn")

    def draw_snake(self):
        c, T, cs = self.canvas, THEME, self.cell
        n = len(self.snake)
        inset = cs * 0.1
        thick = cs - 2 * inset
        colors = [lerp_color(T["snake_head"], T["snake_tail"], i / max(1, n - 1))
                  for i in range(n)]

        for i in range(n - 1, -1, -1):     # tail first, head on top
            x, y = self.snake[i]
            sx, sy = self.px(x, y)
            if i > 0:                      # connector to the next segment
                nx, ny = self.px(*self.snake[i - 1])
                c1x, c1y = sx + cs / 2, sy + cs / 2
                c2x, c2y = nx + cs / 2, ny + cs / 2
                if c1y == c2y:
                    c.create_rectangle(min(c1x, c2x), c1y - thick / 2, max(c1x, c2x),
                                       c1y + thick / 2, fill=colors[i], width=0, tags="dyn")
                else:
                    c.create_rectangle(c1x - thick / 2, min(c1y, c2y), c1x + thick / 2,
                                       max(c1y, c2y), fill=colors[i], width=0, tags="dyn")
            rrect(c, sx + inset, sy + inset, sx + cs - inset, sy + cs - inset,
                  cs * 0.35, fill=colors[i], tags="dyn")

        # eyes
        hx, hy = self.px(*self.snake[0])
        cx, cy = hx + cs / 2, hy + cs / 2
        dx, dy = self.direction
        if self.queue and self.state != "playing":
            dx, dy = self.queue[0]
        perp = (-dy, dx)
        er, pr = cs * 0.12, cs * 0.065
        for side in (-1, 1):
            ex = cx + dx * cs * 0.14 + perp[0] * cs * 0.18 * side
            ey = cy + dy * cs * 0.14 + perp[1] * cs * 0.18 * side
            c.create_oval(ex - er, ey - er, ex + er, ey + er, fill=T["eye"], width=0, tags="dyn")
            px_, py_ = ex + dx * cs * 0.04, ey + dy * cs * 0.04
            c.create_oval(px_ - pr, py_ - pr, px_ + pr, py_ + pr, fill=T["pupil"],
                          width=0, tags="dyn")

    def draw_particles(self):
        c, cs = self.canvas, self.cell
        for p in self.particles:
            frac = p["life"] / p["max"]
            x, y = self.ox + p["x"] * cs, self.oy + p["y"] * cs
            if p["text"]:
                col = lerp_color(p["color"], THEME["bg"], 1 - frac)
                c.create_text(x, y, text=p["text"], fill=col, font=self.f(cs * 0.6), tags="dyn")
            else:
                r = cs * 0.12 * frac + 0.5
                c.create_oval(x - r, y - r, x + r, y + r, fill=p["color"], width=0, tags="dyn")

    def draw_card(self, lines, accent):
        c, T, cs = self.canvas, THEME, self.cell
        bw, bh = cs * COLS, cs * ROWS
        cx, cy = self.ox + bw / 2, self.oy + bh / 2
        heights = [s * cs * 1.5 for (_, s, _, _) in lines]
        ch = min(bh * 0.92, sum(heights) + cs * 2)
        cw = bw * 0.72
        x1, y1 = cx - cw / 2, cy - ch / 2
        rrect(c, x1 + cs * 0.2, y1 + cs * 0.3, x1 + cw + cs * 0.2, y1 + ch + cs * 0.3,
              cs * 0.9, fill=T["shadow"], tags="dyn")
        rrect(c, x1, y1, x1 + cw, y1 + ch, cs * 0.9, fill=accent, tags="dyn")
        rrect(c, x1 + 2, y1 + 2, x1 + cw - 2, y1 + ch - 2, cs * 0.85, fill=T["panel"], tags="dyn")
        y = cy - sum(heights) / 2
        for (text, s, color, weight), hh in zip(lines, heights):
            if text:
                c.create_text(cx, y + hh / 2, text=text, fill=color,
                              font=self.f(s * cs, weight), tags="dyn")
            y += hh

    def draw_overlay(self, now):
        T, cs = THEME, self.cell
        blink = T["text"] if int(now * 2) % 2 == 0 else T["muted"]

        if self.state == "menu":
            self.draw_card([
                ("SNAKE", 2.2, T["snake_head"], "bold"),
                ("Eat  -  Grow  -  Level up", 0.7, T["muted"], "normal"),
                ("", 0.3, "", ""),
                ("Arrows / WASD  -  move", 0.6, T["text"], "normal"),
                ("P / Space  -  pause      Esc  -  quit", 0.6, T["text"], "normal"),
                (f"Best score: {self.best}", 0.7, T["gold"], "bold"),
                ("", 0.2, "", ""),
                ("Press ENTER or click to start", 0.75, blink, "bold"),
            ], T["accent"])

        elif self.state == "paused":
            self.draw_card([
                ("PAUSED", 1.8, T["text"], "bold"),
                ("P / Space to resume   -   Esc for menu", 0.65, T["muted"], "normal"),
            ], T["accent"])

        elif self.state == "over":
            lines = [
                ("GAME OVER", 1.9, T["danger"], "bold"),
                (f"Score  {self.score}", 1.0, T["text"], "bold"),
                (f"Level {self.level}   -   Length {len(self.snake)}", 0.7, T["muted"], "normal"),
            ]
            if self.new_record:
                lines.append(("NEW RECORD!", 0.85, T["gold"], "bold"))
            lines.append(("Press ENTER or click to play again", 0.7, blink, "bold"))
            self.draw_card(lines, T["danger"])

        elif self.state == "playing" and self.banner:
            text, until = self.banner
            if now < until:
                c = self.canvas
                cx = self.ox + cs * COLS / 2
                cy = self.oy + cs * ROWS * 0.3
                fs = cs * 1.8
                c.create_text(cx + 2, cy + 3, text=text, fill=T["shadow"],
                              font=self.f(fs), tags="dyn")
                c.create_text(cx, cy, text=text, fill=T["accent_hi"],
                              font=self.f(fs), tags="dyn")
                c.create_text(cx, cy + fs * 0.9, text="Faster snake  -  new walls!",
                              fill=T["text"], font=self.f(cs * 0.6, "normal"), tags="dyn")
            else:
                self.banner = None

    # ------------------------------------------------------- persistence
    @staticmethod
    def load_best():
        try:
            return int(json.loads(SAVE_FILE.read_text(encoding="utf-8")).get("best", 0))
        except (OSError, ValueError, AttributeError, TypeError):
            return 0

    def save_best(self):
        try:
            SAVE_FILE.write_text(json.dumps({"best": self.best}), encoding="utf-8")
        except OSError:
            pass

    def quit(self):
        self.root.destroy()

# ======================= language switch (add-on) =======================
import re

LANG = {"current": "en"}          # "en" = English, "he" = Hebrew

PAIRS = [  # (English, Hebrew)
    ("SNAKE", "נחש"),
    ("SCORE", "ניקוד"),
    ("LEVEL", "שלב"),
    ("BEST", "שיא"),
    ("Eat  -  Grow  -  Level up", "אוכלים - גדלים - עולים שלב"),
    ("Arrows / WASD  -  move", "חיצים - תזוזה"),
    ("P / Space  -  pause      Esc  -  quit", "P או רווח - השהיה      Esc - יציאה"),
    ("Press ENTER or click to start", "לחצו Enter או הקליקו כדי להתחיל"),
    ("Press R or click to start", "לחצו R כדי להתחיל"),
    ("Press R or click to start", "לחצו R או Enter כדי להתחיל"),
    ("PAUSED", "השהיה"),
    ("P / Space to resume   -   Esc for menu", "P או רווח להמשך   -   Esc לתפריט"),
    ("GAME OVER", "המשחק נגמר"),
    ("NEW RECORD!", "שיא חדש!"),
    ("Press ENTER or click to play again", "לחצו Enter או הקליקו למשחק חוזר"),
    ("Press R or click to play again", "לחצו R למשחק חוזר"),
    ("Press R or click to play again", "לחצו R או Enter למשחק חוזר"),
    ("Faster snake  -  new walls!", "הנחש מהיר יותר - קירות חדשים!"),
]
PATTERNS = [  # texts that contain numbers
    (r"Best score: (\d+)", r"שיא: \1", r"שיא: (\d+)", r"Best score: \1"),
    (r"Score  (\d+)", r"ניקוד  \1", r"ניקוד  (\d+)", r"Score  \1"),
    (r"Level (\d+)   -   Length (\d+)", r"שלב \1   -   אורך \2",
     r"שלב (\d+)   -   אורך (\d+)", r"Level \1   -   Length \2"),
    (r"LEVEL (\d+)", r"שלב \1", r"שלב (\d+)", r"LEVEL \1"),
]
TO_HE = {en: he for en, he in PAIRS}
TO_EN = {he: en for en, he in PAIRS}


def translate(text):
    text = str(text)
    if LANG["current"] == "he":
        if text in TO_HE:
            return TO_HE[text]
        for en, he, _, _ in PATTERNS:
            if re.fullmatch(en, text):
                return re.sub(en, he, text)
    else:
        if text in TO_EN:
            return TO_EN[text]
        for _, _, he, en in PATTERNS:
            if re.fullmatch(he, text):
                return re.sub(he, en, text)
    return text


_original_create_text = tk.Canvas.create_text


def _create_text(self, *args, **kw):
    if "text" in kw:
        kw["text"] = translate(kw["text"])
    return _original_create_text(self, *args, **kw)


tk.Canvas.create_text = _create_text

_original_init = SnakeGame.__init__
_original_draw_hud = SnakeGame.draw_hud
_original_on_click = SnakeGame.on_click


def _init(self, root):
    _original_init(self, root)
    self.lang_box = None
    for key in ("<KeyPress-l>", "<KeyPress-L>", "<KeyPress-hebrew_finalkaph>"):
        try:
            root.bind(key, lambda e: self.toggle_language())
        except tk.TclError:
            pass


def _toggle_language(self):
    LANG["current"] = "he" if LANG["current"] == "en" else "en"
    self.root.title(translate("SNAKE"))


def _draw_hud(self):
    _original_draw_hud(self)
    c, T = self.canvas, THEME
    h = self.hud_h
    right = self.ox + self.cell * COLS
    top, bottom = self.pad * 0.4, h - 12
    cy = (top + bottom) / 2
    ph = (bottom - top) * 0.92
    pw, gap = ph * 2.1, ph * 0.22
    x2 = right - (3 * pw + 2 * gap) - gap
    x1 = x2 - ph * 1.9
    y1, y2 = cy - ph * 0.3, cy + ph * 0.3
    rrect(c, x1, y1, x2, y2, ph * 0.3, fill=T["panel"],
          outline=T["accent"], width=1, tags="dyn")
    label = "עברית" if LANG["current"] == "en" else "English"
    _original_create_text(c, (x1 + x2) / 2, cy, text=label, fill=T["accent_hi"],
                          font=self.f(ph * 0.26), tags="dyn")
    self.lang_box = (x1, y1, x2, y2)


def _on_click(self, e):
    if self.lang_box:
        x1, y1, x2, y2 = self.lang_box
        if x1 <= e.x <= x2 and y1 <= e.y <= y2:
            self.toggle_language()
            return
    _original_on_click(self, e)


SnakeGame.__init__ = _init
SnakeGame.toggle_language = _toggle_language
SnakeGame.draw_hud = _draw_hud
SnakeGame.on_click = _on_click
# ===================== end of language switch add-on =====================

# ======================= fixed food spot (add-on) =======================
FOOD_SPOT = (20, 10)   # (column, row): column 0-27 from the left, row 0-19 from the top

_fixed_original_reset = SnakeGame.reset
_fixed_original_step = SnakeGame.step


def _place_fixed_food(self):
    if FOOD_SPOT not in self.obstacles:          # if a wall covers the spot, stay random
        self.food = FOOD_SPOT
        if self.bonus and self.bonus["pos"] == FOOD_SPOT:
            pos = self.random_free_cell()
            self.bonus = {"pos": pos, "life": self.bonus["life"]} if pos else None


def _fixed_reset(self):
    _fixed_original_reset(self)
    _place_fixed_food(self)


def _fixed_step(self, now):
    _fixed_original_step(self, now)
    if self.state == "playing":
        _place_fixed_food(self)


SnakeGame.reset = _fixed_reset
SnakeGame.step = _fixed_step
# ===================== end of fixed food spot add-on =====================

# ======================= second player (add-on) =======================
# Player 1 = arrow keys, Player 2 = W A S D
P2_HEAD_COLOR = "#f472b6"   # pink
P2_TAIL_COLOR = "#7c3aed"   # purple
P2_WRAP_EDGES = True        # True = player 2 comes back from the opposite edge
P2_WALLS_KILL = False       # False = player 2 passes through the inner walls

P2_KEYS = {
    "w": (0, -1), "W": (0, -1), "apostrophe": (0, -1),
    "s": (0, 1), "S": (0, 1), "hebrew_dalet": (0, 1),
    "a": (-1, 0), "A": (-1, 0), "hebrew_shin": (-1, 0),
    "d": (1, 0), "D": (1, 0), "hebrew_gimel": (1, 0),
}
for _k in ("w", "a", "s", "d"):
    DIRS.pop(_k, None)          # W A S D now belong to player 2

_p2_original_init = SnakeGame.__init__
_p2_original_reset = SnakeGame.reset
_p2_original_step = SnakeGame.step
_p2_original_build = SnakeGame.build_obstacles
_p2_original_draw_snake = SnakeGame.draw_snake
_p2_original_draw_hud = SnakeGame.draw_hud
_p2_original_draw_overlay = SnakeGame.draw_overlay


def _p2_he():
    lang = globals().get("LANG")
    return bool(lang) and lang.get("current") == "he"


def _p2_init(self, root):
    self.snake2 = []
    _p2_original_init(self, root)
    for key, d in P2_KEYS.items():
        try:
            root.bind("<KeyPress-%s>" % key, lambda e, d=d: self.enqueue2(d))
        except tk.TclError:
            pass


def _p2_enqueue(self, d):
    if self.state != "playing":
        return
    last = self.queue2[-1] if self.queue2 else self.direction2
    if d == last or (d[0] == -last[0] and d[1] == -last[1]):
        return
    if len(self.queue2) < 3:
        self.queue2.append(d)


def _p2_reset(self):
    self.snake2 = []
    _p2_original_reset(self)
    y = ROWS - 5
    self.snake2 = [(COLS - 11 + i, y) for i in range(4)]   # head first, facing left
    self.direction2 = (-1, 0)
    self.queue2 = []
    self.score2 = 0
    self.winner = None
    if self.food in self.snake2:
        self.food = None
        self.food = self.random_free_cell()


def _p2_random_free_cell(self):
    taken = set(self.snake) | set(getattr(self, "snake2", [])) | self.obstacles
    if self.food:
        taken.add(self.food)
    if self.bonus:
        taken.add(self.bonus["pos"])
    free = [(x, y) for x in range(COLS) for y in range(ROWS) if (x, y) not in taken]
    return random.choice(free) if free else None


def _p2_build_obstacles(self):
    _p2_original_build(self)
    s2 = getattr(self, "snake2", [])
    if s2:
        safe = set(s2)
        hx, hy = s2[0]
        dx, dy = self.direction2
        for k in range(1, 7):
            safe.add((hx + dx * k, hy + dy * k))
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                safe.add((hx + ox, hy + oy))
        self.obstacles = self.obstacles - safe


def _p2_finish(self, winner):
    self.winner = winner
    if self.state != "over":
        self.game_over()


def _p2_step(self, now):
    _p2_original_step(self, now)                 # player 1 moves
    if self.state == "over" and self.winner is None:
        self.winner = 2                          # player 1 crashed
        return
    if self.state != "playing":
        return
    if self.snake[0] in self.snake2:             # player 1 ran into player 2
        _p2_finish(self, 2)
        return

    # ---- player 2 moves ----
    if self.queue2:
        self.direction2 = self.queue2.pop(0)
    dx, dy = self.direction2
    hx, hy = self.snake2[0]
    head = (hx + dx, hy + dy)
    if P2_WRAP_EDGES:
        head = (head[0] % COLS, head[1] % ROWS)
    eats_food = head == self.food
    eats_bonus = self.bonus is not None and head == self.bonus["pos"]
    growing = eats_food or eats_bonus
    body = self.snake2 if growing else self.snake2[:-1]

    if head == self.snake[0]:                    # head to head
        _p2_finish(self, 0)
        return
    if (not (0 <= head[0] < COLS and 0 <= head[1] < ROWS)
            or (P2_WALLS_KILL and head in self.obstacles)
            or head in body or head in self.snake):
        _p2_finish(self, 1)
        return

    self.snake2.insert(0, head)
    if not growing:
        self.snake2.pop()

    if eats_bonus:
        pts = 50 * self.level
        self.score2 += pts
        self.burst(head, THEME["gold"], 18)
        self.popup(head, f"+{pts}", P2_HEAD_COLOR)
        self.bonus = None
    if eats_food:
        pts = 10 * self.level
        self.score2 += pts
        self.eaten += 1
        self.burst(head, P2_HEAD_COLOR, 14)
        self.popup(head, f"+{pts}", P2_HEAD_COLOR)
        self.food = None
        self.food = self.random_free_cell()
        if self.eaten >= FOODS_PER_LEVEL:
            self.level_up(now)


def _p2_draw_snake(self):
    _p2_original_draw_snake(self)                # player 1
    if not self.snake2:
        return
    saved = (self.snake, self.direction, self.queue,
             THEME["snake_head"], THEME["snake_tail"])
    self.snake, self.direction, self.queue = self.snake2, self.direction2, self.queue2
    THEME["snake_head"], THEME["snake_tail"] = P2_HEAD_COLOR, P2_TAIL_COLOR
    try:
        _p2_original_draw_snake(self)            # player 2, same drawing, other colors
    finally:
        (self.snake, self.direction, self.queue,
         THEME["snake_head"], THEME["snake_tail"]) = saved


def _p2_draw_hud(self):
    _p2_original_draw_hud(self)
    c, cs = self.canvas, self.cell
    y = self.oy + cs * 0.55
    p1 = ("שחקן 1 (חיצים): %d" if _p2_he() else "P1 (arrows): %d") % self.score
    p2 = ("שחקן 2 (WASD): %d" if _p2_he() else "P2 (WASD): %d") % self.score2
    c.create_text(self.ox + cs * 0.4, y, text=p1, anchor="w", fill=THEME["snake_head"],
                  font=self.f(cs * 0.55), tags="dyn")
    c.create_text(self.ox + cs * COLS - cs * 0.4, y, text=p2, anchor="e",
                  fill=P2_HEAD_COLOR, font=self.f(cs * 0.55), tags="dyn")


def _p2_draw_overlay(self, now):
    _p2_original_draw_overlay(self, now)
    if self.state == "over" and self.winner is not None:
        cs = self.cell
        if self.winner == 0:
            text, color = ("תיקו!" if _p2_he() else "DRAW!"), THEME["text"]
        elif self.winner == 1:
            text, color = ("שחקן 1 ניצח!" if _p2_he() else "PLAYER 1 WINS!"), THEME["snake_head"]
        else:
            text, color = ("שחקן 2 ניצח!" if _p2_he() else "PLAYER 2 WINS!"), P2_HEAD_COLOR
        self.canvas.create_text(self.ox + cs * COLS / 2, self.oy + cs * 2.2, text=text,
                                fill=color, font=self.f(cs * 1.3), tags="dyn")


SnakeGame.__init__ = _p2_init
SnakeGame.enqueue2 = _p2_enqueue
SnakeGame.reset = _p2_reset
SnakeGame.random_free_cell = _p2_random_free_cell
SnakeGame.build_obstacles = _p2_build_obstacles
SnakeGame.step = _p2_step
SnakeGame.draw_snake = _p2_draw_snake
SnakeGame.draw_hud = _p2_draw_hud
SnakeGame.draw_overlay = _p2_draw_overlay
# ===================== end of second player add-on =====================

def main():
    if sys.platform.startswith("win"):        # sharp rendering on HiDPI screens
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
