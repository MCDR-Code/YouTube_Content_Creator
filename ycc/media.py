"""Wednesday, after the agents: build the actual files. Plain code, no language model.

  slides   Pillow draws each slide (channel colors, captions burned in)
  voice    offline text-to-speech: Windows voices through pyttsx3; if no voice engine exists,
           a silent track of the right length (clearly labeled) so the pipeline still runs
  video    ffmpeg (from imageio-ffmpeg) turns slides + voice into MP4s
  extras   3 thumbnail variants (1280x720), 3 vertical Shorts (1080x1920), an .srt caption file
Only text and shapes we draw ourselves are used, so there are no image or music rights issues.
"""
from __future__ import annotations

import os
import re
import subprocess
import textwrap
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY, WHITE, TEAL, GREY = (16, 28, 54), (255, 255, 255), (0, 168, 150), (170, 182, 204)
LONG_SIZE, SHORT_SIZE, THUMB_SIZE = (1280, 720), (1080, 1920), (1280, 720)
WORDS_PER_SECOND = 2.6
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font(size: int):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + r.stderr[-800:])


# ---------------- drawing ----------------
def _wrap(draw, text, fnt, max_w):
    lines = []
    for para in str(text).split("\n"):
        words, line = para.split(), ""
        for w in words:
            test = (line + " " + w).strip()
            if draw.textlength(test, font=fnt) <= max_w:
                line = test
            else:
                if line:
                    lines.append(line)
                line = w
        lines.append(line)
    return lines


