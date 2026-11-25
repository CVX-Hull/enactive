// Measures, on a controlled clock, what the current host does when a pre-output
// server refusal asks for a provider delay that is longer than the time left on the
// request deadline (the #803 request 32 timing: HTTP 502 about 34 seconds into a
// 60-second request, a 60-second delay). These tests pin the shipped contract: the
// original request timer covers the backoff and the retry, so a wait that cannot fit
// ends the run with `request-timeout` and no second fetch. They do not propose a change.
//
// Clock: `t.mock.timers` replaces `setTimeout` only. `clock.advance(ms)` first adds to
// `clock.ms`, then ticks the mocked timers, so an event emitted from a timer callback
// is stamped with the instant the timer fired. Every advance below lands on an instant
// stated in the test, and each boundary is shown from both sides (one millisecond
// before: nothing happened; at the instant: it happened). No test sleeps real time
// for the controlled stretch.
import test from 'node:test';
import assert from 'node:assert/strict';
import { realDelay, route, reply, scenario, usageRecord } from './host-scenario.mjs';

const REQUEST_DEADLINE_SECONDS = 60;
const REFUSAL_AT_MS = 34_000;
const stopCommand = {schema:'player-control/1',id:'a'.repeat(32),session:'2'.repeat(32),actor_id:'3'.repeat(32),type:'orderly_stop'};

function badGateway(retryAfterSeconds) {
  return new Response(JSON.stringify({error:{code:502,message:'fixture-key upstream unavailable'}}),
    {status:502,headers:{'content-type':'application/json','retry-after':String(retryAfterSeconds)}});
}
// A response that the controlled clock releases `afterMs` after the fetch began.
const after = (afterMs, make) => () => new Promise(resolve => setTimeout(() => resolve(make()), afterMs));

function controlledClock(t) {
  t.mock.timers.enable({apis:['setTimeout']});
  const clock = {ms:0, stamps:[],
    advance(ms) { clock.ms += ms; t.mock.timers.tick(ms); },
    stamp(event) {
      const detail = event.stage ?? event.status ?? event.reason ?? event.control_id;
      clock.stamps.push([event.type, event.request_id ?? null, detail ?? null, clock.ms]);
    },
    at(type, requestId = null, detail = undefined) {
      return clock.stamps.find(s => s[0] === type && (requestId === null || s[1] === requestId) && (detail === undefined || s[2] === detail))?.[3];
    },
  };
  return clock;
}
async function until(predicate, what) {
  const limit = performance.now() + 10_000;
  while (!predicate() && performance.now() < limit) await realDelay(5);
  assert.ok(predicate(), `real fixture stage must precede the controlled advance: ${what}`);
}
// Real time only lets the host's promise continuations run; the controlled clock is unchanged.
const settleMicrotasks = () => realDelay(40);
// A failed stage would otherwise leave the host waiting on frozen timers and hang the test.
// Run the controlled clock far past every host deadline so the host settles, then rethrow.
const releaseOnFailure = (t, stages) => async (...args) => {
  try {
    await stages(...args);
  } catch (error) {
    for (let step = 0; step < 20; step += 1) { t.mock.timers.tick(1_000_000); await realDelay(10); }
    throw error;
  }
};

function watch(clock, state) {
  return event => {
    if (['request-start','response-headers','provider-retry','response-complete','abort','control-accepted','tool-start'].includes(event.type)) clock.stamp(event);
    if (event.type === 'provider-retry' && event.stage === 'eligible') state.eligible = true;
    if (event.type === 'provider-retry' && event.stage === 'started') state.started = true;
    if (event.type === 'abort') state.aborted = true;
    if (event.type === 'control-accepted') state.controlAccepted = true;
    if (event.type === 'settled') state.settled = true;
  };
}
const summary = events => ({
  settled: events.find(e => e.type === 'settled'),
  completions: events.filter(e => e.type === 'response-complete'),
  tools: events.filter(e => e.type === 'tool-start'),
});

