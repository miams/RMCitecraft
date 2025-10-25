#!/usr/bin/env python3
"""
Generate extension icons for RMCitecraft.

Creates PNG icons in three sizes: 16x16, 48x48, 128x128
Uses PIL/Pillow to draw a simple but recognizable icon.
"""

from PIL import Image, ImageDraw, ImageFont


def create_icon(size: int, output_path: str):
    """Create a simple RMCitecraft icon.

    Design: Blue gradient background with white "RM" text
    """
    # Create image with transparency
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw rounded rectangle background (gradient blue)
    # Using primary color from popup: #2563eb
    background_color = (37, 99, 235, 255)  # Primary blue
    border_radius = size // 6

    # Draw rounded rectangle
    draw.rounded_rectangle(
        [(0, 0), (size, size)],
        radius=border_radius,
        fill=background_color
    )

    # Add subtle gradient effect with overlay
    overlay = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Lighter top half
    for i in range(size // 2):
        alpha = int(30 * (1 - i / (size // 2)))  # Fade from 30 to 0
        overlay_draw.rectangle(
            [(0, i), (size, i + 1)],
            fill=(255, 255, 255, alpha)
        )

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Draw text "RM" in white
    text = "RM"

    # Try to use a system font, fall back to default
    try:
        # Try different common system fonts
        font_size = size // 2
        for font_name in [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            "Arial",
            "Helvetica"
        ]:
            try:
                font = ImageFont.truetype(font_name, font_size)
                break
            except:
                continue
        else:
            # Fall back to default font
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Center the text
    x = (size - text_width) // 2 - bbox[0]
    y = (size - text_height) // 2 - bbox[1]

    # Draw text with slight shadow for depth
    shadow_offset = max(1, size // 32)
    draw.text((x + shadow_offset, y + shadow_offset), text, fill=(0, 0, 0, 80), font=font)
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)

    # Save
    img.save(output_path, 'PNG')
    print(f"Created {size}x{size} icon: {output_path}")


def main():
    """Generate all required icon sizes."""
    import os

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Icon sizes required by Chrome
    sizes = [16, 48, 128]

    for size in sizes:
        output_path = os.path.join(script_dir, f"icon{size}.png")
        create_icon(size, output_path)

    print("\n✓ All icons generated successfully!")
    print(f"Icons saved to: {script_dir}")


if __name__ == "__main__":
    main()
