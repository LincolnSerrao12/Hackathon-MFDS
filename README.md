# ME3 File System Intelligence

AI-powered local search, organisation and cleanup for local storage. Private data is detected and redacted **on-device** before any non-sensitive metadata reaches a cloud LLM.

> **For AI agents:** read the "STATUS" and "NEXT STEPS" sections first. After EVERY change, update this file (see `CLAUDE.md`).

---

## STATUS (update every change)

- **Last updated:** 2026-11-23 (UI redesign: light/dark/royal themes, cleaner search, sources, cleanup, organise, privacy)
- **Phase:** 2 - all three brief requirements implemented and tested: (1) efficient live index, (2) Google Drive connector (SFTP removed on purpose: no data may leave the machine to arbitrary hosts), (3) search by meaning (text + images) with type/date/size filters; plus hybrid privacy layer, cleanup and AI organisation suggestions.
- **Run it:** `cd ~/Desktop/AquaFlare/me3-fsi && source env.sh && python -m me3 serve --port 8765` then open http://127.0.0.1:8765 (or `make run`). Small demo: `python scripts/make_demo.py && ME3_DB=$PWD/data/demo.db python -m me3 index data/demo && ME3_DB=$PWD/data/demo.db python -m me3 serve --port 8766`.
- **Tests:** `make test` -> 18 pass (core, privacy, connectors, semantic).
- **Working:**
  - Index: incremental crawler, inotify live watcher (polling fallback; remote sources rescan every 120s), low priority threads, text extraction txt/code/pdf/docx/gdoc into FTS5.
  - Search: hybrid = FTS5 keywords + MiniLM text meaning + CLIP image meaning, fused with RRF; local NL parser (`nlq.py`) extracts type/size/date ("last semester", "photos", "larger than 5MB", "in March 2024"); synonym expansion for everyday document words; thumbnails in UI.
  - Connectors: Local, Google Drive (live: OAuth done, source added).
  - Privacy: `privacy.py` (Presidio + PAN/Aadhaar/IFSC/UPI/phone/Luhn cards/secrets), `prepare_payload` builds the only thing that can reach `llm.py`; UI shows the exact redacted payload and requires an explicit send click; works without an API key (on-device rule-based ideas).
  - Cleanup: duplicates (size -> partial hash -> full hash), large files, stale media, reversible trash (`data/trash/`), organisation ideas.
- **Benchmarks:** 100k synthetic files (2.1GB): crawl 2.2s, text extraction 62k files 5.3s, keyword search ~5ms, hybrid search 13-30ms warm (first query ~3s model load), duplicate analysis ~8s. Background embedding of the 100k set runs at ~30 files/s (about 30 min for 62k texts) while the app stays usable.
- **Known issues / limits:**
  - Text embedding model is all-MiniLM-L6-v2 (weak on short abstract queries); a synonym lexicon (`nlq.SYNONYMS`) compensates. A stronger model (`BAAI/bge-small-en-v1.5`, set `ME3_TEXT_MODEL`, needs query prefix handling in embed.py) was not tested: download stalled.
  - Image meaning is only verified on synthetic cartoon scenes (`scripts/make_demo.py`), not real photo libraries. Synthetic 100k "images" are random bytes so they fail to embed (expected).
  - Google Drive: WORKING (2026-11-23): client_secret_*.json auto-detected, consent done, live Drive API call verified, source indexed by the server.
  - Cloud AI: now Gemini by default (`GEMINI_API_KEY` in .env; `gemini-3.5-flash-lite`, fallbacks on 503/404/timeout; override with ME3_GEMINI_MODEL or ME3_LLM_PROVIDER=anthropic). Verified live via /api/suggest. Anthropic path kept but that account has no credits.
  - OCR is wired (extract.py) and turns on automatically once `tesseract` is installed (needs sudo: `sudo pacman -S --needed tesseract tesseract-data-eng`); untested without the binary.
  - Real folder test: ~/Pictures (51 screenshots) indexed+embedded in 17s into data/real.db; search works. Cloud LLM path (`llm.py`) untested without an API key.
  - Real `~` scan and inotify watch limits untested on a large real tree.
  - Do NOT use `pkill -f` with text that matches your own command (kills the shell); find the server with `ss -ltnp | grep :8765`.
  - Do not `source` a different venv: this project is venv-free by design.
- **Deadline:** 7-hour build window, started 2026-11-23 (~09:30).

## NEXT STEPS (ordered; the top item is what to do next)