test('a 60-second delay requested 34 seconds into a 60-second request is cut off by the original timer with no second fetch',async t=>{
  const clock = controlledClock(t), state = {};
  const configuration = route(); configuration.request_timeout_seconds = REQUEST_DEADLINE_SECONDS;
  let fetchStarted = false, secondFetchAtMs;
  const {result,payloads,calls,events} = await scenario(t,[
    init => { fetchStarted = true; return after(REFUSAL_AT_MS, () => badGateway(60))(init); },
    // Were it ever reached, this reply would dispatch a tool call.
    () => { secondFetchAtMs = clock.ms; return reply(null,[['mutate',{mode:'ok'}]]); },
  ],{configuration,timeoutSeconds:3600,expectedAbort:'request-timeout',advanceCleanupTimers:()=>t.mock.timers.tick(1000),
    onEvent:watch(clock,state),
    synchronize:releaseOnFailure(t,async()=>{
      await until(() => fetchStarted, 'first fetch');
      assert.equal(clock.at('request-start','request-1'),0);
      clock.advance(REFUSAL_AT_MS - 1); await settleMicrotasks();
      assert.equal(state.eligible,undefined,'the refusal has not arrived one millisecond early');
      clock.advance(1); await until(() => state.eligible, 'eligible refusal');
      // The provider asked for 60 s; 26 s of the original 60 s deadline remain.
      assert.equal(clock.at('provider-retry','request-1','eligible'),REFUSAL_AT_MS);
      clock.advance(REQUEST_DEADLINE_SECONDS * 1000 - REFUSAL_AT_MS - 1); await settleMicrotasks();
      assert.equal(state.aborted,undefined,'the original timer has not fired one millisecond early');
      assert.equal(state.started,undefined);
      clock.advance(1); await until(() => state.aborted, 'request timer');
      assert.equal(clock.at('abort'),REQUEST_DEADLINE_SECONDS * 1000);
      // The backoff would end at 34 s + 60 s = 94 s. A cancelled sleep lets the host settle
      // before then; a sleep still running would hold it until 94 s.
      while (!state.settled && clock.ms < 90_000) { clock.advance(1000); await realDelay(10); }
      assert.equal(state.settled,true,'the host settled while the backoff would still be sleeping');
      assert.ok(clock.ms < 94_000,`settled at ${clock.ms} ms, before the backoff's end at 94 s`);
      assert.equal(secondFetchAtMs,undefined);
      // Run the clock past 94 s as well: nothing is dispatched then either.
      clock.advance(94_000 - clock.ms + 1000); await settleMicrotasks();
      assert.equal(secondFetchAtMs,undefined,'the abort cancelled the sleep; nothing is dispatched at 94 s');
    }),
  });
  assert.equal(result.ok,false);assert.equal(result.reason,'request-timeout');
  assert.equal(result.requests,1);assert.equal(payloads.length,1);assert.equal(calls.length,0);
  const {settled,completions,tools} = summary(events);
  assert.equal(tools.length,0,'no tool call was dispatched');
  assert.equal(events.find(e=>e.type==='response-headers').requested_retry_delay_ms,60_000);
  assert.deepEqual(completions.map(e=>[e.request_id,e.stop_reason,e.http_status,e.cost_counted_as]),[['request-1','error',502,'unpriced']]);
  assert.equal(settled.unpriced_requests,1);assert.equal(settled.player_requests,1);
  assert.equal(events.filter(e=>e.type==='provider-retry'&&e.stage==='started').length,0);
  // Controlled-clock timeline of this run, in ms: request 0, refusal 34000, deadline 60000.
  assert.deepEqual(clock.stamps,[
    ['request-start','request-1',null,0],
    ['response-headers','request-1',502,REFUSAL_AT_MS],
    ['response-complete','request-1',null,REFUSAL_AT_MS],
    ['provider-retry','request-1','eligible',REFUSAL_AT_MS],
    ['abort','request-1','request-timeout',60_000],
  ]);
});

