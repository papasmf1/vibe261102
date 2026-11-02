"""
AURORA DRIFT (오로라 드리프트) - 세로 스크롤 슈팅 게임

외부 이미지/사운드 파일 없이 pygame 도형만으로 그리는 독창적인 종스크롤 슈팅입니다.

조작
  방향키 / WASD : 이동
  스페이스      : 사격 (누르고 있으면 연사)
  P             : 일시정지 / 재개
  R             : 재시작 (게임 오버 화면 또는 플레이 중)
  M             : 효과음 켜기 / 끄기
  ESC           : 종료

P 아이템을 먹을 때마다 동시 발사 탄 수가 2 → 4 → 8 → 16개로 늘어납니다.
효과음은 파일 없이 코드에서 직접 파형을 합성합니다.
"""

import math
from array import array
import random
import sys

import pygame

# ---------------------------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 480, 720
FPS = 60
TITLE = "AURORA DRIFT"

TERRAIN_SPEED = 1.2  # 지형(지상 구조물)이 흘러내리는 속도

# 색상 팔레트
BLACK = (6, 8, 18)
WHITE = (240, 244, 255)
CYAN = (90, 230, 255)
TEAL = (60, 200, 170)
ORANGE = (255, 150, 60)
RED = (255, 70, 80)
YELLOW = (255, 225, 90)
PURPLE = (180, 110, 255)
MAGENTA = (255, 90, 200)
GREEN = (110, 240, 130)
GREY = (120, 130, 150)


def clamp(v, lo, hi):
    """값을 lo~hi 범위로 제한"""
    return max(lo, min(hi, v))


def aim(x, y, tx, ty, speed):
    """(x, y)에서 (tx, ty)를 향하는 속도 벡터를 반환"""
    ang = math.atan2(ty - y, tx - x)
    return math.cos(ang) * speed, math.sin(ang) * speed


def circle_hit(ax, ay, ar, bx, by, br):
    """원과 원의 충돌 판정"""
    dx, dy = ax - bx, ay - by
    return dx * dx + dy * dy <= (ar + br) * (ar + br)


# ---------------------------------------------------------------------------
# 효과음: 외부 파일 없이 사각파/톱니파/사인파/노이즈를 합성해 만든다
# ---------------------------------------------------------------------------
class Sfx:
    def __init__(self):
        self.enabled = False
        self.muted = False
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.freq, size, self.channels = pygame.mixer.get_init()
            if size != -16:
                return  # 16비트 부호 있는 형식만 지원
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(1)  # 0번 채널은 사격음 전용
            self._build()
            self.enabled = True
        except (pygame.error, TypeError):
            # 오디오 장치가 없으면 소리 없이 진행
            self.enabled = False

    # ----- 파형 생성기 (p: 0~1 진행도) -----
    def _tone(self, f_start, f_end, wave="square"):
        phase = [0.0]

        def fn(p):
            phase[0] += (f_start + (f_end - f_start) * p) / self.freq
            x = phase[0] % 1.0
            if wave == "square":
                return 1.0 if x < 0.5 else -1.0
            if wave == "saw":
                return 2 * x - 1
            return math.sin(x * math.tau)
        return fn

    def _noise(self, hold_start, hold_end):
        """샘플 유지 노이즈: 유지 길이가 길수록 낮고 둔탁한 소리"""
        state = [0, 0.0]

        def fn(p):
            if state[0] <= 0:
                state[0] = int(hold_start + (hold_end - hold_start) * p)
                state[1] = random.uniform(-1, 1)
            state[0] -= 1
            return state[1]
        return fn

    def _synth(self, dur, fn, vol):
        """fn(p)로 샘플을 만들어 pygame Sound로 변환"""
        n = int(self.freq * dur)
        buf = array("h")
        for i in range(n):
            s = int(clamp(fn(i / n), -1, 1) * vol * 32767)
            buf.extend([s] * self.channels)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _build(self):
        sq = self._tone(1400, 600)
        self.sounds["shoot"] = self._synth(0.07, lambda p: sq(p) * (1 - p) ** 2, 0.12)

        nz = self._noise(2, 9)
        self.sounds["explode"] = self._synth(0.4, lambda p: nz(p) * (1 - p) ** 2, 0.45)

        big = self._noise(4, 24)
        self.sounds["big_explode"] = self._synth(1.3, lambda p: big(p) * (1 - p) ** 1.5, 0.7)

        saw, nz2 = self._tone(500, 50, "saw"), self._noise(3, 12)
        self.sounds["player_hit"] = self._synth(0.7, lambda p: (saw(p) * 0.6 + nz2(p) * 0.4) * (1 - p), 0.55)

        # 파워업: 도-미-솔-도 상승 아르페지오
        notes = [self._tone(f, f) for f in (523, 659, 784, 1047)]
        self.sounds["powerup"] = self._synth(
            0.32, lambda p: notes[min(3, int(p * 4))](p) * (1 - (p * 4) % 1 * 0.5), 0.2)

        shine = self._tone(900, 1700, "sine")
        self.sounds["shield"] = self._synth(0.18, lambda p: shine(p) * (1 - p), 0.4)

        # 보스 경고: 두 음이 번갈아 울리는 사이렌
        hi, lo = self._tone(440, 440), self._tone(330, 330)
        self.sounds["warning"] = self._synth(
            1.4, lambda p: (hi(p) if int(p * 7) % 2 == 0 else lo(p)) * (1 - (p * 7) % 1 * 0.6), 0.18)

    def play(self, name):
        if not self.enabled or self.muted:
            return
        if name == "shoot":
            # 연사음이 겹쳐 쌓이지 않도록 전용 채널에서 덮어쓰며 재생
            pygame.mixer.Channel(0).play(self.sounds[name])
        else:
            self.sounds[name].play()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted and self.enabled:
            pygame.mixer.stop()


