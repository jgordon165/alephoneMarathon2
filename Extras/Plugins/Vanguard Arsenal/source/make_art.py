"""Draws the Vanguard Arsenal first-person weapon sprites and writes
vanguard_weapons.shpp, a shapes patch for Marathon 2's weapons-in-hand
collection (collection 1).

All art is drawn here procedurally; nothing is copied from any game.

Usage:
    python3 make_art.py <Marathon 2 Shapes.shpA> <output dir>

The Shapes file is only read for the true-colour collection's colour table and the
original frame placement (so the new frames sit where the old ones did);
none of its pixels end up in the patch. Writes the patch plus PNG
previews of every frame.
"""
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapes_tool as st  # noqa: E402

COLLECTION = 1
DENSITY = 2      # pixels per original pixel; world size is unchanged
SS = 4           # supersampling while drawing


# --------------------------------------------------------------- helpers
class Canvas:
    """RGBA drawing surface addressed in output pixels, drawn at SS x."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))

    def P(self, pts):
        return [(x * SS, y * SS) for x, y in pts]

    def mask(self, shape, pts, **kw):
        m = Image.new('L', self.img.size, 0)
        d = ImageDraw.Draw(m)
        if shape == 'poly':
            d.polygon(self.P(pts), fill=255)
        elif shape == 'ellipse':
            (x0, y0), (x1, y1) = pts
            d.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=255)
        elif shape == 'rrect':
            (x0, y0), (x1, y1) = pts
            d.rounded_rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], radius=kw.get('r', 2) * SS, fill=255)
        elif shape == 'line':
            d.line(self.P(pts), fill=255, width=max(1, int(kw.get('width', 1) * SS)), joint='curve')
        return m

    def fill(self, mask, top, bottom=None, axis='y', box=None, glow=False):
        """Fill mask with a linear gradient from `top` to `bottom`."""
        bottom = bottom or top
        W, H = self.img.size
        if box:
            (bx0, by0), (bx1, by1) = box
            bx0, by0, bx1, by1 = bx0 * SS, by0 * SS, bx1 * SS, by1 * SS
        else:
            bb = mask.getbbox() or (0, 0, W, H)
            bx0, by0, bx1, by1 = bb
        grad = Image.new('RGBA', (W, H))
        gd = ImageDraw.Draw(grad)
        span = max(1, (by1 - by0) if axis == 'y' else (bx1 - bx0))
        n = int(span)
        for i in range(n + 1):
            t = i / n
            c = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3)) + (255,)
            if axis == 'y':
                gd.line([(0, by0 + i), (W, by0 + i)], fill=c)
            else:
                gd.line([(bx0 + i, 0), (bx0 + i, H)], fill=c)
        if axis == 'y':
            gd.rectangle([0, 0, W, by0], fill=tuple(top) + (255,))
            gd.rectangle([0, by1, W, H], fill=tuple(bottom) + (255,))
        else:
            gd.rectangle([0, 0, bx0, H], fill=tuple(top) + (255,))
            gd.rectangle([bx1, 0, W, H], fill=tuple(bottom) + (255,))
        if glow:
            mask = mask.filter(ImageFilter.GaussianBlur(SS * 1.5))
        self.img.paste(grad, (0, 0), mask)

    def poly(self, pts, top, bottom=None, axis='y'):
        self.fill(self.mask('poly', pts), top, bottom, axis)

    def ellipse(self, box, top, bottom=None, axis='y'):
        self.fill(self.mask('ellipse', box), top, bottom, axis)

    def rrect(self, box, top, bottom=None, r=2, axis='y'):
        self.fill(self.mask('rrect', box, r=r), top, bottom, axis)

    def line(self, pts, color, width=1):
        self.fill(self.mask('line', pts, width=width), color)

    def glow(self, center, radius, color, strength=1.0):
        """Soft additive-looking glow (alpha-blended, fades out)."""
        W, H = self.img.size
        m = Image.new('L', (W, H), 0)
        d = ImageDraw.Draw(m)
        cx, cy = center[0] * SS, center[1] * SS
        steps = 24
        for i in range(steps, 0, -1):
            r = radius * SS * i / steps
            a = int(255 * strength * (1 - i / steps) ** 1.6)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=a)
        layer = Image.new('RGBA', (W, H), tuple(color) + (255,))
        self.img.paste(layer, (0, 0), m)

    def flare(self, center, radius, color, spikes=8, seed=0):
        """Jagged starburst for muzzle flashes."""
        cx, cy = center
        pts = []
        for i in range(spikes * 2):
            ang = math.pi * i / spikes + seed
            r = radius * (1.0 if i % 2 == 0 else 0.42) * (0.85 + 0.3 * ((i * 7 + seed * 13) % 5) / 4)
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        self.poly(pts, color)

    def compose(self, other, dx=0, dy=0):
        self.img.alpha_composite(other.img, (int(dx * SS), int(dy * SS)))

    def result(self):
        out = self.img.resize((self.w, self.h), Image.LANCZOS)
        return out


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


# Palette-friendly material colours (see the collection colour table)
GUNMETAL = (92, 96, 104)
GUNMETAL_DARK = (40, 42, 48)
STEEL_LIGHT = (176, 180, 188)
ACCENT = (232, 120, 28)        # orange stripe on the rifle
LENS = (60, 210, 230)
PLASMA_BODY = (150, 160, 176)
PLASMA_DARK = (60, 66, 84)
PLASMA_GLOW = (40, 220, 255)
PLASMA_CORE = (210, 250, 255)
GLOVE = (92, 52, 36)
GLOVE_DARK = (52, 28, 20)
SLEEVE = (54, 92, 44)
SLEEVE_DARK = (26, 48, 22)
FLASH_OUT = (255, 150, 30)
FLASH_IN = (255, 236, 150)


# ------------------------------------------------------------ extras
def radial(c, center, rx, ry, colors):
    """Opaque radial gradient disc; colors run from the rim to the centre."""
    cx, cy = center
    n = 28
    for i in range(n):
        t = i / (n - 1)
        k = t * (len(colors) - 1)
        a, b = colors[int(k)], colors[min(int(k) + 1, len(colors) - 1)]
        f = k - int(k)
        col = tuple(int(a[j] + (b[j] - a[j]) * f) for j in range(3))
        s_ = 1 - t * 0.92
        c.ellipse([(cx - rx * s_, cy - ry * s_), (cx + rx * s_, cy + ry * s_)], col)


def aura(c, center, radius, seed=1):
    """Opaque, ragged energy cloud (for the charged plasma shot)."""
    cx, cy = center
    layers = [((10, 40, 120), 1.0), ((20, 110, 210), 0.82), ((40, 200, 250), 0.62), ((170, 245, 255), 0.36)]
    for col, scale in layers:
        pts = []
        for i in range(40):
            ang = 2 * math.pi * i / 40
            wob = 0.82 + 0.18 * math.sin(ang * 7 + seed * 3.1 + scale * 5) * math.cos(ang * 3 + seed)
            r = radius * scale * wob
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang) * 1.1))
        c.poly(pts, col)


def grain(img, amount=10, seed=7):
    """Deterministic per-pixel brightness noise on opaque pixels, so flat
    gradients read as metal rather than vector art."""
    px = img.load()
    W, H = img.size
    state = seed * 2654435761 & 0xffffffff
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            state = (state * 1103515245 + 12345) & 0x7fffffff
            d = (state % (2 * amount + 1)) - amount
            px[x, y] = (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d)), a)
    return img


# ------------------------------------------------------------ the rifle
def draw_rifle_rear(w, h, flash=False, flash_box=None):
    """Burst rifle seen from behind. Only the top ~30% of this frame is on
    screen at rest, so the optic and the receiver's shoulders live there;
    the stock below shows when the gun kicks or is reloaded."""
    c = Canvas(w, h)
    X = lambda f: f * w
    Y = lambda f: f * h

    # receiver shoulders widening toward the camera
    c.poly([(X(0.30), Y(0.08)), (X(0.04), Y(0.62)), (X(0.04), Y(1.0)), (X(0.44), Y(1.0)), (X(0.44), Y(0.08))],
           GUNMETAL_DARK, GUNMETAL, axis='x')
    c.poly([(X(0.56), Y(0.08)), (X(0.56), Y(1.0)), (X(0.96), Y(1.0)), (X(0.96), Y(0.62)), (X(0.70), Y(0.08))],
           GUNMETAL, GUNMETAL_DARK, axis='x')
    c.poly([(X(0.44), Y(0.08)), (X(0.56), Y(0.08)), (X(0.56), Y(1.0)), (X(0.44), Y(1.0))], STEEL_LIGHT, GUNMETAL)
    # bevel highlight on the shoulders' upper edges
    c.line([(X(0.30), Y(0.085)), (X(0.06), Y(0.60))], STEEL_LIGHT, 1.2)
    c.line([(X(0.70), Y(0.085)), (X(0.94), Y(0.60))], shade(STEEL_LIGHT, 0.85), 1.2)
    # orange accent stripes
    c.poly([(X(0.27), Y(0.16)), (X(0.31), Y(0.16)), (X(0.13), Y(0.58)), (X(0.09), Y(0.56))], ACCENT, shade(ACCENT, 0.65))
    c.poly([(X(0.73), Y(0.16)), (X(0.69), Y(0.16)), (X(0.87), Y(0.58)), (X(0.91), Y(0.56))], ACCENT, shade(ACCENT, 0.65))
    # vent slots on the shoulders
    for i in range(3):
        y = Y(0.34 + i * 0.06)
        c.line([(X(0.20 - i * 0.03), y), (X(0.34), y)], (22, 24, 28), 1.4)
        c.line([(X(0.66), y), (X(0.80 + i * 0.03), y)], (22, 24, 28), 1.4)
    # top rail
    c.rrect([(X(0.38), Y(0.0)), (X(0.62), Y(0.05))], GUNMETAL, GUNMETAL_DARK, r=1)
    for i in range(5):
        x = X(0.40 + i * 0.045)
        c.line([(x, Y(0.005)), (x, Y(0.045))], (24, 26, 30), 1)
    # optic: squat housing, dark bezel, cyan lens with a highlight
    c.rrect([(X(0.29), Y(0.035)), (X(0.71), Y(0.25))], STEEL_LIGHT, GUNMETAL_DARK, r=4)
    c.rrect([(X(0.33), Y(0.06)), (X(0.67), Y(0.225))], (26, 30, 36), (10, 12, 16), r=3)
    radial(c, (X(0.5), Y(0.142)), w * 0.14, h * 0.068, [(10, 60, 80), LENS, (150, 240, 250)])
    c.ellipse([(X(0.43), Y(0.095)), (X(0.48), Y(0.12))], (235, 252, 255))
    # side knobs on the optic
    c.rrect([(X(0.24), Y(0.10)), (X(0.30), Y(0.17))], GUNMETAL, GUNMETAL_DARK, r=1)
    c.rrect([(X(0.70), Y(0.10)), (X(0.76), Y(0.17))], GUNMETAL, GUNMETAL_DARK, r=1)
    # stock and butt plate (below the screen edge at rest)
    c.line([(X(0.22), Y(0.70)), (X(0.78), Y(0.70))], (24, 26, 30), 1.2)
    c.rrect([(X(0.16), Y(0.86)), (X(0.84), Y(1.04))], shade(GUNMETAL_DARK, 0.9), (16, 16, 20), r=4)
    for i in range(6):
        x = X(0.24 + i * 0.104)
        c.line([(x, Y(0.89)), (x, Y(1.0))], GUNMETAL, 1)
    return c


def draw_rifle_firing(w, h, idle_w, idle_h, dx, dy):
    """Firing frame: the idle rifle at its usual spot plus a muzzle flash
    spread across the top, the way Marathon's flashes frame the gun."""
    c = Canvas(w, h)
    gun = draw_rifle_rear(idle_w, idle_h)
    c.compose(gun, dx, dy)
    fx, fy = dx + idle_w * 0.5, dy + idle_h * 0.03
    c.flare((fx, fy), w * 0.40, FLASH_OUT, spikes=9, seed=0.3)
    c.flare((fx, fy), w * 0.24, (255, 200, 70), spikes=9, seed=0.8)
    radial(c, (fx, fy), w * 0.10, w * 0.07, [(255, 210, 90), FLASH_IN, (255, 255, 235)])
    # the optic stays visible through the flash
    sub = draw_rifle_rear(idle_w, idle_h)
    crop = sub.img.crop((0, int(idle_h * 0.03 * SS), sub.img.width, int(idle_h * 0.26 * SS)))
    keep = Canvas(w, h)
    keep.img.alpha_composite(crop, (int(dx * SS), int((dy + idle_h * 0.03) * SS)))
    c.img.alpha_composite(keep.img)
    return c


