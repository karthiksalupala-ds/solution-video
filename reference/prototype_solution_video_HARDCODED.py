import math, random, subprocess, sys, wave, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, S, FPS = 720, 1280, 2, 30
FD = "/usr/share/fonts/truetype/google-fonts/"
BG1, BG2 = (12, 16, 40), (40, 18, 78)
ACCENT, GREEN, WHITE, GREY = (255, 196, 0), (60, 220, 130), (255, 255, 255), (165, 175, 215)
BLUE, ORANGE = (50, 110, 230), (230, 130, 40)

SS = [0, 2.8, 6.0, 11.2, 14.4, 18.2, 22.0, 25.8]   # scene start times
TOTAL = 28.8
TR = 0.35  # crossfade

# ---------------------------------------------------------------- helpers
_fc = {}
def font(sz, bold=True):
    k = (int(sz), bold)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FD + ("Poppins-Bold.ttf" if bold else "Poppins-Medium.ttf"), max(2, int(sz * S)))
    return _fc[k]

def lerp(a, b, t): return a + (b - a) * t
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, t0, dur): return clamp((t - t0) / dur)
def e_out(p): return 1 - (1 - p) ** 3
def e_io(p): return p * p * (3 - 2 * p)
def e_back(p):
    if p <= 0: return 0
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
def mix(c1, c2, t): return tuple(int(lerp(c1[i], c2[i], clamp(t))) for i in range(3))
def bgcol(y): return mix(BG1, BG2, y / H)

def T(d, x, y, s, size, col, anchor="la", a=1.0, bold=True):
    if a <= 0.02 or size < 2: return
    d.text((x * S, y * S), s, font=font(size, bold), fill=mix(bgcol(y), col, a), anchor=anchor)

def RR(d, x0, y0, x1, y1, r, fill, outline=None, w=1, a=1.0):
    if a <= 0.02: return
    bc = bgcol((y0 + y1) / 2)
    d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], max(0, r * S),
                        fill=mix(bc, fill, a) if fill else None,
                        outline=mix(bc, outline, a) if outline else None, width=int(w * S))

def EL(d, cx, cy, r, fill, a=1.0):
    if a <= 0.02 or r <= 0: return
    d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=mix(bgcol(cy), fill, a))

def LN(d, pts, col, w, a=1.0):
    d.line([(x * S, y * S) for x, y in pts], fill=mix(bgcol(pts[0][1]), col, a), width=int(w * S), joint="curve")

def wrap(s, size, maxw, bold=True):
    f = font(size, bold); lines, cur = [], ""
    for w in s.split():
        tt = (cur + " " + w).strip()
        if f.getlength(tt) / S <= maxw: cur = tt
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

# ---------------------------------------------------------------- base layers
BASE = CITY = STARS = None
def init():
    global BASE, CITY, STARS
    arr = np.zeros((H * S, W * S, 3), np.uint8)
    t = np.linspace(0, 1, H * S)[:, None]
    for i in range(3):
        arr[:, :, i] = (BG1[i] + (BG2[i] - BG1[i]) * t).astype(np.uint8)
    BASE = Image.fromarray(arr)
    rnd = random.Random(5)
    STARS = [(rnd.uniform(0, W), rnd.uniform(240, 860), rnd.uniform(0, 6.28), rnd.uniform(1, 2.2)) for _ in range(70)]
    tile = Image.new("RGBA", (W * S, 260 * S), (0, 0, 0, 0)); cd = ImageDraw.Draw(tile)
    x = 0
    while x < W:
        bw = rnd.randint(50, 110); bh = rnd.randint(60, 200); x1 = min(W, x + bw)
        cd.rectangle([x * S, (260 - bh) * S, x1 * S, 260 * S], fill=(26, 28, 66, 255))
        for wy in range(260 - bh + 12, 250, 22):
            for wx in range(x + 8, x1 - 12, 20):
                if rnd.random() < 0.35:
                    cd.rectangle([wx * S, wy * S, (wx + 8) * S, (wy + 10) * S], fill=(255, 210, 110, 150))
        x += bw + rnd.randint(0, 6)
    CITY = Image.new("RGBA", (2 * W * S, 260 * S), (0, 0, 0, 0))
    CITY.paste(tile, (0, 0)); CITY.paste(tile, (W * S, 0))

