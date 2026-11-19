"""Quick folder-per-class labeller for personal cat photos (TODO e01).

Serves a tiny local web UI that shows every image in ``my_pets`` one after another.
Press ``s`` for Sunny or ``n`` for Nui and the photo is *copied* into ``cat_sunny`` /
``cat_nui``. Originals are never modified, so every label is reversible (``u`` clears it).

Usage::

    uv run python -m sunnynui.data.label_photos
    uv run python -m sunnynui.data.label_photos --src path/to/my_pets --out data/raw/personal

The server binds to 127.0.0.1 only; nothing leaves the machine.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
LABELS = {"sunny": "cat_sunny", "nui": "cat_nui"}
DEFAULT_SRC = Path("data/raw/personal/my_pets")
DEFAULT_OUT = Path("data/raw/personal")
UI_FILE = Path(__file__).with_name("label_photos.html")


@dataclass
class LabelStore:
    """Maps photos in ``src`` to class folders under ``out`` (one copy per photo)."""

    src: Path
    out: Path

    def class_dir(self, label: str) -> Path:
        return self.out / LABELS[label]

    def images(self) -> list[str]:
        if not self.src.is_dir():
            return []
        return sorted(
            (p.name for p in self.src.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
            key=str.lower,
        )

    def resolve(self, name: str) -> Path:
        """Return the source path for ``name``; reject anything not listed in ``src``."""
        if name not in set(self.images()):
            raise KeyError(name)
        return self.src / name

    def label_of(self, name: str) -> str | None:
        for label in LABELS:
            if (self.class_dir(label) / name).exists():
                return label
        return None

    def set_label(self, name: str, label: str | None) -> None:
        """Copy ``name`` into the folder for ``label`` and remove it from the others.

        ``label=None`` clears the label (removes the copy from every class folder).
        """
        if label is not None and label not in LABELS:
            raise ValueError(f"unknown label {label!r}")
        source = self.resolve(name)
        for other in LABELS:
            if other != label:
                (self.class_dir(other) / name).unlink(missing_ok=True)
        if label is not None:
            target_dir = self.class_dir(label)
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target_dir / name)

    def snapshot(self) -> dict:
        items = [{"name": n, "label": self.label_of(n)} for n in self.images()]
        counts = {label: sum(i["label"] == label for i in items) for label in LABELS}
        return {"src": str(self.src), "out": str(self.out), "items": items, "counts": counts}


def make_handler(store: LabelStore) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # keep the console quiet
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
            self._send(status, json.dumps(payload).encode(), "application/json")

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(HTTPStatus.OK, UI_FILE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._json(store.snapshot())
            elif path.startswith("/img/"):
                try:
                    file = store.resolve(unquote(path[len("/img/") :]))
                except KeyError:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                    return
                ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
                self._send(HTTPStatus.OK, file.read_bytes(), ctype)
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if self.path != "/api/label":
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                store.set_label(body["name"], body.get("label"))
            except KeyError:
                self._json({"error": "unknown image"}, HTTPStatus.NOT_FOUND)
                return
            except (ValueError, TypeError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self._json({"name": body["name"], "label": store.label_of(body["name"])})

    return Handler


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="folder with unlabelled photos")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="parent of cat_sunny/cat_nui")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    store = LabelStore(args.src.resolve(), args.out.resolve())
    if not store.images():
        parser.exit(1, f"No images ({', '.join(sorted(IMAGE_EXTS))}) found in {store.src}\n")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(store))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Labelling {len(store.images())} photos from {store.src}")
    print(f"Copies go to {store.class_dir('sunny')} and {store.class_dir('nui')}")
    print(f"Open {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
