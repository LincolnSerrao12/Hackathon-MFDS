# source this file: keeps all libs/models inside the project, no venv
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/libs:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$ROOT/libs/bin:$PATH"
export HF_HOME="$ROOT/models"
export TORCH_HOME="$ROOT/models"
export SENTENCE_TRANSFORMERS_HOME="$ROOT/models"
export PYTHONPYCACHEPREFIX="$ROOT/.pycache"  # bytecode cache stays inside the project (torch import is very slow without it)
export UV_CACHE_DIR="$ROOT/.uv-cache"
export HF_HUB_OFFLINE=1   # models are cached in ./models; no network calls at runtime
