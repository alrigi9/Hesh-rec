import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

def create_recmap_logo(size=1024):
    # Create canvas with alpha
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    
    # 1. Background Rounded Rectangle
    bg_margin = int(size * 0.04) # 4% margin for nice border spacing
    radius = int(size * 0.22)    # Smooth modern squircle radius
    
    # Create background mask & image
    bg_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_bg = ImageDraw.Draw(bg_layer)
    
    # Deep obsidian background fill
    bg_box = [bg_margin, bg_margin, size - bg_margin, size - bg_margin]
    draw_bg.rounded_rectangle(bg_box, radius=radius, fill=(12, 13, 17, 255))
    
    # Subtle dark border
    draw_bg.rounded_rectangle(bg_box, radius=radius, outline=(255, 92, 71, 55), width=int(size * 0.012))
    
    # 2. Subtle Radial Glow behind Waveform
    glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_glow = ImageDraw.Draw(glow_layer)
    center_x, center_y = size // 2, size // 2
    glow_radius = int(size * 0.32)
    
    for r in range(glow_radius, 0, -8):
        alpha = int(35 * (1.0 - (r / glow_radius) ** 1.5))
        draw_glow.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            fill=(255, 92, 71, alpha)
        )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=int(size * 0.04)))
    
    # 3. Signature AudioWaveform Geometry
    icon_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw_icon = ImageDraw.Draw(icon_layer)
    
    # Waveform bar specifications (normalized heights centered around middle)
    # Heights relative to total height (0.15 to 0.58)
    bar_height_ratios = [0.18, 0.34, 0.52, 0.62, 0.44, 0.28, 0.16]
    num_bars = len(bar_height_ratios)
    
    bar_width = int(size * 0.052)   # width of each capsule bar
    gap = int(size * 0.042)         # spacing between bars
    total_waveform_width = num_bars * bar_width + (num_bars - 1) * gap
    start_x = (size - total_waveform_width) // 2
    
    for i, h_ratio in enumerate(bar_height_ratios):
        bx = start_x + i * (bar_width + gap)
        bh = int(size * h_ratio)
        by1 = center_y - (bh // 2)
        by2 = center_y + (bh // 2)
        
        # Primary Coral/Orange color (#FF5C47 -> #FF7461)
        # Add subtle vertical gradient or solid vibrant coral
        bar_box = [bx, by1, bx + bar_width, by2]
        bar_radius = bar_width // 2
        
        # Draw capsule bar
        draw_icon.rounded_rectangle(bar_box, radius=bar_radius, fill=(255, 92, 71, 255))
    
    # Composite all layers together
    composite = Image.alpha_composite(img, bg_layer)
    composite = Image.alpha_composite(composite, glow_layer)
    composite = Image.alpha_composite(composite, icon_layer)
    
    return composite

def main():
    print("[*] Generating official RecMap logos...")
    master = create_recmap_logo(1024)
    
    # Export 512x512
    logo_512 = master.resize((512, 512), Image.Resampling.LANCZOS)
    path_512 = Path("D:/claude/Hesh rec/recmap-logo.png")
    path_512_alt = Path("D:/claude/Hesh rec/recmap-logo-512.png")
    logo_512.save(path_512, "PNG", optimize=True)
    logo_512.save(path_512_alt, "PNG", optimize=True)
    print(f"[+] Saved 512x512 Logo to: {path_512} ({path_512.stat().st_size / 1024:.1f} KB)")
    
    # Export 120x120 for Google OAuth Console
    logo_120 = master.resize((120, 120), Image.Resampling.LANCZOS)
    path_120 = Path("D:/claude/Hesh rec/recmap-logo-120.png")
    logo_120.save(path_120, "PNG", optimize=True)
    print(f"[+] Saved 120x120 Logo to: {path_120} ({path_120.stat().st_size / 1024:.1f} KB)")
    
    # Also save to frontend/public directory
    public_dir = Path("D:/claude/Hesh rec/frontend/public")
    if public_dir.exists():
        logo_512.save(public_dir / "recmap-logo.png", "PNG", optimize=True)
        logo_512.save(public_dir / "icon.png", "PNG", optimize=True)
        logo_120.save(public_dir / "recmap-logo-120.png", "PNG", optimize=True)
        logo_120.save(public_dir / "apple-icon.png", "PNG", optimize=True)
        print("[+] Saved logos to frontend/public/")

if __name__ == "__main__":
    main()
