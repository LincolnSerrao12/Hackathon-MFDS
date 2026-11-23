# Project rules for AI agents

Project: ME3 File System Intelligence. See `README.md` for goals, architecture, status and next steps.

## Mandatory workflow
1. At the start of every session, read `README.md` (STATUS and NEXT STEPS) before doing anything else.
2. After EVERY change (code, deps, config), update `README.md` in the same turn:
   - STATUS: last updated date, phase, what works, what is broken.
   - NEXT STEPS: tick finished items `[x]`, add new ones, keep them ordered with the next action on top and specific enough for another AI to execute without asking.
   - CHANGELOG: add a one-line entry at the top.
   - SETUP COMMANDS: add any new dependency or system package.
3. Build in vertical slices; keep the app runnable after each one. Commit after each slice.

## Constraints
- Privacy: raw file contents, names with PII, or personal identifiers must never go to a cloud API. All cloud calls go through `src/me3/privacy.py` redaction.
- Project root is `/home/lincoln/Desktop/AquaFlare/me3-fsi`. ALL files created must live inside it (nothing outside ~/Desktop/AquaFlare/me3-fsi).
- NO virtual environments. Install deps with `uv pip install --python /usr/bin/python --target ./libs ...`; run via `source env.sh` (PYTHONPATH=./libs). Models cache in `./models`.
- Never commit `.env`, tokens or `credentials.json`.
- Background indexing must stay low priority (nice/ionice, batched DB writes).
