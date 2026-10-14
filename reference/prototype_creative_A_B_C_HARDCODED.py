import sys
from creative import *

def grad(c1, c2):
    arr = np.zeros((H * S, W * S, 3), np.uint8); t = np.linspace(0, 1, H * S)[:, None]
    for i in range(3): arr[:, :, i] = (c1[i] + (c2[i] - c1[i]) * t).astype(np.uint8)
    return Image.fromarray(arr)
def hsv(h, s=0.75, v=1.0): return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h % 1, s, v))
def tone(f, dur=0.04, dec=60):
    tt = np.arange(int(dur * SR)) / SR; return np.sin(2 * math.pi * f * tt) * np.exp(-tt * dec) * np.minimum(1, tt / 0.003)
def confetti(d, cx, cy, tau, seed=1, n=70, bgy=None):
    rc = random.Random(seed)
    for _ in range(n):
        ang = rc.uniform(-math.pi * 0.95, -math.pi * 0.05); sp = rc.uniform(200, 560); col = rc.choice([ACCENT, GREEN, (255, 120, 160), (120, 190, 255), WHITE]); sz = rc.randint(6, 12)
        x = cx + math.cos(ang) * sp * tau; y = cy + math.sin(ang) * sp * tau + 420 * tau * tau; al = clamp(1 - (tau - 1.4) / 0.6)
        if 0 <= x < W and 0 <= y < H and al > 0.02:
            d.rectangle([x * S, y * S, (x + sz) * S, (y + sz * 0.6) * S], fill=mix((20, 20, 40), col, al))

# ============ A: sorting ============
def sorting(out):
    n = 36; rnd = random.Random(7); a = list(range(1, n + 1)); rnd.shuffle(a)
    snaps, sw_c = [], 0
    for i in range(n - 1):
        for j in range(n - 1 - i):
            sw = a[j] > a[j + 1]
            if sw: a[j], a[j + 1] = a[j + 1], a[j]; sw_c += 1
            snaps.append((a[:], j, sw, i, sw_c))
    NS = len(snaps); SPS = 60.0; T0 = 1.2; T1 = T0 + NS / SPS; T2 = T1 + 2.0; TOTAL = T2 + 1.6
    G = grad((10, 10, 26), (28, 12, 52)); BGc = (18, 11, 40)
    bw = 640 / n
    def render(t):
        img = G.copy(); d = ImageDraw.Draw(img)
        T(d, 360, 150, "BUBBLE SORT", 62, WHITE, "mm", e_out(prog(t, 0, 0.5)), BGc)
        if t < T2:
            T(d, 360, 218, "36 random numbers, bar height = value", 24, GREY, "mm", e_out(prog(t, 0.3, 0.5)), BGc, False)
        k = min(NS - 1, int(max(0, t - T0) * SPS)) if t >= T0 else -1
        if k >= 0: arr, j, sw, ps, swc = snaps[k]
        else: arr, j, sw, ps, swc = list(snaps[0][0]) if False else [0] * n, -1, False, 0, 0
        if k < 0:
            arr = list(range(1, n + 1)); rr = random.Random(7); rr.shuffle(arr)
        done = t >= T1
        for i, v in enumerate(arr):
            h = v / n * 600; x0 = 40 + i * bw; col = hsv(v / n * 0.8)
            if k >= 0 and not done and i in (j, j + 1): col = (255, 90, 90) if sw else (255, 255, 255)
            if done:
                sp = prog(t, T1 + i * (2.0 / n), 0.15); col = mix(col, (60, 230, 140), e_out(sp))
            elif k >= 0 and i >= n - ps: col = mix(col, (255, 255, 255), 0.35)
            RR(d, x0, 1000 - h, x0 + bw - 4, 1000, 4, col, bg=BGc)
        cmp_n = (k + 1) if k >= 0 else 0; sw_n = snaps[k][4] if k >= 0 else 0
        T(d, 40, 1080, "Comparisons", 22, GREY, "lm", 1, BGc, False); T(d, 40, 1125, str(cmp_n), 54, WHITE, "lm", 1, BGc)
        T(d, 680, 1080, "Swaps", 22, GREY, "rm", 1, BGc, False); T(d, 680, 1125, str(sw_n), 54, ACCENT, "rm", 1, BGc)
        if t >= T2:
            s = e_back(prog(t, T2, 0.5)); T(d, 360, 218, "SORTED!", int(54 * s), (60, 230, 140), "mm", clamp(s), BGc)
        T(d, 360, 1215, "Time complexity: O(n^2)", 26, GREY, "mm", e_out(prog(t, 0.6, 0.5)), BGc, False)
        return img
    au = mk(TOTAL)
    for kk in range(NS):
        arr, j, sw, ps, swc = snaps[kk]; v = max(arr[j], arr[j + 1])
        add(au, T0 + kk / SPS, tone(220 + 900 * v / n, 0.035, 70), 0.10 if not sw else 0.14)
    for i in range(n): add(au, T1 + i * (2.0 / n), tone(220 + 900 * (i + 1) / n, 0.14, 18), 0.22)
    add(au, T2, ding(), 0.3); add(au, 0, whoosh(), 0.25)
    finish(au, "aA.wav"); encode(render, TOTAL, "aA.wav", out)