def draw_hand(c, x, y, scale, angle=0.0, holding_mag=False):
    """Gloved hand with sleeve, reaching in from the lower left."""
    s = scale
    ca, sa = math.cos(angle), math.sin(angle)

    def T(px, py):
        return (x + (px * ca - py * sa) * s, y + (px * sa + py * ca) * s)

    c.poly([T(-70, 110), T(-20, 8), T(14, 22), T(-24, 120)], SLEEVE, SLEEVE_DARK, axis='x')
    c.line([T(-46, 60), T(-8, 30)], SLEEVE_DARK, max(1, s))
    c.poly([T(-18, 12), T(-8, -14), T(20, -18), T(30, 2), T(14, 24)], GLOVE, GLOVE_DARK)
    for fx, fy in [(-4, -16), (6, -19), (16, -18), (25, -10)]:
        c.poly([T(fx - 4, fy + 4), T(fx - 3, fy - 15), T(fx + 3, fy - 16), T(fx + 4, fy + 3)],
               shade(GLOVE, 1.2), GLOVE_DARK)
    if holding_mag:
        c.poly([T(-2, -10), T(4, -52), T(24, -50), T(20, -8)], GUNMETAL, GUNMETAL_DARK, axis='x')
        c.poly([T(4, -52), T(24, -50), T(23, -45), T(5, -47)], (200, 166, 84), (140, 110, 50))
        c.line([T(7, -32), T(21, -30)], ACCENT, max(1, s * 0.8))


