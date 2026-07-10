import io
import urllib.request
from PIL import Image
import collections

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

def get_dominant_color_from_local(file_path, num_colors=16):
    try:
        img = Image.open(file_path)
        img = img.convert('RGB')
        img.thumbnail((150, 150))
        img = img.quantize(colors=num_colors, method=Image.Quantize.FASTOCTREE)
        img = img.convert('RGB')
        
        colors = img.getcolors(maxcolors=22500)
        if not colors:
            return "#FFFFFF"
            
        colors.sort(key=lambda x: x[0], reverse=True)
        dominant_rgb = colors[0][1]
        return rgb_to_hex(dominant_rgb)
    except Exception as e:
        print(f"Error extracting color from local file {file_path}: {e}")
        return "#FFFFFF"

def get_dominant_color_from_url(url, num_colors=16):
    """
    Downloads an image from URL and extracts the most dominant color.
    Uses quantization to group similar colors.
    """
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            img_data = response.read()
        
        img = Image.open(io.BytesIO(img_data))
        img = img.convert('RGB')
        
        # Resize to speed up processing and naturally smooth out noise
        img.thumbnail((150, 150))
        
        # Quantize to a small palette to group similar background pixels
        img = img.quantize(colors=16, method=Image.Quantize.FASTOCTREE)
        img = img.convert('RGB')
        
        colors = img.getcolors(maxcolors=22500) # 150x150 = 22500
        if not colors:
            return "#FFFFFF" # Fallback
            
        # Sort colors by frequency (descending)
        colors.sort(key=lambda x: x[0], reverse=True)
        dominant_rgb = colors[0][1]
        
        return rgb_to_hex(dominant_rgb)
    except Exception as e:
        print(f"Error analyzing image {url}: {e}")
        return "#FFFFFF" # Fallback color

def is_collage(file_path):
    """
    Analyzes an image to determine if it is a collage (e.g. 4-piece or 6-piece grid).
    It looks for solid grid lines (very low variance rows and columns) in the middle of the image.
    """
    try:
        import numpy as np
        img = Image.open(file_path).convert('L')
        data = np.array(img)
        
        h, w = data.shape
        if h < 50 or w < 50:
            return False
            
        # Check variance across rows and columns
        row_vars = np.var(data, axis=1)
        col_vars = np.var(data, axis=0)
        
        # Grid lines are usually not exactly at the edge. 
        # Look for very low variance rows/cols in the middle 60% of the image.
        mid_row_vars = row_vars[int(h*0.2) : int(h*0.8)]
        mid_col_vars = col_vars[int(w*0.2) : int(w*0.8)]
        
        if len(mid_row_vars) == 0 or len(mid_col_vars) == 0:
            return False
            
        # If there is a row with very low variance (solid line) AND a col with very low variance,
        # it strongly indicates a grid/collage layout.
        if np.min(mid_row_vars) < 50 and np.min(mid_col_vars) < 50:
            return True
            
        return False
    except Exception as e:
        print(f"Error checking collage {file_path}: {e}")
        return False
