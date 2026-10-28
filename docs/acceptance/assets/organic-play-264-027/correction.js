function step(view, state) {
  var st = state || {};
  var evals = (st.evals || 0) + 1;
  var rows = (view.ui && view.ui.rows) || [];
  var isPickup = !!(view.ui && view.ui.purpose === 'inventory');
  var kind = (view.boundary && view.boundary.kind) || '';
  var sig = rows.map(function (r) { return (r.hotkey || '!') + (r.enabled ? '1' : '0') + (r.rendered_marker || '-') + (r.text || ''); }).join('|');
  var next = function (patch) {
    var out = {evals: evals, phase: st.phase, passes: st.passes || 0, marked: st.marked || 0, expanded: st.expanded === true, lastSig: st.lastSig || '', finished: st.finished === true};
    var k;
    for (k in patch) { if (Object.prototype.hasOwnProperty.call(patch, k)) { out[k] = patch[k]; } }
    return out;
  };
  if (!view.in_game) { return {status: 'yield', state: next({}), input: null, reason: 'not in game'}; }
  if (evals > 16 || (st.passes || 0) > 2 || st.finished === true) { return {status: 'done', state: next({}), input: null, reason: 'sweep budget spent'}; }
  if (!isPickup) {
    if (kind !== 'normal_play') {
      return {status: 'act', state: next({}), input: {type: 'key', key: 'ESC', modifiers: []}, reason: 'cancel stray prompt (' + kind + ')'};
    }
    return {status: 'act', state: next({phase: 'pick'}), input: {type: 'key', key: 'g', modifiers: []}, reason: 'open pickup menu'};
  }
  if (rows.length === 0) {
    return {status: 'act', state: next({finished: true}), input: {type: 'key', key: 'ESC', modifiers: []}, reason: 'pickup menu empty'};
  }
  var enabled = [];
  var hasContents = false;
  var i;
  for (i = 0; i < rows.length; i += 1) {
    if (rows[i].enabled) { enabled.push(rows[i]); }
    if (String(rows[i].text || '').indexOf('>') >= 0) { hasContents = true; }
  }
  if (enabled.length === 0) {
    if (hasContents && st.expanded !== true) {
      return {status: 'act', state: next({phase: 'pick', expanded: true, marked: 0}), input: {type: 'key', key: '>', modifiers: []}, reason: 'container does not fit; expand to reach contained food'};
    }
    return {status: 'act', state: next({phase: 'pick', finished: true}), input: {type: 'key', key: 'ESC', modifiers: []}, reason: 'no item fits; report leftovers'};
  }
  var unmarked = [];
  var j;
  for (j = 0; j < enabled.length; j += 1) {
    if (enabled[j].rendered_marker !== '+') { unmarked.push(enabled[j]); }
  }
  var inner = [];
  var outer = [];
  var m;
  for (m = 0; m < unmarked.length; m += 1) {
    if (String(unmarked[m].text || '').indexOf('>') >= 0) { outer.push(unmarked[m]); } else { inner.push(unmarked[m]); }
  }
  var pick = inner.length > 0 ? inner[0] : outer[0];
  if (pick && (st.marked || 0) < 4) {
    return {status: 'act', state: next({phase: 'pick', marked: (st.marked || 0) + 1, lastSig: sig}), input: {type: 'key', key: pick.hotkey || 'a', modifiers: []}, reason: 'mark ' + String(pick.text || 'item')};
  }
  if (st.lastSig === sig) {
    return {status: 'done', state: next({}), input: null, reason: 'no progress after confirm; leftovers remain'};
  }
  return {status: 'act', state: next({phase: 'pick', passes: (st.passes || 0) + 1, marked: 0, lastSig: sig}), input: {type: 'key', key: 'ENTER', modifiers: []}, reason: 'confirm marked items'};
}