def base(t, day=10):
    img = BASE.copy(); d = ImageDraw.Draw(img)
    for (x, y, ph, r) in STARS:
        a = 0.3 + 0.3 * math.sin(t * 2 + ph)
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=mix(bgcol(y), (255, 255, 255), a))
    off = (t * 18) % W
    city = CITY.crop((int(off * S), 0, int((off + W) * S), 260 * S))
    img.paste(city, (0, (1090 - 260) * S), city)
    d.rectangle([0, 1090 * S, W * S, 1098 * S], fill=(75, 82, 130))
    d.rectangle([0, 1098 * S, W * S, 1136 * S], fill=(20, 22, 50))
    for sx in range(-28, W + 28, 28):
        xx = sx - (t * 60) % 28
        d.rectangle([xx * S, 1100 * S, (xx + 12) * S, 1106 * S], fill=(34, 36, 70))
    RR(d, 28, 36, 208, 84, 24, ACCENT)
    T(d, 118, 60, f"DAY {day}/100", 26, (20, 20, 40), "mm")
    RR(d, 28, 102, 692, 112, 5, (58, 62, 110))
    RR(d, 28, 102, 28 + 664 * day / 100, 112, 5, GREEN)
    T(d, 360, 1262, "Aptitude Daily  |  AVN 2028 T&P", 20, GREY, "mm", 1.0, False)
    return img, d

def caption(d, txt, lt):
    a = e_out(prog(lt, 0.3, 0.4))
    RR(d, 30, 1148, 690, 1232, 22, (30, 34, 84), (70, 80, 150), 2, a)
    lines = wrap(txt, 25, 610, False)
    y = 1190 - (len(lines) - 1) * 17
    for ln in lines:
        T(d, 360, y, ln, 25, WHITE, "mm", a, False); y += 34