0. [ ] **Check the redesigned UI while signed in**: all 3 themes, search + filters + load more + grid, add/remove source, cleanup trash, organise send. It was only rendered headless against a mock API (same response shapes) plus JS syntax / id checks.
1. [x] Core index, watcher, extraction, FTS, NL parser, API, UI, tests.
2. [x] Privacy layer + LLM layer (preview-then-send) + cleanup + organisation ideas.
3. [x] Google Drive connector (SFTP removed). 4. [x] Torch, MiniLM + CLIP embeddings, hybrid search, thumbnails.
5. [~] **Real-world validation** (~/Pictures done; ~/Documents and long-running inotify still to try): index a real folder (e.g. ~/Documents, ~/Pictures: 44 screenshots) via the UI; check inotify mode, search quality, CPU usage while embedding. Fix issues found.
6. [ ] **Google Drive live test**: `client_secret_362846242510-...json` is in the project root but untracked/unignored (do NOT `git add .`; code expects `credentials.json`, so either copy/rename it (gitignored) or point gdrive.py at it); then user runs a browser consent:  runs `python -m me3 gdrive-auth`, then `python -m me3 add-gdrive`. Verify walk/fetch/export of Docs. Consider Drive Changes API instead of full rescans.
7. [ ] **Cloud LLM live test**: `.env` key is DONE (detected). Remaining: verify `/api/suggest` with `send=true`; consider LLM query-understanding fallback (redacted).
8. [ ] Embedding model upgrade experiment (bge-small / mpnet) with eval queries in tests; OCR for scanned PDFs/images (needs `sudo pacman -S tesseract tesseract-data-eng poppler`, then wire pytesseract into extract.py).
9. [ ] Extra: SMB connector (`smbprotocol`), file preview/open-folder actions, saved searches, scheduled cleanup.
10. [ ] Final polish: visually check `docs/ME3_Project_Guide.pptx` once LibreOffice is installed; screenshots, demo script, README walkthrough, `make build` wheel.

## SETUP COMMANDS

**No virtual environment.** Libraries live in `./libs` (installed with `uv pip install --target`), models in `./models`, bytecode in `./.pycache`, uv cache in `./.uv-cache`. Always `source env.sh` first. Everything stays under `~/Desktop/AquaFlare/me3-fsi`. Python is the system 3.14 (torch 2.15 CPU wheels work).

Already installed (for reproducing on a fresh machine):

```bash
cd ~/Desktop/AquaFlare/me3-fsi && source env.sh
uv pip install --python /usr/bin/python --target ./libs fastapi "uvicorn[standard]" watchdog aiosqlite python-multipart jinja2 python-dotenv rich typer \
  pypdf python-docx python-magic pillow pytesseract sqlite-vec numpy presidio-analyzer presidio-anonymizer spacy \
  google-api-python-client google-auth-oauthlib anthropic pytest ruff
uv pip install --python /usr/bin/python --target ./libs torch --index-url https://download.pytorch.org/whl/cpu
uv pip install --python /usr/bin/python --target ./libs sentence-transformers
uv pip install --python /usr/bin/python --target ./libs https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
# one-time model download (then env.sh sets HF_HUB_OFFLINE=1; unset it only to download new models)
HF_HUB_OFFLINE=0 python -c "from sentence_transformers import SentenceTransformer as S; S('all-MiniLM-L6-v2'); S('clip-ViT-B-32')"
```

Optional system packages (user runs, needs sudo): `sudo pacman -S --needed tesseract tesseract-data-eng poppler openssh` (OCR not wired in yet).

Cloud LLM (optional): create `.env` with `ANTHROPIC_API_KEY=...` (gitignored). Model default `claude-haiku-5-5`, override `ME3_LLM_MODEL`.

Google Drive: see docstring of `src/me3/connectors/gdrive.py` (Cloud Console -> Drive API -> OAuth Desktop client -> `credentials.json` in project root -> `python -m me3 gdrive-auth` -> `python -m me3 add-gdrive`).

## NOTES

Presidio with the small model (no downloads):

```python
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
nlp = NlpEngineProvider(nlp_configuration={"nlp_engine_name":"spacy","models":[{"lang_code":"en","model_name":"en_core_web_sm"}]}).create_engine()
analyzer = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])
```

`uv` cache lives in `./.uv-cache` (set in env.sh). sqlite-vec: `db.enable_load_extension(True); sqlite_vec.load(db)`.

## ARCHITECTURE OVERVIEW

Modular monolith, one Python process (FastAPI) with background worker threads, one SQLite file (`data/me3.db`).

