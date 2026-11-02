import tkinter as tk

WIDTH, HEIGHT = 600, 500
PADDLE_W, PADDLE_H = 90, 12
BALL_R = 8
ROWS, COLS = 5, 10
BRICK_W, BRICK_H = 54, 20
COLORS = ["#e74c3c", "#e67e22", "#f1c40f", "#2ecc71", "#3498db"]
FPS_MS = 16


class Breakout:
    def __init__(self, root):
        self.root = root
        root.title("블럭깨기")
        root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="black")
        self.canvas.pack()
        self.left = self.right = False
        root.bind("<KeyPress-Left>", lambda e: setattr(self, "left", True))
        root.bind("<KeyRelease-Left>", lambda e: setattr(self, "left", False))
        root.bind("<KeyPress-Right>", lambda e: setattr(self, "right", True))
        root.bind("<KeyRelease-Right>", lambda e: setattr(self, "right", False))
        root.bind("<space>", self.on_space)
        self.canvas.bind("<Motion>", self.on_mouse)
        self.new_game()
        self.loop()

    def new_game(self):
        self.canvas.delete("all")
        self.score = 0
        self.lives = 3
        self.running = False
        self.over = False
        self.bricks = {}
        for r in range(ROWS):
            for c in range(COLS):
                x = 4 + c * (BRICK_W + 4)
                y = 50 + r * (BRICK_H + 4)
                item = self.canvas.create_rectangle(
                    x, y, x + BRICK_W, y + BRICK_H, fill=COLORS[r], outline="")
                self.bricks[item] = (x, y)
        self.paddle = self.canvas.create_rectangle(0, 0, PADDLE_W, PADDLE_H, fill="white")
        self.ball = self.canvas.create_oval(0, 0, BALL_R * 2, BALL_R * 2, fill="white")
        self.hud = self.canvas.create_text(10, 10, anchor="nw", fill="white",
                                           font=("Arial", 14))
        self.msg = self.canvas.create_text(WIDTH / 2, HEIGHT / 2, fill="white",
                                           font=("Arial", 18), text="")
        self.reset_ball()

    def reset_ball(self):
        px = (WIDTH - PADDLE_W) / 2
        py = HEIGHT - 40
        self.canvas.coords(self.paddle, px, py, px + PADDLE_W, py + PADDLE_H)
        bx = WIDTH / 2
        by = py - BALL_R * 2
        self.canvas.coords(self.ball, bx - BALL_R, by, bx + BALL_R, by + BALL_R * 2)
        self.vx, self.vy = 4, -5
        self.running = False
        self.canvas.itemconfig(self.msg, text="스페이스바: 시작 / 방향키·마우스: 이동")
        self.update_hud()

    def update_hud(self):
        self.canvas.itemconfig(self.hud, text=f"점수: {self.score}   목숨: {self.lives}")

    def on_space(self, _):
        if self.over:
            self.new_game()
        elif not self.running:
            self.running = True
            self.canvas.itemconfig(self.msg, text="")

    def on_mouse(self, e):
        self.move_paddle_to(e.x - PADDLE_W / 2)

    def move_paddle_to(self, x):
        x = max(0, min(WIDTH - PADDLE_W, x))
        y = self.canvas.coords(self.paddle)[1]
        self.canvas.coords(self.paddle, x, y, x + PADDLE_W, y + PADDLE_H)
        if not self.running and not self.over:
            self.canvas.coords(self.ball, x + PADDLE_W / 2 - BALL_R, y - BALL_R * 2,
                               x + PADDLE_W / 2 + BALL_R, y)

    def loop(self):
        if self.left:
            self.move_paddle_to(self.canvas.coords(self.paddle)[0] - 8)
        if self.right:
            self.move_paddle_to(self.canvas.coords(self.paddle)[0] + 8)
        if self.running:
            self.step()
        self.root.after(FPS_MS, self.loop)

    def step(self):
        self.canvas.move(self.ball, self.vx, self.vy)
        x1, y1, x2, y2 = self.canvas.coords(self.ball)

        if x1 <= 0:
            self.vx = abs(self.vx)
        elif x2 >= WIDTH:
            self.vx = -abs(self.vx)
        if y1 <= 0:
            self.vy = abs(self.vy)

        px1, py1, px2, py2 = self.canvas.coords(self.paddle)
        if self.vy > 0 and y2 >= py1 and y1 <= py2 and x2 >= px1 and x1 <= px2:
            hit = ((x1 + x2) / 2 - (px1 + px2) / 2) / (PADDLE_W / 2)
            self.vx = hit * 6
            self.vy = -abs(self.vy)

        for item in self.canvas.find_overlapping(x1, y1, x2, y2):
            if item in self.bricks:
                bx1, by1, bx2, by2 = self.canvas.coords(item)
                overlap_x = min(x2, bx2) - max(x1, bx1)
                overlap_y = min(y2, by2) - max(y1, by1)
                if overlap_x < overlap_y:
                    self.vx = -self.vx
                else:
                    self.vy = -self.vy
                self.canvas.delete(item)
                del self.bricks[item]
                self.score += 10
                self.update_hud()
                break

        if not self.bricks:
            self.finish("클리어! 스페이스바: 다시 시작")
        elif y1 >= HEIGHT:
            self.lives -= 1
            if self.lives <= 0:
                self.finish("게임 오버! 스페이스바: 다시 시작")
            else:
                self.reset_ball()

    def finish(self, text):
        self.running = False
        self.over = True
        self.update_hud()
        self.canvas.itemconfig(self.msg, text=text)


if __name__ == "__main__":
    root = tk.Tk()
    Breakout(root)
    root.mainloop()
