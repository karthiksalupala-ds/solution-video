import math, random, subprocess, sys, wave, colorsys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from scipy.signal import butter, lfilter

W, H, S, FPS, SR = 720, 1280, 2, 30, 44100
FD = "/usr/share/fonts/truetype/google-fonts/"
ACCENT, GREEN, WHITE, GREY = (255, 196, 0), (60, 220, 130), (255, 255, 255), (150, 165, 175)
_fc = {}
def font(sz, bold=True):
    k = (int(sz), bold)
    if k not in _fc: _fc[k] = ImageFont.truetype(FD + ("Poppins-Bold.ttf" if bold else "Poppins-Medium.ttf"), max(2, int(sz * S)))
    return _fc[k]
def lerp(a, b, t): return a + (b - a) * t
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def prog(t, t0, d): return clamp((t - t0) / d)
def e_out(p): return 1 - (1 - p) ** 3
def e_io(p): return p * p * (3 - 2 * p)
def e_back(p):
    if p <= 0: return 0
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
def mix(c1, c2, t): return tuple(int(lerp(c1[i], c2[i], clamp(t))) for i in range(3))
def T(d, x, y, s, size, col, anchor="la", a=1.0, bg=(0, 0, 0), bold=True):
    if a <= 0.02 or size < 2: return
    d.text((x * S, y * S), s, font=font(size, bold), fill=mix(bg, col, a), anchor=anchor)
def RR(d, x0, y0, x1, y1, r, fill, outline=None, w=1, a=1.0, bg=(0, 0, 0)):
    if a <= 0.02: return
    d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], max(0, r * S), fill=mix(bg, fill, a) if fill else None,
                        outline=mix(bg, outline, a) if outline else None, width=int(w * S))
def wrap(s, size, maxw, bold=True):
    f = font(size, bold); lines, cur = [], ""
    for w in s.split():
        tt = (cur + " " + w).strip()
        if f.getlength(tt) / S <= maxw: cur = tt
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

# ---- audio
rng = np.random.default_rng(3)
def mk(total): return np.zeros(int(total * SR))
def add(au, t0, sig, g=1.0):
    i = int(t0 * SR); j = min(len(au), i + len(sig))
    if j > i: au[i:j] += sig[:j - i] * g
def bp(x, lo, hi):
    b, a = butter(2, [lo / (SR / 2), hi / (SR / 2)], btype="band"); return lfilter(b, a, x)
def kick():
    tt = np.arange(int(0.35 * SR)) / SR; f = 45 + 110 * np.exp(-tt * 35)
    return np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-tt * 9)
def hat():
    tt = np.arange(int(0.08 * SR)) / SR; return np.diff(rng.normal(size=len(tt) + 1)) * np.exp(-tt * 55) * 0.5
def bass(f, dur=0.5):
    tt = np.arange(int(dur * SR)) / SR; return np.sin(2 * math.pi * f * tt) * np.exp(-tt * 3) * np.minimum(1, tt / 0.01)
def pop(f0=500, f1=2500, dec=28):
    tt = np.arange(int(0.16 * SR)) / SR; return np.sin(2 * math.pi * (f0 * tt + f1 * tt ** 2)) * np.exp(-tt * dec)
def ding():
    tt = np.arange(int(1.3 * SR)) / SR
    return (np.sin(2 * math.pi * 880 * tt) + 0.6 * np.sin(2 * math.pi * 1320 * tt)) * np.exp(-tt * 3.2)
def whoosh(dur=0.5):
    n = int(dur * SR); return bp(rng.normal(size=n), 400, 3500) * np.sin(np.linspace(0, math.pi, n)) ** 2 * 2.2
def pluck(f, dur=1.2):
    tt = np.arange(int(dur * SR)) / SR
    return (np.sin(2 * math.pi * f * tt) * np.exp(-tt * 4) + 0.4 * np.sin(2 * math.pi * 2 * f * tt) * np.exp(-tt * 7)
            + 0.15 * np.sin(2 * math.pi * 3 * f * tt) * np.exp(-tt * 10))
