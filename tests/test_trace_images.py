"""Image hashing, region diff and similarity over synthetic PNGs."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from harness.trace import images


def scene(seed=0, size=(160, 120)):
    """A structured image (smooth gradients plus blocks) so hashes are meaningful."""
    rng = np.random.default_rng(seed)
    h, w = size[1], size[0]
    base = np.zeros((h, w, 3), dtype=np.uint8)
    for _ in range(12):
        y, x = int(rng.integers(0, h - 20)), int(rng.integers(0, w - 20))
        base[y:y + 20, x:x + 20] = rng.integers(0, 256, 3)
    return base


def save(path, array):
    Image.fromarray(array).save(path)
    return path


def test_identical_images_hash_equal(tmp_path):
    a = scene(1)
    p, q = save(tmp_path / 'a.png', a), save(tmp_path / 'b.png', a.copy())
    assert images.dhash(images.load(p)) == images.dhash(images.load(q))
    assert images.ahash(a) == images.ahash(a.copy())
    assert images.hamming(images.dhash(a), images.dhash(a)) == 0
    assert 0 <= images.dhash(a) < 2 ** 64 and 0 <= images.ahash(a) < 2 ** 64


def test_load_roundtrip_and_alpha_dropped(tmp_path):
    a = scene(2)
    rgba = Image.fromarray(a).convert('RGBA')
    rgba.save(tmp_path / 'x.png')
    loaded = images.load(tmp_path / 'x.png')
    assert loaded.dtype == np.uint8 and loaded.shape == a.shape
    assert (loaded == a).all()


def test_region_diff_localises_change():
    a = scene(3)
    b = a.copy()
    b[70:110, 90:150] = 255 - b[70:110, 90:150]  # inside grid cell row 2, col 2 of a 4x4 grid on 160x120
    cells = images.region_diff(a, b, grid=(4, 4))
    assert len(cells) == 16
    changed = [c for c in cells if c['changed_fraction'] > 0]
    assert changed, 'the edit must register'
    assert {(c['row'], c['col']) for c in changed} <= {(2, 2), (2, 3), (3, 2), (3, 3)}
    assert all(c['changed_fraction'] == 0 and c['mean_abs_diff'] == 0 for c in cells if (c['row'], c['col']) not in {(2, 2), (2, 3), (3, 2), (3, 3)})
    assert cells[0]['box'] == [0, 0, 40, 30]
    assert cells[-1]['box'] == [120, 90, 160, 120]


def test_region_diff_identical_and_threshold():
    a = scene(4)
    assert all(c['changed_fraction'] == 0 for c in images.region_diff(a, a.copy()))
    b = a.copy()
    b[:] = np.clip(a.astype(int) + 10, 0, 255).astype(np.uint8)
    assert all(c['changed_fraction'] == 0 for c in images.region_diff(a, b))  # below default threshold 16
    assert any(c['changed_fraction'] > 0 for c in images.region_diff(a, b, threshold=5))


def test_region_diff_refuses_size_mismatch_and_bad_grid():
    with pytest.raises(ValueError, match='sizes differ'):
        images.region_diff(scene(5, (160, 120)), scene(5, (120, 160)))
    with pytest.raises(ValueError):
        images.region_diff(scene(5), scene(5), grid=(0, 4))
    with pytest.raises(ValueError):
        images.region_diff(scene(5), scene(5), grid=(500, 4))


def test_rejects_malformed_arrays():
    with pytest.raises(ValueError):
        images.dhash(np.zeros((8, 8), dtype=np.uint8))
    with pytest.raises(ValueError):
        images.dhash(np.zeros((8, 8, 3), dtype=np.float32))


def test_noise_is_near_and_different_image_is_far():
    a = scene(6)
    rng = np.random.default_rng(0)
    noisy = np.clip(a.astype(int) + rng.integers(-4, 5, a.shape), 0, 255).astype(np.uint8)
    other = scene(99)
    near = images.hamming(images.dhash(a), images.dhash(noisy))
    far = images.hamming(images.dhash(a), images.dhash(other))
    assert near <= 6
    assert far > 12
    assert far > near


def test_hamming_counts_bits():
    assert images.hamming(0b1010, 0b0110) == 2
    assert images.hamming(0, 2 ** 64 - 1) == 64


def test_similar_ordering_k_and_max_distance():
    idx = {'b': 0b0001, 'a': 0b0010, 'c': 0b0111, 'far': 0b11111111}
    got = images.similar(0, idx, k=10)
    assert got == [('a', 1), ('b', 1), ('c', 3), ('far', 8)]  # ties broken by id
    assert images.similar(0, idx, k=2) == [('a', 1), ('b', 1)]
    assert images.similar(0, idx, k=10, max_distance=1) == [('a', 1), ('b', 1)]
    assert images.similar(0, idx, k=10, max_distance=0) == []
    assert images.similar(0, {}, k=3) == []
    assert images.similar(0, idx, k=0) == []
    with pytest.raises(ValueError):
        images.similar(0, idx, k=-1)


def test_index_uses_stems_and_refuses_duplicates(tmp_path):
    (tmp_path / 'x').mkdir()
    p1 = save(tmp_path / 'one.png', scene(7))
    p2 = save(tmp_path / 'two.png', scene(8))
    p3 = save(tmp_path / 'x' / 'one.png', scene(9))
    idx = images.index([p1, p2])
    assert set(idx) == {'one', 'two'}
    assert idx['one'] == images.dhash(scene(7))
    with pytest.raises(ValueError, match='duplicate'):
        images.index([p1, p3])


def test_load_refuses_non_png(tmp_path):
    jpg = tmp_path / 'a.png'  # a PNG name must not be trusted
    Image.fromarray(scene(10)).save(jpg, format='JPEG')
    with pytest.raises(ValueError, match='not a PNG'):
        images.load(jpg)
    text = tmp_path / 'b.png'
    text.write_text('hello')
    with pytest.raises(ValueError, match='not a PNG'):
        images.load(text)
    empty = tmp_path / 'c.png'
    empty.write_bytes(b'')
    with pytest.raises(ValueError, match='not a PNG'):
        images.load(empty)


def test_load_refuses_oversize(tmp_path):
    big = tmp_path / 'big.png'
    Image.new('RGB', (4001, 4001)).save(big)  # 16,008,001 pixels, a few KB on disk
    with pytest.raises(ValueError, match='exceeds'):
        images.load(big)
    ok = tmp_path / 'ok.png'
    Image.new('RGB', (4000, 4000)).save(ok)
    assert images.load(ok).shape == (4000, 4000, 3)
