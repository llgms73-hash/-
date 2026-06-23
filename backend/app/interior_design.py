import asyncio
import base64
import json
import logging
import os
from typing import Optional

import anthropic
import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

DESIGN_STYLES: dict[str, dict] = {
    "modern": {
        "name_zh": "現代簡約", "emoji": "🏛️",
        "desc_zh": "乾淨俐落的線條，中性色調，功能美學",
        "prompt": "modern minimalist interior, clean geometric lines, neutral tones, sleek furniture, open plan, functional elegance",
    },
    "scandinavian": {
        "name_zh": "北歐風格", "emoji": "🌿",
        "desc_zh": "淺色木材、白牆、hygge 舒適氛圍",
        "prompt": "Scandinavian Nordic interior, light birch wood, white walls, hygge cozy atmosphere, natural wool textiles, soft diffused light",
    },
    "industrial": {
        "name_zh": "工業風", "emoji": "⚙️",
        "desc_zh": "裸露磚牆、鋼鐵、原木的都市韻味",
        "prompt": "industrial loft interior, exposed brick walls, structural steel beams, weathered reclaimed wood, Edison filament bulbs, urban aesthetic",
    },
    "japanese": {
        "name_zh": "日式禪意", "emoji": "🎋",
        "desc_zh": "侘寂美學，天然素材，靜謐禪意",
        "prompt": "Japanese zen interior, wabi-sabi minimalism, natural bamboo and stone, shoji paper screens, tatami elements, serene tranquility",
    },
    "luxury": {
        "name_zh": "奢華古典", "emoji": "💎",
        "desc_zh": "大理石、金色細節、絲絨的頂級質感",
        "prompt": "luxury classical interior, Calacatta marble surfaces, brushed gold accents, velvet upholstery, crystal chandelier, opulent grandeur",
    },
    "mediterranean": {
        "name_zh": "地中海風", "emoji": "🌊",
        "desc_zh": "赤陶磚、藍白配色、拱門的陽光感",
        "prompt": "Mediterranean coastal interior, handmade terracotta tiles, blue and white palette, arched doorways, mosaic tile accents, warm sunshine",
    },
    "rustic": {
        "name_zh": "鄉村質樸", "emoji": "🏡",
        "desc_zh": "回收老木、石砌壁爐的溫暖鄉村風",
        "prompt": "rustic farmhouse interior, reclaimed wood ceiling beams, stone fireplace, vintage patchwork textiles, warm ochre and brown tones, countryside charm",
    },
    "art_deco": {
        "name_zh": "裝飾藝術", "emoji": "🎭",
        "desc_zh": "幾何圖案、黃銅配件、珠寶色的魅力",
        "prompt": "Art Deco interior, bold geometric patterns, polished brass and chrome fixtures, jewel tones emerald sapphire, symmetrical grandeur, 1920s glamour",
    },
}

COLOR_PALETTES: dict[str, dict] = {
    "neutral":    {"name_zh": "中性溫暖", "colors": ["#F7F3EE", "#E8DDD1", "#C4B5A5", "#8B7D72"], "prompt": "warm white ivory, soft beige linen, warm stone grey, natural neutral tones"},
    "earthy":     {"name_zh": "大地色調", "colors": ["#C2714F", "#8B9D6A", "#8B6F4E", "#D4A853"], "prompt": "terracotta burnt sienna, sage green, warm chocolate brown, golden ochre"},
    "coastal":    {"name_zh": "海岸藍調", "colors": ["#3B82C4", "#E8D5A3", "#FF7F6B", "#93C5BC"], "prompt": "ocean navy blue, sandy beach beige, soft coral, seafoam turquoise"},
    "monochrome": {"name_zh": "黑白簡約", "colors": ["#F9FAFB", "#9CA3AF", "#374151", "#111827"], "prompt": "pure white, silver mid-grey, dark charcoal, jet black monochrome"},
    "warm":       {"name_zh": "暖色夕陽", "colors": ["#DC2626", "#EA580C", "#D97706", "#FEF3C7"], "prompt": "deep crimson, burnt orange, warm amber gold, soft cream, sunset palette"},
    "cool":       {"name_zh": "冷色北歐", "colors": ["#1E40AF", "#7C3AED", "#93C5FD", "#EFF6FF"], "prompt": "deep navy blue, lavender purple, powder blue, crisp cool white"},
    "nature":     {"name_zh": "自然森林", "colors": ["#166534", "#365314", "#78716C", "#E7E5E4"], "prompt": "deep forest green, olive, natural warm taupe, stone grey"},
    "bold":       {"name_zh": "大膽對比", "colors": ["#1E3A5F", "#065F46", "#7F1D1D", "#713F12"], "prompt": "deep navy, emerald green, burgundy wine, mustard yellow, bold jewel tones"},
}

MATERIALS: dict[str, str] = {
    "marble":   "大理石",
    "wood":     "木材",
    "metal":    "金屬",
    "glass":    "玻璃",
    "fabric":   "布料",
    "concrete": "混凝土",
    "leather":  "皮革",
    "stone":    "石材",
    "ceramic":  "陶瓷",
    "bamboo":   "竹材",
}