# ============ B: 100 day grid ============
MS = {10: "10 days. Start ayindhi.", 25: "25 days. Habit avthundhi.", 50: "50 days. Half way!", 75: "75 days. Inka konchem!", 100: "100 days. Nuvvu chesav!"}
def streak(out):
    ti, t = {}, 1.0
    for dd in range(1, 101):
        ti[dd] = t; t += 0.085
        if dd in MS and dd != 100: t += 0.8
    TF = ti[100]; TOTAL = TF + 3.6
    G = grad((8, 14, 34), (30, 14, 60)); BGc = (18, 14, 46)
    def cellcol(dd):
        p = dd / 100; return hsv(lerp(0.6, 0.38, p / 0.6) if p < 0.6 else lerp(0.38, 0.12, (p - 0.6) / 0.4), 0.8, 1.0)
    def render(t):
        img = G.copy(); d = ImageDraw.Draw(img)
        T(d, 360, 150, "100 DAY CHALLENGE", 44, ACCENT, "mm", e_out(prog(t, 0, 0.5)), BGc)
        cur = max([dd for dd in ti if ti[dd] <= t], default=0)
        T(d, 360, 270, f"DAY {cur}", 110, WHITE, "mm", 1, BGc)
        for idx in range(100):
            dd = idx + 1; r, c = divmod(idx, 10); x0 = 60 + c * 60; y0 = 400 + r * 60
            if dd in ti and t >= ti[dd]:
                age = t - ti[dd]; sc = 1 + 0.45 * (1 - e_out(prog(age, 0, 0.3))); col = cellcol(dd)
                col = mix(col, (255, 255, 255), 0.7 * (1 - e_out(prog(age, 0, 0.25))))
                if t >= TF: col = mix(col, ACCENT, 0.55 * (0.5 + 0.5 * math.sin((t - TF) * 6 - idx * 0.15)))
                cx, cy, hs = x0 + 27, y0 + 27, 27 * sc
                RR(d, cx - hs, cy - hs, cx + hs, cy + hs, 8, col, bg=BGc)
            else:
                RR(d, x0, y0, x0 + 54, y0 + 54, 8, None, (60, 62, 110), 2, bg=BGc)
        for m, txt in MS.items():
            if ti[m] <= t < ti[m] + (1.7 if m != 100 else 99):
                s = e_back(prog(t - ti[m], 0, 0.4)); T(d, 360, 1100, txt, int((44 if m != 100 else 50) * s), ACCENT if m != 100 else GREEN, "mm", clamp(s), BGc)
        if t >= TF: confetti(d, 360, 700, t - TF, 4)
        T(d, 360, 1215, "Aptitude Daily  |  Chinna steps. Pedda results.", 22, GREY, "mm", 1, BGc, False)
        return img
    au = mk(TOTAL)
    for dd in range(1, 101): add(au, ti[dd], tone(300 + 900 * dd / 100, 0.04, 55), 0.16)
    for m in MS:
        add(au, ti[m], ding(), 0.25 if m != 100 else 0.4); add(au, ti[m], whoosh(0.4), 0.2)
    add(au, TF + 0.2, pluck(523.3), 0.5); add(au, TF + 0.35, pluck(659.3), 0.5); add(au, TF + 0.5, pluck(784), 0.5)
    finish(au, "aB.wav"); encode(render, TOTAL, "aB.wav", out)