def finish(au, path, peak=0.85):
    au = au / (np.abs(au).max() + 1e-9) * peak
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((au * 32767).astype(np.int16).tobytes()); w.close()

def encode(render, total, wav, out):
    n = int(total * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out],
                          stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for k in range(n):
        img = render(k / FPS)
        if img.size != (W, H): img = img.reduce(S)
        ff.stdin.write(img.tobytes())
    ff.stdin.close(); ff.wait()

# ================= VIDEO 1: chat POV =================
MSGS = [("f", "Bro TCS NQT register chesava?"), ("m", "Repu chestha le"), ("f", "Last date ninne"), ("m", "..."),
        ("m", "NINNE???"), ("f", "Link pampana?"), ("m", "Pampu pampu pampu"), ("f", "Apply chesaka aptitude prepare chey"),
        ("m", "Prepare ante?"), ("f", "Daily 1 question solve chey"), ("m", "Tomorrow nundi pakka"),
        ("f", "Day 1 nundi ide cheptunnav")]
def v1(out):
    BG = (11, 20, 26); HDR = (24, 35, 42)
    lay, y = [], 190
    for who, txt in MSGS:
        ls = wrap(txt, 30, 430, False); f = font(30, False)
        w = max(f.getlength(l) / S for l in ls) + 44; h = len(ls) * 40 + 30
        lay.append((who, ls, w, h, y)); y += h + 14
    tk, t = [], 1.4
    for i, (who, _) in enumerate(MSGS):
        if i: t += 1.0 if MSGS[i - 1][0] == who else 1.5
        tk.append(t)
    T_END = tk[-1] + 1.8; TOTAL = T_END + 3.4
    offs = [max(0, l[4] + l[3] - 1070) for l in lay]
    def render(t):
        img = Image.new("RGB", (W * S, H * S), BG); d = ImageDraw.Draw(img)
        k = max([i for i in range(len(tk)) if t >= tk[i]], default=-1)
        prev = offs[k - 1] if k > 0 else 0
        off = lerp(prev, offs[k], e_out(prog(t - tk[k], 0, 0.35))) if k >= 0 else 0
        for i in range(k + 1):
            who, ls, w, h, yy = lay[i]; a = e_out(prog(t - tk[i], 0, 0.25)); sl = (1 - a) * 30
            x0 = 30 if who == "f" else 690 - w; y0 = yy - off + sl
            RR(d, x0, y0, x0 + w, y0 + h, 22, (32, 44, 53) if who == "f" else (0, 92, 75), a=a, bg=BG)
            for li, l in enumerate(ls): T(d, x0 + 22, y0 + 15 + li * 40 + 20, l, 30, (233, 237, 239), "lm", a, BG, False)
        nxt = k + 1; typing_f = False
        if nxt < len(tk) and t >= tk[nxt] - 0.8:
            who = lay[nxt][0]; a = e_out(prog(t, tk[nxt] - 0.8, 0.2)); y0 = lay[nxt][4] - off
            x0 = 30 if who == "f" else 580
            RR(d, x0, y0, x0 + 110, y0 + 62, 24, (32, 44, 53) if who == "f" else (0, 92, 75), a=a, bg=BG)
            for j in range(3):
                bo = -7 * max(0, math.sin(t * 9 - j * 0.8))
                d.ellipse([(x0 + 30 + j * 25 - 6) * S, (y0 + 31 + bo - 6) * S, (x0 + 30 + j * 25 + 6) * S, (y0 + 31 + bo + 6) * S],
                          fill=mix(BG, (200, 210, 215), a))
            typing_f = who == "f"
        d.rectangle([0, 0, W * S, 150 * S], fill=HDR)
        d.line([(46 * S, 76 * S), (28 * S, 90 * S), (46 * S, 104 * S)], fill=WHITE, width=4 * S, joint="curve")
        d.ellipse([78 * S, 46 * S, 146 * S, 114 * S], fill=(90, 110, 130)); T(d, 112, 80, "R", 36, WHITE, "mm", 1, (90, 110, 130))
        T(d, 165, 68, "Ravi", 34, WHITE, "lm", 1, HDR); T(d, 165, 102, "typing..." if typing_f else "online", 22, (0, 200, 160) if typing_f else GREY, "lm", 1, HDR, False)
        d.rectangle([0, 1170 * S, W * S, H * S], fill=HDR)
        RR(d, 20, 1190, 626, 1262, 36, (42, 57, 66), bg=HDR); T(d, 56, 1226, "Message", 26, GREY, "lm", 1, (42, 57, 66), False)
        d.ellipse([632 * S, 1190 * S, 704 * S, 1262 * S], fill=(0, 168, 132))
        d.polygon([(654 * S, 1210 * S), (686 * S, 1226 * S), (654 * S, 1242 * S)], fill=WHITE)
        if t >= T_END:
            p = prog(t, T_END, 0.5); img = Image.blend(img, Image.new("RGB", img.size, (7, 12, 16)), 0.9 * p); d = ImageDraw.Draw(img)
            B = (7, 12, 16); lt = t - T_END
            T(d, 360, 480, "Tomorrow nundi", 46, GREY, "mm", e_out(prog(lt, 0.3, 0.4)), B, False)
            s = e_back(prog(lt, 0.8, 0.5)); T(d, 360, 590, "Today nundi.", int(104 * s), ACCENT, "mm", clamp(s), B)
            T(d, 360, 720, "Day 1 start chey.", 52, WHITE, "mm", e_out(prog(lt, 1.6, 0.4)), B)
            pa = e_out(prog(lt, 2.2, 0.4)); RR(d, 160, 840, 560, 910, 35, GREEN, a=pa, bg=B)
            T(d, 360, 875, "Aptitude Daily  -  Day 1/100", 26, (10, 40, 20), "mm", pa, B)
        return img
    au = mk(TOTAL)
    for i, (who, _) in enumerate(MSGS): add(au, tk[i], pop(700, 3000) if who == "m" else pop(380, 1500), 0.5)
    add(au, T_END, whoosh(), 0.4); add(au, T_END + 0.8, pop(500, 2500), 0.4); add(au, T_END + 2.4, ding(), 0.35)
    finish(au, "a1.wav"); encode(render, TOTAL, "a1.wav", out)

