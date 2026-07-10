import re

def clean_title(title):
    """
    Cleans the Amazon product title to extract core keywords.
    Removes common promotional spam words.
    """
    # Convert to lowercase for matching
    t = title.lower()
    
    # Remove sizes, measurements, and spam words
    spam_words = [
        r'\b\d+\s*x\s*\d+\s*(inches|inch|cm|mm)\b',
        r'\b\d+\s*pcs?\b',
        r'\b\d+\s*pieces?\b',
        r'fat quarters?',
        r'bundle',
        r'fabric for sewing',
        r'quilting',
        r'patchwork',
        r'diy',
        r'crafts?',
        r'scrap',
        r'by the yard'
    ]
    for w in spam_words:
        t = re.sub(w, '', t)
        
    t = re.sub(r'[^a-z\s]', ' ', t)
    t = ' '.join(t.split())
    
    # If the title became too short, fallback to a generic description
    if len(t) < 5:
        return "vintage ditsy floral"
    return t

def generate_prompts(title, hex_color, index=1):
    """
    Generates a strong constraint prompt based on the title and color.
    Returns a single prompt.
    """
    base_theme = clean_title(title)
    
    template = (
        f"Please look closely at the attached reference image of a floral fabric. "
        f"Extract the core floral pattern design from the fabric, "
        f"and generate a SINGLE, FLAT, SEAMLESS continuous ditsy floral pattern (四方连续小碎花印花) based on that design. "
        f"CRITICAL REQUIREMENT: I need exactly a 1024x1024 resolution image. "
        f"Do NOT include any folds, wrinkles, text, or background elements. "
        f"It must be a perfect flat, seamless texture tile. "
        f"Theme: {base_theme}. "
        f"Main color tone should be similar to {hex_color}."
    )
    
    return [template]