# ============ C: mascot ============
DK, ORG, GRN, BLU = (30, 30, 70), (220, 90, 20), (10, 140, 70), (40, 90, 220)
SC = [(0.3, [("Hi! Nenu Chinnu.", DK)], "wave"),
      (2.8, [("Speed question lo", DK), ("oka trick cheptha:", DK)], "talk"),
      (5.2, [("km/h ni m/s ki", DK), ("marchali ante", DK), ("x 5/18 !", ORG)], "talk"),
      (8.6, [("Example:", DK), ("72 x 5/18", DK), ("= 20 m/s", GRN)], "talk"),
      (12.0, [("Nuvvu try chey!", DK), ("54 km/h = ? m/s", BLU)], "think"),
      (15.4, [("54 x 5/18", DK), ("= 15 m/s !", GRN)], "happy"),
      (18.2, [("Daily tips kosam", DK), ("Aptitude Daily", BLU), ("follow ayyi!", DK)], "wave")]
TOTALC = 21.2; CPS = 28.0
def mascot(out):
    G = grad((22, 70, 100), (62, 30, 104)); BGc = (40, 50, 100)
    rb = random.Random(2); BOK = [(rb.uniform(0, W), rb.uniform(0, H), rb.uniform(20, 70), rb.uniform(15, 40)) for _ in range(14)]
    def render(t):
        img = G.copy(); d = ImageDraw.Draw(img)
        for (x, y, r, sp) in BOK:
            yy = (y - t * sp) % (H + 140) - 70; EL = d.ellipse; EL([(x - r) * S, (yy - r) * S, (x + r) * S, (yy + r) * S], fill=mix(BGc, (255, 255, 255), 0.07))
        si = max([i for i in range(len(SC)) if SC[i][0] <= t], default=-1)
        lt = t - SC[si][0] if si >= 0 else 0; mood = SC[si][2] if si >= 0 else "talk"
        total = sum(len(l[0]) for l in SC[si][1]) if si >= 0 else 0; cnt = int(lt * CPS) if si >= 0 else 0
        talking = si >= 0 and cnt < total
        pin = e_back(prog(t, 0, 0.6)); b = (-11 * abs(math.sin(t * 3.4)) if talking else -4 * math.sin(t * 2)) * pin
        sy = lerp(260, 0, e_out(prog(t, 0, 0.6)))
        def Y(v): return v + b + sy
        d.ellipse([240 * S, 1018 * S, 480 * S, 1050 * S], fill=mix(BGc, (0, 0, 0), 0.25))
        BODY, DARK = (70, 140, 255), (40, 90, 200)
        RR(d, 285, Y(955), 335, Y(1012) - b * 0.5, 16, DARK); RR(d, 385, Y(955), 435, Y(1012) - b * 0.5, 16, DARK)
        arm_l = (215, Y(790)); th = 0.55
        hl = (arm_l[0] - 80 * math.cos(th), arm_l[1] + 80 * math.sin(th))
        waving = mood == "wave" or mood == "happy"
        thr = (-1.0 + 0.45 * math.sin(t * 9)) if waving else 0.6
        sh = (505, Y(790)); hr = (sh[0] + 90 * math.cos(thr), sh[1] + 90 * math.sin(thr))
        for (p0, p1) in ((arm_l, hl), (sh, hr)):
            d.line([(p0[0] * S, p0[1] * S), (p1[0] * S, p1[1] * S)], fill=DARK, width=28 * S)
            d.ellipse([(p1[0] - 20) * S, (p1[1] - 20) * S, (p1[0] + 20) * S, (p1[1] + 20) * S], fill=BODY)
        RR(d, 210, Y(680), 510, Y(970), 74, BODY); RR(d, 270, Y(860), 450, Y(945), 36, (115, 172, 255))
        d.line([(360 * S, Y(680) * S), (360 * S, Y(628) * S)], fill=(120, 140, 200), width=8 * S)
        pulse = 14 + 3 * math.sin(t * (14 if mood == "think" else 5)); gl = pulse + 12
        d.ellipse([(360 - gl) * S, (Y(618) - gl) * S, (360 + gl) * S, (Y(618) + gl) * S], fill=mix(BODY, ACCENT, 0.25))
        d.ellipse([(360 - pulse) * S, (Y(618) - pulse) * S, (360 + pulse) * S, (Y(618) + pulse) * S], fill=ACCENT)
        RR(d, 248, Y(706), 472, Y(850), 42, (14, 24, 60))
        blink = (t % 2.7) < 0.12; cy = Y(770); CY = (90, 225, 255)
        for ex in (310, 410):
            if mood == "happy":
                d.line([((ex - 24) * S, (cy + 12) * S), (ex * S, (cy - 12) * S), ((ex + 24) * S, (cy + 12) * S)], fill=CY, width=9 * S, joint="curve")
            elif blink:
                d.line([((ex - 22) * S, cy * S), ((ex + 22) * S, cy * S)], fill=CY, width=8 * S)
            else:
                d.ellipse([(ex - 23) * S, (cy - 27) * S, (ex + 23) * S, (cy + 27) * S], fill=WHITE)
                po = (-8, -12) if mood == "think" else (0, 4)
                d.ellipse([(ex + po[0] - 12) * S, (cy + po[1] - 12) * S, (ex + po[0] + 12) * S, (cy + po[1] + 12) * S], fill=(30, 60, 140))
        for cx_ in (282, 438): d.ellipse([(cx_ - 11) * S, (Y(818) - 8) * S, (cx_ + 11) * S, (Y(818) + 8) * S], fill=mix((14, 24, 60), (255, 130, 160), 0.6))
        mo = 6 + 15 * abs(math.sin(t * 17)) if talking else (14 if mood == "happy" else 5)
        d.ellipse([(360 - 20) * S, (Y(826) - mo / 2) * S, (360 + 20) * S, (Y(826) + mo / 2) * S], fill=(255, 140, 165))
        if si >= 0:
            lines = SC[si][1]; h = len(lines) * 56 + 54; y0 = 160; pa = e_out(prog(lt, 0, 0.2))
            RR(d, 50, y0, 670, y0 + h, 36, WHITE, a=pa, bg=BGc)
            d.polygon([(325 * S, (y0 + h - 2) * S), (395 * S, (y0 + h - 2) * S), (360 * S, (y0 + h + 44) * S)], fill=mix(BGc, WHITE, pa))
            rem = cnt
            for li, (txt, col) in enumerate(lines):
                shown = txt[:max(0, rem)]; rem -= len(txt)
                if shown: T(d, 360, y0 + 27 + 28 + li * 56, shown, 42, col, "mm", 1, WHITE)
            if mood == "happy" and lt > 0.2: confetti(d, 360, 560, lt - 0.2, 9, 60)
        T(d, 360, 1235, "Aptitude Daily", 24, WHITE, "mm", 0.6, BGc, False)
        return img
    au = mk(TOTALC); rs = random.Random(4)
    for st, lines, mood in SC:
        total = sum(len(l[0]) for l in lines)
        for c in range(0, total, 2):
            add(au, st + c / CPS, tone(rs.uniform(420, 760), 0.05, 40), 0.14)
        add(au, st - 0.05, pop(500, 2500), 0.25)
    add(au, SC[5][0], ding(), 0.4); add(au, 0.0, whoosh(), 0.3)
    finish(au, "aC.wav"); encode(render, TOTALC, "aC.wav", out)

if __name__ == "__main__":
    {"A": sorting, "B": streak, "C": mascot}[sys.argv[1]](sys.argv[2])
    print("DONE", sys.argv[1], flush=True)
