"""Source-only wire invariants; native behavior requires computer_native_check.

These checks deliberately do not qualify fixture behavior with a simulated bridge.
"""
from pathlib import Path
import struct
import unittest

from harness.computer import protocol

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'harness/computer/native/bridge.mm'


class ComputerWireTests(unittest.TestCase):
    def test_framing_uses_utf8_header_byte_length_and_raw_png(self):
        png = b'\x89PNG\r\n\x1a\n\x00\xff'
        value = dict(schema='computer-receipt/2', id='a' * 32, session='b' * 32,
                     disposition='delivered', emitted_events=0, reason='hé✓',
                     frame=dict(name='frame-1.png', capture_id=1, presented_ms=1,
                                width=1, height=1, window_width=1, window_height=1, viewport=[0, 0, 1, 1]))
        data = protocol.encode_packet('receipt', value, png)
        size = struct.unpack('!I', data[:4])[0]
        header = protocol.wire_header(protocol.decode_json(data[4:4 + size]))
        protocol.receipt(header['value'], identity='a' * 32, session='b' * 32)
        self.assertEqual(header['value'], value)
        self.assertEqual(header['payload_bytes'], len(png))
        self.assertEqual(data[4 + size:], png)

    def test_current_closed_wire_refuses_legacy_and_nonreceipt_payload(self):
        for header in (
            dict(schema='computer-wire/0', kind='request', value={}, payload_bytes=0),
            dict(schema=protocol.WIRE_SCHEMA, kind='request', value={}, payload_bytes=1),
            dict(schema=protocol.WIRE_SCHEMA, kind='state', value={}, payload_bytes=True),
            dict(schema=protocol.WIRE_SCHEMA, kind='receipt', value={}, payload_bytes=0, extra=1),
        ):
            with self.subTest(header=header), self.assertRaises(protocol.ControlError):
                protocol.wire_header(header)

    def test_python_producer_rejects_duplicate_keys(self):
        with self.assertRaises(protocol.ControlError):
            protocol.decode_json(b'{"id":"a","id":"b"}')

    def test_native_has_no_callback_filesystem_or_environment_polling(self):
        source = NATIVE.read_text()
        callbacks = source[source.index('struct Bridge {'):]
        for forbidden in ('getenv(', 'fstat(', 'lstat(', 'stat(', 'open(', 'unlink(',
                          'rename(', 'writeJSON(', 'IMG_SavePNG(', 'fileSystemRepresentation', 'LOCK_UN'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, callbacks)
        self.assertIn('IMG_SavePNG_RW(', source)
        self.assertIn('SDL_RWFromMem(', source)
        self.assertIn('FD_CLOEXEC', source)
        self.assertIn('SO_NOSIGPIPE', source)
        self.assertIn('O_NONBLOCK', source)

    def test_native_uses_bounded_pump_and_one_time_monotonic_expiry(self):
        source = NATIVE.read_text()
        self.assertIn('size_t budget=256*1024', source)
        self.assertIn('packets<8', source)
        self.assertIn('seen.size()<65536', source)
        self.assertEqual(source.count('expiresMonotonic=monotonicMS()+remaining'), 1)
        self.assertIn('monotonicMS()>=expiresMonotonic', source)
        for schema in ('computer-wire/1', 'computer-request/2', 'computer-target/2', 'computer-receipt/2'):
            self.assertIn(schema, source)
        self.assertIn('SDL_HasEvents(SDL_FIRSTEVENT,SDL_LASTEVENT)', source)


if __name__ == '__main__':
    unittest.main()
