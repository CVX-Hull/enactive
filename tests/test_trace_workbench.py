"""Frame cue comparisons across projected traces."""
from io import StringIO
import json

import numpy as np
from PIL import Image, PngImagePlugin

from harness.trace import images, manifest, workbench


def _png(path, pixels, *, metadata=None):
    Image.fromarray(pixels).save(path, pnginfo=metadata)


def test_frame_cues_use_decoded_pixels_and_previous_frame_of_same_actor(tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps(dict(schema=manifest.SCHEMA)))
    frame_dir = tmp_path/'frames'
    frame_dir.mkdir()
    original = np.zeros((2, 2, 3), dtype=np.uint8)
    changed = original.copy()
    changed[0, 0, 1] = 255
    changed[0, 1, 0] = 16  # Exact threshold is excluded.
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('comment', 'different encoding')
    _png(frame_dir/'first.png', original)
    _png(frame_dir/'second.png', original, metadata=metadata)
    _png(frame_dir/'third.png', changed)
    _png(frame_dir/'resized.png', original.reshape(1, 4, 3))

    for actor, frames in (('001', ['first', 'second', 'third', 'resized']), ('002', ['first'])):
        path = tmp_path/'session'/actor/'steps.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text(''.join(json.dumps(dict(seq=seq, frame=frame)) + '\n'
                                for seq, frame in enumerate(frames, start=1)))

    def run(*args):
        output = StringIO()
        assert workbench.main(['frames', str(tmp_path), *args], out=output) == 0
        return [json.loads(line) for line in output.getvalue().splitlines()]

    assert (frame_dir/'first.png').read_bytes() != (frame_dir/'second.png').read_bytes()
    assert images.pixel_sha256(frame_dir/'first.png') != images.pixel_sha256(frame_dir/'resized.png')
    assert images.changed_percent(changed, original) == 25.0
    one, two, three, resized, other = run('--with-diff')
    assert one['pixel_sha256'] == two['pixel_sha256'] == images.pixel_sha256(frame_dir/'first.png')
    assert [row['duplicate_of'] for row in (one, two, three, resized, other)] == [None, 'first', None, None, 'first']
    assert [row['changed_pct'] for row in (one, two, three, resized, other)] == [None, 0.0, 25.0, None, None]
    assert run('--with-diff', '--actor', 'session/001', '--from', '2', '--to', '3') == [two, three]
    assert 'pixel_sha256' not in run()[0]
