"""File classification helpers."""
import os

KINDS = {
    "document": ["pdf", "doc", "docx", "odt", "rtf", "txt", "md", "rst", "tex", "csv", "tsv", "xls", "xlsx", "ppt", "pptx", "epub", "html", "htm", "log", "gdoc", "gsheet", "gslides"],
    "code": ["py", "js", "ts", "jsx", "tsx", "java", "c", "cpp", "h", "hpp", "rs", "go", "rb", "php", "sh", "sql", "css", "json", "yml", "yaml", "toml", "xml", "ini", "cfg", "lua", "kt", "swift", "cs", "ipynb"],
    "image": ["jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "tif", "heic", "svg"],
    "video": ["mp4", "mkv", "avi", "mov", "webm", "wmv", "flv"],
    "audio": ["mp3", "wav", "flac", "ogg", "m4a", "aac", "opus"],
    "archive": ["zip", "tar", "gz", "7z", "rar", "xz", "bz2", "zst", "iso"],
}
EXT2KIND = {e: k for k, exts in KINDS.items() for e in exts}

# extensions whose text we can read
TEXT_EXTS = set(["txt", "md", "rst", "tex", "csv", "tsv", "html", "htm", "log", "json", "yml", "yaml", "xml", "ini", "cfg", "toml"]) | set(KINDS["code"]) - {"ipynb"}
EXTRACTABLE = TEXT_EXTS | {"pdf", "docx", "gdoc", "gsheet", "gslides"}

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".cache", ".venv", "venv", ".uv-cache", ".mypy_cache", ".pytest_cache"}
PSEUDO_FS = {"/proc", "/sys", "/dev", "/run"}


def ext_of(name: str) -> str:
    return os.path.splitext(name)[1].lstrip(".").lower()


def classify(ext: str) -> str:
    return EXT2KIND.get(ext, "other")


def human_size(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
