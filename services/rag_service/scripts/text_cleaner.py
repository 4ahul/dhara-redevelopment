"""
Text Cleaning & Multilingual Preprocessing
Handles Devanagari normalization, OCR artifacts, language detection.
"""

import re
import unicodedata
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def detect_language(text: str) -> str:
    """Detect text language: en, mr, hi, or mixed."""
    if not text or len(text.strip()) < 20:
        return "en"

    try:
        from langdetect import detect

        lang = detect(text)
        if lang in ("mr", "hi", "bn", "gu", "ta", "te", "kn", "ml", "pa", "ur"):
            # Map all Indic to mr/hi heuristic
            devanagari_count = sum(1 for c in text if "\u0900" <= c <= "\u097f")
            latin_count = sum(1 for c in text if c.isascii() and c.isalpha())
            if devanagari_count > latin_count:
                # Distinguish Marathi vs Hindi by common words
                marathi_markers = {
                    "आहे",
                    "म्हणून",
                    "तर",
                    "काय",
                    "करणे",
                    "यांचे",
                    "असे",
                    "झाले",
                    "होते",
                    "पाहिजे",
                }
                hindi_markers = {
                    "है",
                    "के",
                    "से",
                    "को",
                    "में",
                    "पर",
                    "का",
                    "की",
                    "करना",
                    "होना",
                }
                text_words = set(text.split())
                mr_hits = len(text_words & marathi_markers)
                hi_hits = len(text_words & hindi_markers)
                return "mr" if mr_hits >= hi_hits else "hi"
            return "mixed"
        elif lang == "en":
            devanagari_count = sum(1 for c in text if "\u0900" <= c <= "\u097f")
            if devanagari_count > len(text) * 0.1:
                return "mixed"
            return "en"
        return lang
    except Exception:
        # Fallback: count scripts
        devanagari = sum(1 for c in text if "\u0900" <= c <= "\u097f")
        latin = sum(1 for c in text if c.isascii() and c.isalpha())
        if devanagari > latin:
            return "hi"
        if devanagari > 0:
            return "mixed"
        return "en"


# ---------------------------------------------------------------------------
# Devanagari normalization
# ---------------------------------------------------------------------------

# Zero-width characters that break embeddings
ZERO_WIDTH_RE = re.compile(
    "["
    + "\u200b"  # ZERO WIDTH SPACE
    + "\u200c"  # ZERO WIDTH NON-JOINER
    + "\u200d"  # ZERO WIDTH JOINER
    + "\u200e"  # LEFT-TO-RIGHT MARK
    + "\u200f"  # RIGHT-TO-LEFT MARK
    + "\ufeff"  # BYTE ORDER MARK
    + "\u00ad"  # SOFT HYPHEN
    + "\u2060"  # WORD JOINER
    + "]",
    re.UNICODE,
)

# Common Devanagari ligature/variant mappings for normalization
DEVANAGARI_NORMALIZE = {
    "\u0958": "\u0915\u093c",  # क़
    "\u0959": "\u0916\u093c",  # ख़
    "\u095a": "\u0917\u093c",  # ग़
    "\u095b": "\u091c\u093c",  # ज़
    "\u095c": "\u0921\u093c",  # ड़
    "\u095d": "\u0922\u093c",  # ढ़
    "\u095e": "\u092b\u093c",  # फ़
    "\u095f": "\u092f\u093c",  # य़
}


def normalize_devanagari(text: str) -> str:
    """Normalize Devanagari script: NFC, fix ligatures, remove combining junk."""
    # Unicode NFC normalization
    text = unicodedata.normalize("NFC", text)

    # Replace nuktas with composed forms
    for composed, decomposed in DEVANAGARI_NORMALIZE.items():
        text = text.replace(composed, decomposed)

    # Remove stray halant + virama sequences
    text = re.sub(r"\u094d\s+", "\u094d", text)

    return text


# ---------------------------------------------------------------------------
# OCR artifact cleaning
# ---------------------------------------------------------------------------

# Common OCR misreads in Devanagari/English mixed text
OCR_ARTIFACTS = [
    (re.compile(r"\|\s*\|"), " "),  # Double pipes from table borders
    (re.compile(r"(?<![a-zA-Z])l(?![a-zA-Z])"), "1"),  # lone l -> 1
    (re.compile(r"(?<![a-zA-Z])O(?=\d)"), "0"),  # O before digit -> 0
    (re.compile(r"(?<=\d),(?=\d{3})"), ","),  # keep comma in numbers
    (re.compile(r"\.{4,}"), "..."),  # Excessive dots
    (re.compile(r"-{4,}"), "—"),  # Excessive dashes
    (re.compile(r"_{3,}"), ""),  # Underscore lines
    (re.compile(r"\x00+"), ""),  # Null bytes
]