```
 Web UI (HTML/JS) --HTTP--> FastAPI (api.py)
                               |
     +-------------+-----------+-------------+----------------+
     | Search      | Cleanup   | Privacy gate| Source registry |
     | FTS5+vector | dupes,    | Presidio +  | Local |      |  |
     | + filters   | large,    | regex redact| GDrive (same    |
     |             | org. ideas| -> LLM      | Source interface)|
     +------+------+-----+-----+------+------+--------+--------+
            |            |            |               |
            +------ Indexing pipeline (background, low priority) ------+
              crawl/watch -> queue -> extract -> embed -> SQLite (files, fts5, sqlite-vec)
```

Key decisions:
- Hybrid privacy: raw content never leaves the device; only redacted metadata/snippets reach the cloud LLM (`privacy.py` is the only path to `llm.py`).
- Connectors implement one `Source` interface (`list`, `stat`, `open`, `watch`), so the indexer is source-agnostic.
- Tiered indexing: metadata + filename first (fast, covers all 100k files), then text extraction, then embeddings lazily in the background.
- Hybrid search: FTS5 keyword score + sqlite-vec cosine similarity, merged by rank fusion, then filtered by type/date/size.
- Local-first embeddings (MiniLM for text, CLIP for images); the LLM only parses queries ("last semester" -> date range) and suggests organisation, on redacted data.

## MODULE LAYOUT (all built)

```
src/me3/
  db.py          SQLite schema (sources, files, fts5); thread-local connections
  crawler.py     incremental scan
  watcher.py     watchdog live updates
  extract.py     text/OCR extraction
  embed.py       text + CLIP embeddings
  search.py      hybrid FTS + vector search, filters
  privacy.py     PII detection/redaction before cloud calls
  llm.py         cloud LLM client (receives redacted data only)
  cleanup.py     duplicates, large files, organisation suggestions
  connectors/    local.py, gdrive.py (common Source interface)
  api.py         FastAPI app + static UI
scripts/         gen_data.py, benchmark.py
tests/
```

## CHANGELOG (newest first)
- 2026-11-23: look-before-you-trash: file viewer (images, PDF, video, audio, text) with Open / Show in folder / Copy path; Cleanup 'Compare copies' shows each duplicate side by side with the SHA-1 match and lets you pick which copy to keep; View buttons on every cleanup row, search result and Organise idea ('View files' lists that folder). New endpoints: GET /api/files/{id}, /api/files/{id}/raw (HTML/SVG/JS sent as plain text, sandbox CSP), POST /api/files/{id}/open, GET /api/folder.
- 2026-11-23: privacy: password detection widened ("my password is x", "pass: x", "PIN 1234", "OTP is x", "password for gmail is x", Google/Slack/GitHub tokens); only the value is replaced so the keyword stays readable; normal sentences untouched; test added.
- 2026-11-23: UI redesign (static/index.html rewritten, login.html themed): light/dark/royal themes (saved in localStorage, follows OS on first visit); type pills + collapsible filters with removable chips; example queries; stale-response guard; Load more paging; list/grid view; image preview (/api/thumb?size=); copy path; toasts + confirm dialogs instead of alert/confirm; Add-source panel; live privacy redaction; tab kept in URL hash; '/' focuses search. Fixed: Add source threw after success (referenced removed SFTP fields); Organise note claimed on-device even with a cloud model. All API calls unchanged.
- 2026-11-23: REMOVED SFTP entirely (connector, UI tab, API branch, add-sftp CLI, tests, paramiko dep): user decision, security/privacy. Local + Google Drive only.
- 2026-11-23: Drive tab now lets you index a specific Drive folder (name or ID; blank = whole Drive); multiple Drive sources allowed, overlap with whole-Drive rejected; unknown folder fails instead of wiping the index.
- 2026-11-23: Drive tab hides the name box and Add button unless Drive is authorised but not yet added.
- 2026-11-23: Drive tab status reworded (was mistaken for an error); Add disabled while Drive is already connected.
- 2026-11-23: SFTP: unreadable root now raises (an empty scan used to wipe the source index); ssh-agent/default keys used when no password/key given; ~ expanded in key path + missing-key error; same folder on different hosts no longer collapses into one source; UI validation + clearer placeholders. Live sshd tests pass (3).
- 2026-11-23: Drive tab no longer shows the stale "needs credentials.json" note: /api/gdrive/status reports client file/authorised/added, and a Connect button runs the Google consent in-UI using the same client_secret_*.json.
- 2026-11-23: Sources panel: reject local folders nested in / containing an existing source (duplicate results); added remove source (DELETE /api/sources/{id}, index only, files untouched) + rescan/remove feedback.
- 2026-11-23: removed the AI vision button, /api/search/vision and llm.vision_match (unused; normal search + filters already find images by meaning).
- 2026-11-23: AI vision button is hidden when a non-image type is selected and labelled "in images"; result header says images only.
- 2026-11-23: AI vision search now honours the size/date filters from the UI (was ignoring them: showed 125KB screenshots under a >=100MB filter). UI sends lastFilters; api.py merges them over parsed ones. Needs server restart.
- 2026-11-23: search filters verified against the index (type/size/date/ext, NL + explicit, 0 violations); fixed UI date filters using UTC midnight instead of local (missed files modified 00:00-05:30 IST, chip dates shifted).

