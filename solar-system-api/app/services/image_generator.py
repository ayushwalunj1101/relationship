"""
Strava-style image generator for the Relationship Solar System.

Generates a 1080x1080 PNG with:
- Deep space background with radial gradient
- Star field (deterministic based on solar_system_id)
- Orbital reference rings
- Connection lines from center to each person
- Glowing planet circles for each person (colored by tag)
- Center user with gold glow
- Stats bar at bottom
- Title at top
"""

import logging
import math
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# Constants
WIDTH, HEIGHT = 1080, 1080
CENTER = (540, 540)
SCALE = 450  # normalized coords * SCALE = pixel offset from center

# Font loading with fallback
ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
FONT_DIR = ASSETS_DIR / "fonts"

_fonts_cache: dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = f"{name}_{size}"
    if key in _fonts_cache:
        return _fonts_cache[key]

    font_path = FONT_DIR / name
    try:
        font = ImageFont.truetype(str(font_path), size)
    except (OSError, IOError):
        logger.warning(f"Font {font_path} not found, using default font")
        font = ImageFont.load_default()
    _fonts_cache[key] = font
    return font


def _get_fonts() -> dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    return {
        "bold_20": _load_font("Inter-Bold.ttf", 20),
        "bold_18": _load_font("Inter-Bold.ttf", 18),
        "bold_16": _load_font("Inter-Bold.ttf", 16),
        "regular_13": _load_font("Inter-Regular.ttf", 13),
        "regular_12": _load_font("Inter-Regular.ttf", 12),
        "regular_10": _load_font("Inter-Regular.ttf", 10),
    }


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _draw_radial_gradient(img: Image.Image) -> Image.Image:
    """Draw a subtle radial gradient from center (dark blue) to edges (deep space)."""
    gradient_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gradient_draw = ImageDraw.Draw(gradient_layer)

    center_color = (15, 27, 61)  # #0F1B3D
    max_radius = 500

    for r in range(max_radius, 0, -10):
        # Alpha decreases as radius increases (center is brighter)
        alpha = int(40 * (1.0 - r / max_radius))
        color = (*center_color, alpha)
        bbox = (CENTER[0] - r, CENTER[1] - r, CENTER[0] + r, CENTER[1] + r)
        gradient_draw.ellipse(bbox, fill=color)

    return Image.alpha_composite(img, gradient_layer)


def _draw_stars(draw: ImageDraw.Draw, seed: str) -> None:
    """Draw a deterministic star field."""
    rng = random.Random(seed)

    # 150 small stars (1-2px)
    for _ in range(150):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(0, HEIGHT - 1)
        r = rng.choice([1, 1, 1, 2])
        brightness = rng.randint(180, 255)
        draw.ellipse(
            [x - r, y - r, x + r, y + r],
            fill=(brightness, brightness, brightness, 255),
        )

    # 20 larger stars at 50% opacity for depth
    for _ in range(20):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(0, HEIGHT - 1)
        r = rng.choice([2, 3])
        draw.ellipse(
            [x - r, y - r, x + r, y + r],
            fill=(255, 255, 255, 128),
        )


def _draw_orbital_rings(draw: ImageDraw.Draw) -> None:
    """Draw concentric reference circles."""
    for radius in [100, 200, 300, 400, 450]:
        bbox = (
            CENTER[0] - radius,
            CENTER[1] - radius,
            CENTER[0] + radius,
            CENTER[1] + radius,
        )
        draw.ellipse(bbox, outline=(255, 255, 255, 18), width=1)


def _draw_connections(draw: ImageDraw.Draw, people: list[dict]) -> None:
    """Draw subtle connection lines from center to each person."""
    for person in people:
        px = CENTER[0] + int(person["x_position"] * SCALE)
        py = CENTER[1] + int(person["y_position"] * SCALE)

        if person.get("tag"):
            r, g, b = _hex_to_rgb(person["tag"]["color"])
            line_color = (r, g, b, 38)  # ~15% opacity
        else:
            line_color = (255, 255, 255, 38)

        draw.line([CENTER, (px, py)], fill=line_color, width=1)


def _draw_people_glow(img: Image.Image, people: list[dict]) -> Image.Image:
    """Draw glow effects for all people on a single layer, then blur and composite."""
    glow_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    for person in people:
        px = CENTER[0] + int(person["x_position"] * SCALE)
        py = CENTER[1] + int(person["y_position"] * SCALE)

        alpha_mult = person.get("alpha", 1.0)
        if person.get("tag"):
            r, g, b = _hex_to_rgb(person["tag"]["color"])
        else:
            r, g, b = 255, 255, 255

        # Draw concentric glow circles
        for glow_r, base_alpha in [(26, 30), (24, 50), (22, 80)]:
            alpha = int(base_alpha * alpha_mult)
            glow_draw.ellipse(
                [px - glow_r, py - glow_r, px + glow_r, py + glow_r],
                fill=(r, g, b, alpha),
            )

    # Blur the entire glow layer once
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=4))
    return Image.alpha_composite(img, glow_layer)


