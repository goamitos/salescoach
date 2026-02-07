"""
Generate placeholder avatar images for influencers.
Creates simple colored circles with initials as PNG files.
"""
import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. Run: pip install Pillow")
    exit(1)

# Influencer data
INFLUENCERS = [
    ("30MPC", "30mpc", "#FF6B6B"),
    ("Armand Farrokh", "armand-farrokh", "#4ECDC4"),
    ("Nick Cegelski", "nick-cegelski", "#45B7D1"),
    ("Samantha McKenna", "samantha-mckenna", "#96CEB4"),
    ("Ian Koniak", "ian-koniak", "#FFEAA7"),
    ("Daniel Disney", "daniel-disney", "#DDA0DD"),
    ("Will Aitken", "will-aitken", "#98D8C8"),
    ("Devin Reed", "devin-reed", "#F7DC6F"),
    ("Florin Tatulea", "florin-tatulea", "#BB8FCE"),
    ("Gal Aga", "gal-aga", "#85C1E9"),
    ("Nate Nasralla", "nate-nasralla", "#F8B500"),
    ("Morgan J Ingram", "morgan-j-ingram", "#E74C3C"),
    ("Kyle Coleman", "kyle-coleman", "#3498DB"),
    # Additional existing experts
    ("John Barrows", "john-barrows", "#2C3E50"),
    ("Josh Braun", "josh-braun", "#F39C12"),
    ("Jeb Blount", "jeb-blount", "#E67E22"),
    ("Chris Voss", "chris-voss", "#C0392B"),
    ("Gong.io", "gong-io", "#6C3483"),
    # --- Monday CRM Top 25 (18 new) ---
    ("Anthony Iannarino", "anthony-iannarino", "#E67E22"),
    ("Giulio Segantini", "giulio-segantini", "#1ABC9C"),
    ("Mark Hunter", "mark-hunter", "#2ECC71"),
    ("Jill Konrath", "jill-konrath", "#9B59B6"),
    ("Shari Levitin", "shari-levitin", "#E74C3C"),
    ("Jim Keenan", "jim-keenan", "#3498DB"),
    ("Tiffani Bova", "tiffani-bova", "#F39C12"),
    ("Amy Volas", "amy-volas", "#8E44AD"),
    ("Ron Kimhi", "ron-kimhi", "#16A085"),
    ("Chris Orlob", "chris-orlob", "#D35400"),
    ("Becc Holland", "becc-holland", "#C0392B"),
    ("Jen Allen-Knuth", "jen-allen-knuth", "#27AE60"),
    ("Alexandra Carter", "alexandra-carter", "#2980B9"),
    ("Kwame Christian", "kwame-christian", "#7D3C98"),
    ("Mo Bunnell", "mo-bunnell", "#117A65"),
    ("Rosalyn Santa Elena", "rosalyn-santa-elena", "#AF7AC5"),
    ("Mark Kosoglow", "mark-kosoglow", "#5DADE2"),
    ("Scott Leese", "scott-leese", "#F1948A"),
    # --- Proposify Best Sales Voices (14 new) ---
    ("Sarah Brazier", "sarah-brazier", "#48C9B0"),
    ("Jesse Gittler", "jesse-gittler", "#EB984E"),
    ("Chantel George", "chantel-george", "#A569BD"),
    ("Bryan Tucker", "bryan-tucker", "#5499C7"),
    ("Colin Specter", "colin-specter", "#45B39D"),
    ("Kevin Dorsey", "kevin-dorsey", "#DC7633"),
    ("Belal Batrawy", "belal-batrawy", "#CB4335"),
    ("Caroline Celis", "caroline-celis", "#F5B041"),
    ("Julie Hansen", "julie-hansen", "#85C1E9"),
    ("Hannah Ajikawo", "hannah-ajikawo", "#58D68D"),
    ("Justin Michael", "justin-michael", "#7FB3D8"),
    ("Erica Franklin", "erica-franklin", "#D7BDE2"),
    ("Maria Bross", "maria-bross", "#F0B27A"),
    ("Niraj Kapur", "niraj-kapur", "#82E0AA"),
    # Special avatar for combined wisdom (not tied to individual influencer)
    ("Collective Wisdom", "collective-wisdom", "#9B59B6"),
]

def get_initials(name: str) -> str:
    """Get initials from a name."""
    if name == "30MPC":
        return "30"
    words = name.split()
    if len(words) >= 2:
        return words[0][0] + words[-1][0]
    return name[:2].upper()

def create_avatar(name: str, slug: str, color: str, output_dir: Path, size: int = 200):
    """Create a circular avatar with initials."""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw circle
    draw.ellipse([0, 0, size-1, size-1], fill=color)

    # Get initials
    initials = get_initials(name)

    # Try fonts in order: macOS → Windows → Linux → default
    font_size = size // 3
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",  # macOS
        "C:/Windows/Fonts/arial.ttf",            # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
    ]
    font = None
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()

    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), initials, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (size - text_width) // 2
    y = (size - text_height) // 2 - bbox[1]  # Adjust for font baseline

    # Draw text in white
    draw.text((x, y), initials, fill='white', font=font)

    # Save as PNG
    output_path = output_dir / f"{slug}.png"
    img.save(output_path, 'PNG')
    print(f"Created: {output_path}")

def main():
    # Setup paths
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "assets" / "avatars"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating avatars in: {output_dir}")

    generated = 0
    skipped = 0
    for name, slug, color in INFLUENCERS:
        output_path = output_dir / f"{slug}.png"
        if output_path.exists():
            print(f"Skipped (exists): {output_path}")
            skipped += 1
            continue
        create_avatar(name, slug, color, output_dir)
        generated += 1

    print(f"\nGenerated {generated} placeholder avatars, skipped {skipped} existing.")

if __name__ == "__main__":
    main()
