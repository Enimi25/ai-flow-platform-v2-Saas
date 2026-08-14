from pathlib import Path
import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/social/2026-08-14/ai-flow-reel-01-source.png"
OUT_DIR = ROOT / "media/social/2026-08-14"
OUTPUT = OUT_DIR / "ai-flow-reel-01.mp4"
FONT_PATH = "/System/Library/Fonts/SFNS.ttf"

SLIDES = [
    ("LEADS DON'T WAIT.", "Most businesses lose opportunities in the first few minutes."),
    ("AI FLOW REPLIES.", "Every website and social conversation gets an immediate response."),
    ("QUALIFIES. BOOKS. PAYS.", "AI collects the lead, books the appointment and sends payment."),
    ("YOUR AI SALES DEPARTMENT", "Always on. Built for real business outcomes. 24/7."),
]


def font(size: int):
    return ImageFont.truetype(FONT_PATH, size=size)


def cover(source: Image.Image, width: int, height: int):
    scale = max(width / source.width, height / source.height)
    resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def wrap(draw: ImageDraw.ImageDraw, text: str, chosen_font, max_width: int):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=chosen_font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build_frame(base: Image.Image, headline: str, supporting: str, index: int):
    canvas = cover(base, 1080, 1920).convert("RGB")
    canvas = ImageEnhance.Contrast(canvas).enhance(1.08)
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=0.35))
    shade = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.rectangle((0, 0, 1080, 1920), fill=(2, 7, 14, 38))
    sd.rectangle((0, 0, 1080, 590), fill=(2, 7, 14, 205))
    sd.rectangle((0, 1500, 1080, 1920), fill=(2, 7, 14, 185))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shade)

    draw = ImageDraw.Draw(canvas)
    cyan = (98, 222, 255, 255)
    white = (248, 250, 252, 255)
    muted = (196, 208, 220, 255)
    draw.text((72, 95), "AI FLOW", font=font(38), fill=cyan)

    headline_font = font(82 if len(headline) < 24 else 68)
    y = 205
    for line in wrap(draw, headline, headline_font, 930):
        draw.text((72, y), line, font=headline_font, fill=white)
        y += headline_font.size + 10

    supporting_font = font(38)
    y += 38
    for line in wrap(draw, supporting, supporting_font, 900):
        draw.text((76, y), line, font=supporting_font, fill=muted)
        y += 52

    draw.rounded_rectangle((72, 1635, 310, 1760), radius=62, fill=(57, 189, 248, 244))
    draw.text((118, 1663), "24/7", font=font(55), fill=(2, 12, 22, 255))
    draw.text((72, 1815), f"0{index + 1} / 04", font=font(28), fill=muted)
    return canvas.convert("RGB")


def ffmpeg_path():
    configured = os.getenv("FFMPEG_BIN", "").strip()
    if configured:
        return configured
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("Install ffmpeg or imageio-ffmpeg, or set FFMPEG_BIN") from exc


OUT_DIR.mkdir(parents=True, exist_ok=True)
frames_dir = Path(os.getenv("AI_FLOW_REEL_FRAMES_DIR", "/tmp/ai-flow-reel-01-frames"))
frames_dir.mkdir(parents=True, exist_ok=True)
base = Image.open(SOURCE).convert("RGB")
frames = []
for idx, (headline, supporting) in enumerate(SLIDES):
    path = frames_dir / f"frame-{idx + 1}.png"
    build_frame(base, headline, supporting, idx).save(path, "PNG", optimize=True)
    frames.append(path)

cmd = [ffmpeg_path(), "-y"]
for frame in frames:
    cmd += ["-loop", "1", "-t", "3.5", "-i", str(frame)]
cmd += [
    "-f", "lavfi", "-i", "sine=frequency=110:sample_rate=44100:duration=12.5",
    "-filter_complex",
    "[0:v]fps=30,scale=1080:1920,setsar=1[v0];"
    "[1:v]fps=30,scale=1080:1920,setsar=1[v1];"
    "[2:v]fps=30,scale=1080:1920,setsar=1[v2];"
    "[3:v]fps=30,scale=1080:1920,setsar=1[v3];"
    "[v0][v1]xfade=transition=fade:duration=0.5:offset=3.0[x1];"
    "[x1][v2]xfade=transition=fade:duration=0.5:offset=6.0[x2];"
    "[x2][v3]xfade=transition=fade:duration=0.5:offset=9.0[v];"
    "[4:a]volume=0.025,afade=t=in:st=0:d=1,afade=t=out:st=11:d=1[a]",
    "-map", "[v]", "-map", "[a]", "-t", "12.5",
    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(OUTPUT),
]
subprocess.run(cmd, check=True)
print(OUTPUT)
