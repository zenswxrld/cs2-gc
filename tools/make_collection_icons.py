"""Draw the custom collections' set emblems (CS2 style: a bevelled diamond badge with a glyph and the name).

Run once by a developer; the PNGs in tools/collection_icons are committed and packed by native_finishes.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent / 'collection_icons'
SIZE, SCALE = 256, 4
FONT = '/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf'
# name: (top colour, bottom colour, accent)
THEMES = {
    'ashfall': ((120, 118, 116), (52, 48, 46), (255, 132, 54)),
    'aurora': ((64, 214, 160), (88, 52, 170), (210, 255, 240)),
    'brimstone': ((236, 76, 40), (110, 16, 16), (255, 214, 80)),
    'cascade': ((70, 190, 240), (18, 70, 150), (230, 250, 255)),
    'cinder': ((255, 150, 60), (60, 30, 22), (255, 236, 170)),
    'eclipse': ((40, 40, 52), (8, 8, 14), (255, 196, 70)),
    'halcyon': ((150, 220, 255), (40, 120, 200), (255, 255, 255)),
    'kaleido': ((250, 90, 200), (60, 90, 230), (255, 240, 120)),
    'monsoon': ((46, 110, 150), (14, 34, 66), (150, 230, 255)),
    'nebula': ((180, 70, 230), (40, 14, 90), (255, 170, 240)),
    'solstice': ((255, 200, 60), (210, 90, 20), (255, 255, 220)),
    'zephyr': ((140, 240, 210), (30, 140, 140), (255, 255, 255)),
}


def glyph(draw, name, c, s, colour):
    """A simple symbol for each collection, centred at c, scale s."""
    x, y = c
    w = max(2, int(s * .09))
    if name == 'ashfall':
        draw.polygon([(x - s * .45, y + s * .3), (x - s * .1, y - s * .25), (x + s * .1, y - s * .25), (x + s * .45, y + s * .3)], fill=colour)
        for dx, dy in ((-.25, -.55), (.05, -.7), (.3, -.5)): draw.ellipse([x + dx * s - w, y + dy * s - w, x + dx * s + w, y + dy * s + w], fill=colour)
    elif name == 'aurora':
        for i in range(3):
            pts = [(x - s * .5 + t * s / 20, y - s * .3 + i * s * .28 + math.sin(t / 3 + i) * s * .1) for t in range(21)]
            draw.line(pts, fill=colour, width=w)
    elif name in ('brimstone', 'cinder'):
        draw.polygon([(x, y - s * .55), (x + s * .32, y), (x + s * .2, y + s * .35), (x - s * .2, y + s * .35), (x - s * .32, y)], fill=colour)
        if name == 'cinder':
            for dx, dy in ((-.4, -.4), (.42, -.3), (.35, .45)): draw.ellipse([x + dx * s - w, y + dy * s - w, x + dx * s + w, y + dy * s + w], fill=colour)
    elif name == 'cascade':
        for i in range(3): draw.line([(x - s * .4, y - s * .4 + i * s * .3), (x, y - s * .15 + i * s * .3), (x + s * .4, y - s * .4 + i * s * .3)], fill=colour, width=w)
    elif name == 'eclipse':
        draw.ellipse([x - s * .42, y - s * .42, x + s * .42, y + s * .42], fill=colour)
        draw.ellipse([x - s * .32, y - s * .48, x + s * .5, y + s * .34], fill=(0, 0, 0, 0))
    elif name == 'halcyon':
        draw.line([(x - s * .5, y), (x - s * .15, y - s * .3), (x, y - s * .05), (x + s * .15, y - s * .3), (x + s * .5, y)], fill=colour, width=w)
        draw.line([(x - s * .3, y + s * .25), (x, y + s * .05), (x + s * .3, y + s * .25)], fill=colour, width=w)
    elif name == 'kaleido':
        pts = [(x + math.cos(a) * s * (.5 if i % 2 == 0 else .22), y + math.sin(a) * s * (.5 if i % 2 == 0 else .22))
               for i, a in enumerate(math.radians(-90 + k * 30) for k in range(12))]
        draw.polygon(pts, fill=colour)
    elif name == 'monsoon':
        draw.ellipse([x - s * .45, y - s * .5, x + s * .1, y - s * .05], fill=colour)
        draw.ellipse([x - s * .15, y - s * .55, x + s * .45, y - s * .05], fill=colour)
        for i in range(4): draw.line([(x - s * .35 + i * s * .22, y + s * .05), (x - s * .45 + i * s * .22, y + s * .45)], fill=colour, width=w)
    elif name == 'nebula':
        for i in range(36):
            a, r = i * .5, s * .04 + i * s * .013
            d = w * (.4 + i / 50)
            draw.ellipse([x + math.cos(a) * r - d, y + math.sin(a) * r - d, x + math.cos(a) * r + d, y + math.sin(a) * r + d], fill=colour)
    elif name == 'solstice':
        draw.ellipse([x - s * .22, y - s * .22, x + s * .22, y + s * .22], fill=colour)
        for k in range(8):
            a = math.radians(k * 45)
            draw.line([(x + math.cos(a) * s * .32, y + math.sin(a) * s * .32), (x + math.cos(a) * s * .5, y + math.sin(a) * s * .5)], fill=colour, width=w)
    elif name == 'zephyr':
        for i, l in enumerate((.9, .7, .5)):
            yy = y - s * .3 + i * s * .3
            draw.line([(x - s * .5, yy), (x - s * .5 + s * l, yy)], fill=colour, width=w)
            draw.arc([x - s * .5 + s * l - s * .15, yy - s * .3, x - s * .5 + s * l + s * .15, yy], 90, 300, fill=colour, width=w)


def emblem(name, top, bottom, accent):
    n = SIZE * SCALE
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    mask = Image.new('L', (n, n), 0)
    c, r = n / 2, n * .47
    diamond = [(c, c - r), (c + r, c), (c, c + r), (c - r, c)]
    ImageDraw.Draw(mask).polygon(diamond, fill=255)
    grad = Image.new('RGBA', (n, n))
    gd = ImageDraw.Draw(grad)
    for yy in range(n):
        t = yy / n
        gd.line([(0, yy), (n, yy)], fill=tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3)) + (255,))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # Gloss on the upper half and a bevelled double border, like the stock set emblems.
    gloss = Image.new('L', (n, n), 0)
    ImageDraw.Draw(gloss).polygon([(c, c - r * .93), (c + r * .93, c), (c - r * .93, c)], fill=46)
    img.paste(Image.new('RGBA', (n, n), (255, 255, 255, 255)), (0, 0), Image.composite(gloss, Image.new('L', (n, n), 0), mask))
    d.polygon(diamond, outline=(20, 20, 24, 255), width=int(n * .035))
    inner = [(c, c - r * .84), (c + r * .84, c), (c, c + r * .84), (c - r * .84, c)]
    d.polygon(inner, outline=accent + (200,), width=int(n * .012))
    glyph(d, name, (c, c - r * .12), r * .62, accent + (255,))
    font = ImageFont.truetype(FONT, int(n * .072))
    label = name.upper()
    box = d.textbbox((0, 0), label, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    ty = c + r * .30
    d.text((c - tw / 2 + n * .006, ty + n * .006), label, font=font, fill=(0, 0, 0, 160))
    d.text((c - tw / 2, ty), label, font=font, fill=(255, 255, 255, 255))
    shadow = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    shadow.paste(Image.new('RGBA', (n, n), (0, 0, 0, 150)), (int(n * .012), int(n * .02)), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(n * .01))
    return Image.alpha_composite(shadow, img).resize((SIZE, SIZE), Image.LANCZOS)


def main():
    OUT.mkdir(exist_ok=True)
    for name, (top, bottom, accent) in THEMES.items():
        emblem(name, top, bottom, accent).save(OUT / ('set_cs2gc_case_%s.png' % name), optimize=True)


if __name__ == '__main__':
    main()
