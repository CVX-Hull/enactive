"""Current mechanical ingress rejects obsolete/ambiguous data before dispatch."""
import json
import struct
import unittest

from harness.computer.protocol import (
    ControlError, decode_json, encode_packet, source, state, validate_actions, wire_header,
)


class ComputerProtocolTests(unittest.TestCase):
    def test_stream_packet_retains_raw_png_without_base64(self):
        png = b'\x89PNG\r\n\x1a\n' + bytes(range(256))
        packet = encode_packet('receipt', {'id': 'a' * 32}, png)
        size = struct.unpack('!I', packet[:4])[0]
        header = wire_header(decode_json(packet[4:4 + size]))
        self.assertEqual(header['payload_bytes'], len(png))
        self.assertEqual(packet[4 + size:], png)
        self.assertEqual(header['schema'], 'computer-wire/1')

    def test_no_image_or_unbounded_body_can_enter_native_request(self):
        for kind, count in [('request', 1), ('state', 1), ('receipt', 67108865)]:
            with self.subTest(kind=kind, count=count), self.assertRaises(ControlError):
                wire_header({'schema': 'computer-wire/1', 'kind': kind,
                             'value': {}, 'payload_bytes': count})
        with self.assertRaises(ControlError):
            wire_header({'schema': 'computer-wire/0', 'kind': 'request',
                         'value': {}, 'payload_bytes': 0})

    def test_json_ingress_rejects_duplicate_keys_nonfinite_and_oversize(self):
        for text in ('{"id":1,"id":2}', '{"remaining":NaN}', '{"x":Infinity}'):
            with self.subTest(text=text), self.assertRaises(ControlError):
                decode_json(text)
        with self.assertRaises(ControlError):
            decode_json('"' + 'x' * 64 + '"', maximum=64)

    def test_obsolete_target_version_cannot_be_current_authority(self):
        old = {'schema': 'computer-target/1', 'session': 'a' * 32, 'pid': 1,
               'window_id': 1, 'paused': False, 'takeover_generation': 0,
               'latest_frame': None, 'error': ''}
        with self.assertRaises(ControlError):
            state(old, session='a' * 32, pid=1)
        old['schema'] = 'computer-target/2'
        self.assertEqual(state(old, session='a' * 32, pid=1), old)

    def test_keys_need_no_informing_image_but_public_click_cannot_supply_geometry(self):
        self.assertEqual(validate_actions([{'type': 'key', 'key': 'ESC', 'modifiers': []}]),
                         [{'type': 'key', 'key': 'ESC', 'modifiers': []}])
        self.assertEqual(validate_actions([{'type': 'click', 'x': 0, 'y': 1, 'button': 'left'}])[0]['x'], 0)
        with self.assertRaises(ControlError):
            validate_actions([{'type': 'click', 'x': 0, 'y': 1, 'button': 'left', 'geometry': {}}])
        with self.assertRaises(ControlError):
            validate_actions([{'type': 'wait', 'seconds': 2}] * 8)

    def test_source_identity_has_original_receipt_time_and_no_per_read_field(self):
        value = {'schema': 'computer-source/1', 'session': 'a' * 32,
                 'source_id': 'a' * 32 + '-1', 'capture_id': 1, 'sha256': 'b' * 64,
                 'media_type': 'image/png', 'presented_ms': 1000, 'received_wall': 1.1,
                 'width': 96, 'height': 64, 'window_width': 96, 'window_height': 64,
                 'viewport': [0, 0, 96, 64]}
        self.assertEqual(source(json.loads(json.dumps(value))), value)
        with self.assertRaises(ControlError):
            source(dict(value, read_wall=2))
        with self.assertRaises(ControlError):
            source(dict(value, source_id='c' * 32 + '-1'))
