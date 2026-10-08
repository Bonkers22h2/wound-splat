import re
from difflib import SequenceMatcher
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

ROOT = Path(r"C:\Users\bonkc\Documents\wound-splat")
ORIGINAL = ROOT / "MAIN DOCUMENT (WOUND-SPLAT) - WORKING COPY.docx"
REVISED = ROOT / "MAIN DOCUMENT (WOUND-SPLAT) - REVISED.docx"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}


def extract(path):
    with ZipFile(path) as zf:
        root = etree.fromstring(zf.read("word/document.xml"))
    paragraphs = []
    for p in root.xpath(".//w:body//w:p", namespaces=NS):
        text = "".join(p.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS)).strip()
        if text:
            paragraphs.append(text)
    all_text = "\n".join(paragraphs)
    words = re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*|[^\w\s]", all_text, flags=re.UNICODE)
    return paragraphs, words


op, ow = extract(ORIGINAL)
rp, rw = extract(REVISED)

word_matcher = SequenceMatcher(None, ow, rw, autojunk=False)
matched_words = sum(block.size for block in word_matcher.get_matching_blocks())
original_changed_words = len(ow) - matched_words
new_or_rewritten_words = len(rw) - matched_words
retained_pct = matched_words / len(ow) * 100
changed_original_pct = original_changed_words / len(ow) * 100

para_matcher = SequenceMatcher(None, op, rp, autojunk=False)
matched_paragraphs = sum(block.size for block in para_matcher.get_matching_blocks())
changed_original_paragraphs = len(op) - matched_paragraphs
paragraph_changed_pct = changed_original_paragraphs / len(op) * 100

print(f"original_words={len(ow)}")
print(f"revised_words={len(rw)}")
print(f"matched_words={matched_words}")
print(f"retained_original_words_pct={retained_pct:.2f}")
print(f"changed_original_words_pct={changed_original_pct:.2f}")
print(f"new_or_rewritten_words={new_or_rewritten_words}")
print(f"original_paragraphs={len(op)}")
print(f"revised_paragraphs={len(rp)}")
print(f"matched_paragraphs={matched_paragraphs}")
print(f"changed_original_paragraphs={changed_original_paragraphs}")
print(f"changed_original_paragraphs_pct={paragraph_changed_pct:.2f}")
