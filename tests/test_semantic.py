import pytest

from me3 import crawler, db, embed, extract, nlq, search, sources

needs_models = pytest.mark.skipif(not embed.available(), reason="sentence-transformers / sqlite-vec not installed")


def test_expand_adds_domain_synonyms():
    assert "tuition" in nlq.expand("fee receipt") and nlq.expand("holiday") == "holiday"


def test_phrase_keeps_inner_stopwords():
    _, _, phrase = nlq.parse_full("something to cook for dinner")
    assert phrase == "something to cook for dinner"


@needs_models
def test_meaning_search_without_shared_keywords(tmp_path):
    root = tmp_path / "f"; root.mkdir()
    (root / "a.txt").write_text("Dal tadka: boil toor dal with turmeric, temper with cumin and garlic.")
    (root / "b.txt").write_text("Even semester class timetable. Monday data structures, Tuesday operating systems lab.")
    (root / "c.txt").write_text("Gate closes at ten pm. Visitors must register at the front desk.")
    conn = db.connect(tmp_path / "t.db")
    src = sources.load(conn, sources.add_source(conn, "local", str(root)))
    crawler.scan(conn, src); extract.run_pending(conn); embed.run_pending(conn)
    r = search.search(conn, "something to cook for dinner")
    assert r["mode"] == "hybrid" and r["results"][0]["name"] == "a.txt" and "meaning" in r["results"][0]["why"]
    # deleting a file removes its vector too
    (root / "a.txt").unlink(); crawler.scan(conn, src)
    assert all(h["name"] != "a.txt" for h in search.search(conn, "something to cook for dinner")["results"])
