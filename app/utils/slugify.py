import re


def slugify(input_str: str) -> str:
    """
    Convert a string to a URL-friendly slug.
    Mirrors the JavaScript slugify behavior:
    1. Lowercase and trim
    2. Replace non-alphanumeric chars with hyphens
    3. Remove leading/trailing hyphens
    """
    if not input_str:
        return ""
        
    s = str(input_str).lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"(^-|-$)+", "", s)
    return s
