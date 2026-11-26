import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from sunnynui.data.label_photos import LabelStore, make_handler


@pytest.fixture
def store(tmp_path):
    src = tmp_path / "my_pets"
    src.mkdir()
    for name in ["b.jpg", "A.png", "c.JPEG"]:
        (src / name).write_bytes(b"img-" + name.encode())
    (src / "notes.txt").write_text("not an image")
    return LabelStore(src, tmp_path / "out")


def test_lists_only_images_sorted(store):
    assert store.images() == ["A.png", "b.jpg", "c.JPEG"]


def test_label_copies_and_keeps_original(store):
    store.set_label("b.jpg", "sunny")
    assert (store.out / "cat_sunny" / "b.jpg").read_bytes() == b"img-b.jpg"
    assert (store.src / "b.jpg").exists()
    assert store.label_of("b.jpg") == "sunny"


def test_relabel_moves_between_folders(store):
    store.set_label("b.jpg", "sunny")
    store.set_label("b.jpg", "nui")
    assert not (store.out / "cat_sunny" / "b.jpg").exists()
    assert (store.out / "cat_nui" / "b.jpg").exists()


def test_together_label(store):
    store.set_label("A.png", "together")
    assert (store.out / "cat_together" / "A.png").exists()
    store.set_label("A.png", "sunny")
    assert not (store.out / "cat_together" / "A.png").exists()


def test_clear_label(store):
    store.set_label("b.jpg", "nui")
    store.set_label("b.jpg", None)
    assert store.label_of("b.jpg") is None
    assert (store.src / "b.jpg").exists()


def test_rejects_unknown_label_and_path_traversal(store):
    with pytest.raises(ValueError):
        store.set_label("b.jpg", "garfield")
    with pytest.raises(KeyError):
        store.set_label("../secret.jpg", "sunny")
    with pytest.raises(KeyError):
        store.set_label("notes.txt", "sunny")


def test_snapshot_counts(store):
    store.set_label("A.png", "sunny")
    store.set_label("b.jpg", "nui")
    snap = store.snapshot()
    assert snap["counts"] == {"sunny": 1, "nui": 1, "together": 0}
    assert [i["label"] for i in snap["items"]] == ["sunny", "nui", None]


def test_http_roundtrip(store):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert b"Sunny or Nui" in urllib.request.urlopen(base + "/").read()
        assert urllib.request.urlopen(base + "/img/b.jpg").read() == b"img-b.jpg"
        req = urllib.request.Request(
            base + "/api/label",
            data=json.dumps({"name": "c.JPEG", "label": "nui"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        assert json.loads(urllib.request.urlopen(req).read())["label"] == "nui"
        state = json.loads(urllib.request.urlopen(base + "/api/state").read())
        assert state["counts"] == {"sunny": 0, "nui": 1, "together": 0}
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(base + "/img/..%2Fsecret.jpg")
        assert err.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
