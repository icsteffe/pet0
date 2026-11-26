# Sunny & Nui Distinguisher

Personal computer-vision project: tell the look-alike cats **Sunny** and **Nui** apart on
Petlibro Luma litter-box images. See [CLAUDE.md](CLAUDE.md) for goals, hard rules and the phased plan.

## Setup

```bash
uv sync
cp .env.example .env   # fill in credentials of the dedicated Petlibro sub-account
uv run pytest
```

## Label personal photos (e01)

1. Import downloaded photos into `data/raw/personal/my_pets/` (`data/` is gitignored).
   HEIC is converted to JPEG (browsers can't show HEIC), other images are copied, videos skipped:
   ```bash
   uv run python -m sunnynui.data.import_photos ~/Downloads/pets
   ```
2. Start the labeller:
   ```bash
   uv run python -m sunnynui.data.label_photos
   ```
3. In the browser: **S** = Sunny, **N** = Nui, **T** = both together, **U** = clear,
   **←/→** navigate, **Space** = jump to next unlabelled.

Labelled photos are *copied* to `data/raw/personal/cat_sunny/`, `cat_nui/` and `cat_together/`;
originals stay untouched. Restarting resumes at the first unlabelled photo.
Use `--src` / `--out` to point at other folders.
