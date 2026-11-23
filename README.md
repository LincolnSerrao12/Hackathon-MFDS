# ME3 File System Intelligence

AI-powered local search, organisation and cleanup for local storage. Private data is detected and redacted **on-device** before any non-sensitive metadata reaches a cloud LLM.

> **For AI agents:** read the "STATUS" and "NEXT STEPS" sections first. After EVERY change, update this file (see `CLAUDE.md`).

---

## STATUS (update every change)

- **Last updated:** 2026-11-23 (buildable: `make build` produces dist/me3_fsi-0.1.0-py3-none-any.whl; lint + tests pass)
- **Phase:** 1 - core keyword search slice DONE and runnable (crawl, extract, FTS5 search, NL filters, live watcher, API, UI).
- **Run it:** `cd ~/Desktop/AquaFlare/me3-fsi && source env.sh && python -m me3 serve --port 8765` then open http://127.0.0.1:8765 . CLI: `python -m me3 index <folder>`, `python -m me3 search "<query>"`. Tests: `make test` (5 pass). Build wheel: `make build` (-> dist/). Lint: `make lint`.
- **Working:** incremental crawler; text extraction (txt/code/pdf/docx) into FTS5 (bm25, filename boosted); local natural-language parser (`nlq.py`: "last semester", "photos", "pdf", "larger than 5MB", "in March 2024"); filters type/ext/size/date; inotify live watcher with polling fallback; FastAPI + single-page UI; synthetic data generator.
- **Benchmark (100k synthetic files, 2.1GB, hot cache):** crawl 2.2s, extract 62k text files 5.3s, DB 76MB, search ~5ms, watcher picks up create/rename/delete in ~2-5s.
- **Broken / known issues:**
  - No semantic search yet: images match by filename only ("photos from Goa trip" returns 0 on synthetic data). Needs torch + CLIP (step 7).
  - torch/sentence-transformers not installed; tesseract/poppler not installed (user can run pacman line below).
  - No SFTP / cloud connectors yet; no privacy layer / LLM yet; no duplicates/cleanup yet.
  - Real-world `~` scan untested (inotify watch limit may force polling mode; code falls back automatically).
  - Do NOT use `pkill -f` with text matching the command itself (kills the shell). Find server PID via `ss -ltnp | grep :8765`.
- **Deadline:** 7-hour build window, started 2026-11-23 (~09:30).

## NEXT STEPS (ordered; the top item is what to do next)

1. [x] Deps (non-torch), package layout, DB schema, crawler, watcher, extraction, FTS search, NL parser, API, UI, synthetic data, tests.
2. [ ] **Privacy layer** `src/me3/privacy.py`: Presidio (en_core_web_sm, see NOTES) + regex for Indian PAN/Aadhaar/IFSC/phone; `redact(text)->(text, findings)`; unit tests. Mandatory before any cloud call.
3. [ ] **LLM layer** `src/me3/llm.py` (anthropic SDK, key from `.env`): (a) query understanding fallback, (b) folder-organisation suggestions from REDACTED metadata only; endpoint `/api/suggest` returns suggestions + the exact "what was sent" payload for UI preview.
4. [ ] **Cleanup** `src/me3/cleanup.py` + `/api/cleanup`: duplicates (group by size, then partial hash, then full hash; store in files.hash), largest files, old/unused media; UI tab.
5. [ ] **SFTP connector** `src/me3/connectors/sftp.py` (class `SftpSource(id, root, name, config)` with `walk/stat/fetch`, `watchable=False`; config: host, port, user, password/key). Test against local sshd (`sudo systemctl start sshd`) or a paramiko test server. Add UI form.
6. [ ] **Google Drive connector** `src/me3/connectors/gdrive.py` (`GDriveSource`, OAuth `credentials.json` in project root, `fetch` exports Docs to text/downloads files to temp). If OAuth is blocked, ship it behind the interface + clearly documented.
7. [ ] **Semantic search**: install torch + sentence-transformers (see SETUP), `src/me3/embed.py` (MiniLM for extracted text, CLIP for images), sqlite-vec table, hybrid rank fusion in `search.py`, background embedding worker (lazy, low priority, cap per file).
8. [ ] UI polish: privacy preview modal, cleanup tab, connector forms, open-containing-folder action.
9. [ ] Demo data set + screenshots + final README (how to run, architecture, privacy model, benchmark table).

## SETUP COMMANDS

**No virtual environment.** Libraries are installed into `./libs` inside the project (no venv, nothing in system site-packages) using system Python and `uv pip install --target`. Models are cached in `./models`. Everything stays under `~/Desktop/AquaFlare/me3-fsi`.

```bash
# system packages (OCR, optional; installed system-wide by pacman)
sudo pacman -S --needed tesseract tesseract-data-eng poppler openssh

cd ~/Desktop/AquaFlare/me3-fsi
source env.sh        # sets PYTHONPATH=./libs, HF_HOME=./models, etc. (created in step 1)

uv pip install --python /usr/bin/python --target ./libs \
  fastapi "uvicorn[standard]" watchdog aiosqlite python-multipart jinja2 python-dotenv rich typer \
  pypdf python-docx python-magic pillow pytesseract \
  sentence-transformers sqlite-vec numpy \
  presidio-analyzer presidio-anonymizer spacy \
  paramiko google-api-python-client google-auth-oauthlib anthropic pytest ruff

# DEFERRED: sentence-transformers was left out of the first install because it pulls torch. Install both later.
# CPU-only torch (smaller); if it has no wheel for the system Python (3.14), see Known issues
uv pip install --python /usr/bin/python --target ./libs torch --index-url https://download.pytorch.org/whl/cpu

# spaCy model for PII detection
uv pip install --python /usr/bin/python --target ./libs \
  https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# pre-download embedding models into ./models
python -c "from sentence_transformers import SentenceTransformer as S; S('all-MiniLM-L6-v2'); S('clip-ViT-B-32')"
```

Run anything with `source env.sh && python -m me3 ...`.

Known issues: system Python is 3.14 and some ML wheels may lag. If an install fails, fall back to `uv pip install --python 3.12 --target ./libs ...` (uv fetches Python 3.12 into its cache; still no venv).

Env vars go in `.env` (never commit): `ANTHROPIC_API_KEY=...`, Google OAuth `credentials.json` path.

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

## MODULE LAYOUT (built unless marked TODO)

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

- 2026-11-23: Made project buildable: pyproject.toml (setuptools, src layout, `me3` entry point, extras), static UI moved to src/me3/static (packaged), connectors/ is a package, Makefile (build/test/lint/run/clean), ruff config, lint clean; wheel verified to import standalone. Live watcher create/rename/delete re-verified.
- 2026-11-23: Phase 1 slice built: db, sources, crawler, extract, watcher, indexer, nlq, search, api, cli, static UI, gen_data, tests; benchmarked on 100k files; fixed watcher ignoring paths under data/.
- 2026-11-23: Project moved to ~/Desktop/AquaFlare/me3-fsi (all files must live here).
- 2026-11-23: Installed all non-torch deps into ./libs + en_core_web_sm; verified imports, sqlite-vec, FTS5, Presidio.
- 2026-11-23: Added env.sh.
- 2026-11-23: Dropped venv; deps go to ./libs via --target, models to ./models.
- 2026-11-23: Moved project to ~/Desktop/AquaFlare/me3-fsi (all files must live here).
- 2026-11-23: Created project, README.md, CLAUDE.md.
