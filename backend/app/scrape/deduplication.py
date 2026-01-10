"""
Deduplication utilities for scraping.
Provides functions to normalize URLs and content, and generate hashes for deduplication.
"""
import hashlib
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def normalize_url(url: str) -> str:
    """
    Normalize a URL for deduplication.

    Steps:
    1. Parse URL
    2. Convert to lowercase (scheme and domain)
    3. Remove default ports (80 for http, 443 for https)
    4. Remove trailing slashes
    5. Sort query parameters
    6. Remove tracking parameters (utm_*, fbclid, etc.)
    7. Remove fragment

    Example:
        https://Example.com:443/path/?utm_source=twitter&id=123#section
        -> https://example.com/path?id=123
    """
    parsed = urlparse(url.strip())

    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Remove default ports
    if ":" in netloc:
        host, port = netloc.rsplit(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host

    # Remove trailing slash from path
    path = parsed.path.rstrip("/") or "/"

    # Parse and filter query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=True)

    # List of tracking parameters to remove
    tracking_params = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "msclkid",
        "_ga",
        "mc_cid",
        "mc_eid",
    }

    # Filter out tracking params and sort
    filtered_params = {k: v for k, v in query_params.items() if k not in tracking_params}

    # Sort params and rebuild query string
    sorted_query = urlencode(sorted(filtered_params.items()), doseq=True)

    # Rebuild URL without fragment
    normalized = urlunparse((scheme, netloc, path, "", sorted_query, ""))

    return normalized


def normalize_content(content: str) -> str:
    """
    Normalize content text for deduplication.

    Steps:
    1. Convert to lowercase
    2. Remove extra whitespace (multiple spaces, tabs, newlines)
    3. Remove punctuation (keep only alphanumeric and spaces)
    4. Trim

    This helps detect near-duplicate content even with minor formatting differences.
    """
    # Lowercase
    normalized = content.lower()

    # Remove extra whitespace
    normalized = re.sub(r"\s+", " ", normalized)

    # Remove punctuation (optional - comment out if too aggressive)
    # normalized = re.sub(r'[^\w\s]', '', normalized)

    # Trim
    normalized = normalized.strip()

    return normalized


def hash_text(text: str) -> str:
    """
    Generate SHA-256 hash of text.

    Args:
        text: Text to hash

    Returns:
        64-character hex string (SHA-256 hash)
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_url_hash(url: str) -> str:
    """
    Generate a hash for a URL after normalization.

    Args:
        url: Original URL

    Returns:
        64-character hex string (SHA-256 hash of normalized URL)
    """
    normalized_url = normalize_url(url)
    return hash_text(normalized_url)


def generate_content_hash(content: str, normalize: bool = True) -> str:
    """
    Generate a hash for content.

    Args:
        content: Content text
        normalize: Whether to normalize content before hashing (recommended)

    Returns:
        64-character hex string (SHA-256 hash)
    """
    text_to_hash = normalize_content(content) if normalize else content
    return hash_text(text_to_hash)


def check_similarity(content1: str, content2: str, threshold: float = 0.9) -> bool:
    """
    Check if two content strings are similar using simple character-based similarity.

    This is a basic implementation. For production, consider using:
    - Levenshtein distance
    - Jaccard similarity
    - TF-IDF + cosine similarity

    Args:
        content1: First content string
        content2: Second content string
        threshold: Similarity threshold (0.0 to 1.0)

    Returns:
        True if similarity >= threshold
    """
    # Normalize both
    norm1 = normalize_content(content1)
    norm2 = normalize_content(content2)

    # Simple character overlap similarity
    set1 = set(norm1)
    set2 = set(norm2)

    if not set1 or not set2:
        return False

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    similarity = intersection / union if union > 0 else 0

    return similarity >= threshold


# Example usage and testing
if __name__ == "__main__":
    # Test URL normalization
    test_urls = [
        "https://Example.com:443/path/?utm_source=twitter&id=123#section",
        "https://example.com/path?id=123",
        "https://example.com/path/?id=123&utm_campaign=test",
    ]

    print("URL Normalization:")
    for url in test_urls:
        normalized = normalize_url(url)
        url_hash = generate_url_hash(url)
        print(f"  {url}")
        print(f"  -> {normalized}")
        print(f"  -> {url_hash[:16]}...")
        print()

    # Test content hashing
    content1 = "This is a test article about politics."
    content2 = "this   is  a TEST article   about politics."  # Different whitespace/case
    content3 = "This is a completely different article."

    print("Content Hashing:")
    print(f"Content 1: {content1}")
    print(f"  Hash: {generate_content_hash(content1)[:16]}...")
    print(f"Content 2: {content2}")
    print(f"  Hash: {generate_content_hash(content2)[:16]}...")
    print(f"Content 3: {content3}")
    print(f"  Hash: {generate_content_hash(content3)[:16]}...")
    print()
    print(f"Content 1 == Content 2? {generate_content_hash(content1) == generate_content_hash(content2)}")
    print(f"Content 1 == Content 3? {generate_content_hash(content1) == generate_content_hash(content3)}")
