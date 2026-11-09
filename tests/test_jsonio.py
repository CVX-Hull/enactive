"""The shared strict-JSON, canonical-dump and file-hash helpers."""
import hashlib

import pytest

from harness.jsonio import canonical, file_sha256, strict_loads

VALUE = {'b': [1, 2.5, None, True], 'a': {'é': 'ü "\\', 'z': 0}}


class Rejected(ValueError):
    pass


def test_canonical_bytes_are_fixed():
    assert canonical(VALUE) == '{"b":[1,2.5,null,true],"a":{"é":"ü \\"\\\\","z":0}}'
    assert canonical(VALUE, sort_keys=True) == '{"a":{"z":0,"é":"ü \\"\\\\"},"b":[1,2.5,null,true]}'


def test_canonical_refuses_non_finite_numbers():
    for number in (float('nan'), float('inf')):
        with pytest.raises(ValueError):
            canonical({'a': number})


@pytest.mark.parametrize('text, reason', [('{"a": 1, "a": 2}', 'duplicate key'), ('{"x": {"a": 1, "a": 1}}', 'duplicate key'),
                                          ('{"a": NaN}', 'non-finite'), ('[Infinity]', 'non-finite'), ('[-Infinity]', 'non-finite')])
def test_strict_loads_raises_the_callers_error(text, reason):
    with pytest.raises(Rejected, match=reason):
        strict_loads(text, Rejected)
    with pytest.raises(ValueError, match=reason):
        strict_loads(text.encode())


def test_strict_loads_decodes_ordinary_documents():
    assert strict_loads(canonical(VALUE).encode(), Rejected) == VALUE
    assert strict_loads('[1, {"a": []}]') == [1, {'a': []}]


def test_file_sha256_matches_hashlib(tmp_path):
    path = tmp_path / 'blob'
    data = b'0123456789' * 100_000
    path.write_bytes(data)
    assert file_sha256(path) == hashlib.sha256(data).hexdigest()