# ---------------------------------------------------------------- train
def train(d, fx, t, u=1.45, lines=True, label=False):
    L = 150 * u; rx = fx - L; yt, yb = 972, 1066
    body, dark = (70, 140, 255), (40, 90, 200)
    if lines:
        rnd = random.Random(int(t * 30) // 2)
        for i in range(7):
            yy = yt + 10 + i * 13; ln = rnd.uniform(40, 130)
            LN(d, [(rx - ln - 12, yy), (rx - 12, yy)], (190, 205, 255), 2, 0.45)
    RR(d, rx, yt, fx - 36, yb, 12, body)
    d.polygon([((fx - 50) * S, yt * S), ((fx - 16) * S, (yt + 24) * S), (fx * S, (yb - 8) * S), ((fx - 50) * S, yb * S)],
              fill=body)
    d.rectangle([rx * S, (yt + 62) * S, (fx - 24) * S, (yt + 74) * S], fill=ACCENT)
    n = int((L - 70) // 34)
    for i in range(n):
        wx = rx + 14 + i * 34
        RR(d, wx, yt + 14, wx + 22, yt + 46, 5, (215, 238, 255))
    RR(d, fx - 40, yt + 14, fx - 14, yt + 44, 5, (215, 238, 255))
    EL(d, fx - 5, yb - 22, 6, (255, 242, 150))
    d.polygon([((fx) * S, (yb - 26) * S), ((fx + 70) * S, (yb - 8) * S), (fx * S, (yb - 2) * S)],
              fill=mix(bgcol(yb), (255, 235, 140), 0.18))
    for wf in (0.14, 0.3, 0.7, 0.86):
        wx = rx + L * wf; ang = fx / 13.0
        EL(d, wx, 1077, 13, (28, 30, 52))
        EL(d, wx, 1077, 5, (150, 160, 200))
        LN(d, [(wx + 11 * math.cos(ang), 1077 + 11 * math.sin(ang)), (wx - 11 * math.cos(ang), 1077 - 11 * math.sin(ang))], (150, 160, 200), 2)
    if label:
        cx = fx - L / 2
        RR(d, cx - 62, 936, cx + 62, 966, 14, dark)
        T(d, cx, 951, "TRAIN 150 m", 17, WHITE, "mm")

# ---------------------------------------------------------------- scenes
def title(d, s, lt):
    T(d, 360, 165, s, 32, ACCENT, "mm", e_out(prog(lt, 0, 0.4)))

def sA(d, lt, t):
    T(d, 60, 300, "TODAY'S TOPIC", 30, GREY, "la", e_out(prog(lt, 0.1, 0.4)))
    for i, (s, c) in enumerate([("Speed,", WHITE), ("Time &", WHITE), ("Distance", ACCENT)]):
        p = prog(lt, 0.3 + 0.25 * i, 0.5)
        T(d, 60 - 70 * (1 - e_out(p)), 370 + i * 118, s, 100, c, "la", p)
    p = prog(lt, 1.2, 0.4)
    RR(d, 60, 760, 440, 822, 30, GREEN, a=p)
    T(d, 250, 791, "Solve in 20 seconds", 26, (10, 30, 20), "mm", p)
    fx = lerp(-40, 1000, e_io(prog(lt, 0.2, 1.6)))
    train(d, fx, t)

Q = "A train 150 m long crosses a platform 250 m long in 20 seconds. What is the speed of the train in km/h?"
def sB(d, lt, t):
    T(d, 60, 165, "QUESTION", 30, ACCENT, "lm", e_out(prog(lt, 0, 0.3)))
    n = len(Q.split()); shown = int(prog(lt, 0.3, 1.2) * n + 0.999)
    idx, y = 0, 225
    for ln in wrap(Q, 38, 600):
        x = 60
        for w in ln.split():
            if idx < shown: T(d, x, y, w, 38, WHITE)
            x += font(38).getlength(w + " ") / S; idx += 1
        y += 56
    for i, (l, v) in enumerate([("A", "72"), ("B", "90"), ("C", "108"), ("D", "120")]):
        p = prog(lt, 1.5 + 0.3 * i, 0.4); xo = (1 - e_out(p)) * 220; y0 = 520 + i * 90
        RR(d, 60 + xo, y0, 660 + xo, y0 + 76, 20, (34, 40, 96), (80, 90, 170), 2, p)
        EL(d, 102 + xo, y0 + 38, 24, ACCENT, p); T(d, 102 + xo, y0 + 38, l, 28, (20, 20, 40), "mm", p)
        T(d, 150 + xo, y0 + 38, v + " km/h", 34, WHITE, "lm", p)

U = 1.45; PS = 180; PE = PS + 250 * U; LT = 150 * U
def sC(d, lt, t):
    title(d, "Train crossing a platform", lt)
    tn = prog(lt, 0.6, 3.6); e = 0.35 * tn + 0.65 * e_io(tn)
    fx = lerp(-20, PS + 400 * U + 40, e); rear = fx - LT
    pm = clamp((fx - PS) / U, 0, 400)
    T(d, 360, 300, "Distance covered", 28, GREY, "mm", e_out(prog(lt, 0.2, 0.4)), False)
    T(d, 360, 420, f"{int(pm)} m", 130, GREEN, "mm", e_out(prog(lt, 0.2, 0.4)))
    RR(d, 60, 520, 660, 542, 11, (50, 56, 110))
    if pm > 1: RR(d, 60, 520, 60 + 600 * pm / 400, 542, 11, GREEN)
    p = e_out(prog(lt, 0.4, 0.5))
    RR(d, 50, 610, 250, 666, 20, BLUE, a=p); T(d, 150, 638, "Train 150 m", 26, WHITE, "mm", p)
    T(d, 290, 638, "+", 44, WHITE, "mm", p)
    RR(d, 330, 610, 670, 666, 20, ORANGE, a=p); T(d, 500, 638, "Platform 250 m", 26, WHITE, "mm", p)
    s = e_back(prog(lt, 4.1, 0.5))
    if s > 0: T(d, 360, 760, "= 400 m total", int(48 * s), ACCENT, "mm", clamp(s))
    # platform
    active = (fx > PS) and (rear < PE)
    RR(d, PS, 1090, PE, 1135, 6, mix((95, 104, 160), (70, 190, 130), 1 if active else 0))
    d.rectangle([PS * S, 1090 * S, PE * S, 1096 * S], fill=ACCENT)
    T(d, (PS + PE) / 2, 1117, "PLATFORM 250 m", 19, WHITE, "mm")
    for lx in (PS + 28, PE - 28):
        LN(d, [(lx, 1090), (lx, 1030)], (120, 130, 180), 3); EL(d, lx, 1026, 8, (255, 225, 120))
    # markers
    f1 = GREEN if PS <= fx < PS + 70 else GREY
    f2 = GREEN if PE <= rear < PE + 70 else GREY
    for mx, col, lab in ((PS, f1, "FRONT ENTERS"), (PE, f2, "REAR LEAVES")):
        for yy in range(900, 1090, 16): LN(d, [(mx, yy), (mx, yy + 8)], col, 2)
        RR(d, mx - 68, 868, mx + 68, 896, 12, (30, 34, 84), col, 2); T(d, mx, 882, lab, 16, col, "mm")
    train(d, fx, t, label=True)

def card(d, x0, y0, x1, y1, col, label, val, p):
    if p <= 0.02: return
    s = e_back(p); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = (x1 - x0) / 2 * s, (y1 - y0) / 2 * s
    RR(d, cx - w, cy - h, cx + w, cy + h, 18 * s, col, a=clamp(p * 2))
    T(d, cx, cy - 22 * s, label, int(24 * s), (230, 240, 255), "mm", clamp(p * 2), False)
    T(d, cx, cy + 16 * s, val, int(54 * s), WHITE, "mm", clamp(p * 2))

def sD(d, lt, t):
    title(d, "STEP 1  -  Total distance", lt)
    card(d, 110, 290, 610, 390, BLUE, "Train length", "150 m", prog(lt, 0.3, 0.5))
    T(d, 360, 437, "+", 60, WHITE, "mm", e_out(prog(lt, 0.8, 0.3)))
    card(d, 110, 480, 610, 580, ORANGE, "Platform length", "250 m", prog(lt, 1.0, 0.5))
    pl = prog(lt, 1.7, 0.4)
    if pl > 0: LN(d, [(160, 635), (160 + 400 * e_out(pl), 635)], WHITE, 4)
    T(d, 360, 680, "Total distance", 28, GREY, "mm", e_out(prog(lt, 1.8, 0.3)), False)
    s = e_back(prog(lt, 2.0, 0.5))
    if s > 0: T(d, 360, 780, "400 m", int(120 * s), GREEN, "mm", clamp(s))

def sE(d, lt, t):
    title(d, "STEP 2  -  Speed", lt)
    T(d, 360, 285, "Speed = Distance / Time", 42, WHITE, "mm", e_out(prog(lt, 0.3, 0.4)))
    cx, cy, r = 360, 520, 118; a0 = prog(lt, 0.5, 0.3); pr = prog(lt, 0.8, 1.8)
    bb = [(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S]
    if a0 > 0.02:
        d.ellipse(bb, outline=mix(bgcol(cy), (60, 66, 120), a0), width=14 * S)
        if pr > 0.01: d.arc(bb, -90, -90 + 360 * pr, fill=GREEN, width=14 * S)
    T(d, cx, cy - 8, f"{int(round(20 * pr))}", 84, WHITE, "mm", a0)
    T(d, cx, cy + 58, "seconds", 22, GREY, "mm", a0, False)
    s = e_back(prog(lt, 2.8, 0.5))
    if s > 0: T(d, 360, 760, "400 / 20 = 20 m/s", int(54 * s), GREEN, "mm", clamp(s))

def sF(d, lt, t):
    title(d, "SHORTCUT TRICK", lt)
    T(d, 360, 290, "m/s  to  km/h", 54, WHITE, "mm", e_out(prog(lt, 0.3, 0.4)))
    card(d, 30, 460, 230, 640, (70, 80, 160), "speed", "20", prog(lt, 0.7, 0.5))
    T(d, 130, 612, "m/s", 22, GREY, "mm", e_out(prog(lt, 0.9, 0.3)), False)
    cp = e_back(prog(lt, 1.3, 0.5))
    if cp > 0:
        RR(d, 360 - 90 * cp, 500 - 0, 360 + 90 * cp, 600, 40, ACCENT, a=clamp(cp))
        T(d, 360, 550, "x 18/5", int(38 * cp), (30, 24, 0), "mm", clamp(cp))
        a = clamp(cp)
        d.polygon([(236 * S, 535 * S), (254 * S, 550 * S), (236 * S, 565 * S)], fill=mix(bgcol(550), WHITE, a))
        d.polygon([(466 * S, 535 * S), (484 * S, 550 * S), (466 * S, 565 * S)], fill=mix(bgcol(550), WHITE, a))
    rp = prog(lt, 1.8, 0.5)
    card(d, 490, 460, 690, 640, (30, 150, 100), "speed", str(int(lerp(20, 72, e_out(prog(lt, 1.9, 1.0))))), rp)
    T(d, 590, 612, "km/h", 22, WHITE, "mm", e_out(prog(lt, 2.0, 0.3)), False)
    s = e_back(prog(lt, 2.9, 0.5))
    if s > 0: T(d, 360, 770, "20 x 18/5 = 72", int(50 * s), GREEN, "mm", clamp(s))

def gpt(cx, cy, r, v):
    th = math.radians(180 - v / 140 * 180)
    return cx + r * math.cos(th), cy - r * math.sin(th)

_rc = random.Random(11)
CONF = [(_rc.uniform(-math.pi * 0.95, -math.pi * 0.05), _rc.uniform(200, 520),
         _rc.choice([ACCENT, GREEN, (255, 120, 160), (120, 190, 255), WHITE]), _rc.randint(6, 12)) for _ in range(60)]

def sG(d, lt, t):
    title(d, "ANSWER", lt)
    cx, cy, R = 360, 600, 235; a = e_out(prog(lt, 0.1, 0.4))
    bb = [(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S]
    d.arc(bb, 180, 360, fill=mix(bgcol(cy), (55, 60, 115), a), width=26 * S)
    vv = clamp(72 * e_back(prog(lt, 0.6, 1.5)), 0, 140)
    if vv > 0.5: d.arc(bb, 180, 180 + vv / 140 * 180, fill=GREEN, width=26 * S)
    for k in range(0, 141, 20):
        x1, y1 = gpt(cx, cy, R - 34, k); x2, y2 = gpt(cx, cy, R - 50, k); x3, y3 = gpt(cx, cy, R - 78, k)
        LN(d, [(x1, y1), (x2, y2)], GREY, 3, a); T(d, x3, y3, str(k), 20, GREY, "mm", a, False)
    ex, ey = gpt(cx, cy, 185, vv)
    LN(d, [(cx, cy), (ex, ey)], WHITE, 8); EL(d, cx, cy, 16, ACCENT)
    T(d, cx, cy + 110, f"{int(round(vv))}", 110, WHITE, "mm", a)
    T(d, cx, cy + 190, "km/h", 32, GREY, "mm", a, False)
    s = e_back(prog(lt, 2.3, 0.4))
    if s > 0:
        RR(d, 360 - 150 * s, 828 - 28 * s, 360 + 150 * s, 828 + 28 * s, 28 * s, GREEN, a=clamp(s))
        T(d, 375, 828, "Option A", int(30 * s), (10, 40, 20), "mm", clamp(s))
        LN(d, [(290, 829), (300, 840), (320, 816)], (10, 40, 20), 5, clamp(s))
    if lt > 2.3:
        tau = lt - 2.3
        for ang, sp, col, sz in CONF:
            x = cx + math.cos(ang) * sp * tau; y = 560 + math.sin(ang) * sp * tau + 380 * tau * tau
            al = clamp(1 - (tau - 1.2) / 0.5)
            if 0 <= x < W and y < 1090 and al > 0.02:
                d.rectangle([x * S, y * S, (x + sz) * S, (y + sz * 0.6) * S], fill=mix(bgcol(y), col, al))

def sH(d, lt, t):
    p = e_back(prog(lt, 0.2, 0.5))
    EL(d, 360, 320, 70 * p, GREEN, clamp(p))
    if p > 0.6: LN(d, [(330, 322), (352, 346), (392, 298)], (10, 40, 20), 12, clamp(p))
    T(d, 360, 450, "Day 10 complete", 56, WHITE, "mm", e_out(prog(lt, 0.5, 0.4)))
    T(d, 360, 535, "Roju 8 AM   -   New question", 28, GREY, "mm", e_out(prog(lt, 0.8, 0.4)), False)
    T(d, 360, 585, "Roju 6 PM   -   Full solution", 28, GREY, "mm", e_out(prog(lt, 1.0, 0.4)), False)
    pa = e_out(prog(lt, 1.2, 0.4)); pulse = 1 + 0.05 * math.sin(lt * 7)
    RR(d, 360 - 190 * pulse, 680, 360 + 190 * pulse, 760, 38, ACCENT, a=pa)
    T(d, 360, 720, "Vote on the poll!", int(34 * pulse), (30, 24, 0), "mm", pa)
    if lt > 1.5: train(d, lerp(-40, 1000, e_io(prog(lt, 1.5, 1.4))), t)

SCENES = [sA, sB, sC, sD, sE, sF, sG, sH]
CAPS = ["Ee roju topic: Speed, Time & Distance",
        "Question baga chadivi, options chudandi",
        "Train platform cross avvali ante, train + platform length anta travel cheyyali",
        "150 + 250 = 400 m total distance",
        "Speed = Distance / Time, so 400 / 20 = 20 m/s",
        "m/s ni km/h ki marchali ante 18/5 tho multiply cheyyi",
        "Answer: 72 km/h, Option A",
        "Repu kaluddam, poll lo vote cheyyadam marchipoku"]

def render_scene(i, t):
    img, d = base(t)
    lt = t - SS[i]
    SCENES[i](d, lt, t); caption(d, CAPS[i], lt)
    return img

def render_frame(idx):
    t = idx / FPS
    i = max(k for k in range(len(SS)) if SS[k] <= t)
    img = render_scene(i, t)
    if i > 0 and t - SS[i] < TR:
        prev = render_scene(i - 1, t)
        img = Image.blend(prev, img, e_io((t - SS[i]) / TR))
    return img.reduce(S)

# ---------------------------------------------------------------- audio
def make_audio(path):
    from scipy.signal import butter, lfilter
    SR = 44100; N = int(TOTAL * SR); au = np.zeros(N); rng = np.random.default_rng(1)
    def add(t0, sig, g=1.0):
        i = int(t0 * SR); j = min(N, i + len(sig))
        if j > i: au[i:j] += sig[:j - i] * g
    def bp(x, lo, hi, order=2):
        b, a = butter(order, [lo / (SR / 2), hi / (SR / 2)], btype="band"); return lfilter(b, a, x)
    def whoosh(dur=0.5):
        n = int(dur * SR); x = bp(rng.normal(size=n), 400, 3500); env = np.sin(np.linspace(0, math.pi, n)) ** 2
        return x * env * 2.2
    def rumble(dur):
        n = int(dur * SR); x = bp(rng.normal(size=n), 35, 140); tt = np.arange(n) / SR
        env = np.minimum(1, np.minimum(tt / 0.2, (dur - tt) / 0.3))
        return x * (0.6 + 0.4 * np.sin(2 * math.pi * 7 * tt)) * env * 9
    def pop():
        tt = np.arange(int(0.14 * SR)) / SR
        return np.sin(2 * math.pi * (500 * tt + 2500 * tt ** 2)) * np.exp(-tt * 28)
    def ding():
        tt = np.arange(int(1.3 * SR)) / SR
        return (np.sin(2 * math.pi * 880 * tt) + 0.6 * np.sin(2 * math.pi * 1320 * tt)) * np.exp(-tt * 3.2)
    for s in SS: add(max(0, s - 0.05), whoosh(), 0.28)
    add(0.2, rumble(1.7), 0.35); add(SS[2] + 0.6, rumble(3.8), 0.4); add(SS[7] + 1.5, rumble(1.6), 0.3)
    pops = [SS[1] + 1.5 + 0.3 * i for i in range(4)] + [SS[3] + 0.3, SS[3] + 0.8, SS[3] + 1.0, SS[3] + 2.0,
            SS[4] + 0.5, SS[4] + 2.8, SS[5] + 0.7, SS[5] + 1.3, SS[5] + 1.8, SS[5] + 2.9, SS[7] + 0.2, SS[7] + 1.2]
    for p_ in pops: add(p_, pop(), 0.22)
    add(SS[6] + 2.3, ding(), 0.35)
    tt = np.arange(N) / SR
    pad = sum(np.sin(2 * math.pi * f * tt) for f in (110, 164.8, 220, 261.6)) * (0.6 + 0.4 * np.sin(2 * math.pi * 0.2 * tt))
    pad *= np.minimum(1, np.minimum(tt / 1.5, (TOTAL - tt) / 1.5)); au += pad * 0.025
    au = au / (np.abs(au).max() + 1e-9) * 0.85
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((au * 32767).astype(np.int16).tobytes()); w.close()

# ---------------------------------------------------------------- main
if __name__ == "__main__":
    init()
    if sys.argv[1] == "stills":
        for k in sys.argv[2:]:
            t0 = time.time(); render_frame(int(k)).save(f"still_{k}.png"); print(k, round(time.time() - t0, 2), "s")
    elif sys.argv[1] == "full":
        make_audio("audio.wav")
        n = int(TOTAL * FPS)
        ff = subprocess.Popen(["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                               "-i", "-", "-i", "audio.wav", "-c:v", "libx264", "-preset", "medium", "-crf", "23",
                               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                               sys.argv[2]], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        for k in range(n):
            ff.stdin.write(render_frame(k).tobytes())
            if k % 60 == 0: print("frame", k, "/", n, flush=True)
        ff.stdin.close(); ff.wait(); print("DONE", flush=True)
