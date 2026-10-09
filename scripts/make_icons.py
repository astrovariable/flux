"""Draw the Flux light-curve icon as PNG files (run once; needs Pillow)."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "docs" / "icons"
LAV, NAVY = (212, 194, 245), (35, 43, 58)

def draw(size, maskable=False, radius=True):
    s = 4  # draw big, then shrink, for smooth edges
    W = size * s
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if radius and not maskable:
        d.rounded_rectangle([0, 0, W - 1, W - 1], radius=int(W * 0.23), fill=LAV)
    else:
        d.rectangle([0, 0, W, W], fill=LAV)
    k = 0.78 if maskable else 1.0          # keep art inside the safe zone for maskable icons
    off = W * (1 - k) / 2
    P = lambda x, y: (off + x / 100 * W * k, off + y / 100 * W * k)
    lw = int(W * k * 0.045)
    pts = [P(14, 68), P(40, 68), P(48, 32), P(54, 60), P(60, 64), P(86, 64)]
    d.line(pts, fill=NAVY, width=lw, joint="curve")
    for x, y in (pts[0], pts[-1]):
        r = lw / 2; d.ellipse([x - r, y - r, x + r, y + r], fill=NAVY)
    base = NAVY + (90,)
    over = Image.new("RGBA", img.size, (0, 0, 0, 0)); od = ImageDraw.Draw(over)
    bw = int(W * k * 0.025)
    od.line([P(14, 80), P(86, 80)], fill=base, width=bw)
    for x, y in (P(14, 80), P(86, 80)):
        r = bw / 2; od.ellipse([x - r, y - r, x + r, y + r], fill=base)
    img = Image.alpha_composite(img, over); d = ImageDraw.Draw(img)
    cx, cy = 48, 21.2
    star = [(cx, cy - 8.2), (cx + 2.2, cy - 2.2), (cx + 8.2, cy), (cx + 2.2, cy + 2.2), (cx, cy + 8.2), (cx - 2.2, cy + 2.2), (cx - 8.2, cy), (cx - 2.2, cy - 2.2)]
    d.polygon([P(x, y) for x, y in star], fill=NAVY)
    return img.resize((size, size), Image.LANCZOS)

OUT.mkdir(parents=True, exist_ok=True)
draw(192).save(OUT / "icon-192.png")
draw(512).save(OUT / "icon-512.png")
draw(512, maskable=True).save(OUT / "icon-maskable-512.png")
draw(180, radius=False).save(OUT / "apple-touch-icon.png")
print("icons written to", OUT)