test('an accepted orderly stop wakes the backoff and sends a fresh logical request',async t=>{
  const clock = controlledClock(t), state = {};
  const configuration = route(); configuration.request_timeout_seconds = REQUEST_DEADLINE_SECONDS;
  let fetchStarted = false, control;
  const {result,payloads,calls,events} = await scenario(t,[
    init => { fetchStarted = true; return after(REFUSAL_AT_MS, () => badGateway(60))(init); },
    () => reply(null,[['player_finish',{disposition:'external_stop_complete',report:'Finished',source_ids:[],control_id:stopCommand.id}]]),
  ],{configuration,timeoutSeconds:3600,advanceCleanupTimers:()=>t.mock.timers.tick(1000),
    controlReady:stream=>{control=stream;},onEvent:watch(clock,state),
    synchronize:releaseOnFailure(t,async()=>{
      await until(() => fetchStarted, 'first fetch');
      clock.advance(REFUSAL_AT_MS); await until(() => state.eligible, 'eligible refusal');
      clock.advance(6000);
      control.write(JSON.stringify(stopCommand)+'\n');
      await until(() => clock.at('request-start','request-2') !== undefined, 'fresh control request');
      assert.equal(clock.at('control-accepted'),40_000);
      assert.equal(clock.at('request-start','request-2'),40_000);
      assert.equal(state.started,undefined);
      assert.equal(state.aborted,undefined);
    }),
  });
  assert.equal(result.reason,'external_stop_complete');
  assert.equal(payloads.length,2);assert.equal(calls.length,0);
  assert.match(JSON.stringify(payloads[1].messages), new RegExp(`control_id: ${stopCommand.id}`));
  assert.deepEqual(events.filter(e=>e.type==='request-start').map(e=>e.logical_request_id),['request-1','request-2']);
  assert.equal(summary(events).settled.unpriced_requests,1);
});

test('when the host allowance ends before the request timer, the actor limit cuts the backoff',async t=>{
  // The driver gives the host the smaller of the actor allowance and the custody
  // deadline less 30 s as --timeout-seconds, so one 50-second host allowance stands
  // for either limit. Work stops 1 s before it (cleanup budget): at 49 s.
  const clock = controlledClock(t), state = {};
  const configuration = route(); configuration.request_timeout_seconds = REQUEST_DEADLINE_SECONDS;
  let fetchStarted = false;
  const {result,payloads,calls,events} = await scenario(t,[
    init => { fetchStarted = true; return after(REFUSAL_AT_MS, () => badGateway(60))(init); },
    () => reply(null,[['mutate',{mode:'ok'}]]),
  ],{configuration,timeoutSeconds:50,expectedAbort:'host-timeout',advanceCleanupTimers:()=>t.mock.timers.tick(1000),
    onEvent:watch(clock,state),
    synchronize:releaseOnFailure(t,async()=>{
      await until(() => fetchStarted, 'first fetch');
      clock.advance(REFUSAL_AT_MS); await until(() => state.eligible, 'eligible refusal');
      clock.advance(49_000 - REFUSAL_AT_MS - 1); await settleMicrotasks();
      assert.equal(state.aborted,undefined);
      clock.advance(1); await until(() => state.aborted, 'host work timer');
      assert.equal(clock.at('abort'),49_000);
    }),
  });
  assert.equal(result.reason,'host-timeout');assert.equal(payloads.length,1);assert.equal(calls.length,0);
  assert.equal(events.filter(e=>e.type==='provider-retry'&&e.stage==='started').length,0);
  assert.equal(summary(events).settled.unpriced_requests,1);
});

