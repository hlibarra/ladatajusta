"""
Utility for generating URL-friendly slugs from text.
"""
import re
import unicodedata


def slugify(text: str, max_length: int = 100) -> str:
    """
    Convert text to URL-friendly slug.

    Examples:
        "¿Cómo está el clima?" -> "como-esta-el-clima"
        "Argentina clasifica al Mundial 2026" -> "argentina-clasifica-al-mundial-2026"
    """
    # Normalize unicode characters (áéíóú -> aeiou)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)

    # Remove leading/trailing hyphens
    text = text.strip('-')

    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length].rsplit('-', 1)[0]

    return text


def generate_unique_slug(base_slug: str, existing_slugs: set[str]) -> str:
    """
    Generate a unique slug by appending a number if necessary.

    Example:
        base_slug="noticia", existing={"noticia", "noticia-2"}
        returns "noticia-3"
    """
    if base_slug not in existing_slugs:
        return base_slug

    counter = 2
    while f"{base_slug}-{counter}" in existing_slugs:
        counter += 1

    return f"{base_slug}-{counter}"
