"""Watches the data/ folder and embeds any new or changed PDF into Qdrant."""
import json
import threading
import time
from pathlib import Path

from . import config
from .embedder import GeminiEmbedder
from .pdf import iter_pages, to_base64
from .vector_store import VectorStore

STATE_FILE = config.DATA_DIR / ".processed_files.json"


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _signature(pdf: Path) -> list:
    stat = pdf.stat()
    return [stat.st_mtime, stat.st_size]


def ingest_pdf(pdf: Path, embedder: GeminiEmbedder, store: VectorStore, source: str | None = None):
    source = source or pdf.name
    print(f"Ingesting {source}...")
    for page, total, image in iter_pages(pdf):
        vector = embedder.embed_image(image)
        store.ensure_collection(len(vector))
        store.add_page(vector, to_base64(image), source, page)
        print(f"  {source}: page {page}/{total}")
    print(f"Done: {source}")


def scan_once(embedder: GeminiEmbedder, store: VectorStore):
    state = _load_state()
    for pdf in sorted(config.DATA_DIR.glob("*.pdf")):
        sig = _signature(pdf)
        if state.get(pdf.name) == sig:
            continue
        try:
            ingest_pdf(pdf, embedder, store)
            state[pdf.name] = sig
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception as e:
            print(f"Failed to ingest {pdf.name}: {e}")


def _loop(embedder, store):
    while True:
        try:
            scan_once(embedder, store)
        except Exception as e:
            print(f"Ingestion scan error: {e}")
        time.sleep(config.SCAN_INTERVAL_SECONDS)


def start_background_ingestion(embedder, store):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=_loop, args=(embedder, store), daemon=True).start()