// An instant reply would also complete under a renewed timer; the next test tells the two apart.
test('a 20-second delay fits: the second attempt starts at 54 s with the identical body and completes before 60 s',async t=>{
  const clock = controlledClock(t), state = {};
  const configuration = route(); configuration.request_timeout_seconds = REQUEST_DEADLINE_SECONDS;
  let fetchStarted = false, secondFetchAtMs;
  const {result,payloads,bodies,events} = await scenario(t,[
    init => { fetchStarted = true; return after(REFUSAL_AT_MS, () => badGateway(20))(init); },
    () => { secondFetchAtMs = clock.ms; return reply(); },
  ],{configuration,timeoutSeconds:3600,advanceCleanupTimers:()=>t.mock.timers.tick(1000),onEvent:watch(clock,state),
    synchronize:releaseOnFailure(t,async()=>{
      await until(() => fetchStarted, 'first fetch');
      clock.advance(REFUSAL_AT_MS); await until(() => state.eligible, 'eligible refusal');
      clock.advance(19_999); await settleMicrotasks();
      assert.equal(secondFetchAtMs,undefined,'never redispatch before the provider permits');
      clock.advance(1); await until(() => secondFetchAtMs !== undefined, 'second fetch');
    }),
  });
  assert.equal(secondFetchAtMs,54_000);
  assert.equal(result.ok,true);assert.equal(result.requests,2);assert.equal(bodies[0],bodies[1]);assert.deepEqual(payloads[0],payloads[1]);
  const {settled,completions} = summary(events);
  assert.deepEqual(completions.map(e=>e.cost_counted_as),['unpriced','provider-reported']);
  assert.equal(settled.unpriced_requests,1);assert.equal(settled.player_requests,2);
  assert.equal(settled.spent_usd,String(usageRecord.cost).replace(/^0\./,'0.').padEnd(8,'0'));
  assert.equal(clock.at('request-start','request-2'),54_000);
});

test('a 20-second delay that fits still leaves the second attempt only the remaining 6 seconds of the original deadline',async t=>{
  const clock = controlledClock(t), state = {};
  const configuration = route(); configuration.request_timeout_seconds = REQUEST_DEADLINE_SECONDS;
  let fetchStarted = false, secondFetchAtMs;
  const {result,payloads,bodies,calls,events} = await scenario(t,[
    init => { fetchStarted = true; return after(REFUSAL_AT_MS, () => badGateway(20))(init); },
    // The second response would arrive 10 s after its dispatch, at 64 s: after the deadline.
    init => { secondFetchAtMs = clock.ms; return after(10_000, () => reply(null,[['mutate',{mode:'ok'}]]))(init); },
  ],{configuration,timeoutSeconds:3600,expectedAbort:'request-timeout',advanceCleanupTimers:()=>t.mock.timers.tick(1000),
    onEvent:watch(clock,state),
    synchronize:releaseOnFailure(t,async()=>{
      await until(() => fetchStarted, 'first fetch');
      clock.advance(REFUSAL_AT_MS); await until(() => state.eligible, 'eligible refusal');
      clock.advance(20_000); await until(() => secondFetchAtMs !== undefined, 'second fetch');
      clock.advance(6_000 - 1); await settleMicrotasks();
      assert.equal(state.aborted,undefined);
      clock.advance(1); await until(() => state.aborted, 'request timer');
      assert.equal(clock.at('abort'),60_000);
    }),
  });
  assert.equal(secondFetchAtMs,54_000);
  assert.equal(result.reason,'request-timeout');assert.equal(result.requests,2);
  assert.equal(bodies[0],bodies[1]);assert.deepEqual(payloads[0],payloads[1]);assert.equal(calls.length,0);
  const {settled,completions,tools} = summary(events);
  assert.equal(tools.length,0);
  assert.deepEqual(completions.map(e=>[e.request_id,e.cost_counted_as]),[['request-1','unpriced'],['request-2','unpriced']]);
  assert.equal(settled.unpriced_requests,2);
});
