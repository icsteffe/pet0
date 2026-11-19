# CLAUDE.md — Sunny & Nui Distinguisher

## What this project is
A personal computer-vision project (HSLU CVAI context) to tell two look-alike cats,
**Sunny** and **Nui**, apart on images from a **Petlibro Luma** smart litter box.
The Luma's built-in cat recognition is ~60% accurate for these two cats (barely better
than chance). Goal: a custom classifier with ≥ 95% accuracy on held-out Luma visits, and
an isolated service that automatically reassigns misattributed visits in the Petlibro
cloud — the same correction that is possible by hand in the app today.

Project brief (goals, data, API findings, risks, phased plan):
https://claude.ai/artifact/9psJrgVtU3Ej8YainYjv4n

## Hard rules (read before writing any code)
1. **Never touch the device.** No firmware patching, reflashing, local device protocols,
   or device commands (cleaning, modes, sensors, calibration). The Luma's camera-based
   "cat present" check is part of its safety system that stops the drum while a cat is
   inside. We only ever *read* visit data and *write* cat reassignments on past visits.
2. **Writes are dry-run by default.** Anything that changes data in the Petlibro cloud
   must require an explicit flag (`--apply` / `WRITE_ENABLED=true`), log the old and new
   value, and be reversible.
3. **Own account only.** Use a dedicated Petlibro sub-account shared from the main
   account. Keep request rates low (poll ≥ 1 min apart, back off on errors).
4. **No secrets or private images in git.** Tokens live in `.env`; `data/` is gitignored.
   Never print tokens in logs.
5. **Prefer abstaining over a wrong correction.** Low-confidence predictions go to the
   review queue, never to the writer.
6. The Petlibro API is unofficial and reverse-engineered — it can change at any time.
   Keep all API knowledge in `src/petlibro/` and nowhere else.

## Current phase: 0 — evaluate API access
Nothing is proven yet. Before building the model pipeline, answer these (record findings
in `docs/api_findings.md`):
- [ ] Log in via the community client (see References) and list devices; is the Luma
      (model `PLLB001`) present?
- [ ] Which endpoint lists litter-box visits/events? Does each event include a cat/pet ID
      and confidence?
