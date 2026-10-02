import re
import unicodedata
from typing import List

class TextNormalizer:
    @staticmethod
    def remove_accents(text: str) -> str:
        text = unicodedata.normalize('NFD', text)
        text = text.encode('ascii', 'ignore').decode('utf-8')
        return text

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        # Lowercase
        text = text.lower()
        # Remove accents for better matching
        text = TextNormalizer.remove_accents(text)
        # Remove special characters except common ones used in IT/Finance (like +, #)
        text = re.sub(r'[^a-z0-9\s\+\#\-\&]', ' ', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def normalize_list(items: List[str]) -> List[str]:
        return [TextNormalizer.normalize_text(i) for i in items if i]
