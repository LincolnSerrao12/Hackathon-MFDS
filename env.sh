# source this file: keeps all libs/models inside the project, no venv
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/libs:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$ROOT/libs/bin:$PATH"
export HF_HOME="$ROOT/models"
export TORCH_HOME="$ROOT/models"
export SENTENCE_TRANSFORMERS_HOME="$ROOT/models"
export PYTHONDONTWRITEBYTECODE=1
export UV_CACHE_DIR="$ROOT/.uv-cache"
