# ME3 File System Intelligence

AI-powered local search, organisation and cleanup for local storage. Private data is detected and redacted **on-device** before any non-sensitive metadata reaches a cloud LLM.

> **For AI agents:** read the "STATUS" and "NEXT STEPS" sections first. After EVERY change, update this file (see `CLAUDE.md`).

---

## STATUS (update every change)

- **Last updated:** 2026-11-23 (server verified running; `.env` key configured, detected by app)
- **Phase:** 2 - all three brief requirements implemented and tested: (1) efficient live index, (2) SFTP + Google Drive connectors, (3) search by meaning (text + images) with type/date/size filters; plus hybrid privacy layer, cleanup and AI organisation suggestions.
- **Run it:** `cd ~/Desktop/AquaFlare/me3-fsi && source env.sh && python -m me3 serve --port 8765` then open http://127.0.0.1:8765 (or `make run`). Small demo: `python scripts/make_demo.py && ME3_DB=$PWD/data/demo.db python -m me3 index data/demo && ME3_DB=$PWD/data/demo.db python -m me3 serve --port 8766`.
- **Tests:** `make test` -> 17 pass (core, privacy, connectors incl. real SFTP round trip, semantic).
- **Working:**
  - Index: incremental crawler, inotify live watcher (polling fallback; remote sources rescan every 120s), low priority threads, text extraction txt/code/pdf/docx/gdoc into FTS5.
  - Search: hybrid = FTS5 keywords + MiniLM text meaning + CLIP image meaning, fused with RRF; local NL parser (`nlq.py`) extracts type/size/date ("last semester", "photos", "larger than 5MB", "in March 2024"); synonym expansion for everyday document words; thumbnails in UI.
  - Connectors: Local, SFTP (tested live against a local sshd on :2222), Google Drive (code + fake-service tests; real OAuth needs the user's `credentials.json`, see Notes).
  - Privacy: `privacy.py` (Presidio + PAN/Aadhaar/IFSC/UPI/phone/Luhn cards/secrets), `prepare_payload` builds the only thing that can reach `llm.py`; UI shows the exact redacted payload and requires an explicit send click; works without an API key (on-device rule-based ideas).
  - Cleanup: duplicates (size -> partial hash -> full hash), large files, stale media, reversible trash (`data/trash/`), organisation ideas.
- **Benchmarks:** 100k synthetic files (2.1GB): crawl 2.2s, text extraction 62k files 5.3s, keyword search ~5ms, hybrid search 13-30ms warm (first query ~3s model load), duplicate analysis ~8s. Background embedding of the 100k set runs at ~30 files/s (about 30 min for 62k texts) while the app stays usable.
- **Known issues / limits:**
  - Text embedding model is all-MiniLM-L6-v2 (weak on short abstract queries); a synonym lexicon (`nlq.SYNONYMS`) compensates. A stronger model (`BAAI/bge-small-en-v1.5`, set `ME3_TEXT_MODEL`, needs query prefix handling in embed.py) was not tested: download stalled.
  - Image meaning is only verified on synthetic cartoon scenes (`scripts/make_demo.py`), not real photo libraries. Synthetic 100k "images" are random bytes so they fail to embed (expected).
  - Google Drive not tested against a real account. Cloud LLM path (`llm.py`) untested without an API key.
  - SFTP host keys are auto-accepted unless `known_hosts` is set; credentials are stored in plaintext in the local SQLite DB (use key auth).
  - Real `~` scan and inotify watch limits untested on a large real tree.
  - Do NOT use `pkill -f` with text that matches your own command (kills the shell); find the server with `ss -ltnp | grep :8765`.
  - Do not `source` a different venv: this project is venv-free by design.
- **Deadline:** 7-hour build window, started 2026-11-23 (~09:30).

## NEXT STEPS (ordered; the top item is what to do next)

1. [x] Core index, watcher, extraction, FTS, NL parser, API, UI, tests.
2. [x] Privacy layer + LLM layer (preview-then-send) + cleanup + organisation ideas.
3. [x] SFTP and Google Drive connectors. 4. [x] Torch, MiniLM + CLIP embeddings, hybrid search, thumbnails.
5. [ ] **Real-world validation**: index a real folder (e.g. ~/Documents, ~/Pictures: 44 screenshots) via the UI; check inotify mode, search quality, CPU usage while embedding. Fix issues found.
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
  paramiko google-api-python-client google-auth-oauthlib anthropic pytest ruff
uv pip install --python /usr/bin/python --target ./libs torch --index-url https://download.pytorch.org/whl/cpu
uv pip install --python /usr/bin/python --target ./libs sentence-transformers
uv pip install --python /usr/bin/python --target ./libs https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
# one-time model download (then env.sh sets HF_HUB_OFFLINE=1; unset it only to download new models)
HF_HUB_OFFLINE=0 python -c "from sentence_transformers import SentenceTransformer as S; S('all-MiniLM-L6-v2'); S('clip-ViT-B-32')"
```

Optional system packages (user runs, needs sudo): `sudo pacman -S --needed tesseract tesseract-data-eng poppler openssh` (OCR not wired in yet).

Cloud LLM (optional): create `.env` with `ANTHROPIC_API_KEY=...` (gitignored). Model default `claude-haiku-5-5`, override `ME3_LLM_MODEL`.

SFTP test server (unprivileged sshd on :2222, all inside `data/`; used by `tests/test_connectors.py`):

```bash
cd ~/Desktop/AquaFlare/me3-fsi/data && mkdir -p sshd sftp_demo && cd sshd
ssh-keygen -q -t ed25519 -N "" -f hostkey && ssh-keygen -q -t ed25519 -N "" -f client && cp client.pub authorized_keys
# sshd_config: Port 2222, ListenAddress 127.0.0.1, HostKey/PidFile/AuthorizedKeysFile under data/sshd, PasswordAuthentication no, UsePAM no, StrictModes no, Subsystem sftp /usr/lib/ssh/sftp-server
nohup /usr/bin/sshd -D -f $PWD/sshd_config -E $PWD/sshd.log &
python -m me3 add-sftp 127.0.0.1 --port 2222 --username $USER --key-file $PWD/client --root $PWD/../sftp_demo --name "NAS (test)"
```

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
     | FTS5+vector | dupes,    | Presidio +  | Local | SFTP |  |
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
  connectors/    local.py, sftp.py, gdrive.py (common Source interface)
  api.py         FastAPI app + static UI
scripts/         gen_data.py, benchmark.py
tests/
```

## CHANGELOG (newest first)

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