- [ ] Do events carry downloadable snapshot/thumbnail URLs? Video?
- [ ] What request does the app send when a visit is reassigned to another cat? (Capture
      with mitmproxy on the user's own phone/emulator, replay once on a verified visit.)
- [ ] Token lifetime, rate limits, does data depend on the Video Cloud AI subscription?

Gates: see the phased plan in the brief. Phase 0 → 1 (data) → 2 (model) → 3 (shadow mode,
dry-run 2 weeks) → 4 (auto-correct). Don't skip gates.

## Repository layout (target)
```
.
├── CLAUDE.md
├── README.md
├── pyproject.toml            # uv-managed, Python 3.11+
├── .env.example              # PETLIBRO_EMAIL, PETLIBRO_PASSWORD, PETLIBRO_REGION=US, WRITE_ENABLED=false
├── .gitignore                # .env, data/, models/, *.mitm, notebooks/.ipynb_checkpoints
├── docs/
│   ├── api_findings.md       # endpoints, payloads (redacted), what works / what doesn't
│   └── labelling_guide.md    # how Sunny vs Nui are told apart (markings, tail, size...)
├── notebooks/                # exploration only; promote stable code into src/
│   ├── 00_api_exploration.ipynb
│   ├── 01_dataset_overview.ipynb
│   └── 02_baseline_embeddings.ipynb
├── src/sunnynui/
│   ├── petlibro/             # ONLY place that knows the Petlibro API
│   │   ├── client.py         # login, token refresh, list devices, list visits, download images
│   │   ├── models.py         # pydantic models: Device, Visit, Pet, Snapshot
│   │   └── writer.py         # reassign_visit(visit_id, pet_id, dry_run=True)
│   ├── data/
│   │   ├── sync.py           # pull new visits + images into data/raw/luma/<visit_id>/
│   │   ├── import_photos.py  # import personal photos into data/raw/personal/
│   │   └── dataset.py        # build splits from labels; split BY VISIT, never by frame
│   ├── vision/
│   │   ├── detect.py         # crop the cat (e.g. pretrained detector) before classifying
│   │   ├── embed.py          # frozen backbone embeddings (DINOv2 / EfficientNet)
│   │   ├── train.py          # head training + threshold calibration
│   │   └── predict.py        # visit-level prediction: aggregate frames -> label + confidence
│   ├── service/
│   │   ├── poller.py         # loop: new visits -> predict -> decide -> writer or review queue
│   │   └── review.py         # simple review queue (CSV/SQLite) feeding back into labels
│   └── evaluate.py           # metrics vs. Luma's own labels on the frozen test set
├── data/                     # gitignored
│   ├── raw/luma/  raw/personal/
│   ├── labels/visits.csv     # visit_id, cat in {sunny, nui, unknown}, labelled_by, date
│   └── splits/               # frozen test set lives here — never train on it
├── models/                   # gitignored checkpoints + model card per version
└── tests/                    # unit tests; mock all Petlibro HTTP calls
```
Create pieces only as the current phase needs them. In phase 0 that means
`src/sunnynui/petlibro/client.py`, `notebooks/00_api_exploration.ipynb`, and `docs/api_findings.md`.

## Data and labelling conventions
- Classes: `sunny`, `nui`, `unknown` (both cats, empty box, unusable frame).
- Luma's own labels are **untrusted predictions**, stored separately as `luma_label`, never
  used as ground truth. Visits the user already corrected manually in the app are ground truth.
- Label **per visit**; all frames of a visit inherit the visit label.
- Test set: the most recent ~20% of labelled Luma visits, frozen in `data/splits/test.csv`.
- Personal photos are training-only; evaluation is always on Luma frames (incl. IR/night).
- Labelling tool: Label Studio, or folder-per-class for quick starts.

## Modelling approach
1. Baseline: frozen embeddings (DINOv2 ViT-S/14 or similar) on cat crops + logistic
   regression / kNN. Report accuracy, per-class recall, and accuracy split into day vs. night.
2. If needed: fine-tune the backbone with strong augmentation (color jitter, IR-like
   grayscale, crops) — watch for overfitting on few Luma images.
3. Visit-level decision: aggregate frame probabilities (mean log-prob), calibrate
   (temperature scaling), and pick an abstain threshold from the validation set.
4. Always compare against the Luma baseline on the same test visits.

Success criteria: ≥ 95% accuracy, ≤ 10% abstain, < 2% wrong auto-corrections in shadow mode.

## Commands
```bash
uv sync                                    # install
uv run pytest                              # tests (no network)
uv run python -m sunnynui.data.sync --since 7d          # pull visits + images (read-only)
uv run python -m sunnynui.vision.train --config configs/baseline.yaml
uv run python -m sunnynui.evaluate --split test
uv run python -m sunnynui.service.poller                # dry-run by default
uv run python -m sunnynui.service.poller --apply        # only after Gate 3 passes
```

## Coding conventions
- Python 3.11+, `uv`, `ruff` (lint + format), type hints, `pydantic` for API payloads,
  `httpx` for HTTP, PyTorch + `timm`/`transformers` for vision.
- Tests mock every Petlibro request; no test may hit the real API.
- Log API payloads only after redacting tokens, emails and device serials.
- Notebooks are for exploration; once something works, move it into `src/` with a test.
- Communicate with the user in English or German, whichever he writes in.

## References
- Home Assistant community integration (lists Luma `PLLB001`): https://github.com/jjjonesjr33/petlibro
- Reverse-engineering thread (API base `https://api.us.petlibro.com`, EU accounts use region US):
  https://community.home-assistant.io/t/petlibro-cloud-integration-non-tuya-wip/759978
- Luma safety design (camera + IR + weight checks): https://ca.petlibro.com/pages/how-the-luma-smart-litter-box-puts-your-cats-safety-first
