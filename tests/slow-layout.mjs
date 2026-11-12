// Run from Telegram's pinned widget-sandbox checkout with node --import tsx.
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const { runWidget } = await import(pathToFileURL(resolve('packages/core/scripts/sandbox-node.ts')));
const examples = new URL('../examples/', import.meta.url);
const input = (name, ext) => readFileSync(new URL(name + '.' + ext, examples), 'utf8');
const sleeper = new Int32Array(new SharedArrayBuffer(4));
const slowHost = {
  answer() { Atomics.wait(sleeper, 0, 0, 1200); },
  cpuLimitMs: 1000,
  timerRounds: 2,
};

const firstFrame = {
  'price-snapshot': ["document.getElementById('price').textContent", '$175.04'],
  'bar-chart': ["document.getElementById('chart').childNodes.length > 1", 'true'],
  'checklist': ["document.getElementById('count').textContent", '3 / 5'],
  'poll-results': ["document.getElementById('q').textContent", 'Where do we meet on Friday?'],
  'countdown': ["document.getElementById('title').textContent", 'Mainnet launch'],
  'token-comparison': ["document.querySelector('.row b').textContent", 'BTC'],
};

async function render(name, chatData, opts) {
  const result = await runWidget(input(name, 'html'), { ...slowHost, data: { chatData }, ...opts });
  assert.equal(result.stopped, undefined, name + ': ' + result.stopped);
  assert.deepEqual(result.diags.filter(d => d.kind === 'query-limit'), [], name);
  assert.deepEqual(result.logs.filter(log => log.level === 'error'), [], name);
  return result.probes;
}

for (const file of readdirSync(examples).filter(f => f.endsWith('.html'))) {
  const name = file.slice(0, -5);
  assert.ok(firstFrame[name], 'Add a first-frame assertion for ' + name);
  const [probe, expected] = firstFrame[name];
  assert.deepEqual(await render(name, input(name, 'json'), { probes: [probe] }), [expected], name);
}

// The same message is edited twice, then reopened with only its latest price.
const name = 'price-snapshot';
const full = JSON.parse(input(name, 'json'));
const priceOnly = { ...full, p: 172.25 };
delete priceOnly.h;
const restored = { ...priceOnly, h: [2, 1, 3] };
const snapshot = `JSON.stringify([
  document.getElementById('price').textContent,
  document.getElementById('chart').style.display,
  document.getElementById('line').getAttribute('points')
])`;
const steps = [
  { probe: snapshot }, { data: { chatData: JSON.stringify(priceOnly) } }, { probe: snapshot },
  { data: { chatData: JSON.stringify(restored) } }, { probe: snapshot },
];
const [initial, cleared, redrawn] = (await render(name, JSON.stringify(full), { script: steps })).map(value => JSON.parse(value));
assert.ok(initial[2].length > 0);
assert.deepEqual(cleared, ['$172.25', 'none', '']);
assert.deepEqual(redrawn.slice(0, 2), ['$172.25', 'block']);
assert.equal(redrawn[2].trim().split(/\s+/).length, restored.h.length);
for (const history of [undefined, [], [10]]) {
  const data = JSON.stringify({ ...priceOnly, h: history });
  const [cold] = await render(name, data, { probes: [snapshot] });
  assert.deepEqual(JSON.parse(cold), cleared);
}
console.log('All example first frames and the price-only edit cycle passed.');