def draw_rifle_reload(w, h, stage):
    """0: magazine out, 1: new magazine in, 2: settling back."""
    c = Canvas(w, h)
    gw, gh = int(w * 0.46), int(h * 0.80)
    gun = draw_rifle_rear(gw, gh)
    tilt = [-26, -32, -14][stage]
    rot = gun.img.rotate(tilt, resample=Image.BICUBIC, expand=True)
    # keep the rotated rifle inside the frame
    gx = min(w * SS - rot.width, int([0.46, 0.48, 0.42][stage] * w * SS))
    gy = min(h * SS - rot.height, int([0.10, 0.06, 0.14][stage] * h * SS))
    c.img.alpha_composite(rot, (max(0, gx), max(0, gy)))
    draw_hand(c, [0.24, 0.40, 0.30][stage] * w, [0.70, 0.60, 0.80][stage] * h,
              scale=min(w, h) / 160.0, angle=[-0.5, -0.2, -0.7][stage], holding_mag=(stage != 2))
    return c


# ------------------------------------------------------- the plasma pistol
def draw_plasma_pistol(w, h, energy=0.0, charged=0.0, flash=False):
    """Plasma pistol held in the right hand, twin emitter prongs facing
    away. Drawn in the idle frame's layout; about the top 57% is on screen.
    energy: core/coil brightness 0..1, charged: charge aura 0..1."""
    c = Canvas(w, h)
    X = lambda f: f * w
    Y = lambda f: f * h

    if charged > 0:
        aura(c, (X(0.5), Y(0.17)), w * (0.40 + 0.12 * charged), seed=charged)

    # sleeve and glove around the grip (mostly below the screen edge)
    c.poly([(X(0.28), Y(1.02)), (X(0.36), Y(0.72)), (X(0.88), Y(0.76)), (X(1.0), Y(1.02))],
           SLEEVE, SLEEVE_DARK, axis='x')
    c.poly([(X(0.28), Y(0.80)), (X(0.28), Y(0.56)), (X(0.76), Y(0.54)), (X(0.82), Y(0.78))], GLOVE, GLOVE_DARK)
    for i in range(4):
        y = Y(0.59 + i * 0.045)
        c.line([(X(0.29), y), (X(0.58), y + 1)], GLOVE_DARK, 1)

    # housing
    c.rrect([(X(0.18), Y(0.25)), (X(0.82), Y(0.62))], STEEL_LIGHT, PLASMA_DARK, r=9 * w / 160)
    c.rrect([(X(0.24), Y(0.30)), (X(0.76), Y(0.58))], PLASMA_BODY, shade(PLASMA_DARK, 0.85), r=7 * w / 160)
    # energy coils
    k = 0.45 + 0.55 * energy
    for fy in (0.35, 0.43, 0.51):
        c.rrect([(X(0.27), Y(fy)), (X(0.73), Y(fy + 0.04))], (8, 20, 30), (8, 20, 30), r=1)
        c.rrect([(X(0.29), Y(fy + 0.008)), (X(0.71), Y(fy + 0.032))],
                shade(PLASMA_CORE, k), shade(PLASMA_GLOW, k), r=1)
    # prongs with lit inner edges
    c.poly([(X(0.20), Y(0.30)), (X(0.27), Y(0.03)), (X(0.39), Y(0.0)), (X(0.41), Y(0.30))],
           STEEL_LIGHT, PLASMA_DARK, axis='x')
    c.poly([(X(0.59), Y(0.30)), (X(0.61), Y(0.0)), (X(0.73), Y(0.03)), (X(0.80), Y(0.30))],
           PLASMA_BODY, PLASMA_DARK, axis='x')
    c.line([(X(0.395), Y(0.02)), (X(0.405), Y(0.28))], shade(PLASMA_GLOW, k), 1.2)
    c.line([(X(0.605), Y(0.02)), (X(0.595), Y(0.28))], shade(PLASMA_GLOW, k), 1.2)
    # emitter core between the prongs
    r = w * (0.085 + 0.035 * energy + 0.05 * charged)
    radial(c, (X(0.5), Y(0.15)), r, r, [(20, 80, 170), PLASMA_GLOW, PLASMA_CORE, (255, 255, 255)])

    if flash:
        c.flare((X(0.5), Y(0.10)), w * 0.40, (30, 150, 240), spikes=6, seed=0.5)
        c.flare((X(0.5), Y(0.10)), w * 0.26, PLASMA_GLOW, spikes=6, seed=1.1)
        radial(c, (X(0.5), Y(0.10)), w * 0.11, w * 0.11, [PLASMA_GLOW, PLASMA_CORE, (255, 255, 255)])
    return c