- 2026-11-23: Web UI now requires Google sign-in (src/me3/auth.py, static/login.html; signed cookie; first account to sign in is owner, or ME3_ALLOWED_EMAILS). Gemini LLM provider added. Replaced synthetic 100k + SFTP test data with real sources: home folder (credential/config dirs excluded via util.IGNORE_DIRS) and Google Drive. DB backup of the pre-cleanup state: data/me3.db.bak-before-cleanup (delete when happy). Regenerate fake data with scripts/gen_data.py if needed. 20 tests pass.
- 2026-11-23: Fixed/hardened: gdrive finds client_secret_*.json + prints consent URL + clear token errors; /api/suggest maps Anthropic errors (401 key type, 402 no credits); optional OCR (images + scanned PDFs) auto-enabled when tesseract exists; test added (18 pass); validated real ~/Pictures indexing.
- 2026-11-23: Recorded in STATUS that Google auth is not working (user report); needs debugging with the actual error.
- 2026-11-23: Added docs/ME3_Project_Presentation.pptx (17 slides: project, architecture, libraries, algorithms, user manual); built with pptxgenjs from a scratchpad script outside the project. Not visually rendered (no LibreOffice installed).
- 2026-11-23: Added `docs/ME3_Project_Guide.pptx` (22 slides: project, architecture, libraries, algorithms, user manual) generated by `scripts/build_deck.js` (pptxgenjs; needs `npm install pptxgenjs react-icons react react-dom sharp` outside the project, run with NODE_PATH, args: output path). Schema-validated and text-fit checked; NOT visually rendered (no LibreOffice installed: `sudo pacman -S libreoffice-fresh` then convert to PDF and eyeball).
- 2026-11-23: Ran the project: server already up on :8765 (pid from 10:29), UI 200, stats/index/search/llm-status OK (100k synthetic files indexed, watcher inotify), 17 tests pass. User created `.env` with ANTHROPIC_API_KEY (gitignored, chmod 600); `/api/llm/status` reports cloud_available=true. Live `/api/suggest send=true` NOT yet run. Google `client_secret_*.json` (Desktop app, project aquaflare) sits untracked in project root; never commit it.
- 2026-11-23: Fixed lint error; restarted server and smoke-tested cleanup/privacy/suggest/llm-status endpoints (all respond); added tests/test_sftp.py (in-process paramiko server: scan+extract+search over SFTP passes). GDrive untested (needs OAuth).
- 2026-11-23: Made project buildable: pyproject.toml (setuptools, src layout, `me3` entry point, extras), static UI moved to src/me3/static (packaged), connectors/ is a package, Makefile (build/test/lint/run/clean), ruff config, lint clean; wheel verified to import standalone. Live watcher create/rename/delete re-verified.
- 2026-11-23: Phase 2: privacy.py, llm.py, cleanup.py, connectors (sftp, gdrive), embed.py (MiniLM+CLIP, sqlite-vec), hybrid RRF search, synonym lexicon, thumbnails, new UI (search/cleanup/organise/privacy tabs), make_demo.py, 17 tests. env.sh: bytecode cache in ./.pycache (DONTWRITEBYTECODE made torch imports take minutes), HF_HUB_OFFLINE=1.
- 2026-11-23: Phase 1 slice built: db, sources, crawler, extract, watcher, indexer, nlq, search, api, cli, static UI, gen_data, tests; benchmarked on 100k files; fixed watcher ignoring paths under data/.
- 2026-11-23: Project moved to ~/Desktop/AquaFlare/me3-fsi (all files must live here).
- 2026-11-23: Installed all non-torch deps into ./libs + en_core_web_sm; verified imports, sqlite-vec, FTS5, Presidio.
- 2026-11-23: Added env.sh.
- 2026-11-23: Dropped venv; deps go to ./libs via --target, models to ./models.
- 2026-11-23: Moved project to ~/Desktop/AquaFlare/me3-fsi (all files must live here).
- 2026-11-23: Created project, README.md, CLAUDE.md.
