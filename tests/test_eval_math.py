from sentcite.eval import _prf


def test_prf_perfect():
    assert _prf({"a", "b"}, {"a", "b"}) == (1.0, 1.0, 1.0)


def test_prf_partial():
    p, r, f = _prf({"a", "b"}, {"b", "c"})
    assert p == 0.5
    assert r == 0.5
    assert f == 0.5


def test_prf_empty_pred():
    assert _prf(set(), {"a"}) == (0.0, 0.0, 0.0)


def test_prf_both_empty():
    assert _prf(set(), set()) == (1.0, 1.0, 1.0)