def draw_pistol_frame(w, h, idle_w, idle_h, dx, dy, **kw):
    """Any pistol frame: the idle-layout pistol placed by origin offset so
    it doesn't jump between frames."""
    c = Canvas(w, h)
    c.compose(draw_plasma_pistol(idle_w, idle_h, **kw), dx, dy)
    return c


# ------------------------------------------------------------- quantize
def quantize(img, palette):
    """Map RGBA to palette indexes; alpha < 50% is transparent (index 0).
    Index 0 is the transparent colour, so opaque pixels never use it."""
    W, H = img.size
    px = img.load()
    cache = {}
    out = [[0] * W for _ in range(H)]

    def nearest(rgb):
        if rgb in cache:
            return cache[rgb]
        r, g, b = rgb
        best, bi = None, 1
        for i in range(1, len(palette)):
            pr, pg, pb = palette[i]
            # weighted RGB distance (rough perceptual weighting)
            d = 2 * (r - pr) ** 2 + 4 * (g - pg) ** 2 + 3 * (b - pb) ** 2
            if best is None or d < best:
                best, bi = d, i
        cache[rgb] = bi
        return bi

    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if a >= 128:
                # un-premultiply the edge pixels LANCZOS left darkened
                out[y][x] = nearest((r, g, b))
    return out


