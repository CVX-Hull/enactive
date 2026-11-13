import test from 'node:test';
import assert from 'node:assert/strict';
test('probe fails on purpose', () => { assert.fail('probe: the adapter lane must fail'); });