async def analyze_room(image_bytes: bytes, filename: str) -> dict:
    """Use Claude Vision to analyze uploaded room photo."""
    if not ANTHROPIC_API_KEY:
        return _default_analysis()

    ext = (filename.rsplit(".", 1)[-1].lower()) if "." in filename else "jpeg"
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    b64 = base64.standard_b64encode(image_bytes).decode()

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {
                        "type": "text",
                        "text": (
                            'Analyze this room photo. Reply ONLY with JSON, no other text:\n'
                            '{"room_type":"living room|bedroom|kitchen|bathroom|dining room|study|other",'
                            '"size":"small|medium|large",'
                            '"flooring":"describe the floor type briefly",'
                            '"natural_light":"dark|moderate|bright",'
                            '"key_features":["list up to 4 notable structural or design features"],'
                            '"description_zh":"一句中文描述這個空間現況"}'
                        ),
                    },
                ],
            }],
        )
        text = resp.content[0].text
        s, e = text.find("{"), text.rfind("}") + 1
        if s >= 0 and e > s:
            return json.loads(text[s:e])
    except Exception as exc:
        logger.error("Room analysis failed: %s", exc)

    return _default_analysis()


def _default_analysis() -> dict:
    return {
        "room_type": "living room",
        "size": "medium",
        "flooring": "unknown",
        "natural_light": "moderate",
        "key_features": ["walls", "floor", "ceiling"],
        "description_zh": "您的空間已準備好進行設計改造",
    }


def build_prompt(
    room: dict,
    style_key: str,
    palette_key: str,
    materials: list[str],
    custom: str,
) -> tuple[str, str]:
    """Build positive and negative prompts for image generation."""
    style = DESIGN_STYLES.get(style_key, DESIGN_STYLES["modern"])
    palette = COLOR_PALETTES.get(palette_key, COLOR_PALETTES["neutral"])
    room_type = room.get("room_type", "interior room")
    mat_str = ", ".join(materials) if materials else "quality mixed materials"

    positive = (
        f"photorealistic 3D interior design visualization, {room_type}, "
        f"{style['prompt']}, "
        f"color palette {palette['prompt']}, "
        f"materials {mat_str}, "
        f"professional architectural CGI render, "
        f"8K ultra high resolution, perfect HDR global illumination, ray tracing, "
        f"wide angle interior photography, bokeh depth of field, "
        f"hyperrealistic textures, award-winning interior design photo"
    )
    if custom.strip():
        positive += f", {custom.strip()}"

    negative = (
        "deformed, blurry, ugly, low quality, distorted, cartoon, anime, illustration, "
        "painting, sketch, oversaturated, dark, gloomy, dirty, cluttered mess, "
        "text, watermark, logo, signature, people, humans, faces"
    )
    return positive, negative


async def generate_image(
    image_bytes: bytes,
    positive: str,
    negative: str,
    strength: float,
) -> Optional[bytes]:
    """Try Stability AI first, fall back to Replicate."""
    result = await _try_stability(image_bytes, positive, negative, strength)
    if result:
        return result
    return await _try_replicate(image_bytes, positive)


async def _try_stability(
    image_bytes: bytes,
    positive: str,
    negative: str,
    strength: float,
) -> Optional[bytes]:
    if not STABILITY_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {STABILITY_API_KEY}",
                },
                data={
                    "text_prompts[0][text]": positive,
                    "text_prompts[0][weight]": "1",
                    "text_prompts[1][text]": negative,
                    "text_prompts[1][weight]": "-1",
                    "init_image_mode": "IMAGE_STRENGTH",
                    "image_strength": str(strength),
                    "cfg_scale": "8",
                    "samples": "1",
                    "steps": "35",
                    "style_preset": "photographic",
                },
                files={"init_image": ("room.jpg", image_bytes, "image/jpeg")},
            )
        if r.status_code == 200:
            data = r.json()
            if data.get("artifacts"):
                return base64.b64decode(data["artifacts"][0]["base64"])
        else:
            logger.error("Stability AI %d: %s", r.status_code, r.text[:300])
    except Exception as exc:
        logger.error("Stability AI exception: %s", exc)
    return None


async def _try_replicate(image_bytes: bytes, positive: str) -> Optional[bytes]:
    if not REPLICATE_API_TOKEN:
        return None
    data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
    try:
        async with httpx.AsyncClient(timeout=200.0) as c:
            r = await c.post(
                "https://api.replicate.com/v1/predictions",
                headers={
                    "Authorization": f"Token {REPLICATE_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "version": "adirik/interior-design:76604baddc85b1b4616e1c6475eca080da339c8875bd4996705440484a6f5f46",
                    "input": {
                        "image": data_url,
                        "prompt": positive,
                        "guidance_scale": 8,
                        "negative_prompt": "cartoon, blurry, low quality, ugly, distorted",
                        "num_inference_steps": 30,
                    },
                },
            )
            if r.status_code not in (200, 201):
                logger.error("Replicate start error %d", r.status_code)
                return None
            pid = r.json()["id"]
            for _ in range(80):
                await asyncio.sleep(2)
                poll = await c.get(
                    f"https://api.replicate.com/v1/predictions/{pid}",
                    headers={"Authorization": f"Token {REPLICATE_API_TOKEN}"},
                )
                d = poll.json()
                if d["status"] == "succeeded":
                    out = d.get("output")
                    url = out[0] if isinstance(out, list) else out
                    return (await c.get(url)).content if url else None
                if d["status"] in ("failed", "canceled"):
                    logger.error("Replicate failed: %s", d.get("error"))
                    break
    except Exception as exc:
        logger.error("Replicate exception: %s", exc)
    return None