# ================= VIDEO 2: kinetic typography =================
PH = [(["PERFECT", "TIME ANTE", "EM UNDADU."], (20, 28, 90), (255, 196, 0), 3.0),
      (["START", "CHEYYI."], (95, 25, 125), (80, 255, 170), 2.5),
      (["DAILY 1", "QUESTION."], (205, 75, 20), (25, 25, 60), 2.5),
      (["100", "DAYS."], (8, 110, 115), (255, 232, 90), 2.5),
      (["NUVVE", "DIFFERENT", "AVTHAV."], (14, 14, 20), (255, 196, 0), 3.5)]
def v2(out):
    starts = [0.0]
    for p in PH: starts.append(starts[-1] + p[3])
    TOTAL = starts[-1]
    def render(t):
        i = max(k for k in range(len(PH)) if starts[k] <= t); words, bg, acc, dur = PH[i]; lt = t - starts[i]
        img = Image.new("RGB", (W * S, H * S), bg); d = ImageDraw.Draw(img)
        bt = (t % 0.5) / 0.5
        for j in range(3):
            ft = ((t / 0.5) - j * 0.5) % 1.5 / 1.5; r = 60 + 560 * e_out(ft)
            col = mix(bg, (255, 255, 255), 0.16 * (1 - ft))
            d.ellipse([(360 - r) * S, (640 - r) * S, (360 + r) * S, (640 + r) * S], outline=col, width=5 * S)
        pul = 1 + 0.035 * (1 - bt) ** 2
        n = len(words); fs = []
        for wd in words:
            w1 = font(150).getlength(wd) / S; fs.append(min(150, 150 * 640 / w1))
        gap = 1.18; total_h = sum(f * gap for f in fs); y = 640 - total_h / 2
        for k, wd in enumerate(words):
            ap = k * 0.5; p = prog(lt, ap, 0.28)
            cy = y + fs[k] * gap / 2; y += fs[k] * gap
            if p <= 0: continue
            s = (0.35 + 0.65 * e_back(p)) * pul; col = acc if k == n - 1 else WHITE
            T(d, 360, cy, wd, fs[k] * s, col, "mm", 1, bg)
        if lt < 0.14:
            img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), 0.5 * (1 - lt / 0.14))
        d = ImageDraw.Draw(img); T(d, 360, 1210, "Aptitude Daily", 26, WHITE, "mm", 0.55, bg, False)
        return img
    au = mk(TOTAL)
    for b in range(int(TOTAL / 0.5)):
        add(au, b * 0.5, kick(), 0.9); add(au, b * 0.5 + 0.25, hat(), 0.5)
    for si, s in enumerate(starts[:-1]):
        add(au, s, whoosh(0.4), 0.35); add(au, s, bass([55, 65.4, 49, 55, 73.4][si], 1.2), 0.5)
    for si, p in enumerate(PH):
        for k in range(len(p[0])): add(au, starts[si] + k * 0.5, pop(600 + 80 * k, 2200), 0.25)
    add(au, starts[-2] + 1.0, ding(), 0.3)
    finish(au, "a2.wav"); encode(render, TOTAL, "a2.wav", out)

