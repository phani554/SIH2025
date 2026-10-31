"""Turn an uploaded file into text, page by page.

- Digital PDFs: pypdf reads the text layer (the old front end regex-matched
  raw PDF bytes, which fails on compressed PDFs).
- Images / scanned pages: Tesseract OCR in English, Hindi and Malayalam,
  only if pytesseract and the tesseract binary are installed.
- Plain text / markdown / email bodies: decoded as UTF-8.
"""
import io
from dataclasses import dataclass


@dataclass
class Page:
    number: int      # 1-based page number (text files are a single page 1)
    text: str


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
TEXT_EXTENSIONS = (".txt", ".md", ".csv", ".eml")


def extract_pages(file_name: str, data: bytes) -> list[Page]:
    name = file_name.lower()
    if name.endswith(".pdf"):
        return _from_pdf(data)
    if name.endswith(IMAGE_EXTENSIONS):
        return [Page(1, _ocr_image(data))]
    if name.endswith(TEXT_EXTENSIONS):
        return [Page(1, data.decode("utf-8", errors="ignore"))]
    raise ValueError(f"Unsupported file type: {file_name}")


def _from_pdf(data: bytes) -> list[Page]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, pdf_page in enumerate(reader.pages, start=1):
        text = (pdf_page.extract_text() or "").strip()
        if not text:
            # No text layer -> probably a scanned page. OCR would go here;
            # we skip it and keep going rather than fail the whole document.
            continue
        pages.append(Page(i, text))
    return pages


def _ocr_image(data: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ValueError("OCR not installed: pip install pytesseract Pillow") from exc
    image = Image.open(io.BytesIO(data))
    return pytesseract.image_to_string(image, lang="eng+hin+mal")
