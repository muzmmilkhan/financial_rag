import base64
import gc
from io import BytesIO

from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image


def iter_pages(pdf_path, dpi=130, max_dim=1400):
    """Yield (page_number, total_pages, PIL image), one page at a time to save memory."""
    total = int(pdfinfo_from_path(str(pdf_path)).get("Pages", 0))
    for n in range(1, total + 1):
        try:
            img = convert_from_path(str(pdf_path), dpi=dpi, first_page=n, last_page=n)[0]
        except Exception as e:
            print(f"Skipping page {n}: {e}")
            continue
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        yield n, total, img
        gc.collect()


def to_base64(image: Image.Image) -> str:
    buf = BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()
