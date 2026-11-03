"""Devpost image gallery: 3:2 (1800x1200) captioned images built from frames of the real app recording.

Usage: python gallery.py  (after record.py; writes ../SENTINEL_Gallery/*.jpg)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from build_video import BLUE, CYAN, MUTED, PURPLE, WHITE, background, font, run

HERE = Path(__file__).resolve().parent
SRC = HERE / "generated" / "gallery_src"
OUT = HERE.parent / "SENTINEL_Gallery"
GW, GH = 1800, 1200

# (file, footage clip, second into the clip, title, subtitle[, 16:9 crop box])
SHOTS = [
    ("02_command_centre", "s2_solution", 15.0, "Real-time Command Centre",
     "Volume, risk mix and model performance across 2,000 synthetic payments"),
    ("03_paypal_checkout", "s3_paypal", 15.0, "PayPal Orders API checkout",
     "Server-side Sandbox orders; shown here honestly as not configured", (390, 0, 1670, 720)),
    ("04_ml_shap", "s4_ml", 10.0, "ML risk score + SHAP explanation",
     "Random Forest probability, anomaly percentile and per-feature drivers"),
    ("05_fraud_network", "s5_graph", 27.0, "Graph intelligence: a fraud ring",
     "One device shared by four accounts paying a flagged mule wallet"),
    ("06_ai_agent", "s6_agent", 9.5, "LangGraph AI investigation agent",
     "Seven tools, evidence-cited findings, recommendation only"),
    ("07_human_review", "s7_review", 12.0, "Human-in-the-loop decision",
     "Password re-entry and typed transaction ID before any action"),
    ("08_audit_trail", "s8_close", 6.0, "Hash-chained audit trail",
     "Every score, investigation and decision, tamper-evident"),
]


def frame(clip: str, t: float) -> Path:
    """Frame t seconds into the clip; a negative t counts back from its end."""
    dest = SRC / f"{clip}_{t:g}.png"
    run(["-sseof" if t < 0 else "-ss", str(t), "-i", f"footage/{clip}.webm", "-frames:v", "1", str(dest.relative_to(HERE))])
    return dest


def framed(img: Image.Image, shot: Image.Image, box: tuple[int, int, int, int], radius: int = 22) -> None:
    x0, y0, x1, y1 = box
    shot = shot.convert("RGBA").resize((x1 - x0, y1 - y0), Image.LANCZOS)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle([x0 - 10, y0 - 10, x1 + 10, y1 + 10], radius=radius + 10, fill=(*PURPLE, 110))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30)))
    mask = Image.new("L", shot.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, shot.size[0] - 1, shot.size[1] - 1], radius=radius, fill=255)
    img.paste(shot, (x0, y0), mask)
    ImageDraw.Draw(img).rounded_rectangle([x0, y0, x1 - 1, y1 - 1], radius=radius, outline=(*BLUE, 200), width=3)


def captioned(shot: Path, title: str, subtitle: str, dest: Path, crop=None) -> None:
    img = background(GW, GH).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.rectangle([60, 62, 130, 68], fill=(*CYAN, 255))
    d.text((58, 80), title, font=font("segoeuib.ttf", 58), fill=WHITE)
    d.text((60, 160), subtitle, font=font("seguisb.ttf", 30), fill=MUTED)
    src = Image.open(shot)
    framed(img, src.crop(crop) if crop else src, (60, 225, GW - 60, 225 + int((GW - 120) * 9 / 16)))
    img.convert("RGB").save(dest, quality=92, optimize=True)


def cover(graph_frame: Path, dest: Path) -> None:
    img = background(GW, GH).convert("RGBA")
    shot = Image.open(graph_frame).crop((310, 190, 1340, 980))
    framed(img, shot, (900, 300, 1740, 944), 28)
    d = ImageDraw.Draw(img)
    d.rectangle([90, 300, 180, 308], fill=(*CYAN, 255))
    d.text((86, 325), "PROJECT", font=font("segoeuib.ttf", 104), fill=WHITE)
    d.text((86, 440), "SENTINEL", font=font("segoeuib.ttf", 132), fill=WHITE)
    d.text((92, 615), "AI-Powered Payment", font=font("seguisb.ttf", 52), fill=(147, 197, 253))
    d.text((92, 682), "Risk Intelligence", font=font("seguisb.ttf", 52), fill=(147, 197, 253))
    d.rounded_rectangle([92, 800, 560, 858], radius=29, fill=(*BLUE, 255))
    d.text((120, 808), "PayPal Sandbox + AI", font=font("seguisb.ttf", 31), fill=WHITE)
    d.text((92, 1070), "ML  ·  Graph intelligence  ·  LangGraph agent  ·  Human review  ·  Audit trail",
           font=font("seguisb.ttf", 28), fill=MUTED)
    img.convert("RGB").save(dest, quality=92, optimize=True)


def main() -> None:
    SRC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    cover(frame("s5_graph", -2), OUT / "01_cover.jpg")
    for name, clip, t, title, sub, *crop in SHOTS:
        captioned(frame(clip, t), title, sub, OUT / f"{name}.jpg", *crop)
        print("ok", name)


if __name__ == "__main__":
    main()
