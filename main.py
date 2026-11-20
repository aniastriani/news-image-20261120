#!/usr/bin/env python3
"""The World in One Image - Friday 20 November 2026.

A newspaper front page that sums up the day's world news in one picture.
Pure Python 3.13 standard library: a hand-drawn 5x7 bitmap font, simple
vector shapes for the illustrations, and a small PNG encoder written by
hand (zlib for compression, CRCs computed with binascii). No network, no
clock, no randomness, no external files - the same bytes come out on
every run.

Run it with:
    python3 main.py
The picture is written to /output/entry.png, or to $MAKEFUN_OUTPUT_DIR
when that variable is set.
"""

import os
import struct
import zlib
from binascii import crc32

# ---------------------------------------------------------------- canvas

WIDTH = 1024
HEIGHT = 1024

PAPER = (247, 243, 234)      # warm newsprint
PANEL = (255, 253, 246)      # slightly lighter panel fill
INK = (26, 26, 26)           # near-black ink
GREY = (110, 106, 96)        # secondary ink
RED = (172, 38, 28)          # masthead rule + justice kicker
NAVY = (28, 64, 116)         # diplomacy kicker
TEAL = (16, 104, 100)        # markets kicker
RUST = (150, 74, 22)         # conflict kicker
GREEN = (30, 104, 64)        # climate + health kickers
GOLD = (178, 134, 30)        # chart and flag accents
SKY = (120, 170, 205)        # globe sea
WHITE = (255, 255, 255)


