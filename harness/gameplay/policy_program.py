"""Bounded passive JavaScript policies; returned input is data, never dispatched."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Self

from py_mini_racer import JSEvalException, JSFunction, mini_racer

from .contracts import _enum, _object, _text, canonical, json_object, validate_json
from .native_input import input_schema

_SOURCE_BYTES = 32 * 1024
_VIEW_BYTES = 256 * 1024
_STATE_BYTES = 16 * 1024
_RESULT_BYTES = 32 * 1024
_HEAP_BYTES = 32 * 1024 * 1024
_COMPILE_SECONDS = .25
_STEP_SECONDS = .05


class PolicyProgramError(ValueError):
    """A compile, evaluation or validation fault; the program cannot be replayed."""


def _result_schema() -> dict:
    ordinary = input_schema(text_limit=24)
    click = ordinary['anyOf'][2]
    del click['properties']['geometry']
    click['required'].remove('geometry')
    return {
        **_object({'status': _enum('act', 'yield', 'done'),
                   'state': {'type': 'object'}, 'input': {}, 'reason': _text(1024)}),
        'if': {'properties': {'status': {'const': 'act'}}},
        'then': {'properties': {'input': ordinary}},
        'else': {'properties': {'input': {'type': 'null'}}},
    }


_RESULT_SCHEMA = _result_schema()

# The policy is compiled in a separate Function scope, so it cannot access the
# bridge's captured intrinsics. The returned bridge is held only by Python.
# Clone descriptor-checked data into prototype-free containers before stringify:
# even inherited toJSON or changed Array/Object methods cannot omit/coerce data.
_BRIDGE = r"""
(() => {
  'use strict';
  const compile = Function;
  const parse = JSON.parse, stringify = JSON.stringify;
  const ownKeys = Reflect.ownKeys;
  const descriptor = Object.getOwnPropertyDescriptor;
  const hasOwn = Object.hasOwn;
  const prototype = Object.getPrototypeOf;
  const create = Object.create, setPrototype = Object.setPrototypeOf;
  const define = Object.defineProperty;
  const isArray = Array.isArray, finite = Number.isFinite;
  const objectPrototype = Object.prototype, arrayPrototype = Array.prototype;
  const ErrorType = TypeError;
  const global = globalThis;

  // The installed timer manager is a global lexical class plus global vars.
  // Clear the lexical class as well as sealing every exposed scheduling handle.
  __TimerManager = undefined;
  const removed = ['__timer_manager', '__TimerManager', 'setTimeout', 'clearTimeout',
    'setInterval', 'clearInterval', 'queueMicrotask', 'SharedArrayBuffer',
    'Worker', 'WebAssembly', 'FinalizationRegistry', 'WeakRef'];
  for (let i = 0; i < removed.length; i++) {
    define(global, removed[i], {value:undefined, writable:false, configurable:false});
  }
  define(Atomics, 'waitAsync', {value:undefined, writable:false, configurable:false});
  define(Atomics, 'wait', {value:undefined, writable:false, configurable:false});

  function clone(value, ancestors) {
    if (value === null || typeof value === 'boolean' || typeof value === 'string')
      return value;
    if (typeof value === 'number') {
      if (!finite(value)) throw new ErrorType('Nonfinite JSON number');
      return value;
    }
    if (typeof value !== 'object') throw new ErrorType('Non-JSON value');
    for (let i = 0; i < ancestors.length; i++)
      if (ancestors[i] === value) throw new ErrorType('Cyclic JSON value');
    const array = isArray(value);
    const proto = prototype(value);
    if (proto !== null && proto !== (array ? arrayPrototype : objectPrototype))
      throw new ErrorType('Non-plain JSON object');
    const result = array ? [] : create(null);
    if (array) setPrototype(result, null);
    const keys = ownKeys(value);
    const length = array ? descriptor(value, 'length').value : 0;
    if (array && keys.length !== length + 1) throw new ErrorType('Sparse or extended array');
    ancestors[ancestors.length] = value;
    for (let i = 0; i < keys.length; i++) {
      const key = keys[i];
      if (typeof key !== 'string') throw new ErrorType('Symbol JSON key');
      if (array && key === 'length') continue;
      const prop = descriptor(value, key);
      if (!prop || !hasOwn(prop, 'value') || !prop.enumerable)
        throw new ErrorType('Accessor or hidden JSON property');
      if (array && (key !== `${+key}` || +key < 0 || +key >= length || +key % 1))
        throw new ErrorType('Non-index array property');
      // Define instead of assignment: policy prototype setters are irrelevant.
      define(result, key, {value:clone(prop.value, ancestors), enumerable:true,
                           writable:true, configurable:true});
    }
    ancestors.length--;
    return result;
  }

  const step = compile('"use strict";\n' + SOURCE +
    '\n; if (typeof step !== "function") throw new TypeError("Policy requires step(view, state)");' +
    '\nreturn step;')();
  return (view, state) => {
    const result = step(parse(view), parse(state));
    const ancestors = [];
    setPrototype(ancestors, null);
    return stringify(clone(result, ancestors));
  };
})()
"""


def _bounded_object(value: Any, limit: int, name: str) -> str:
    if type(value) is not dict:
        raise PolicyProgramError(f'{name} must be a JSON object')
    encoded = canonical(value)
    if len(encoded.encode('utf-8')) > limit:
        raise PolicyProgramError(f'{name} exceeds {limit} UTF-8 bytes')
    # V8 parses JSON numbers as binary64. Never silently round an integer the
    # Python caller could represent exactly, or turn a large integer infinite.
    def numbers(item):
        if type(item) is int and abs(item) > 2**53 - 1:
            raise PolicyProgramError(f'{name} integer exceeds JavaScript safe precision')
        if type(item) is float and item.is_integer() and abs(item) > 2**53 - 1:
            raise PolicyProgramError(f'{name} integer exceeds JavaScript safe precision')
        if isinstance(item, dict):
            for child in item.values():
                numbers(child)
        elif isinstance(item, list):
            for child in item:
                numbers(child)
    numbers(json.loads(encoded))
    return encoded


class PolicyProgram:
    """Compile once and evaluate passive steps on an owned synchronous lifetime.

    The caller serializes calls on its existing writer/adapter thread. This API
    must be called outside an already running asyncio loop. Every fault closes
    the isolate; a caller must not retry the failed decision automatically.
    """

    def __init__(self, code: str) -> None:
        self._runner: asyncio.Runner | None = None
        self._context = None
        self._runtime = None
        self._bridge = None
        try:
            if type(code) is not str or len(code.encode('utf-8')) > _SOURCE_BYTES:
                raise PolicyProgramError('Policy source must be a string within 32768 UTF-8 bytes')
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                pass
            else:
                raise PolicyProgramError('PolicyProgram requires a synchronous caller thread')
            self._runner = asyncio.Runner()
            self._runner.run(self._compile(code))
        except (ValueError, TypeError, RecursionError, JSEvalException, TimeoutError) as exc:
            self.close()
            raise PolicyProgramError(f'Policy compile failed: {exc}') from exc

    async def _compile(self, code: str) -> None:
        # The public context binds to this running loop. Free it while the loop
        # is still alive; using MiniRacer's default loop has different teardown.
        self._context = mini_racer()
        self._runtime = self._context.__enter__()
        self._runtime.set_hard_memory_limit(_HEAP_BYTES)
        source = _BRIDGE.replace('SOURCE', json.dumps(code, ensure_ascii=True))
        async def compile_and_drain():
            bridge = await self._runtime.eval_cancelable(source)
            # MiniRacer returns evaluation results before the V8 microtask
            # checkpoint finishes. A second evaluation is queued after that
            # checkpoint; include it in the same timeout, even during compile.
            await self._runtime.eval_cancelable('void 0')
            if self._runtime.was_hard_memory_limit_reached():
                raise PolicyProgramError('Policy compile microtasks exceeded the heap limit')
            return bridge

        bridge = await asyncio.wait_for(compile_and_drain(), timeout=_COMPILE_SECONDS)
        if not isinstance(bridge, JSFunction):
            raise PolicyProgramError('Compilation did not return a policy bridge')
        self._bridge = bridge.cancelable()

    def __enter__(self) -> Self:
        if self._runner is None:
            raise PolicyProgramError('Policy program is closed')
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    async def _shutdown(self) -> None:
        self._bridge = None
        if self._runtime is not None:
            self._runtime.close()
            self._runtime = None
        if self._context is not None:
            self._context.__exit__(None, None, None)
            self._context = None

    def close(self) -> None:
        """Idempotently free the isolate before closing its caller-owned loop."""
        runner = self._runner
        if runner is None:
            return
        self._runner = None
        try:
            runner.run(self._shutdown())
        finally:
            runner.close()

    def step(self, view: dict, state: dict, *, timeout_seconds: float = _STEP_SECONDS) -> dict:
        """Return validated act/yield/done data, without performing any input."""
        if self._runner is None:
            raise PolicyProgramError('Policy program is closed or faulted')
        try:
            if (type(timeout_seconds) not in (int, float)
                    or not 0 < timeout_seconds <= _STEP_SECONDS):
                raise PolicyProgramError('Step timeout must be finite and within (0, 0.05] seconds')
            view_json = _bounded_object(view, _VIEW_BYTES, 'View')
            state_json = _bounded_object(state, _STATE_BYTES, 'State')
            result_json = self._runner.run(self._evaluate(view_json, state_json, timeout_seconds))
            if type(result_json) is not str or len(result_json.encode('utf-8')) > _RESULT_BYTES:
                raise PolicyProgramError('Policy result exceeds 32768 UTF-8 bytes or is not JSON')
            result = json_object(result_json)
            _bounded_object(result, _RESULT_BYTES, 'Result')
            validate_json(result, _RESULT_SCHEMA)
            _bounded_object(result['state'], _STATE_BYTES, 'Returned state')
            return result
        except (ValueError, TypeError, RecursionError, JSEvalException, TimeoutError) as exc:
            self.close()
            raise PolicyProgramError(f'Policy step failed: {exc}') from exc

    async def _evaluate(self, view: str, state: str, timeout: float):
        async def evaluate_and_drain():
            result = await self._bridge(view, state)
            await self._runtime.eval_cancelable('void 0')
            if self._runtime.was_hard_memory_limit_reached():
                raise PolicyProgramError('Policy step microtasks exceeded the heap limit')
            return result

        return await asyncio.wait_for(evaluate_and_drain(), timeout=timeout)