# Control characters (except newline and tab)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Multiple whitespace
MULTI_SPACE_RE = re.compile(r"[ \t]{3,}")
MULTI_NEWLINE_RE = re.compile(r"\n{4,}")

# Broken words from PDF extraction (word-\nword -> wordword)
HYPHENATED_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")


def clean_text(text: str, aggressive: bool = False) -> str:
    """
    Clean extracted text for embedding.

    Args:
        text: Raw extracted text
        aggressive: If True, also strip all non-ASCII non-Devanagari chars
    """
    if not text:
        return ""

    # 1. Remove zero-width characters
    text = ZERO_WIDTH_RE.sub("", text)

    # 2. Normalize Devanagari
    text = normalize_devanagari(text)

    # 3. Remove control characters
    text = CONTROL_CHAR_RE.sub("", text)

    # 4. Clean OCR artifacts
    for pattern, replacement in OCR_ARTIFACTS:
        text = pattern.sub(replacement, text)

    # 5. Fix hyphenated line breaks (PDF extraction artifact)
    text = HYPHENATED_LINEBREAK_RE.sub(r"\1\2", text)

    # 6. Normalize whitespace
    text = MULTI_SPACE_RE.sub("  ", text)
    text = MULTI_NEWLINE_RE.sub("\n\n\n", text)

    # 7. Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # 8. Aggressive cleaning: remove stray special chars
    if aggressive:
        # Keep: ASCII printable, Devanagari block, common punctuation
        text = re.sub(
            r"[^\x20-\x7e\u0900-\u097f\u0a00-\u0a7f\n\t.,;:!?\"'()\\[\\]{}/\\-+*=<>@#$%&~`|]",
            " ",
            text,
        )

    # Final whitespace pass
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def clean_and_detect(text: str) -> Tuple[str, str]:
    """Clean text and detect language in one pass. Returns (cleaned_text, language)."""
    cleaned = clean_text(text)
    lang = detect_language(cleaned) if len(cleaned) > 20 else "en"
    return cleaned, lang


# ---------------------------------------------------------------------------
# Content type detection for Milvus metadata
# ---------------------------------------------------------------------------

DOC_TYPE_PATTERNS = {
    "dcpr": re.compile(
        r"DCPR|UDCPR|Development Control|Promotion Regulation", re.IGNORECASE
    ),
    "act": re.compile(r"MRTP|Municipal Corporation Act|Bombay", re.IGNORECASE),
    "circular": re.compile(r"Circular|CIRCULAR|Office Order|Memorandum", re.IGNORECASE),
    "guideline": re.compile(r"Guideline|Guidance|Procedure|Manual", re.IGNORECASE),
    "notice": re.compile(r"Notice|NOTICE|Order|ORDER", re.IGNORECASE),
    "tender": re.compile(r"Tender|TENDER|NIT|Invitation", re.IGNORECASE),
    "policy": re.compile(r"Policy|IT Policy|Information Technology", re.IGNORECASE),
}


def detect_doc_type(text: str, filename: str = "") -> str:
    """Detect document type from text content and filename."""
    combined = f"{filename} {text[:2000]}"
    for doc_type, pattern in DOC_TYPE_PATTERNS.items():
        if pattern.search(combined):
            return doc_type
    return "other"


CHUNK_TYPE_PATTERNS = {
    "table": re.compile(r"^\s*\|.+\|.+\|", re.MULTILINE),
    "heading": re.compile(
        r"^#{1,3}\s|^[A-Z][A-Z\s]{5,}$|^(?:CHAPTER|PART|REGULATION)\s",
        re.MULTILINE | re.IGNORECASE,
    ),
    "clause": re.compile(
        r"^\s*\(\d+\)|^\s*\d+\.\d+|^\s*Clause\s", re.MULTILINE | re.IGNORECASE
    ),
    "list": re.compile(r"^\s*[-*•]\s|^\s*\d+[\.\)]\s", re.MULTILINE),
}


def detect_chunk_type(text: str) -> str:
    """Detect the structural type of a text chunk."""
    for chunk_type, pattern in CHUNK_TYPE_PATTERNS.items():
        if pattern.search(text[:500]):
            return chunk_type
    return "paragraph"


if __name__ == "__main__":
    # Quick test
    test_samples = [
        ("FSI shall not exceed 2.5 for residential buildings", "en"),
        ("महाराष्ट्र शासनाचा निर्णय क्रमांक एफएसआय २.५ पेक्षा जास्त नसावा", "mr"),
        ("महाराष्ट्र सरकार का निर्णय संख्या एफएसआई 2.5 से अधिक नहीं होना चाहिए", "hi"),
    ]
    for text, expected in test_samples:
        cleaned = clean_text(text)
        lang = detect_language(cleaned)
        print(f"Expected: {expected}, Detected: {lang}")
        print(f"  Clean: {cleaned[:80]}")
        print()
