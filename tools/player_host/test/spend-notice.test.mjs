// R-OVERSPEND and R-REGRESSION: early wrap-up guidance with an unchanged cached prefix.
import test from 'node:test';
import assert from 'node:assert/strict';
import {reply, route, scenario} from './host-scenario.mjs';

const look = cost => reply(null, [['observe', {}]], {cost});
const options = (spend_limit_usd, finishReserveUsd) => ({configuration:{...route(), spend_limit_usd},
  finishReserveUsd, enabledTools:['observe', 'player_handoff']});
const notices = events => events.filter(event => event.type === 'tail-notice' && event.kinds.includes('spend-limit'));
const newestText = payload => payload.messages.at(-1).content[0].text;
const spendText = dollars => `Host spend allowance: about $${dollars} of work budget remains before the ending reserve.`;

test('the spend notice crosses the percentage threshold exactly and extends the cached prefix', async t => {
  // At $1.70 spent, the remaining $0.300000000000000001 exceeds 15% of $2.000000000000000001.
  // Spending another $0.000000000000000001 puts the remainder inside the warning band.
  const {result, events, payloads} = await scenario(t, [look(0.7), look(1), look(1e-18), look(0.1), reply()],
    options('2.500000000000000001', '0.5'));
  assert.equal(result.ok, true);
  assert.deepEqual(notices(events).map(event => event.request_id), ['request-4', 'request-5']);
  const first = newestText(payloads[3]);
  assert.ok(first.startsWith(spendText('0.3')));
  assert.match(first, /Wrap up with player_finish/);
  assert.match(first, /Avoid starting a fresh actor with player_handoff/);
  assert.equal(newestText(payloads[4]), spendText('0.2'));
  for (let index = 1; index < payloads.length; index++) {
    const earlier = payloads[index - 1].messages;
    assert.deepEqual(payloads[index].messages.slice(0, earlier.length), earlier);
  }
});

test('the quarter-dollar floor triggers at equality and the notice reports zero inside the reserve', async t => {
  const {result, events, payloads} = await scenario(t, [look(0.49), look(0.01), look(0.26), reply()], options('1', '0.25'));
  assert.equal(result.ok, true);
  assert.deepEqual(notices(events).map(event => event.request_id), ['request-3', 'request-4']);
  assert.ok(newestText(payloads[2]).startsWith(spendText('0.25')));
  assert.equal(newestText(payloads[3]), spendText('0'));
});

test('a tiny work budget and a start at or inside the reserve both warn on the first request', async t => {
  for (const [limit, reserve, expected] of [['0.9', '0.75', '0.15'], ['0.5', '0.5', '0'], ['0.4', '0.5', '0']]) {
    const {result, events, payloads} = await scenario(t, [reply()], options(limit, reserve));
    assert.equal(result.ok, true);
    assert.deepEqual(notices(events).map(event => [event.request_id, event.kinds]), [['request-1', ['spend-limit']]]);
    assert.ok(newestText(payloads[0]).startsWith(spendText(expected)));
  }
});

test('the first spend notice omits handoff advice when the tool is disabled', async t => {
  const {result, events, payloads} = await scenario(t, [reply()], {...options('0.9', '0.75'), enabledTools:['observe']});
  assert.equal(result.ok, true);
  assert.deepEqual(notices(events).map(event => event.request_id), ['request-1']);
  assert.equal(newestText(payloads[0]), `${spendText('0.15')} Wrap up with player_finish, reporting where play stands.`);
});
