"""Turn an uploaded file into text, page by page, including the text inside images.

- Digital PDFs: pypdf reads the text layer of each page.
- Images inside a PDF (diagrams, charts, a scanned page, a photo of a stamp):
  each embedded image is OCR'd with Tesseract and its text is appended to the
  page as "[Figure N, p.P] ...". So a chunk built from it still cites its page,
  and that text goes through PII redaction and the injection scan like any other.
- Image files (.png/.jpg/...): OCR'd the same way.
- Plain text / markdown / email bodies: decoded as UTF-8.

OCR is optional (OCR_IMAGES in .env, needs the tesseract binary + pytesseract).
Every image is reported in the trace: page, size, words read, or why it was skipped.
A page that is only an image we could not read is reported too, and sends the
document to review, because we would otherwise be silently missing part of it.
"""
import io
import os
import re
from dataclasses import dataclass, field

from ..config import settings


@dataclass
class Page:
    number: int      # 1-based page number (text files are a single page 1)
    text: str


@dataclass
class Extraction:
    pages: list[Page]
    figures: list[dict] = field(default_factory=list)    # one entry per image seen
    unreadable_pages: list[int] = field(default_factory=list)


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
TEXT_EXTENSIONS = (".txt", ".md", ".csv", ".eml")
MIN_IMAGE_PIXELS = 120 * 120          # smaller images are logos / icons: not worth OCR
MIN_OCR_WORDS = 3                     # fewer real words than this = "no readable text in image"
WORD = re.compile(r"[^\W\d_]{2,}")


def extract_pages(file_name: str, data: bytes) -> list[Page]:
    return extract_document(file_name, data).pages


def extract_document(file_name: str, data: bytes) -> Extraction:
    name = file_name.lower()
    if name.endswith(".pdf"):
        return _from_pdf(data)
    if name.endswith(IMAGE_EXTENSIONS):
        text, words = _ocr(data)
        fig = {"page": 1, "figure": 1, "ocr_words": words, "status": "read" if words else "no text"}
        return Extraction([Page(1, text)] if words else [], [fig], [] if words else [1])
    if name.endswith(TEXT_EXTENSIONS):
        return Extraction([Page(1, data.decode("utf-8", errors="ignore"))])
    raise ValueError(f"Unsupported file type: {file_name}")


def _from_pdf(data: bytes) -> Extraction:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    result = Extraction([])
    for i, pdf_page in enumerate(reader.pages, start=1):
        text = (pdf_page.extract_text() or "").strip()
        figure_texts = []
        for n, fig, fig_text in _page_figures(pdf_page, i):
            result.figures.append(fig)
            if fig_text:
                figure_texts.append(f"[Figure {n}, p.{i}] {fig_text}")
        if figure_texts:
            text = (text + "\n" + "\n".join(figure_texts)).strip()
        if text:
            result.pages.append(Page(i, text))
        elif any(f["page"] == i for f in result.figures):
            result.unreadable_pages.append(i)       # an image-only page we could not read
    return result


def _page_figures(pdf_page, page_no: int):
    """Yield (figure number, trace entry, OCR text or '') for each image on the page."""
    try:
        images = list(pdf_page.images)
    except Exception as exc:                        # a broken image stream must not fail the upload
        yield 1, {"page": page_no, "figure": 1, "status": f"could not decode images: {exc}"[:120]}, ""
        return
    for n, img in enumerate(images, start=1):
        fig = {"page": page_no, "figure": n, "name": img.name}
        try:
            width, height = img.image.size
            fig["size"] = f"{width}x{height}"
        except Exception:
            width = height = 0
        if width * height < MIN_IMAGE_PIXELS:
            fig["status"] = "skipped: too small (logo/icon)"
            yield n, fig, ""
            continue
        if not settings.ocr_images:
            fig["status"] = "skipped: OCR_IMAGES=false"
            yield n, fig, ""
            continue
        try:
            text, words = _ocr(img.data)
        except ValueError as exc:
            fig["status"] = f"skipped: {exc}"
            yield n, fig, ""
            continue
        fig["ocr_words"] = words
        fig["status"] = "read" if words >= MIN_OCR_WORDS else "no readable text in image"
        fig["preview"] = text[:160]
        yield n, fig, text if words >= MIN_OCR_WORDS else ""


def _ocr(data: bytes) -> tuple[str, int]:
    """OCR one image. Returns (text with one line per OCR line, number of real words)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ValueError("OCR not installed (pip install pytesseract Pillow + tesseract binary)") from exc
    if os.getenv("TESSERACT_CMD"):                 # Windows: path to tesseract.exe if it is not on PATH
        pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")
    try:
        image = Image.open(io.BytesIO(data)).convert("L")
        if min(image.size) < 1000:                 # small renders OCR better when upscaled
            scale = 1000 / min(image.size)
            image = image.resize((int(image.width * scale), int(image.height * scale)))
        raw = pytesseract.image_to_string(image, lang=_ocr_languages())
    except pytesseract.TesseractNotFoundError as exc:
        raise ValueError("tesseract binary not installed") from exc
    # drop OCR noise lines (chart ticks, smudges): keep lines with at least 4 letters/digits
    lines = [ln.strip() for ln in raw.splitlines() if sum(ch.isalnum() for ch in ln) >= 4]
    text = "\n".join(lines)
    return text, len(WORD.findall(text))


_LANGS = None


def _ocr_languages() -> str:
    """English always; Hindi and Malayalam when their Tesseract language packs are installed."""
    global _LANGS
    if _LANGS is None:
        import pytesseract
        installed = set(pytesseract.get_languages(config=""))
        _LANGS = "+".join(lang for lang in ("eng", "hin", "mal") if lang in installed) or "eng"
    return _LANGS