# ---------------------------------------------------------------------------
# 배경: 다층 별 + 아래로 흐르는 지형 판
# ---------------------------------------------------------------------------
class Background:
    def __init__(self):
        # 별은 3개 층으로 나눠 속도를 달리해 원근감을 줌
        self.stars = []
        for layer, (speed, size, color) in enumerate(
            [(0.6, 1, (70, 80, 110)), (1.4, 1, (140, 150, 190)), (2.6, 2, (220, 230, 255))]
        ):
            for _ in range(40 - layer * 10):
                self.stars.append([random.uniform(0, WIDTH), random.uniform(0, HEIGHT), speed, size, color])
        # 지형 판(떠다니는 대지 조각)
        self.plates = []
        y = HEIGHT
        while y > -300:
            self.plates.append(self._make_plate(y))
            y -= random.randint(180, 280)

    def _make_plate(self, y):
        """불규칙한 다각형 대지 조각을 하나 생성"""
        cx = random.uniform(40, WIDTH - 40)
        r = random.uniform(50, 110)
        n = random.randint(7, 11)
        pts = []
        for i in range(n):
            a = i / n * math.tau
            rr = r * random.uniform(0.65, 1.0)
            pts.append((math.cos(a) * rr, math.sin(a) * rr * 0.8))
        # 표면 디테일: 회로 같은 선과 분화구
        lines = []
        for _ in range(random.randint(2, 4)):
            x1, y1 = random.uniform(-r * 0.5, r * 0.5), random.uniform(-r * 0.4, r * 0.4)
            lines.append(((x1, y1), (x1 + random.uniform(-25, 25), y1), (x1 + random.uniform(-25, 25), y1 + random.uniform(-20, 20))))
        craters = [(random.uniform(-r * 0.4, r * 0.4), random.uniform(-r * 0.3, r * 0.3), random.randint(4, 9))
                   for _ in range(random.randint(1, 3))]
        shade = random.randint(0, 12)
        return {
            "x": cx, "y": y, "pts": pts, "lines": lines, "craters": craters,
            "color": (22 + shade, 34 + shade, 48 + shade), "edge": (50 + shade, 78 + shade, 98 + shade),
        }

    def update(self):
        for s in self.stars:
            s[1] += s[2]
            if s[1] > HEIGHT:
                s[0], s[1] = random.uniform(0, WIDTH), random.uniform(-10, 0)
        for p in self.plates:
            p["y"] += TERRAIN_SPEED
        # 화면 밖으로 나간 판은 제거하고 위쪽에 새로 생성
        self.plates = [p for p in self.plates if p["y"] < HEIGHT + 150]
        top = min((p["y"] for p in self.plates), default=HEIGHT)
        if top > -150:
            self.plates.append(self._make_plate(top - random.randint(180, 280)))

    def draw(self, surf):
        surf.fill(BLACK)
        for x, y, _, size, color in self.stars:
            if size == 1:
                surf.set_at((int(x), int(y)), color)
            else:
                pygame.draw.circle(surf, color, (int(x), int(y)), size)
        for p in self.plates:
            ox, oy = p["x"], p["y"]
            poly = [(ox + x, oy + y) for x, y in p["pts"]]
            pygame.draw.polygon(surf, p["color"], poly)
            pygame.draw.polygon(surf, p["edge"], poly, 2)
            for a, b, c in p["lines"]:
                pygame.draw.lines(surf, p["edge"], False, [(ox + a[0], oy + a[1]), (ox + b[0], oy + b[1]), (ox + c[0], oy + c[1])], 1)
                pygame.draw.circle(surf, p["edge"], (int(ox + c[0]), int(oy + c[1])), 2)
            for cx, cy, cr in p["craters"]:
                pygame.draw.circle(surf, (14, 20, 30), (int(ox + cx), int(oy + cy)), cr)
                pygame.draw.circle(surf, p["edge"], (int(ox + cx), int(oy + cy)), cr, 1)


# ---------------------------------------------------------------------------
# 탄환 / 파티클 / 폭발
# ---------------------------------------------------------------------------
class Bullet:
    def __init__(self, x, y, vx, vy, radius=4, color=YELLOW, damage=1):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.radius = radius
        self.color = color
        self.damage = damage
        self.alive = True

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.x < -20 or self.x > WIDTH + 20 or self.y < -20 or self.y > HEIGHT + 20:
            self.alive = False

    def draw_player(self, surf):
        # 아군 탄: 길쭉한 빛줄기
        pygame.draw.line(surf, self.color, (self.x, self.y), (self.x - self.vx * 0.8, self.y - self.vy * 0.8), 3)
        pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), 2)

    def draw_enemy(self, surf):
        # 적 탄: 테두리가 있는 구슬
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), max(1, self.radius - 2))