# ================= VIDEO 3: hypnotic loop =================
def v3(out):
    n, TL = 20, 10.0; BG = (6, 6, 16)
    rings = [(40 + i * 15.5, 6 + 3 * i, (i % 5 + 1) * (1 if i % 2 == 0 else -1)) for i in range(n)]
    def render(t):
        img = Image.new("RGB", (W * S, H * S), BG); d = ImageDraw.Draw(img); ph = t / TL
        for i, (r, m, w) in enumerate(rings):
            col = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((i / n * 0.6 + ph) % 1, 0.7, 1.0))
            rr = r * (1 + 0.07 * math.sin(2 * math.pi * ph + i * 0.3))
            for j in range(m):
                ang = 2 * math.pi * (j / m + w * ph)
                sz = 2.5 + 6.5 * (0.5 + 0.5 * math.sin(2 * math.pi * (2 * ph + 3 * j / m) + i * 0.4))
                x = (360 + rr * math.cos(ang)) * S; y = (640 + rr * math.sin(ang)) * S
                d.ellipse([x - sz * S, y - sz * S, x + sz * S, y + sz * S], fill=col)
        red = img.reduce(S); glow = red.filter(ImageFilter.GaussianBlur(7))
        return ImageChops.screen(red, ImageChops.add(glow, glow))
    au = mk(TL + 0.5); notes = [220, 261.6, 329.6, 392, 440, 523.3, 659.3]
    pat = [0, 2, 4, 3, 5, 4, 2, 1, 3, 6, 4, 2, 0, 3, 5, 6, 4, 3, 1, 2]
    for k in range(20):
        p = pluck(notes[pat[k]]); add(au, k * 0.5, p, 0.5); add(au, k * 0.5 + 0.375, p, 0.2); add(au, k * 0.5 + 0.75, p, 0.1)
        if k % 4 == 0: add(au, k * 0.5, bass(55 if k % 8 == 0 else 65.4, 1.8), 0.7)
    tt = np.arange(len(au)) / SR
    au += sum(np.sin(2 * math.pi * f * tt) for f in (110, 164.8, 220)) * 0.03 * np.minimum(1, np.minimum(tt, (TL - tt) / 1.0).clip(0))
    finish(au[:int(TL * SR)], "a3.wav"); encode(render, TL, "a3.wav", out)

if __name__ == "__main__":
    {"1": v1, "2": v2, "3": v3}[sys.argv[1]](sys.argv[2])
    print("DONE", sys.argv[1], flush=True)
