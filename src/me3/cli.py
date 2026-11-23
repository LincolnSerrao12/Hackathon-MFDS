import time

import typer
from rich import print
from rich.table import Table

from . import crawler, db, extract, sources
from . import search as searchmod
from .util import human_size

app = typer.Typer(add_completion=False, help="ME3 File System Intelligence")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8765):
    """Run the web app."""
    import uvicorn
    uvicorn.run("me3.api:app", host=host, port=port)


@app.command()
def index(root: str, name: str = ""):
    """Index a local folder (no server): crawl + extract."""
    c = db.connect()
    sid = sources.add_source(c, "local", root, name)
    src = sources.load(c, sid)
    t = time.time()
    st = crawler.scan(c, src)
    t1 = time.time()
    n = extract.run_pending(c)
    print(f"[green]crawl[/] {st} in {t1 - t:.1f}s; [green]extracted[/] {n} in {time.time() - t1:.1f}s")


@app.command()
def search(q: str, limit: int = 10):
    """Search the index from the terminal."""
    r = searchmod.search(db.connect(), q, limit=limit)
    print(f"text={r['text']!r} filters={r['filters']} total={r['total']}")
    t = Table()
    for col in ("name", "kind", "size", "modified", "path"):
        t.add_column(col)
    for i in r["results"]:
        t.add_row(i["name"], i["kind"], human_size(i["size"]), i["modified"], i["path"])
    print(t)