class Particle:
    def __init__(self, x, y, color, speed=3.0, life=30, size=3):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(0.3, 1.0) * speed
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(ang) * spd, math.sin(ang) * spd
        self.life = self.max_life = random.randint(life // 2, life)
        self.color = color
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.95
        self.vy *= 0.95
        self.life -= 1

    def draw(self, surf):
        k = self.life / self.max_life
        r = max(1, int(self.size * k + 0.5))
        c = tuple(int(ch * (0.4 + 0.6 * k)) for ch in self.color)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), r)


class Ring:
    """폭발 시 퍼져 나가는 충격파 고리"""

    def __init__(self, x, y, max_r, color, life=20):
        self.x, self.y, self.max_r, self.color = x, y, max_r, color
        self.life = self.max_life = life

    def update(self):
        self.life -= 1

    def draw(self, surf):
        k = 1 - self.life / self.max_life
        r = int(self.max_r * k) + 1
        width = max(1, int(4 * (1 - k)))
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r, width)


# ---------------------------------------------------------------------------
# 플레이어 기체: 루멘-7
# ---------------------------------------------------------------------------
class Player:
    # 파워 단계별 동시 발사 탄 수: 2 → 4 → 8 → 16
    SHOT_COUNTS = (2, 4, 8, 16)
    # 단계별 부채꼴 전체 각도(라디안). 1단계는 평행 2연발
    SHOT_SPREADS = (0.0, 0.22, 0.55, 1.1)
    MAX_POWER = len(SHOT_COUNTS)

    def __init__(self):
        self.reset_position()
        self.speed = 5
        self.radius = 6  # 피격 판정은 기체보다 작게
        self.cooldown = 0
        self.power = 1
        self.lives = 3
        self.invul = 120  # 등장 직후 무적 프레임
        self.shield = 0
        self.t = 0

    def reset_position(self):
        self.x, self.y = WIDTH / 2, HEIGHT - 90

    def update(self, dx, dy):
        self.t += 1
        # 대각선 이동 시 속도 보정
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071
        self.x = clamp(self.x + dx * self.speed, 16, WIDTH - 16)
        self.y = clamp(self.y + dy * self.speed, 40, HEIGHT - 20)
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.invul > 0:
            self.invul -= 1
        if self.shield > 0:
            self.shield -= 1

    def shoot(self):
        """파워 단계에 따라 2/4/8/16발을 부채꼴로 동시 발사"""
        if self.cooldown > 0:
            return []
        self.cooldown = 8
        n = self.SHOT_COUNTS[self.power - 1]
        spread = self.SHOT_SPREADS[self.power - 1]
        shots = []
        for i in range(n):
            k = (i - (n - 1) / 2) / ((n - 1) / 2)  # 탄의 상대 위치 -1 ~ 1
            a = -math.pi / 2 + k * spread / 2
            col = CYAN if abs(k) < 0.5 else GREEN
            shots.append(Bullet(self.x + k * 8, self.y - 16 + abs(k) * 6,
                                math.cos(a) * 12, math.sin(a) * 12, 3, col))
        return shots

    def draw(self, surf):
        # 무적 시간에는 깜빡임
        if self.invul > 0 and (self.invul // 4) % 2 == 0:
            return
        x, y = self.x, self.y
        # 엔진 불꽃
        flame = 8 + (self.t % 6)
        pygame.draw.polygon(surf, ORANGE, [(x - 5, y + 12), (x + 5, y + 12), (x, y + 12 + flame)])
        pygame.draw.polygon(surf, YELLOW, [(x - 2, y + 12), (x + 2, y + 12), (x, y + 8 + flame * 0.6)])
        # 날개(초승달 모양의 두 갈래)
        pygame.draw.polygon(surf, (60, 110, 180), [(x, y - 4), (x - 20, y + 10), (x - 14, y + 14), (x - 4, y + 8)])
        pygame.draw.polygon(surf, (60, 110, 180), [(x, y - 4), (x + 20, y + 10), (x + 14, y + 14), (x + 4, y + 8)])
        # 동체
        pygame.draw.polygon(surf, (200, 220, 240), [(x, y - 20), (x - 7, y + 4), (x - 4, y + 13), (x + 4, y + 13), (x + 7, y + 4)])
        pygame.draw.polygon(surf, CYAN, [(x, y - 12), (x - 3, y - 2), (x + 3, y - 2)])
        # 보호막
        if self.shield > 0:
            k = 0.5 + 0.5 * math.sin(self.t * 0.3)
            col = (int(80 + 100 * k), int(200 + 40 * k), 255)
            pygame.draw.circle(surf, col, (int(x), int(y)), 26, 2)


# ---------------------------------------------------------------------------
# 적 기체들
# ---------------------------------------------------------------------------
class Enemy:
    radius = 12
    hp = 1
    score = 100
    drop_chance = 0.08

    def __init__(self, x, y, stage):
        self.x, self.y = x, y
        self.stage = stage
        self.hp = type(self).hp + (stage - 1) // 2
        self.t = 0
        self.flash = 0
        self.alive = True

    def bullet_speed(self):
        return 3.0 + 0.35 * (self.stage - 1)

    def update(self, game):
        self.t += 1
        if self.flash > 0:
            self.flash -= 1
        self.move(game)
        if self.y > HEIGHT + 60 or self.y < -200 or self.x < -100 or self.x > WIDTH + 100:
            self.alive = False

    def move(self, game):
        pass

    def body_color(self, base):
        # 피격 직후에는 흰색으로 번쩍임
        return WHITE if self.flash > 0 else base


class Dart(Enemy):
    """다트: 빠르게 내리꽂히는 소형 돌격기"""
    radius = 10
    hp = 1
    score = 100

    def __init__(self, x, y, stage, target_x):
        super().__init__(x, y, stage)
        self.vy = 4 + 0.3 * stage
        self.vx = clamp((target_x - x) / 120, -2, 2)

    def move(self, game):
        self.x += self.vx
        self.y += self.vy

    def draw(self, surf):
        x, y = self.x, self.y
        c = self.body_color(ORANGE)
        pygame.draw.polygon(surf, c, [(x, y + 12), (x - 10, y - 8), (x, y - 3), (x + 10, y - 8)])
        pygame.draw.circle(surf, RED, (int(x), int(y)), 3)


class Weaver(Enemy):
    """위버: 사인 곡선을 그리며 내려오고 조준탄을 쏘는 기체"""
    radius = 13
    hp = 2
    score = 150

    def __init__(self, x, y, stage):
        super().__init__(x, y, stage)
        self.base_x = x
        self.amp = random.uniform(40, 90)
        self.phase = random.uniform(0, math.tau)
        self.fire_delay = random.randint(40, 90)

    def move(self, game):
        self.y += 2.0
        self.x = self.base_x + math.sin(self.t * 0.045 + self.phase) * self.amp
        self.fire_delay -= 1
        if self.fire_delay <= 0 and 0 < self.y < HEIGHT * 0.65:
            self.fire_delay = max(45, 100 - self.stage * 8)
            vx, vy = aim(self.x, self.y, game.player.x, game.player.y, self.bullet_speed())
            game.enemy_bullets.append(Bullet(self.x, self.y + 8, vx, vy, 5, TEAL))

    def draw(self, surf):
        x, y = self.x, self.y
        c = self.body_color(TEAL)
        pygame.draw.polygon(surf, c, [(x, y - 12), (x + 8, y), (x, y + 12), (x - 8, y)])
        pygame.draw.polygon(surf, (40, 120, 110), [(x - 8, y), (x - 18, y - 6), (x - 14, y + 6)])
        pygame.draw.polygon(surf, (40, 120, 110), [(x + 8, y), (x + 18, y - 6), (x + 14, y + 6)])
        pygame.draw.circle(surf, WHITE, (int(x), int(y)), 3)


class Bastion(Enemy):
    """바스티온: 지형과 함께 흘러가는 지상 포대. 포신이 플레이어를 따라 돈다"""
    radius = 16
    hp = 5
    score = 250
    drop_chance = 0.25

    def __init__(self, x, y, stage):
        super().__init__(x, y, stage)
        self.fire_delay = random.randint(50, 90)
        self.angle = math.pi / 2

    def move(self, game):
        self.y += TERRAIN_SPEED
        self.angle = math.atan2(game.player.y - self.y, game.player.x - self.x)
        self.fire_delay -= 1
        if self.fire_delay <= 0 and 0 < self.y < HEIGHT - 120:
            self.fire_delay = max(40, 80 - self.stage * 6)
            spd = self.bullet_speed() * 0.9
            for off in ((0,) if self.stage < 3 else (-0.18, 0.18)):
                a = self.angle + off
                game.enemy_bullets.append(Bullet(self.x + math.cos(a) * 20, self.y + math.sin(a) * 20,
                                                 math.cos(a) * spd, math.sin(a) * spd, 5, ORANGE))

    def draw(self, surf):
        x, y = self.x, self.y
        c = self.body_color((90, 100, 120))
        pts = [(x + math.cos(i / 8 * math.tau + math.pi / 8) * 17, y + math.sin(i / 8 * math.tau + math.pi / 8) * 17) for i in range(8)]
        pygame.draw.polygon(surf, c, pts)
        pygame.draw.polygon(surf, (160, 170, 190), pts, 2)
        ex, ey = x + math.cos(self.angle) * 20, y + math.sin(self.angle) * 20
        pygame.draw.line(surf, (200, 210, 225), (x, y), (ex, ey), 5)
        pygame.draw.circle(surf, RED if self.fire_delay < 15 else ORANGE, (int(x), int(y)), 6)


class Orbiter(Enemy):
    """오비터: 내려와 멈춘 뒤 원형 탄막을 뿌리고 떠나는 중형기"""
    radius = 18
    hp = 7
    score = 300
    drop_chance = 0.3

    def __init__(self, x, y, stage):
        super().__init__(x, y, stage)
        self.target_y = random.uniform(90, 260)
        self.state = "enter"
        self.timer = 0
        self.vy = 0

    def move(self, game):
        if self.state == "enter":
            self.y += (self.target_y - self.y) * 0.04 + 0.3
            if self.y >= self.target_y - 2:
                self.state, self.timer = "hold", 0
        elif self.state == "hold":
            self.timer += 1
            if self.timer % 60 == 30:
                n = 8 + min(self.stage, 6) * 2
                base = self.t * 0.07
                for i in range(n):
                    a = base + i / n * math.tau
                    spd = self.bullet_speed() * 0.8
                    game.enemy_bullets.append(Bullet(self.x, self.y, math.cos(a) * spd, math.sin(a) * spd, 4, PURPLE))
            if self.timer > 200:
                self.state = "leave"
        else:
            self.vy += 0.12
            self.y += self.vy

    def draw(self, surf):
        x, y = self.x, self.y
        c = self.body_color(PURPLE)
        for i in range(6):
            a = self.t * 0.05 + i / 6 * math.tau
            pygame.draw.line(surf, (120, 80, 200), (x, y), (x + math.cos(a) * 22, y + math.sin(a) * 22), 3)
        pygame.draw.circle(surf, c, (int(x), int(y)), 14)
        pygame.draw.circle(surf, (60, 30, 110), (int(x), int(y)), 8)
        pygame.draw.circle(surf, MAGENTA, (int(x), int(y)), 4)


class Boss(Enemy):
    """보스: 할시온 워든 - 육각 동체와 양쪽 포드를 가진 거대 요새"""
    radius = 48
    hp = 0
    score = 5000
    drop_chance = 1.0

    def __init__(self, stage):
        super().__init__(WIDTH / 2, -120, stage)
        self.max_hp = 160 + 70 * (stage - 1)
        self.hp = self.max_hp
        self.state = "enter"
        self.pattern_t = 0
        self.spiral = 0.0

    def move(self, game):
        if self.state == "enter":
            self.y += 1.5
            if self.y >= 140:
                self.state = "fight"
            return
        enraged = self.hp < self.max_hp / 2
        # 좌우로 천천히 흔들리며 이동
        self.x = WIDTH / 2 + math.sin(self.t * (0.018 if not enraged else 0.028)) * 150
        self.y = 140 + math.sin(self.t * 0.031) * 25
        self.pattern_t += 1
        cycle = self.pattern_t % 600
        spd = self.bullet_speed()
        bullets = game.enemy_bullets
        if cycle < 200:
            # 패턴 1: 회전 나선탄
            if self.pattern_t % (6 if not enraged else 4) == 0:
                self.spiral += 0.32
                for k in range(2 if not enraged else 3):
                    a = self.spiral + k * math.tau / (2 if not enraged else 3)
                    bullets.append(Bullet(self.x, self.y + 10, math.cos(a) * spd * 0.8, math.sin(a) * spd * 0.8, 5, MAGENTA))
        elif cycle < 400:
            # 패턴 2: 양쪽 포드에서 부채꼴 조준탄
            if self.pattern_t % (40 if not enraged else 28) == 0:
                for px in (self.x - 60, self.x + 60):
                    base = math.atan2(game.player.y - self.y, game.player.x - px)
                    for off in (-0.3, -0.15, 0, 0.15, 0.3):
                        a = base + off
                        bullets.append(Bullet(px, self.y + 20, math.cos(a) * spd, math.sin(a) * spd, 5, ORANGE))
        else:
            # 패턴 3: 원형 탄막 링
            if self.pattern_t % (50 if not enraged else 35) == 0:
                n = 20 + self.stage * 2
                off = random.uniform(0, math.tau)
                for i in range(n):
                    a = off + i / n * math.tau
                    bullets.append(Bullet(self.x, self.y, math.cos(a) * spd * 0.7, math.sin(a) * spd * 0.7, 6, RED))

    def update(self, game):
        # 보스는 화면 밖 판정으로 사라지지 않도록 별도 처리
        self.t += 1
        if self.flash > 0:
            self.flash -= 1
        self.move(game)

    def draw(self, surf):
        x, y = self.x, self.y
        body = self.body_color((70, 60, 110))
        # 양쪽 포드
        for side in (-1, 1):
            px = x + side * 60
            pygame.draw.polygon(surf, self.body_color((90, 80, 140)),
                                [(px - 16, y - 10), (px + 16, y - 10), (px + 12, y + 26), (px - 12, y + 26)])
            pygame.draw.line(surf, GREY, (x + side * 30, y), (px, y), 6)
            pygame.draw.circle(surf, ORANGE, (int(px), int(y + 18)), 5)
        # 육각 동체
        hexa = [(x + math.cos(i / 6 * math.tau) * 46, y + math.sin(i / 6 * math.tau) * 40) for i in range(6)]
        pygame.draw.polygon(surf, body, hexa)
        pygame.draw.polygon(surf, (170, 150, 230), hexa, 3)
        # 회전하는 왕관 장식
        for i in range(5):
            a = self.t * 0.03 + i / 5 * math.tau
            pygame.draw.circle(surf, (150, 130, 220), (int(x + math.cos(a) * 30), int(y + math.sin(a) * 26)), 4)
        # 맥동하는 코어 (체력이 낮으면 붉게)
        pulse = 0.5 + 0.5 * math.sin(self.t * 0.15)
        core = MAGENTA if self.hp >= self.max_hp / 2 else RED
        pygame.draw.circle(surf, core, (int(x), int(y)), int(14 + pulse * 4))
        pygame.draw.circle(surf, WHITE, (int(x), int(y)), 6)


# ---------------------------------------------------------------------------
# 파워업 아이템
# ---------------------------------------------------------------------------
class PowerUp:
    # P: 무기 강화, S: 보호막, L: 목숨 +1
    COLORS = {"P": YELLOW, "S": CYAN, "L": GREEN}

    def __init__(self, x, y, kind):
        self.x, self.y, self.kind = x, y, kind
        self.radius = 11
        self.t = 0
        self.alive = True

    def update(self):
        self.t += 1
        self.y += 1.4
        self.x += math.sin(self.t * 0.08) * 0.8
        if self.y > HEIGHT + 20:
            self.alive = False

    def draw(self, surf, font):
        col = self.COLORS[self.kind]
        r = self.radius + int(math.sin(self.t * 0.2) * 2)
        pygame.draw.circle(surf, (20, 30, 50), (int(self.x), int(self.y)), r)
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)), r, 2)
        txt = font.render(self.kind, True, col)
        surf.blit(txt, txt.get_rect(center=(int(self.x), int(self.y) + 1)))


