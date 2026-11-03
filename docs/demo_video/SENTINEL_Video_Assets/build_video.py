"""Assemble SENTINEL_Hackathon_Demo.mp4 from the generated voiceover (audio/), the genuine screen
recordings (footage/) and generated graphics/music. Run tts.py and record.py first.

Outputs (in docs/demo_video/): SENTINEL_Hackathon_Demo.mp4, SENTINEL_Subtitles.srt,
SENTINEL_Voiceover_Script.txt, SENTINEL_Thumbnail.png.
"""
import json
import math
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
GEN = HERE / "generated"
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1920, 1080, 30
LEAD, TAIL, XF = 0.5, 0.9, 0.5  # voice starts LEAD s into a scene; TAIL s after it ends; crossfade XF s
FONTS = HERE / "fonts"

NAVY, NAVY2 = (7, 11, 26), (12, 24, 52)
BLUE, PURPLE, CYAN, WHITE, MUTED = (59, 130, 246), (139, 92, 246), (34, 211, 238), (240, 244, 250), (150, 166, 196)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def run(args: list[str]) -> None:
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *args], cwd=HERE, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-3000:])


# ------------------------------------------------------------------ graphics
def background(w=W, h=H) -> Image.Image:
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(0, 1, w)[None, :]
    base = np.zeros((h, w, 3))
    for c in range(3):
        base[..., c] = NAVY[c] + (NAVY2[c] - NAVY[c]) * (0.6 * y + 0.4 * x)
    for (cx, cy, r, col, a) in ((0.82, 0.18, 0.55, PURPLE, 0.30), (0.10, 0.95, 0.60, BLUE, 0.22)):
        d = np.sqrt(((x - cx) * w / h) ** 2 + (y - cy) ** 2)
        g = np.clip(1 - d / r, 0, 1) ** 2 * a
        for c in range(3):
            base[..., c] = base[..., c] * (1 - g) + col[c] * g
    return Image.fromarray(base.clip(0, 255).astype(np.uint8))


