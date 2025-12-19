"""
Advanced Theme Analyzer for LocalPix
Extracts dominant colors from logos using K-means clustering
Generates complete color palettes with WCAG-compliant contrast ratios
"""

import os
import colorsys
import math
from typing import Dict, List, Tuple, Optional

try:
    from PIL import Image
    import numpy as np
    from sklearn.cluster import KMeans
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False
    print("WARNING: PIL or scikit-learn not installed. Theme analysis will use fallback mode.")


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color"""
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def rgb_to_hsl(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """Convert RGB to HSL color space"""
    r, g, b = [x / 255.0 for x in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (h * 360, s * 100, l * 100)


def hsl_to_rgb(hsl: Tuple[float, float, float]) -> Tuple[int, int, int]:
    """Convert HSL to RGB color space"""
    h, s, l = hsl[0] / 360.0, hsl[1] / 100.0, hsl[2] / 100.0
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (int(r * 255), int(g * 255), int(b * 255))


def get_luminance(rgb: Tuple[int, int, int]) -> float:
    """Calculate relative luminance for WCAG contrast calculations"""
    def adjust(color_value):
        color_value = color_value / 255.0
        if color_value <= 0.03928:
            return color_value / 12.92
        return ((color_value + 0.055) / 1.055) ** 2.4
    
    r, g, b = rgb
    return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculate WCAG contrast ratio between two colors
    Returns: ratio from 1 to 21 (21 is maximum contrast)
    WCAG AA requires: 4.5:1 for normal text, 3:1 for large text
    """
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    
    lum1 = get_luminance(rgb1)
    lum2 = get_luminance(rgb2)
    
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    
    return (lighter + 0.05) / (darker + 0.05)


def adjust_brightness(hex_color: str, factor: float) -> str:
    """
    Adjust color brightness in HSL space
    factor > 1.0 = lighter, factor < 1.0 = darker
    """
    rgb = hex_to_rgb(hex_color)
    h, s, l = rgb_to_hsl(rgb)
    
    # Adjust lightness
    l = max(0, min(100, l * factor))
    
    new_rgb = hsl_to_rgb((h, s, l))
    return rgb_to_hex(new_rgb)


def adjust_saturation(hex_color: str, factor: float) -> str:
    """Adjust color saturation"""
    rgb = hex_to_rgb(hex_color)
    h, s, l = rgb_to_hsl(rgb)
    
    s = max(0, min(100, s * factor))
    
    new_rgb = hsl_to_rgb((h, s, l))
    return rgb_to_hex(new_rgb)


def get_vibrance(rgb: Tuple[int, int, int]) -> float:
    """Calculate color vibrance (saturation × brightness)"""
    h, s, l = rgb_to_hsl(rgb)
    return (s / 100.0) * (l / 100.0)


def is_grayscale(rgb: Tuple[int, int, int], threshold: int = 15) -> bool:
    """Check if color is grayscale (low saturation)"""
    r, g, b = rgb
    return (max(r, g, b) - min(r, g, b)) < threshold


def kmeans_color_extraction(image_path: str, n_colors: int = 5) -> List[Tuple[int, int, int]]:
    """
    Extract dominant colors from image using K-means clustering
    Returns list of RGB tuples sorted by frequency
    """
    if not DEPENDENCIES_AVAILABLE:
        # Fallback: return default blue palette
        return [
            (59, 130, 246),   # Blue
            (34, 197, 94),    # Green
            (239, 68, 68),    # Red
            (245, 158, 11),   # Orange
            (168, 85, 247),   # Purple
        ]
    
    try:
        # Load and resize image for performance
        img = Image.open(image_path)
        img = img.convert('RGB')
        
        # Resize to max 500px width
        max_width = 500
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to numpy array and reshape
        img_array = np.array(img)
        pixels = img_array.reshape(-1, 3)
        
        # Remove fully transparent or extreme pixels
        pixels = pixels[~np.all(pixels == [0, 0, 0], axis=1)]  # Remove pure black
        pixels = pixels[~np.all(pixels == [255, 255, 255], axis=1)]  # Remove pure white
        
        if len(pixels) < n_colors:
            return [(59, 130, 246)]  # Fallback
        
        # Apply K-means
        kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)
        
        # Get colors and their frequencies
        colors = kmeans.cluster_centers_.astype(int)
        labels = kmeans.labels_
        
        # Sort by frequency
        unique, counts = np.unique(labels, return_counts=True)
        sorted_indices = np.argsort(-counts)
        
        sorted_colors = [tuple(colors[i]) for i in sorted_indices]
        
        return sorted_colors
        
    except Exception as e:
        print(f"Error in K-means extraction: {e}")
        return [(59, 130, 246)]  # Fallback blue


