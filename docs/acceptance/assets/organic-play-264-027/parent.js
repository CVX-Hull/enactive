function step(view, state) {
  var st = state || {};
  var pass = st.pass || 0;
  var rows = (view.ui && view.ui.rows) || [];
  var isPickup = !!(view.ui && view.ui.purpose === 'inventory');
  var sig = rows.map(function (r) { return r.text; }).join('|');
  if (!view.in_game) {
    return {status: 'yield', state: st, input: null, reason: 'not in game'};
  }
  if (pass > 3) {
    return {status: 'done', state: st, input: null, reason: 'pass budget exhausted'};
  }
  if (!isPickup) {
    if (st.emptyConfirmed === true) {
      return {status: 'done', state: st, input: null, reason: 'cupboard emptied'};
    }
    return {status: 'act', state: {pass: pass + 1, marked: 0, lastSig: sig}, input: {type: 'key', key: 'g', modifiers: []}, reason: 'open pickup menu'};
  }
  if (rows.length === 0) {
    return {status: 'act', state: {pass: pass, marked: 0, lastSig: sig, emptyConfirmed: true}, input: {type: 'key', key: 'ESC', modifiers: []}, reason: 'no rows; close menu'};
  }
  var open = rows.filter(function (r) { return r.enabled && r.rendered_marker !== '+'; });
  if (open.length > 0) {
    return {status: 'act', state: {pass: pass, marked: (st.marked || 0) + 1, lastSig: sig}, input: {type: 'key', key: open[0].hotkey || 'a', modifiers: []}, reason: 'mark ' + open[0].text};
  }
  return {status: 'act', state: {pass: pass, marked: 0, lastSig: sig}, input: {type: 'key', key: 'ENTER', modifiers: []}, reason: 'confirm pickup'};
}