def network(img: Image.Image, cx: int, cy: int, scale: float, alpha: int = 255) -> None:
    """Stylised version of the real Demo C ring: 4 accounts on one device, paying one flagged wallet."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    s = scale
    dev, wal = (cx, cy - 40 * s), (cx, cy + 190 * s)
    custs = [(cx - 230 * s, cy - 170 * s), (cx + 230 * s, cy - 170 * s), (cx - 260 * s, cy + 90 * s), (cx + 260 * s, cy + 90 * s)]
    others = [(cx - 420 * s, cy - 40 * s), (cx + 420 * s, cy - 60 * s), (cx - 120 * s, cy - 320 * s), (cx + 150 * s, cy - 330 * s)]
    for o, c in zip(others, custs):
        d.line([o, c], fill=(*MUTED, int(alpha * 0.35)), width=max(1, int(2 * s)))
    for c in custs:
        d.line([c, dev], fill=(244, 63, 94, alpha), width=max(2, int(4 * s)))
        d.line([c, wal], fill=(244, 63, 94, int(alpha * 0.7)), width=max(1, int(3 * s)))
    for o in others:
        r = 16 * s
        d.ellipse([o[0] - r, o[1] - r, o[0] + r, o[1] + r], fill=(*NAVY2, alpha), outline=(52, 211, 153, alpha), width=max(1, int(3 * s)))
    for c in custs:
        r = 26 * s
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(*NAVY2, alpha), outline=(244, 63, 94, alpha), width=max(2, int(4 * s)))
    r = 34 * s
    d.rounded_rectangle([dev[0] - r, dev[1] - r, dev[0] + r, dev[1] + r], radius=int(10 * s), fill=(*NAVY2, alpha),
                        outline=(*CYAN, alpha), width=max(2, int(5 * s)))
    d.polygon([(wal[0], wal[1] - r), (wal[0] + r, wal[1]), (wal[0], wal[1] + r), (wal[0] - r, wal[1])],
              fill=(*NAVY2, alpha), outline=(244, 63, 94, alpha))
    glow = layer.filter(ImageFilter.GaussianBlur(int(10 * s)))
    img.alpha_composite(glow)
    img.alpha_composite(layer)


def title_card(path: Path) -> None:
    img = background().convert("RGBA")
    network(img, 1450, 520, 1.1, 200)
    d = ImageDraw.Draw(img)
    d.rectangle([140, 300, 230, 306], fill=(*BLUE, 255))
    d.text((140, 330), "PROJECT SENTINEL", font=font("segoeuib.ttf", 104), fill=WHITE)
    d.text((144, 470), "Autonomous AI-Powered Payment Risk", font=font("seguisb.ttf", 40), fill=(200, 212, 235))
    d.text((144, 522), "Intelligence & Protection Platform", font=font("seguisb.ttf", 40), fill=(200, 212, 235))
    d.text((144, 620), "“Every Transaction. Every Connection. Every Risk. Understood.”", font=font("segoeuii.ttf", 30), fill=(147, 197, 253))
    d.text((144, 900), "PayPal AI Hackathon 2026", font=font("seguisb.ttf", 26), fill=MUTED)
    img.convert("RGB").save(path)


def closing_card(path: Path) -> None:
    img = background().convert("RGBA")
    network(img, 960, 250, 0.5, 150)
    d = ImageDraw.Draw(img)

    def center(y, text, f, fill):
        w = d.textlength(text, font=f)
        d.text(((W - w) / 2, y), text, font=f, fill=fill)

    center(430, "SENTINEL", font("segoeuib.ttf", 96), WHITE)
    center(556, "Every Transaction. Every Connection. Every Risk. Understood.", font("segoeuii.ttf", 34), (147, 197, 253))
    center(650, "github.com/Tanisha-dey18/hackathon", font("seguisb.ttf", 30), (200, 212, 235))
    center(698, "Live demo: sentinel-payment-risk.netlify.app", font("seguisb.ttf", 30), (200, 212, 235))
    center(780, "PayPal Sandbox · synthetic demo data · built for the PayPal AI Hackathon 2026", font("segoeui.ttf", 24), MUTED)
    img.convert("RGB").save(path)


def chip(path: Path, text: str) -> None:
    f = font("seguisb.ttf", 30)
    tw = int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=f))
    img = Image.new("RGBA", (tw + 64, 66), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, tw + 63, 65], radius=14, fill=(8, 14, 32, 225), outline=(*BLUE, 160), width=2)
    d.rounded_rectangle([0, 0, 8, 65], radius=4, fill=(*PURPLE, 255))
    d.text((34, 13), text, font=f, fill=WHITE)
    img.save(path)


def thumbnail(path: Path, graph_frame: Path) -> None:
    img = background().convert("RGBA")
    shot = Image.open(graph_frame).convert("RGBA")
    shot = shot.crop((310, 190, 1340, 980)).resize((900, 690))
    mask = Image.new("L", shot.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, shot.size[0] - 1, shot.size[1] - 1], radius=28, fill=255)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle([930, 180, 1850, 890], radius=36, fill=(*PURPLE, 140))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
    img.paste(shot, (940, 190), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([940, 190, 1839, 879], radius=28, outline=(*BLUE, 220), width=4)
    d.rectangle([110, 300, 200, 308], fill=(*CYAN, 255))
    d.text((106, 330), "PROJECT", font=font("segoeuib.ttf", 120), fill=WHITE)
    d.text((106, 460), "SENTINEL", font=font("segoeuib.ttf", 150), fill=WHITE)
    d.text((112, 650), "AI-Powered Payment", font=font("seguisb.ttf", 58), fill=(147, 197, 253))
    d.text((112, 724), "Risk Intelligence", font=font("seguisb.ttf", 58), fill=(147, 197, 253))
    d.rounded_rectangle([112, 840, 600, 900], radius=30, fill=(*BLUE, 255))
    d.text((140, 849), "PayPal Sandbox + AI", font=font("seguisb.ttf", 32), fill=WHITE)
    img.convert("RGB").save(path, optimize=True)


# ------------------------------------------------------------------ music (original, generated)
def music(path: Path, seconds: float, sr: int = 44100) -> None:
    """Soft ambient pad: slow detuned-sine chords (Am - F - C - G) with gentle swells."""
    n = int(seconds * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    chords = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 55, 60, 64], [55, 59, 62, 67]]
    bar = 8.0
    for i in range(int(math.ceil(seconds / bar)) + 1):
        notes = chords[i % 4]
        start = i * bar
        s0, s1 = int(max(0, (start - 1.5) * sr)), int(min(n, (start + bar + 1.5) * sr))
        if s0 >= s1:
            continue
        tt = t[s0:s1] - (start - 1.5)
        env = np.sin(np.clip(tt / (bar + 3.0), 0, 1) * math.pi) ** 1.5
        for m in notes:
            f = 440 * 2 ** ((m - 69) / 12)
            for det in (-0.12, 0.0, 0.12):
                ph = 2 * math.pi * f * (1 + det / 100) * t[s0:s1]
                out[s0:s1] += env * (np.sin(ph) + 0.25 * np.sin(2 * ph)) / 12
        bass = 440 * 2 ** ((notes[0] - 12 - 69) / 12)
        out[s0:s1] += env * 0.5 * np.sin(2 * math.pi * bass * t[s0:s1]) / 6
    k = 400  # gentle low-pass
    out = np.convolve(out, np.ones(k) / k, mode="same")
    out *= 0.9 / (np.abs(out).max() + 1e-9)
    fade = int(3 * sr)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    st = np.stack([out, np.roll(out, int(0.012 * sr))], axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((st * 32767 * 0.6).astype(np.int16).tobytes())


# ------------------------------------------------------------------ subtitles
def chunk_cue(cue: dict, max_chars: int = 84) -> list[dict]:
    words = cue["text"].split()
    chunks, cur = [], []
    for w in words:
        if cur and len(" ".join(cur + [w])) > max_chars:
            chunks.append(cur)
            cur = []
        cur.append(w)
    chunks.append(cur)
    total = sum(len(" ".join(c)) for c in chunks)
    out, t = [], cue["start"]
    span = cue["end"] - cue["start"]
    for c in chunks:
        txt = " ".join(c)
        d = span * len(txt) / total
        out.append({"start": t, "end": t + d, "text": txt})
        t += d
    return out


def wrap2(text: str, width: int = 44) -> str:
    if len(text) <= width:
        return text
    words, best = text.split(), None
    for i in range(1, len(text.split())):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = max(len(a), len(b))
        if best is None or score < best[0]:
            best = (score, a, b)
    return best[1] + "\n" + best[2]


def ts(sec: float, sep=",") -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}"


def ass_ts(sec: float) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


# ------------------------------------------------------------------ build
def main() -> None:
    GEN.mkdir(exist_ok=True)
    cfg = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
    scenes = cfg["scenes"]
    timing = json.loads((HERE / "footage" / "timing.json").read_text(encoding="utf-8"))
    cues = {s["id"]: json.loads((HERE / "audio" / f"{s['id']}.json").read_text(encoding="utf-8")) for s in scenes}
    narr = {k: v[-1]["end"] for k, v in cues.items()}

    title_card(GEN / "title.png")
    closing_card(GEN / "closing.png")
    for s in scenes:
        if s["label"]:
            chip(GEN / f"chip_{s['id']}.png", s["label"])

    # scene lengths and start times
    T = {s["id"]: narr[s["id"]] + LEAD + TAIL for s in scenes}
    T["s8_close"] += 2.0  # hold the closing card
    starts, t = {}, 0.0
    for s in scenes:
        starts[s["id"]] = t
        t += T[s["id"]] - XF
    total = t + XF

    # ---- per-scene video clips
    def probe_duration(p: Path) -> float:
        r = subprocess.run([FF, "-i", str(p)], capture_output=True, text=True)
        hms = r.stderr.split("Duration: ")[1].split(",")[0]
        h, m, s = hms.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    zoom = "zoompan=z='1+0.035*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}"

    def still_clip(img: Path, dur: float, out: Path, fade_in: bool = False) -> None:
        n = int(dur * FPS)
        vf = zoom.format(n=n, w=W, h=H, fps=FPS) + (",fade=in:st=0:d=1.0" if fade_in else "") + ",format=yuv420p"
        run(["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(img.relative_to(HERE)), "-vf", vf,
             "-frames:v", str(n), "-c:v", "libx264", "-crf", "18", "-preset", "medium", str(out.relative_to(HERE))])

    def footage_clip(sid: str, dur: float, out: Path, max_len: float | None = None) -> None:
        src = HERE / "footage" / f"{sid}.webm"
        length = timing[sid]["length"] if max_len is None else min(max_len, timing[sid]["length"])
        start = max(0.0, probe_duration(src) - timing[sid]["length"])
        speed = max(1.0, min(1.45, length / dur))
        n = int(dur * FPS)
        vf = (f"trim=start={start:.2f}:duration={length:.2f},setpts=(PTS-STARTPTS)/{speed:.4f},fps={FPS},"
              f"tpad=stop_mode=clone:stop_duration=5,trim=duration={dur:.3f},setpts=PTS-STARTPTS,"
              + zoom.format(n=n, w=W, h=H, fps=FPS))
        chip_png = GEN / f"chip_{sid}.png"
        inputs = ["-i", str(src.relative_to(HERE))]
        if chip_png.exists():
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(chip_png.relative_to(HERE))]
            fc = (f"[0:v]{vf}[v];[1:v]format=rgba,fade=in:st=0.7:d=0.5:alpha=1,fade=out:st={min(dur - 0.6, 6.5):.2f}:d=0.6:alpha=1[c];"
                  f"[v][c]overlay=48:H-268:shortest=1,format=yuv420p[o]")
        else:
            fc = f"[0:v]{vf},format=yuv420p[o]"
        run([*inputs, "-filter_complex", fc, "-map", "[o]", "-frames:v", str(n), "-c:v", "libx264", "-crf", "18",
             "-preset", "medium", str(out.relative_to(HERE))])

    clips = []
    still_clip(GEN / "title.png", T["s1_intro"], GEN / "c1.mp4", fade_in=True)
    clips.append((GEN / "c1.mp4", T["s1_intro"]))
    for i, sid in enumerate(["s2_solution", "s3_paypal", "s4_ml", "s5_graph", "s6_agent", "s7_review"], start=2):
        footage_clip(sid, T[sid], GEN / f"c{i}.mp4")
        clips.append((GEN / f"c{i}.mp4", T[sid]))
        print("clip", sid, round(T[sid], 1), "s")
    audit_len = 7.0
    footage_clip("s8_close", audit_len, GEN / "c8a.mp4", max_len=audit_len + 1.5)
    still_clip(GEN / "closing.png", T["s8_close"] - audit_len + XF, GEN / "c8b.mp4")
    clips.append((GEN / "c8a.mp4", audit_len))
    clips.append((GEN / "c8b.mp4", T["s8_close"] - audit_len + XF))

    # ---- music + subtitles
    music(GEN / "music.wav", total + 1)
    srt, ass_lines, idx = [], [], 1
    for s in scenes:
        for cue in cues[s["id"]]:
            for c in chunk_cue(cue):
                a = starts[s["id"]] + LEAD + c["start"]
                b = starts[s["id"]] + LEAD + c["end"]
                txt = wrap2(c["text"])
                srt.append(f"{idx}\n{ts(a)} --> {ts(b)}\n{txt}\n")
                ass_lines.append(f"Dialogue: 0,{ass_ts(a)},{ass_ts(b)},Sub,,0,0,0,,{txt.replace(chr(10), chr(92) + 'N')}")
                idx += 1
    (OUT / "SENTINEL_Subtitles.srt").write_text("\n".join(srt), encoding="utf-8")
    ass = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n\n"
           "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
           "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding\n"
           "Style: Sub,Segoe UI Semibold,44,&H00FFFFFF,&H00FFFFFF,&H30120A06,&H00000000,0,0,0,0,100,100,0,0,3,12,0,2,200,200,52,1\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" + "\n".join(ass_lines) + "\n")
    (GEN / "subs.ass").write_text(ass, encoding="utf-8")

    # ---- voiceover script file
    lines = [f"SENTINEL demo voiceover ({cfg['voice']}, rate {cfg['rate']})", ""]
    for s in scenes:
        lines += [f"[{ts(starts[s['id']] + LEAD, '.')[:-4]}] {s['id']}", s["text"], ""]
    (OUT / "SENTINEL_Voiceover_Script.txt").write_text("\n".join(lines), encoding="utf-8")

    # ---- final assembly: xfade chain + subtitles, voice + ducked music
    inputs, fc, prev, acc = [], [], "0:v", clips[0][1]
    for c, _ in clips:
        inputs += ["-i", str(c.relative_to(HERE))]
    for i in range(1, len(clips)):
        off = acc - XF
        fc.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]")
        prev, acc = f"x{i}", off + clips[i][1]
    fc.append(f"[{prev}]subtitles=generated/subs.ass:fontsdir=fonts,fade=out:st={total - 1.2:.2f}:d=1.2[vout]")
    a0 = len(clips)
    for s in scenes:
        inputs += ["-i", str((HERE / "audio" / f"{s['id']}.mp3").relative_to(HERE))]
    inputs += ["-i", str((GEN / "music.wav").relative_to(HERE))]
    for j, s in enumerate(scenes):
        ms = int((starts[s["id"]] + LEAD) * 1000)
        fc.append(f"[{a0 + j}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms}[n{j}]")
    fc.append("".join(f"[n{j}]" for j in range(len(scenes))) + f"amix=inputs={len(scenes)}:normalize=0,apad[voice]")
    fc.append("[voice]asplit=2[vk][vm]")
    fc.append(f"[{a0 + len(scenes)}:a]volume=0.14[mus]")
    fc.append("[mus][vk]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=500[duck]")
    fc.append(f"[vm][duck]amix=inputs=2:normalize=0,atrim=0:{total:.3f},afade=t=out:st={total - 1.5:.2f}:d=1.5,"
              "loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    run([*inputs, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-r", str(FPS),
         "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-ar", "48000", "-movflags", "+faststart", "../SENTINEL_Hackathon_Demo.mp4"])

    # ---- thumbnail from a genuine graph frame
    frame = GEN / "graph_frame.png"
    src = HERE / "footage" / "s5_graph.webm"
    run(["-sseof", "-2", "-i", str(src.relative_to(HERE)), "-frames:v", "1", str(frame.relative_to(HERE))])
    thumbnail(OUT / "SENTINEL_Thumbnail.png", frame)
    print(f"done: total {total:.1f}s")


if __name__ == "__main__":
    main()