def select_primary_color(colors: List[Tuple[int, int, int]]) -> Tuple[int, int, int]:
    """Select the most vibrant color as primary"""
    # Filter out grayscale colors
    vibrant_colors = [c for c in colors if not is_grayscale(c)]
    
    if not vibrant_colors:
        # All colors are grayscale, use a default blue
        return (59, 130, 246)
    
    # Select most vibrant
    vibrant_colors.sort(key=lambda c: get_vibrance(c), reverse=True)
    return vibrant_colors[0]


def select_secondary_color(colors: List[Tuple[int, int, int]], primary: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Select a complementary color as secondary"""
    # Get HSL of primary
    primary_h, _, _ = rgb_to_hsl(primary)
    
    # Find color with different hue
    best_color = None
    max_hue_diff = 0
    
    for color in colors:
        if color == primary or is_grayscale(color):
            continue
        
        h, s, l = rgb_to_hsl(color)
        hue_diff = abs(primary_h - h)
        
        # Normalize to 0-180 range
        if hue_diff > 180:
            hue_diff = 360 - hue_diff
        
        if hue_diff > max_hue_diff:
            max_hue_diff = hue_diff
            best_color = color
    
    # If no good secondary found, use green
    if best_color is None:
        return (34, 197, 94)
    
    return best_color


def get_text_color(bg_color: str) -> str:
    """Determine optimal text color (white or dark gray) for background"""
    rgb = hex_to_rgb(bg_color)
    luminance = get_luminance(rgb)
    
    # If background is dark, use white text
    if luminance < 0.5:
        return '#ffffff'
    else:
        return '#1f2937'  # Dark gray for light backgrounds


def tint_color(hex_color: str, factor: float) -> str:
    """Mix color with white (factor 0-1)"""
    rgb = hex_to_rgb(hex_color)
    new_rgb = tuple(int(c + (255 - c) * factor) for c in rgb)
    return rgb_to_hex(new_rgb)

def shade_color(hex_color: str, factor: float) -> str:
    """Mix color with black (factor 0-1)"""
    rgb = hex_to_rgb(hex_color)
    new_rgb = tuple(int(c * (1 - factor)) for c in rgb)
    return rgb_to_hex(new_rgb)

def generate_light_palette_from_colors(colors: List[Tuple[int, int, int]]) -> Dict[str, str]:
    """
    Generate LIGHT MODE theme palette from dominant colors.
    Uses a very light tint of the primary color for the background to make it 'alive'.
    """
    primary_rgb = select_primary_color(colors)
    secondary_rgb = select_secondary_color(colors, primary_rgb)
    
    primary = rgb_to_hex(primary_rgb)
    secondary = rgb_to_hex(secondary_rgb)
    
    # Check contrast of primary on white
    if calculate_contrast_ratio(primary, '#ffffff') < 4.5:
        # Darken primary for accessibility in light mode
        primary = adjust_brightness(primary, 0.7)

    primary_hover = adjust_brightness(primary, 0.9)
    
    # Backgrounds: Tinted white instead of pure white
    # Mix primary with 98% white
    bg_tint = tint_color(primary, 0.98)
    card_bg = '#ffffff'
    surface = tint_color(primary, 0.95)
    
    accent = adjust_saturation(primary, 1.2)
    error = '#dc2626'
    
    palette = {
        'primary': primary,
        'primary_hover': primary_hover,
        'secondary': secondary,
        'bg': bg_tint,
        'card_bg': card_bg,
        'text_primary': '#0f172a',
        'text_secondary': '#475569',
        'surface': surface,
        'accent': accent,
        'error': error,
    }
    return palette


def generate_dark_palette_from_colors(colors: List[Tuple[int, int, int]]) -> Dict[str, str]:
    """
    Generate DARK MODE theme palette from dominant colors.
    Uses a rich dark tint of the primary/dominant color for the background.
    """
    primary_rgb = select_primary_color(colors)
    secondary_rgb = select_secondary_color(colors, primary_rgb)
    
    # For Dark Mode, we often want a lighter/brighter primary to pop against dark
    primary = rgb_to_hex(primary_rgb)
    secondary = rgb_to_hex(secondary_rgb)
    
    # Brighten primary if it's too dark
    if get_luminance(primary_rgb) < 0.3:
        primary = adjust_brightness(primary, 1.4)

    primary_hover = adjust_brightness(primary, 0.9)
    
    # Backgrounds: Deep rich color derived from primary or logo dominance
    # Instead of #0f172a (Slate 900), let's use a very dark shade of the extracted color
    # Mix primary with 95% black
    bg_deep = shade_color(primary, 0.92)
    
    # Ensure it's not pitch black, and has some "flavor"
    # But if primary is very bright yellow, shading it might look weird. 
    # Let's map it to a cool dark slate tint or warm gray depending on hue.
    h, s, l = rgb_to_hsl(primary_rgb)
    
    # Creating a "Night" version of the card
    card_bg = adjust_brightness(bg_deep, 1.5) # Slightly lighter than bg
    surface = adjust_brightness(bg_deep, 2.0)
    
    accent = adjust_saturation(primary, 1.3)
    error = '#ef4444'
    
    palette = {
        'primary': primary,
        'primary_hover': primary_hover,
        'secondary': secondary,
        'bg': bg_deep,
        'card_bg': card_bg,
        'text_primary': '#f8fafc',
        'text_secondary': '#94a3b8',
        'surface': surface,
        'accent': accent,
        'error': error,
    }
    
    # Validate contrast
    if calculate_contrast_ratio(palette['primary'], palette['bg']) < 4.5:
        # If still low contrast, brighten primary more
        palette['primary'] = adjust_brightness(palette['primary'], 1.3)
        
    return palette


def analyze_logo(image_path: str) -> Dict[str, Dict[str, str]]:
    """
    Main function: Analyze logo and return DUAL theme palettes (light + dark)
    
    Args:
        image_path: Path to logo image file
        
    Returns:
        Dictionary with 'light' and 'dark' palettes:
        {
            'light': {color_key: hex_value, ...},
            'dark': {color_key: hex_value, ...}
        }
    """
    if not os.path.exists(image_path):
        # Return default dual palette if file not found
        return {
            'light': {
                'primary': '#3b82f6',
                'primary_hover': '#2563eb',
                'secondary': '#22c55e',
                'bg': '#ffffff',
                'card_bg': '#f8fafc',
                'text_primary': '#0f172a',
                'text_secondary': '#475569',
                'surface': '#e2e8f0',
                'accent': '#f59e0b',
                'error': '#dc2626',
            },
            'dark': {
                'primary': '#3b82f6',
                'primary_hover': '#2563eb',
                'secondary': '#22c55e',
                'bg': '#0f172a',
                'card_bg': '#1e293b',
                'text_primary': '#ffffff',
                'text_secondary': '#94a3b8',
                'surface': '#334155',
                'accent': '#f59e0b',
                'error': '#ef4444',
            }
        }
    
    # Extract dominant colors
    colors = kmeans_color_extraction(image_path, n_colors=5)
    
    # Generate BOTH palettes from the same colors
    light_palette = generate_light_palette_from_colors(colors)
    dark_palette = generate_dark_palette_from_colors(colors)
    
    return {
        'light': light_palette,
        'dark': dark_palette
    }


# Utility function for testing
if __name__ == '__main__':
    # Test with various scenarios
    print("Testing contrast ratios:")
    print(f"White on Black: {calculate_contrast_ratio('#ffffff', '#000000'):.2f}:1")
    print(f"Blue on Navy: {calculate_contrast_ratio('#3b82f6', '#0f172a'):.2f}:1")
    print(f"Green on Navy: {calculate_contrast_ratio('#22c55e', '#0f172a'):.2f}:1")
    
    print("\nTesting brightness adjustment:")
    print(f"Original: #3b82f6")
    print(f"Darker: {adjust_brightness('#3b82f6', 0.8)}")
    print(f"Lighter: {adjust_brightness('#3b82f6', 1.2)}")