def preview(pixels, palette):
    H, W = len(pixels), len(pixels[0])
    im = Image.new('RGBA', (W, H))
    im.putdata([(0, 0, 0, 0) if v == 0 else palette[v] + (255,) for row in pixels for v in row])
    return im


# ---------------------------------------------------------------- frames
def frame_size(coll, lls_index):
    bm = coll.bitmaps[coll.lls[lls_index]['bitmap_index']]
    return bm['width'] * DENSITY, bm['height'] * DENSITY


def build(shapes_path, out_dir):
    data = open(shapes_path, 'rb').read()
    coll = st.read_collection(data, COLLECTION)
    palette = [(r >> 8, g >> 8, b >> 8) for (_, _, r, g, b) in coll.cluts[0]]

    # (low-level shape, drawing) -- the low-level shape picks the bitmap
    # slot and the on-screen placement we keep.
    def size(li):
        return frame_size(coll, li)

    def offset(li, ref):
        """Pixel offset that puts frame `ref`'s art at frame `li`'s origin."""
        a, b = coll.lls[li], coll.lls[ref]
        return ((a['origin_x'] - b['origin_x']) * DENSITY, (a['origin_y'] - b['origin_y']) * DENSITY)

    rw, rh = size(24)
    pw, ph = size(30)
    frames = {
        # burst rifle (assault rifle slot); 24's bitmap is also the 2nd firing frame
        24: lambda w, h: draw_rifle_rear(w, h),
        25: lambda w, h: draw_rifle_firing(w, h, rw, rh, *offset(25, 24)),
        27: lambda w, h: draw_rifle_reload(w, h, 0),
        28: lambda w, h: draw_rifle_reload(w, h, 1),
        29: lambda w, h: draw_rifle_reload(w, h, 2),
        # plasma pistol (fusion pistol slot); 30's bitmap also flashes with 51 when charged
        30: lambda w, h: draw_plasma_pistol(w, h, energy=0.25),
        31: lambda w, h: draw_pistol_frame(w, h, pw, ph, *offset(31, 30), energy=1.0, flash=True),
        32: lambda w, h: draw_pistol_frame(w, h, pw, ph, *offset(32, 30), energy=0.75),
        33: lambda w, h: draw_pistol_frame(w, h, pw, ph, *offset(33, 30), energy=0.5),
        51: lambda w, h: draw_pistol_frame(w, h, pw, ph, *offset(51, 30), energy=1.0, charged=1.0),
    }

    bitmaps, lls_out = {}, {}
    os.makedirs(out_dir, exist_ok=True)
    sheet = []
    for li, draw in frames.items():
        w, h = frame_size(coll, li)
        img = grain(draw(w, h).result())
        pix = quantize(img, palette)
        bi = coll.lls[li]['bitmap_index']
        bitmaps[bi] = st.bitmap_record(pix)
        prev = preview(pix, palette)
        prev.save(os.path.join(out_dir, 'frame_%02d.png' % li))
        sheet.append(prev)

    # Every low-level shape that uses a redrawn bitmap gets its pixel
    # placement scaled to the new density; its world box stays the same,
    # so the frames land where the originals did.
    redrawn = set(bitmaps)
    for li, d in enumerate(coll.lls):
        if d['bitmap_index'] in redrawn:
            n = dict(d)
            for k in ('origin_x', 'origin_y', 'key_x', 'key_y'):
                n[k] = d[k] * DENSITY
            lls_out[li] = n

    patch = st.write_patch(COLLECTION, bitmaps=bitmaps, lls=lls_out)
    with open(os.path.join(out_dir, 'vanguard_weapons.shpp'), 'wb') as f:
        f.write(patch)

    # contact sheet for review
    W = sum(i.width for i in sheet) + 8 * len(sheet)
    H = max(i.height for i in sheet)
    cs = Image.new('RGBA', (W, H), (48, 48, 52, 255))
    x = 0
    for i in sheet:
        cs.alpha_composite(i, (x, H - i.height))
        x += i.width + 8
    cs.save(os.path.join(out_dir, 'contact_sheet.png'))
    print('wrote %d bitmaps, %d low-level shapes, %d bytes' % (len(bitmaps), len(lls_out), len(patch)))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2])
