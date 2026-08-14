from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/social/2026-08-14/ai-flow-reel-01-source.png"
OUTPUT = ROOT / "media/social/2026-08-14/ai-flow-post-01.png"
FONT = "/System/Library/Fonts/SFNS.ttf"


def font(size: int):
    return ImageFont.truetype(FONT, size=size)


image = Image.open(SOURCE).convert("RGB")
target_w, target_h = 1080, 1350
scale = max(target_w / image.width, target_h / image.height)
image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
left = (image.width - target_w) // 2
top = (image.height - target_h) // 2
image = image.crop((left, top, left + target_w, top + target_h))
image = ImageEnhance.Contrast(image).enhance(1.08)

overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)
draw.rectangle((0, 0, target_w, 420), fill=(3, 8, 15, 178))
draw.rectangle((0, 1080, target_w, target_h), fill=(3, 8, 15, 188))

cyan = (100, 222, 255, 255)
white = (247, 250, 252, 255)
muted = (194, 207, 220, 255)

draw.text((72, 66), "AI FLOW", font=font(36), fill=cyan)
draw.text((72, 132), "YOUR AI SALES", font=font(82), fill=white)
draw.text((72, 220), "DEPARTMENT", font=font(82), fill=white)
draw.text((76, 326), "Replies  •  Qualifies  •  Books  •  Follows up", font=font(31), fill=muted)

draw.rounded_rectangle((72, 1136, 278, 1255), radius=58, fill=(56, 189, 248, 238))
draw.text((116, 1163), "24/7", font=font(54), fill=(2, 12, 22, 255))
draw.text((322, 1156), "Turn conversations", font=font(41), fill=white)
draw.text((322, 1208), "into booked revenue.", font=font(41), fill=white)

result = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
result.save(OUTPUT, "PNG", optimize=True)
print(OUTPUT)
