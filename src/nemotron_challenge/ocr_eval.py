"""OCR evaluation: a gold set of hand transcriptions and character and word error rates.

Gold set (team choice):
- 30 text blocks from 15 scans, chosen with a fixed seed from scans with status "ok".
- Block classes with running text only (no tables, pictures, or formulas), 150 to 900 characters.
- Scan row 1032 is excluded: its Super VL output was seen during the first probe.
- The transcriber reads an enlarged crop of each block and does not see any Super VL output first.

Transcription rules, also applied to every system output before scoring:
- The long s is written "s". Original spelling and punctuation stay.
- A word split by a line-break hyphen is joined. Whitespace is collapsed.
- An illegible word is written [?] and counts as one word.
"""
from __future__ import annotations

import random
import re
import unicodedata
from pathlib import Path
from typing import Any

TEXT_CLASSES = {"Text", "Footnote", "Section-header", "List-item", "Caption", "Title"}
GOLD_SEED = 20261018
GOLD_PAGES = 15
GOLD_BLOCKS_PER_PAGE = 2
EXCLUDED_ROWS = {1032}
CROP_PAD = 6
CROP_SCALE = 3


def eligible_blocks(page: dict[str, Any]) -> list[dict[str, Any]]:
    return [b for b in page["blocks"] if b["cls"] in TEXT_CLASSES and 150 <= len(b["text"]) <= 900]


def select_gold(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Choose blocks with a fixed seed. The result does not depend on any model output after Parse."""
    rng = random.Random(GOLD_SEED)
    candidates = sorted((p for p in pages if p["status"] == "ok" and p["row_index"] not in EXCLUDED_ROWS
                         and len(eligible_blocks(p)) >= GOLD_BLOCKS_PER_PAGE), key=lambda p: p["row_index"])
    chosen = sorted(rng.sample(candidates, GOLD_PAGES), key=lambda p: p["row_index"])
    gold = []
    for page in chosen:
        for block in sorted(rng.sample(eligible_blocks(page), GOLD_BLOCKS_PER_PAGE), key=lambda b: b["index"]):
            gold.append({"gold_id": f"G{len(gold) + 1:02d}", "page_id": page["page_id"], "row_index": page["row_index"],
                         "filename": page["filename"], "block_index": block["index"], "cls": block["cls"],
                         "bbox": block["bbox"]})
    return gold


def crop_block(image_path: Path, bbox: list[float], out: Path | None = None, *, pad: int = CROP_PAD,
               scale: int = CROP_SCALE) -> bytes:
    """Cut the block's box from the scan with a small margin and enlarge it. Returns JPEG bytes."""
    from io import BytesIO

    from PIL import Image

    with Image.open(image_path) as image:
        width, height = image.size
        x0, y0, x1, y1 = bbox
        box = (max(0, int(x0 * width) - pad), max(0, int(y0 * height) - pad),
               min(width, int(x1 * width) + pad), min(height, int(y1 * height) + pad))
        region = image.convert("RGB").crop(box)
        region = region.resize((region.width * scale, region.height * scale), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        region.save(buffer, format="JPEG", quality=92)
    data = buffer.getvalue()
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return data


def normalise(text: str) -> str:
    """Apply the transcription rules to any text before scoring. Scoring ignores case and accents."""
    text = text.replace("ſ", "s").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae").replace("Æ", "Ae").replace("—", "-")
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)
    text = re.sub(r"[*_`]+", "", text)  # Markdown emphasis from model output.
    text = re.sub(r"\s+([;:,.!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip().lower()


WORD_LIST = Path("/usr/share/dict/words")


def word_list() -> set[str]:
    """The system word list in lower case, or an empty set when the system has none."""
    if not WORD_LIST.is_file():
        return set()
    return {w.lower() for w in WORD_LIST.read_text(encoding="utf-8", errors="ignore").split()}


def fix_long_s(text: str, vocabulary: set[str]) -> str:
    """Rule-based baseline: read "f" as a long s when only the "s" form is a dictionary word."""
    def repair(match: re.Match[str]) -> str:
        word = match.group(0)
        lower = word.lower()
        if lower in vocabulary or "f" not in lower:
            return word
        positions = [i for i, ch in enumerate(lower) if ch == "f"][:4]
        for mask in range(1, 2 ** len(positions)):
            chars = list(word)
            for bit, position in enumerate(positions):
                if mask >> bit & 1:
                    chars[position] = "S" if chars[position].isupper() else "s"
            if "".join(chars).lower() in vocabulary:
                return "".join(chars)
        return word
    return re.sub(r"[A-Za-z]+", repair, text)


def edit_distance(a: list[str] | str, b: list[str] | str) -> int:
    previous = list(range(len(b) + 1))
    for i, item in enumerate(a, start=1):
        current = [i]
        for j, other in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (item != other)))
        previous = current
    return previous[-1]


def error_rates(reference: str, hypothesis: str) -> dict[str, Any]:
    ref, hyp = normalise(reference), normalise(hypothesis)
    ref_words, hyp_words = ref.split(), hyp.split()
    ref_set = {w.lower().strip(".,;:!?()") for w in ref_words}
    inserted = [w for w in hyp_words if w.lower().strip(".,;:!?()") not in ref_set]
    return {"ref_chars": len(ref), "char_edits": edit_distance(ref, hyp),
            "cer": round(edit_distance(ref, hyp) / max(1, len(ref)), 4),
            "ref_words": len(ref_words), "word_edits": edit_distance(ref_words, hyp_words),
            "wer": round(edit_distance(ref_words, hyp_words) / max(1, len(ref_words)), 4),
            "words_not_in_reference": len(inserted), "examples_not_in_reference": inserted[:8]}
