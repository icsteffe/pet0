from PIL import Image

from sunnynui.data.import_photos import import_photos


def test_import_converts_heic_copies_jpeg_skips_video(tmp_path):
    src = tmp_path / "pets" / "nested"
    src.mkdir(parents=True)
    Image.new("RGB", (8, 8), "orange").save(src / "a.heic", "HEIF")
    Image.new("RGB", (8, 8), "black").save(src / "b.jpeg", "JPEG")
    (src / "clip.mov").write_bytes(b"video")
    dest = tmp_path / "my_pets"

    stats = import_photos(tmp_path / "pets", dest)

    assert sorted(p.name for p in dest.iterdir()) == ["a.jpg", "b.jpeg"]
    with Image.open(dest / "a.jpg") as img:
        assert img.format == "JPEG"
    assert stats["converted heic"] == 1
    assert stats["copied"] == 1
    assert stats["skipped .mov"] == 1
    assert (src / "a.heic").exists()  # source untouched

    again = import_photos(tmp_path / "pets", dest)
    assert again["already imported"] == 2
