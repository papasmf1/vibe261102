"""
뱀 게임 (tkinter 사용 - 별도 설치 불필요)

조작법:
  방향키 / WASD : 이동
  Space        : 일시정지 / 재개
  R            : 게임 오버 후 다시 시작
"""

import random
import tkinter as tk

# 게임 설정
CELL = 20          # 한 칸 크기(픽셀)
COLS = 30          # 가로 칸 수
ROWS = 24          # 세로 칸 수
START_SPEED = 120  # 시작 속도(ms, 작을수록 빠름)
MIN_SPEED = 50     # 최고 속도 제한

BG_COLOR = "#1e1e2e"
SNAKE_HEAD = "#a6e3a1"
SNAKE_BODY = "#40a02b"
FOOD_COLOR = "#f38ba8"
TEXT_COLOR = "#cdd6f4"

DIRECTIONS = {
    "Up": (0, -1), "w": (0, -1), "W": (0, -1),
    "Down": (0, 1), "s": (0, 1), "S": (0, 1),
    "Left": (-1, 0), "a": (-1, 0), "A": (-1, 0),
    "Right": (1, 0), "d": (1, 0), "D": (1, 0),
}


class SnakeGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Snake Game")
        self.root.resizable(False, False)

        self.score_label = tk.Label(
            root, font=("Consolas", 14, "bold"), bg=BG_COLOR, fg=TEXT_COLOR
        )
        self.score_label.pack(fill="x")

        self.canvas = tk.Canvas(
            root, width=COLS * CELL, height=ROWS * CELL,
            bg=BG_COLOR, highlightthickness=0
        )
        self.canvas.pack()

        self.high_score = 0
        self.after_id = None
        self.root.bind("<Key>", self.on_key)
        self.reset()

    def reset(self):
        """게임 상태 초기화"""
        if self.after_id:
            self.root.after_cancel(self.after_id)
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.score = 0
        self.speed = START_SPEED
        self.running = True
        self.paused = False
        self.food = self.spawn_food()
        self.update_score()
        self.tick()

    def spawn_food(self):
        """뱀이 없는 빈 칸에 먹이 생성"""
        empty = [
            (x, y) for x in range(COLS) for y in range(ROWS)
            if (x, y) not in self.snake
        ]
        return random.choice(empty) if empty else None

    def on_key(self, event):
        key = event.keysym
        if key in DIRECTIONS:
            new_dir = DIRECTIONS[key]
            # 반대 방향으로는 바로 꺾을 수 없음
            if (new_dir[0] + self.direction[0], new_dir[1] + self.direction[1]) != (0, 0):
                self.next_direction = new_dir
        elif key == "space" and self.running:
            self.paused = not self.paused
            if not self.paused:
                self.tick()
            else:
                self.draw()
        elif key in ("r", "R") and not self.running:
            self.reset()

    def tick(self):
        """한 프레임 진행"""
        if not self.running or self.paused:
            return

        self.direction = self.next_direction
        head_x, head_y = self.snake[0]
        new_head = (head_x + self.direction[0], head_y + self.direction[1])

        # 벽 충돌 또는 자기 몸 충돌 (꼬리는 이번에 이동하므로 제외)
        hit_wall = not (0 <= new_head[0] < COLS and 0 <= new_head[1] < ROWS)
        hit_self = new_head in self.snake[:-1]
        if hit_wall or hit_self:
            self.game_over()
            return

        self.snake.insert(0, new_head)

        if new_head == self.food:
            self.score += 10
            self.speed = max(MIN_SPEED, self.speed - 3)
            self.food = self.spawn_food()
            self.update_score()
            if self.food is None:  # 화면을 다 채움
                self.draw()
                self.game_over(win=True)
                return
        else:
            self.snake.pop()

        self.draw()
        self.after_id = self.root.after(self.speed, self.tick)

    def draw(self):
        self.canvas.delete("all")

        # 먹이
        if self.food:
            fx, fy = self.food
            self.canvas.create_oval(
                fx * CELL + 3, fy * CELL + 3,
                (fx + 1) * CELL - 3, (fy + 1) * CELL - 3,
                fill=FOOD_COLOR, outline=""
            )

        # 뱀
        for i, (x, y) in enumerate(self.snake):
            color = SNAKE_HEAD if i == 0 else SNAKE_BODY
            self.canvas.create_rectangle(
                x * CELL + 1, y * CELL + 1,
                (x + 1) * CELL - 1, (y + 1) * CELL - 1,
                fill=color, outline=""
            )

        if self.paused:
            self.show_message("일시정지", "Space 키로 계속")

    def show_message(self, title, subtitle):
        w, h = COLS * CELL, ROWS * CELL
        self.canvas.create_text(
            w // 2, h // 2 - 20, text=title,
            fill=TEXT_COLOR, font=("Malgun Gothic", 28, "bold")
        )
        self.canvas.create_text(
            w // 2, h // 2 + 20, text=subtitle,
            fill=TEXT_COLOR, font=("Malgun Gothic", 14)
        )

    def update_score(self):
        self.high_score = max(self.high_score, self.score)
        self.score_label.config(
            text=f"  점수: {self.score}    최고 점수: {self.high_score}"
        )

    def game_over(self, win=False):
        self.running = False
        title = "승리!" if win else "게임 오버"
        self.show_message(title, f"점수: {self.score}  |  R 키로 다시 시작")


if __name__ == "__main__":
    root = tk.Tk()
    root.configure(bg=BG_COLOR)
    SnakeGame(root)
    root.mainloop()