def draw_slide(size, title, bullets, caption="", footer="AI and technology explained by a college professor"):
    w, h = size
    vertical = h > w
    img = Image.new("RGB", size, NAVY)
    d = ImageDraw.Draw(img)
    s = w / 1280 if not vertical else w / 1080
    d.rectangle([0, 0, w, int(14 * s)], fill=TEAL)
    tf, bf, cf, ff = font(int((96 if vertical else 54) * s)), font(int((56 if vertical else 34) * s)), \
        font(int((66 if vertical else 30) * s)), font(int((28 if vertical else 20) * s))
    x, y = int(70 * s), int((300 if vertical else 70) * s)
    for line in _wrap(d, title, tf, w - 2 * x)[:4]:
        d.text((x, y), line, font=tf, fill=WHITE)
        y += int(tf.size * 1.2)
    d.rectangle([x, y + 10, x + int(120 * s), y + 16], fill=TEAL)
    y += int(50 * s)
    for b in bullets[:4]:
        for i, line in enumerate(_wrap(d, b, bf, w - 2 * x - 40)[:3]):
            d.text((x + (0 if i else 0), y), ("•  " if i == 0 else "    ") + line, font=bf, fill=WHITE)
            y += int(bf.size * 1.3)
        y += int(12 * s)
    if caption:
        lines = _wrap(d, caption, cf, w - 2 * x)[:3]
        box_h = len(lines) * int(cf.size * 1.25) + 30
        top = h - box_h - int((560 if vertical else 60) * s)
        d.rectangle([x - 20, top, w - x + 20, top + box_h], fill=(0, 0, 0))
        ty = top + 15
        for line in lines:
            d.text((w // 2, ty), line, font=cf, fill=WHITE, anchor="ma")
            ty += int(cf.size * 1.25)
    d.text((x, h - int(36 * s)), footer, font=ff, fill=GREY)
    return img


def draw_thumbnail(text: str, path: Path, variant: int) -> Path:
    w, h = THUMB_SIZE
    accent = [TEAL, (255, 196, 0), (230, 80, 80)][variant % 3]
    img = Image.new("RGB", THUMB_SIZE, NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, h - 40, w, h], fill=accent)
    d.rectangle([0, 0, 24, h], fill=accent)
    f = font(110)
    lines = _wrap(d, text.upper(), f, w - 160)
    while len(lines) > 3 and f.size > 60:
        f = font(f.size - 10)
        lines = _wrap(d, text.upper(), f, w - 160)
    y = (h - 40 - len(lines) * int(f.size * 1.1)) // 2
    for line in lines[:4]:
        d.text((80, y), line, font=f, fill=WHITE)
        y += int(f.size * 1.1)
    d.text((80, 40), "PROFESSOR EXPLAINS", font=font(34), fill=accent)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


# ---------------- voice ----------------
def speak(text: str, out_wav: Path) -> tuple[float, str]:
    """Return (seconds, engine). Tries the offline Windows voice first."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pyttsx3
        eng = pyttsx3.init()
        eng.setProperty("rate", 165)
        eng.save_to_file(text, str(out_wav))
        eng.runAndWait()
        if out_wav.exists() and out_wav.stat().st_size > 1000:
            return _wav_seconds(out_wav), "pyttsx3"
    except Exception:  # noqa: BLE001
        pass
    seconds = max(1.5, len(text.split()) / WORDS_PER_SECOND)
    _run([ffmpeg(), "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", f"{seconds:.2f}", str(out_wav)])
    return seconds, "silent-placeholder"


def _wav_seconds(p: Path) -> float:
    try:
        with wave.open(str(p)) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:  # noqa: BLE001
        r = subprocess.run([ffmpeg(), "-i", str(p)], capture_output=True, text=True)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 3.0


# ---------------- video ----------------
def _chunks(text: str, n: int = 12) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + n]) for i in range(0, len(words), n)] or [""]


def _segment(size, title, bullets, narration, workdir: Path, name: str) -> tuple[Path, float, list[tuple]]:
    """One slide with its narration: captions change as the voice moves along."""
    wav = workdir / f"{name}.wav"
    seconds, engine = speak(narration, wav)
    parts = _chunks(narration)
    total_words = sum(len(p.split()) for p in parts) or 1
    lines, cues, t = [], [], 0.0
    for i, part in enumerate(parts):
        dur = max(0.5, seconds * len(part.split()) / total_words)
        png = workdir / f"{name}_{i:02d}.png"
        draw_slide(size, title, bullets, caption=part).save(png)
        lines.append(f"file '{png.as_posix()}'\nduration {dur:.3f}")
        cues.append((t, t + dur, part))
        t += dur
    lines.append(f"file '{(workdir / f'{name}_{len(parts) - 1:02d}.png').as_posix()}'")
    listing = workdir / f"{name}.txt"
    listing.write_text("\n".join(lines), encoding="utf-8")
    mp4 = workdir / f"{name}.mp4"
    _run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(wav),
          "-vf", f"fps=24,scale={size[0]}:{size[1]},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
          "-tune", "stillimage", "-c:a", "aac", "-b:a", "128k", "-shortest", str(mp4)])
    return mp4, seconds, [(a, b, c, engine) for a, b, c in cues]


def _concat(parts: list[Path], out: Path) -> Path:
    listing = out.with_suffix(".parts.txt")
    listing.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
    _run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])
    return out


def _srt(cues: list[tuple], path: Path) -> Path:
    def ts(x):
        h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
        return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"
    path.write_text("\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{c}\n" for i, (a, b, c) in enumerate(cues, 1)),
                    encoding="utf-8")
    return path


def render_long(script: dict, visual: dict, out_dir: Path) -> dict:
    work = out_dir / "work_long"
    work.mkdir(parents=True, exist_ok=True)
    slides = visual["slides"]
    by_section = {}
    for sl in slides:
        by_section.setdefault(sl["section"], sl)
    plan = [("intro", slides[0]["title"], slides[0]["bullets"], script["hook"])]
    for i, sec in enumerate(script["sections"]):
        sl = by_section.get(sec["heading"], {"title": sec["heading"], "bullets": [sec["on_screen"]]})
        plan.append((f"s{i + 1:02d}", sl["title"], sl["bullets"], sec["narration"]))
    plan.append(("outro", slides[-1]["title"], slides[-1]["bullets"], script["call_to_action"]))

    parts, cues, t, engines, chapters = [], [], 0.0, set(), []
    for name, title, bullets, narration in plan:
        mp4, secs, seg_cues = _segment(LONG_SIZE, title, bullets, narration, work, name)
        chapters.append((t, title))
        parts.append(mp4)
        for a, b, c, eng in seg_cues:
            cues.append((t + a, t + b, c))
            engines.add(eng)
        t += secs
    video = _concat(parts, out_dir / "long_video.mp4")
    srt = _srt(cues, out_dir / "long_video.srt")
    return {"path": video, "srt": srt, "seconds": round(t, 1), "voice": sorted(engines), "chapters": chapters}


def render_short(short: dict, out_dir: Path, n: int) -> dict:
    work = out_dir / f"work_short_{n}"
    work.mkdir(parents=True, exist_ok=True)
    narration = short["hook"] + " " + short["script"]
    mp4, secs, cues = _segment(SHORT_SIZE, short["title"], [], narration, work, "short")
    final = out_dir / f"short_{n}.mp4"
    final.write_bytes(mp4.read_bytes())
    return {"path": final, "seconds": round(secs, 1), "voice": sorted({c[3] for c in cues})}


def chapter_lines(chapters: list[tuple]) -> str:
    """YouTube chapters: first at 0:00, each at least 10 seconds apart."""
    out, last = [], -10.0
    for t, title in chapters:
        if t - last >= 10 or not out:
            out.append(f"{int(t // 60)}:{int(t % 60):02d} {textwrap.shorten(title, 60)}")
            last = t
    return "\n".join(out) if len(out) >= 3 else ""
