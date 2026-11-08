"""Accent-insensitive matching without changing quoted source content."""

import unicodedata


def fold(text: str) -> str:
    decomposed = unicodedata.normalize('NFKD', text.casefold()).replace('đ', 'd')
    return ' '.join(''.join(c for c in decomposed if not unicodedata.combining(c)).split())


def semantic_query(text: str) -> str:
    """Remove only explicitly labelled document codes, retaining data/conditions."""
    import re

    return re.sub(r'QTK[DĐ]\s*\d\.\d{3}(?!\d)', '', text, flags=re.IGNORECASE).strip()