def _draw_people_solid(
    draw: ImageDraw.Draw,
    people: list[dict],
    fonts: dict,
) -> None:
    """Draw solid planet circles and name labels for each person."""
    for person in people:
        px = CENTER[0] + int(person["x_position"] * SCALE)
        py = CENTER[1] + int(person["y_position"] * SCALE)

        alpha_mult = person.get("alpha", 1.0)
        if person.get("tag"):
            r, g, b = _hex_to_rgb(person["tag"]["color"])
        else:
            r, g, b = 255, 255, 255

        planet_alpha = int(255 * alpha_mult)

        # Solid planet circle (20px radius)
        draw.ellipse(
            [px - 20, py - 20, px + 20, py + 20],
            fill=(r, g, b, planet_alpha),
        )

        # Name label below
        name = person["name"]
        text_bbox = draw.textbbox((0, 0), name, font=fonts["regular_12"])
        text_width = text_bbox[2] - text_bbox[0]
        name_alpha = int(230 * alpha_mult)
        draw.text(
            (px - text_width // 2, py + 25),
            name,
            fill=(255, 255, 255, name_alpha),
            font=fonts["regular_12"],
        )


def _draw_center_user(img: Image.Image, user: dict, fonts: dict) -> Image.Image:
    """Draw the user at the center with a gold glow."""
    # Glow layer for center
    glow_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    gold = (255, 215, 0)  # #FFD700

    # Bloom glow at radii 52, 48, 44
    for glow_r, alpha in [(52, 15), (48, 25), (44, 40)]:
        glow_draw.ellipse(
            [CENTER[0] - glow_r, CENTER[1] - glow_r,
             CENTER[0] + glow_r, CENTER[1] + glow_r],
            fill=(*gold, alpha),
        )

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=6))
    img = Image.alpha_composite(img, glow_layer)

    draw = ImageDraw.Draw(img)

    # Solid gold circle (40px radius)
    draw.ellipse(
        [CENTER[0] - 40, CENTER[1] - 40, CENTER[0] + 40, CENTER[1] + 40],
        fill=(*gold, 255),
    )

    # "YOU" label above
    you_bbox = draw.textbbox((0, 0), "YOU", font=fonts["regular_10"])
    you_width = you_bbox[2] - you_bbox[0]
    draw.text(
        (CENTER[0] - you_width // 2, CENTER[1] - 58),
        "YOU",
        fill=(255, 255, 255, 153),  # 60% opacity
        font=fonts["regular_10"],
    )

    # User name below
    name = user.get("name", "")
    name_bbox = draw.textbbox((0, 0), name, font=fonts["bold_16"])
    name_width = name_bbox[2] - name_bbox[0]
    draw.text(
        (CENTER[0] - name_width // 2, CENTER[1] + 48),
        name,
        fill=(255, 255, 255, 255),
        font=fonts["bold_16"],
    )

    return img


def _draw_stats_bar(img: Image.Image, state: dict, fonts: dict) -> Image.Image:
    """Draw the stats bar at the bottom of the image."""
    # Semi-transparent dark strip at bottom
    overlay = Image.new("RGBA", (WIDTH, 80), (0, 0, 0, 153))  # 60% opacity
    img.paste(overlay, (0, 1000), overlay)

    draw = ImageDraw.Draw(img)

    # Left side line 1: people count
    total = state.get("total_active_people", 0)
    draw.text(
        (30, 1010),
        f"{total} people in my orbit",
        fill=(255, 255, 255, 255),
        font=fonts["bold_18"],
    )

    # Left side line 2: tag breakdown
    tags_summary = state.get("tags_summary", {})
    breakdown = " \u00b7 ".join(
        f"{count} {name}" for name, count in tags_summary.items()
    )
    draw.text(
        (30, 1038),
        breakdown,
        fill=(255, 255, 255, 179),  # 70% opacity
        font=fonts["regular_13"],
    )

    # Right side: date
    date_str = datetime.now().strftime("%b %Y")
    date_bbox = draw.textbbox((0, 0), date_str, font=fonts["regular_13"])
    date_width = date_bbox[2] - date_bbox[0]
    draw.text(
        (1050 - date_width, 1025),
        date_str,
        fill=(255, 255, 255, 128),  # 50% opacity
        font=fonts["regular_13"],
    )

    return img


def _draw_title(draw: ImageDraw.Draw, fonts: dict) -> None:
    """Draw the title and decorative line at the top."""
    title = "My Solar System"
    title_bbox = draw.textbbox((0, 0), title, font=fonts["bold_20"])
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(
        (CENTER[0] - title_width // 2, 25),
        title,
        fill=(255, 255, 255, 204),  # 80% opacity
        font=fonts["bold_20"],
    )

    # Decorative line below title
    draw.line([(510, 55), (570, 55)], fill=(255, 255, 255, 51), width=1)


def generate_solar_system_image(state: dict, output_path: str) -> str:
    """
    Generate a 1080x1080 Strava-style image from solar system state.
    This is a synchronous function — call from run_in_executor.

    Args:
        state: The solar system state dict (same format as snapshot full_state)
        output_path: Where to save the PNG

    Returns:
        The output_path
    """
    fonts = _get_fonts()

    # 1. Create base image
    img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 10, 26, 255))

    # 2. Radial gradient background
    img = _draw_radial_gradient(img)

    draw = ImageDraw.Draw(img)

    # 3. Star field (deterministic seed)
    seed = state.get("user", {}).get("id", "default")
    _draw_stars(draw, seed)

    # 4. Orbital reference rings
    _draw_orbital_rings(draw)

    people = state.get("people", [])

    # 5. Connection lines
    _draw_connections(draw, people)

    # 6. People glow effects (batched)
    img = _draw_people_glow(img, people)

    # 7. People solid circles + labels
    draw = ImageDraw.Draw(img)
    _draw_people_solid(draw, people, fonts)

    # 8. Center user with glow
    img = _draw_center_user(img, state.get("user", {}), fonts)

    # 9. Stats bar
    img = _draw_stats_bar(img, state, fonts)

    # 10. Title
    draw = ImageDraw.Draw(img)
    _draw_title(draw, fonts)

    # Convert to RGB and save
    final = Image.new("RGB", (WIDTH, HEIGHT), (10, 10, 26))
    final.paste(img, mask=img.split()[3])
    final.save(output_path, "PNG", quality=95)

    return output_path