class Sheet:
    """An RGB pixel buffer with a few drawing helpers."""

    def __init__(self, width, height, colour):
        self.w = width
        self.h = height
        self.px = bytearray(colour * (width * height))

    def put(self, x, y, colour):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = colour

    def block(self, x, y, w, h, colour):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = colour

    def outline(self, x, y, w, h, colour, thick=1):
        self.block(x, y, w, thick, colour)
        self.block(x, y + h - thick, w, thick, colour)
        self.block(x, y, thick, h, colour)
        self.block(x + w - thick, y, thick, h, colour)

    def hline(self, x, y, length, colour, thick=1):
        self.block(x, y, length, thick, colour)

    def vline(self, x, y, length, colour, thick=1):
        self.block(x, y, thick, length, colour)

    def line(self, x0, y0, x1, y1, colour, thick=1):
        """Bresenham line, thickened by stamping small squares."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            self.block(x - thick // 2, y - thick // 2, thick, thick, colour)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def disc(self, cx, cy, r, colour):
        """Filled circle, drawn row by row."""
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            half = int((r * r - dy * dy) ** 0.5)
            self.block(cx - half, yy, half * 2 + 1, 1, colour)

    def ring(self, cx, cy, r, colour, thick=2):
        for yy in range(cy - r, cy + r + 1):
            dy = yy - cy
            outer = int((r * r - dy * dy) ** 0.5)
            inner = int(max(0, (r - thick) ** 2 - dy * dy) ** 0.5)
            self.block(cx - outer, yy, outer - inner, 1, colour)
            self.block(cx + inner + 1, yy, outer - inner, 1, colour)


# ------------------------------------------------------------ bitmap font
# A 5-wide, 7-tall pixel font, drawn by hand. '#' is ink, '.' is empty.
# Only the characters the page needs are defined.

FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01111", "10000", "10000", "10111", "10001", "10001", "01110"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "11001", "10101", "10011", "10011", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    '0': ("01110", "10011", "10101", "11001", "10001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    '3': ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    '4': ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "00100", "00100", "00100"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': ("00000", "00000", "00000", "00000", "01100", "01100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ':': ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ';': ("00000", "01100", "01100", "00000", "01100", "01100", "01000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '?': ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    '%': ("11001", "11010", "00100", "01000", "10011", "10011", "00000"),
    '(': ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ')': ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    '/': ("00001", "00001", "00010", "00100", "01000", "10000", "10000"),
    '&': ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    '+': ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    '=': ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '"': ("01010", "01010", "01010", "00000", "00000", "00000", "00000"),
    '*': ("00000", "10101", "01110", "10101", "00000", "00000", "00000"),
}

CHAR_W = 5
CHAR_H = 7


def text_width(text, scale):
    """Pixel width of a string at a given scale, one pixel gap per glyph."""
    return len(text) * (CHAR_W * scale + scale) - scale


def draw_text(sheet, x, y, text, scale, colour, align="left"):
    """Draw a single line of text; align left, center or right on x."""
    w = text_width(text, scale)
    if align == "center":
        x -= w // 2
    elif align == "right":
        x -= w
    cx = x
    for ch in text:
        glyph = FONT.get(ch, FONT[' '])
        for row in range(CHAR_H):
            bits = glyph[row]
            for col in range(CHAR_W):
                if bits[col] == '1':
                    sheet.block(cx + col * scale, y + row * scale,
                                scale, scale, colour)
        cx += CHAR_W * scale + scale
    return w


def wrap(text, max_width, scale):
    """Greedy word wrap; returns a list of lines that fit max_width."""
    words = text.split(' ')
    lines = []
    current = ''
    for word in words:
        trial = word if not current else current + ' ' + word
        if text_width(trial, scale) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ------------------------------------------------------------ PNG encoder

def _chunk(kind, data):
    out = struct.pack('>I', len(data)) + kind + data
    out += struct.pack('>I', crc32(kind + data) & 0xFFFFFFFF)
    return out


def encode_png(sheet):
    """Encode the sheet as a PNG: 8-bit RGB, one filter byte per row."""
    raw = bytearray()
    for y in range(sheet.h):
        raw.append(0)  # filter: none
        start = (y * sheet.w) * 3
        raw += sheet.px[start:start + sheet.w * 3]
    ihdr = struct.pack('>IIBBBBB', sheet.w, sheet.h, 8, 2, 0, 0, 0)
    png = b'\x89PNG\r\n\x1a\n'
    png += _chunk(b'IHDR', ihdr)
    png += _chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    png += _chunk(b'IEND', b'')
    return png


# --------------------------------------------------------- illustrations

def draw_scales(sheet, x, y, w, h):
    """Scales of justice: post, beam, two pans, base."""
    cx = x + w // 2
    sheet.vline(cx, y + 6, h - 26, INK, 3)
    sheet.hline(x + 14, y + 12, w - 28, INK, 3)
    sheet.disc(cx, y + 10, 4, INK)
    for side in (-1, 1):
        px = cx + side * (w // 2 - 20)
        sheet.line(px, y + 12, px - 16, y + 40, INK, 2)
        sheet.line(px, y + 12, px + 16, y + 40, INK, 2)
        sheet.line(px - 16, y + 40, px + 16, y + 40, INK, 2)
        sheet.line(px - 14, y + 40, px - 8, y + 52, INK, 2)
        sheet.line(px + 14, y + 40, px + 8, y + 52, INK, 2)
        sheet.line(px - 8, y + 52, px + 8, y + 52, INK, 2)
    sheet.hline(cx - 26, y + h - 16, 52, INK, 3)
    sheet.hline(cx - 34, y + h - 10, 68, INK, 3)


def draw_summit(sheet, x, y, w, h):
    """Three flags on poles above a table line."""
    cols = [RED, NAVY, GOLD]
    for i, col in enumerate(cols):
        px = x + 40 + i * (w - 80) // 2
        sheet.vline(px, y + 6, h - 34, INK, 3)
        sheet.block(px + 3, y + 6, 34, 20, col)
        sheet.block(px + 3, y + 26, 34, 3, WHITE)
    sheet.hline(x + 10, y + h - 22, w - 20, INK, 3)
    sheet.block(x + w // 2 - 34, y + h - 18, 68, 4, INK)


def draw_market(sheet, x, y, w, h):
    """A falling chart: axes, descending line, red arrowhead."""
    ox, oy = x + 22, y + h - 20
    sheet.vline(ox, y + 8, h - 28, INK, 2)
    sheet.hline(ox, oy, w - 36, INK, 2)
    pts = []
    steps = 7
    for i in range(steps + 1):
        px = ox + 8 + i * (w - 60) // steps
        py = y + 16 + i * (h - 44) // steps + (i % 2) * 3
        pts.append((px, py))
    for a, b in zip(pts, pts[1:]):
        sheet.line(a[0], a[1], b[0], b[1], RED, 3)
    ex, ey = pts[-1]
    sheet.line(ex, ey, ex - 12, ey - 2, RED, 3)
    sheet.line(ex, ey, ex - 2, ey - 12, RED, 3)
    sheet.disc(pts[0][0], pts[0][1], 3, INK)
    draw_text(sheet, x + w - 62, y + 2, "-4.8%", 2, RED)


def draw_tower(sheet, x, y, w, h):
    """A skyscraper with a blast burst at its crown and drifting smoke."""
    cx = x + w // 2
    top = y + 22
    sheet.block(cx - 26, top, 52, h - 34, NAVY)
    for row in range(2):
        for col in range(3):
            sheet.block(cx - 18 + col * 14, top + 8 + row * 12, 8, 6, GOLD)
    sheet.block(cx - 26, top - 6, 52, 6, INK)
    bx, by = cx, top - 12
    for dx, dy in ((0, -10), (9, -7), (11, 2), (5, 9), (-5, 9),
                   (-11, 2), (-9, -7), (0, 0)):
        sheet.line(bx, by, bx + dx, by + dy, RED, 3)
    sheet.disc(bx, by, 4, RED)
    sheet.line(cx - 46, y + 6, cx - 58, y + 2, GREY, 2)
    sheet.line(cx - 44, y + 14, cx - 60, y + 12, GREY, 2)


def draw_globe(sheet, x, y, w, h):
    """A globe ringed by a crossed-out smokestack."""
    cx, cy = x + w // 2 - 30, y + h // 2
    r = h // 2 - 12
    sheet.disc(cx, cy, r, SKY)
    sheet.ring(cx, cy, r, INK, 2)
    sheet.block(cx - r + 8, cy - 8, 18, 12, GREEN)
    sheet.block(cx + 2, cy + 4, 20, 10, GREEN)
    sheet.block(cx - 4, cy - r + 6, 10, 10, GREEN)
    sx = x + w - 44
    sheet.block(sx, cy - 18, 26, 40, INK)
    sheet.block(sx + 4, cy - 26, 6, 8, GREY)
    sheet.block(sx + 16, cy - 26, 6, 8, GREY)
    sheet.line(sx - 6, cy + 26, sx + 32, cy - 30, RED, 4)


def draw_health(sheet, x, y, w, h):
    """A green badge with a white check, beside a small hospital cross."""
    cx = x + w // 2 - 40
    cy = y + h // 2
    sheet.disc(cx, cy, 30, GREEN)
    sheet.ring(cx, cy, 30, INK, 2)
    sheet.line(cx - 14, cy, cx - 4, cy + 10, WHITE, 4)
    sheet.line(cx - 4, cy + 10, cx + 16, cy - 12, WHITE, 4)
    hx = x + w - 56
    sheet.block(hx, cy - 22, 34, 44, WHITE)
    sheet.outline(hx, cy - 22, 34, 44, INK, 2)
    sheet.block(hx + 14, cy - 16, 6, 32, RED)
    sheet.block(hx + 5, cy - 7, 24, 6, RED)


ILLUSTRATIONS = {
    'scales': draw_scales,
    'summit': draw_summit,
    'market': draw_market,
    'tower': draw_tower,
    'globe': draw_globe,
    'health': draw_health,
}


# ------------------------------------------------------------- the stories

# kicker, kicker colour, headline, body, illustration key
STORIES = [
    ("THE HAGUE - JUSTICE", RED,
     "WORLD COURT: MYANMAR COMMITTED GENOCIDE",
     "The ICJ finds Myanmar committed genocide against the Rohingya in "
     "northern Rakhine, 9-6 - the court's first such ruling against a state.",
     'scales'),
    ("SHENZHEN - DIPLOMACY", NAVY,
     "TRUMP, XI AND PUTIN MEET IN SHENZHEN",
     "The first three-way summit ends with a four-point joint peace "
     "declaration from the three leaders.",
     'summit'),
    ("MARKETS - ECONOMY", TEAL,
     "STOCKS FALL FOR A FIFTH STRAIGHT DAY",
     "The S and P 500 is down about 2% and Japan's Nikkei down 4.8%, as "
     "AI-valuation doubts follow Anthropic's Nasdaq debut.",
     'market'),
    ("RIYADH - CONFLICT", RUST,
     "HOUTHI MISSILES HIT RIYADH TOWER",
     "Missiles damage the Public Investment Fund tower in the capital's "
     "financial district.",
     'tower'),
    ("ANTALYA - CLIMATE", GREEN,
     "COP31 DRAFT DROPS FOSSIL-FUEL PHASE-OUT",
     "The draft text in Antalya, Turkey carries no call to phase out "
     "fossil fuels.",
     'globe'),
    ("NAIROBI - HEALTH", GREEN,
     "KENYA'S LAST EBOLA PATIENT GOES HOME",
     "The final patient is discharged 37 days after the country's first "
     "case.",
     'health'),
]


# ------------------------------------------------------------------ layout

MARGIN = 24
PANEL_W = 472
PANEL_H = 268
GAP = 16
GRID_TOP = 152


def draw_masthead(sheet):
    sheet.hline(MARGIN, 22, WIDTH - 2 * MARGIN, INK, 2)
    draw_text(sheet, WIDTH // 2, 38, "THE WORLD IN ONE IMAGE", 7, INK,
              align="center")
    draw_text(sheet, WIDTH // 2, 100, "FRIDAY 20 NOVEMBER 2026", 3, RED,
              align="center")
    draw_text(sheet, WIDTH // 2, 126, "SIX STORIES FROM AROUND THE WORLD",
              2, GREY, align="center")
    sheet.hline(MARGIN, 146, WIDTH - 2 * MARGIN, INK, 4)


def draw_panel(sheet, story, px, py):
    kicker, colour, headline, body, art = story
    sheet.block(px, py, PANEL_W, PANEL_H, PANEL)
    sheet.outline(px, py, PANEL_W, PANEL_H, INK, 2)
    # Kicker band.
    sheet.block(px + 2, py + 2, PANEL_W - 4, 28, colour)
    draw_text(sheet, px + 14, py + 10, kicker, 2, WHITE)
    # Headline, wrapped to two lines at most.
    inner = PANEL_W - 28
    lines = wrap(headline, inner, 3)
    hy = py + 44
    for line in lines[:2]:
        draw_text(sheet, px + 14, hy, line, 3, INK)
        hy += 24
    # Body text (the font is capitals only, so the copy is set in caps).
    by = hy + 6
    for line in wrap(body.upper(), inner, 2)[:4]:
        draw_text(sheet, px + 14, by, line, 2, INK)
        by += 17
    # Illustration strip along the bottom of the panel.
    art_top = py + PANEL_H - 78
    sheet.hline(px + 14, art_top - 8, PANEL_W - 28, GREY, 1)
    ILLUSTRATIONS[art](sheet, px + 14, art_top, PANEL_W - 28, 70)


def draw_footer(sheet):
    sheet.hline(MARGIN, 994, WIDTH - 2 * MARGIN, INK, 2)
    draw_text(sheet, WIDTH // 2, 1000,
              "THE WORLD IN ONE IMAGE - FRIDAY 20 NOVEMBER 2026",
              1, GREY, align="center")


def build():
    sheet = Sheet(WIDTH, HEIGHT, PAPER)
    sheet.outline(8, 8, WIDTH - 16, HEIGHT - 16, INK, 2)
    draw_masthead(sheet)
    for i, story in enumerate(STORIES):
        col = i % 2
        row = i // 2
        px = MARGIN + col * (PANEL_W + GAP)
        py = GRID_TOP + row * (PANEL_H + GAP)
        draw_panel(sheet, story, px, py)
    draw_footer(sheet)
    return sheet


def main():
    out_dir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    os.makedirs(out_dir, exist_ok=True)
    data = encode_png(build())
    path = os.path.join(out_dir, 'entry.png')
    with open(path, 'wb') as f:
        f.write(data)
    print(f"wrote {path} ({len(data)} bytes)")


if __name__ == '__main__':
    main()
