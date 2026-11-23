from me3 import nlq


def test_picture_noun_wins_over_other_type_word():
    text, f, phrase = nlq.parse_full("screenshots of code")
    assert f["kinds"] == ["image"] and "code" in phrase


def test_plain_code_query_unchanged():
    assert nlq.parse_full("python code")[1]["kinds"] == ["code"]