# ---------------------------------------------------------------------------
# 게임 전체 상태 관리
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.font_small = pygame.font.Font(None, 22)
        self.font = pygame.font.Font(None, 30)
        self.font_big = pygame.font.Font(None, 64)
        self.hi_score = 0
        self.sfx = Sfx()
        self.state = "title"  # title / play / pause / over
        self.reset()

    def reset(self):
        """새 게임 시작 시 모든 상태 초기화"""
        self.bg = Background()
        self.player = Player()
        self.player_bullets = []
        self.enemy_bullets = []
        self.enemies = []
        self.powerups = []
        self.particles = []
        self.rings = []
        self.boss = None
        self.score = 0
        self.stage = 1
        self.next_boss_score = 3000
        self.spawn_timer = 60
        self.frame = 0
        self.shake = 0
        self.banner = ("STAGE 1", 150)
        self.over_timer = 0

    # ----- 생성 -----
    def spawn_enemy(self):
        s = self.stage
        roll = random.random()
        x = random.uniform(30, WIDTH - 30)
        if roll < 0.40:
            # 다트는 편대로 등장
            for i in range(random.randint(2, 3 + min(s, 3))):
                self.enemies.append(Dart(clamp(x + (i - 1) * 28, 20, WIDTH - 20), -20 - i * 30, s, self.player.x))
        elif roll < 0.70:
            for i in range(random.randint(2, 4)):
                self.enemies.append(Weaver(clamp(x, 90, WIDTH - 90), -20 - i * 45, s))
        elif roll < 0.88:
            self.enemies.append(Bastion(x, -30, s))
        else:
            self.enemies.append(Orbiter(clamp(x, 60, WIDTH - 60), -30, s))

    def explode(self, x, y, size=1.0, color=ORANGE):
        """폭발 효과: 파티클 + 충격파"""
        for _ in range(int(14 * size)):
            self.particles.append(Particle(x, y, random.choice((color, YELLOW, WHITE)), 3.5 * size, int(35 * min(size, 2)), 3))
        self.rings.append(Ring(x, y, 26 * size, color, int(18 + 6 * size)))

    def drop_powerup(self, x, y):
        kind = random.choices(("P", "S", "L"), weights=(60, 30, 10))[0]
        self.powerups.append(PowerUp(x, y, kind))

    # ----- 피격 처리 -----
    def kill_enemy(self, e):
        e.alive = False
        self.score += e.score
        if isinstance(e, Boss):
            self.sfx.play("big_explode")
            for _ in range(6):
                self.explode(e.x + random.uniform(-50, 50), e.y + random.uniform(-40, 40), 2.2, MAGENTA)
            self.shake = 40
            self.enemy_bullets.clear()
            self.drop_powerup(e.x - 30, e.y)
            self.powerups.append(PowerUp(e.x + 30, e.y, "L"))
            self.boss = None
            self.stage += 1
            self.next_boss_score = self.score + 3000 + self.stage * 1000
            self.banner = (f"STAGE {self.stage}", 150)
        else:
            self.sfx.play("explode")
            self.explode(e.x, e.y, 1.0 if e.radius < 15 else 1.6)
            if random.random() < e.drop_chance:
                self.drop_powerup(e.x, e.y)

    def hit_player(self):
        p = self.player
        if p.invul > 0:
            return
        if p.shield > 0:
            # 보호막이 대신 맞고 사라짐
            p.shield = 0
            p.invul = 60
            self.sfx.play("shield")
            self.rings.append(Ring(p.x, p.y, 40, CYAN, 20))
            return
        self.sfx.play("player_hit")
        self.explode(p.x, p.y, 2.0, CYAN)
        self.shake = 20
        p.lives -= 1
        p.power = max(1, p.power - 1)
        self.enemy_bullets.clear()
        if p.lives <= 0:
            self.state = "over"
            self.over_timer = 0
            self.hi_score = max(self.hi_score, self.score)
        else:
            p.reset_position()
            p.invul = 150

    # ----- 매 프레임 갱신 -----
    def update(self, dx, dy, fire):
        self.frame += 1
        self.bg.update()

        if self.state == "over":
            self.over_timer += 1
            self._update_effects()
            return

        p = self.player
        p.update(dx, dy)
        if fire:
            shots = p.shoot()
            if shots:
                self.player_bullets.extend(shots)
                self.sfx.play("shoot")

        # 보스 등장 조건
        if self.boss is None and self.score >= self.next_boss_score:
            self.boss = Boss(self.stage)
            self.enemies.append(self.boss)
            self.banner = ("WARNING: HALCYON WARDEN", 150)
            self.sfx.play("warning")

        # 일반 적 생성 (보스전 중에는 드물게)
        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.spawn_enemy()
            base = max(35, 95 - self.stage * 10)
            self.spawn_timer = base * (3 if self.boss else 1) + random.randint(0, 30)

        for b in self.player_bullets:
            b.update()
        for b in self.enemy_bullets:
            b.update()
        for e in self.enemies:
            e.update(self)
        for pu in self.powerups:
            pu.update()

        # 아군 탄 vs 적
        for b in self.player_bullets:
            if not b.alive:
                continue
            for e in self.enemies:
                if e.alive and e.y > -10 and circle_hit(b.x, b.y, b.radius, e.x, e.y, e.radius):
                    b.alive = False
                    e.hp -= b.damage
                    e.flash = 3
                    self.particles.append(Particle(b.x, b.y, YELLOW, 2, 10, 2))
                    if e.hp <= 0:
                        self.kill_enemy(e)
                    break

        # 적 탄 / 적 몸체 vs 플레이어
        for b in self.enemy_bullets:
            if b.alive and circle_hit(b.x, b.y, b.radius - 1, p.x, p.y, p.radius):
                b.alive = False
                self.hit_player()
                break
        if self.state == "play":
            for e in self.enemies:
                if e.alive and circle_hit(e.x, e.y, e.radius * 0.8, p.x, p.y, p.radius):
                    if not isinstance(e, Boss) and p.invul == 0:
                        e.hp = 0
                        self.kill_enemy(e)
                    self.hit_player()
                    break

        # 파워업 획득
        if self.state == "play":
            for pu in self.powerups:
                if circle_hit(pu.x, pu.y, pu.radius, p.x, p.y, 16):
                    pu.alive = False
                    self.sfx.play("powerup")
                    if pu.kind == "P":
                        if p.power < Player.MAX_POWER:
                            p.power += 1
                        else:
                            self.score += 500
                    elif pu.kind == "S":
                        p.shield = 600
                    else:
                        p.lives = min(p.lives + 1, 9)
                    self.rings.append(Ring(pu.x, pu.y, 30, PowerUp.COLORS[pu.kind], 15))

        self.player_bullets = [b for b in self.player_bullets if b.alive]
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive]
        self.enemies = [e for e in self.enemies if e.alive]
        self.powerups = [pu for pu in self.powerups if pu.alive]
        self._update_effects()
        self.hi_score = max(self.hi_score, self.score)

    def _update_effects(self):
        for fx in self.particles:
            fx.update()
        for r in self.rings:
            r.update()
        self.particles = [fx for fx in self.particles if fx.life > 0]
        self.rings = [r for r in self.rings if r.life > 0]
        if self.shake > 0:
            self.shake -= 1
        if self.banner and self.banner[1] > 0:
            self.banner = (self.banner[0], self.banner[1] - 1)

    # ----- 그리기 -----
    def draw_text(self, surf, text, font, color, center=None, topleft=None, topright=None):
        img = font.render(text, True, color)
        rect = img.get_rect()
        if center:
            rect.center = center
        elif topleft:
            rect.topleft = topleft
        elif topright:
            rect.topright = topright
        surf.blit(img, rect)

    def draw_hud(self, surf):
        p = self.player
        self.draw_text(surf, f"SCORE {self.score:07d}", self.font, WHITE, topleft=(10, 8))
        self.draw_text(surf, f"HI {self.hi_score:07d}", self.font_small, GREY, topleft=(12, 34))
        self.draw_text(surf, f"STAGE {self.stage}", self.font, YELLOW, topright=(WIDTH - 10, 8))
        # 목숨: 작은 기체 아이콘
        for i in range(p.lives):
            x, y = WIDTH - 18 - i * 18, 44
            pygame.draw.polygon(surf, CYAN, [(x, y - 7), (x - 6, y + 6), (x + 6, y + 6)])
        # 파워 게이지
        self.draw_text(surf, "PWR", self.font_small, GREY, topleft=(10, HEIGHT - 22))
        for i in range(Player.MAX_POWER):
            col = YELLOW if i < p.power else (50, 55, 70)
            pygame.draw.rect(surf, col, (48 + i * 16, HEIGHT - 20, 12, 10))
        self.draw_text(surf, f"x{Player.SHOT_COUNTS[p.power - 1]}", self.font_small, YELLOW, topleft=(118, HEIGHT - 22))
        if p.shield > 0:
            self.draw_text(surf, f"SHIELD {p.shield // FPS + 1}", self.font_small, CYAN, topleft=(165, HEIGHT - 22))
        if self.sfx.muted:
            self.draw_text(surf, "MUTE", self.font_small, GREY, topright=(WIDTH - 10, HEIGHT - 22))
        # 보스 체력 바
        if self.boss:
            w = WIDTH - 40
            k = max(0, self.boss.hp) / self.boss.max_hp
            pygame.draw.rect(surf, (60, 20, 40), (20, 64, w, 8))
            pygame.draw.rect(surf, MAGENTA, (20, 64, int(w * k), 8))
            pygame.draw.rect(surf, WHITE, (20, 64, w, 8), 1)

    def draw(self, screen):
        surf = pygame.Surface((WIDTH, HEIGHT))
        self.bg.draw(surf)

        if self.state != "title":
            for e in self.enemies:
                e.draw(surf)
            for pu in self.powerups:
                pu.draw(surf, self.font_small)
            for b in self.player_bullets:
                b.draw_player(surf)
            if self.state != "over":
                self.player.draw(surf)
            for r in self.rings:
                r.draw(surf)
            for fx in self.particles:
                fx.draw(surf)
            for b in self.enemy_bullets:
                b.draw_enemy(surf)
            self.draw_hud(surf)

            # 배너: 처음엔 고정 표시, 끝무렵엔 깜빡이며 사라짐
            text, timer = self.banner
            if timer > 60 or (timer > 0 and (timer // 10) % 2 == 0):
                self.draw_text(surf, text, self.font, YELLOW, center=(WIDTH / 2, HEIGHT / 2 - 60))

        if self.state == "title":
            self.draw_text(surf, TITLE, self.font_big, CYAN, center=(WIDTH / 2, HEIGHT / 2 - 90))
            self.draw_text(surf, "Pilot the LUMEN-7 through the drift", self.font_small, GREY, center=(WIDTH / 2, HEIGHT / 2 - 45))
            if (self.frame // 30) % 2 == 0:
                self.draw_text(surf, "PRESS SPACE TO START", self.font, WHITE, center=(WIDTH / 2, HEIGHT / 2 + 20))
            for i, line in enumerate(["ARROWS / WASD : MOVE", "SPACE : FIRE", "P : PAUSE    R : RESTART", "M : SOUND    ESC : QUIT",
                                      "P = SHOTS x2/x4/x8/x16", "S = SHIELD   L = LIFE"]):
                self.draw_text(surf, line, self.font_small, GREY, center=(WIDTH / 2, HEIGHT / 2 + 80 + i * 24))
        elif self.state == "pause":
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 140))
            surf.blit(shade, (0, 0))
            self.draw_text(surf, "PAUSED", self.font_big, WHITE, center=(WIDTH / 2, HEIGHT / 2 - 20))
            self.draw_text(surf, "PRESS P TO RESUME", self.font_small, GREY, center=(WIDTH / 2, HEIGHT / 2 + 25))
        elif self.state == "over":
            self.draw_text(surf, "GAME OVER", self.font_big, RED, center=(WIDTH / 2, HEIGHT / 2 - 40))
            self.draw_text(surf, f"SCORE {self.score}", self.font, WHITE, center=(WIDTH / 2, HEIGHT / 2 + 10))
            if self.over_timer > 40:
                self.draw_text(surf, "PRESS R TO RESTART", self.font, YELLOW, center=(WIDTH / 2, HEIGHT / 2 + 50))

        # 화면 흔들림
        ox = oy = 0
        if self.shake > 0:
            ox, oy = random.randint(-4, 4), random.randint(-4, 4)
        screen.fill(BLACK)
        screen.blit(surf, (ox, oy))


# ---------------------------------------------------------------------------
# 메인 루프
# ---------------------------------------------------------------------------
def read_input():
    """현재 눌린 키에서 이동 방향과 사격 여부를 읽음"""
    keys = pygame.key.get_pressed()
    dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
    dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
    return dx, dy, bool(keys[pygame.K_SPACE])


def main():
    # 효과음 합성 형식(22050Hz, 16비트, 모노)을 init 전에 지정
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()
    game = Game()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif game.state == "title" and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    game.reset()
                    game.state = "play"
                elif event.key == pygame.K_m:
                    game.sfx.toggle_mute()
                elif event.key == pygame.K_p and game.state in ("play", "pause"):
                    game.state = "pause" if game.state == "play" else "play"
                elif event.key == pygame.K_r and game.state in ("play", "pause", "over"):
                    game.reset()
                    game.state = "play"

        if game.state == "play" or game.state == "over":
            game.update(*read_input())
        elif game.state == "title":
            game.frame += 1
            game.bg.update()

        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
