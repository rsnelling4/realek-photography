// Runs offline with a stand-in for KV:  node --test tools/testimonials/test/
import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';
import worker from '../worker.js';

const SECRET = 'test-secret';
const ORIGIN = 'https://galleries.test';
const GALLERY = 'abcdefghijklmnopqrstuvwxyz';
// Worked out in Python; test_testimonials.py checks the same pair, so the two can't drift apart.
const KEY = 'cb00ae7aad970690276ee2234adf465e375e8d272e2fd0bc170ecf93aca1c51b';

class FakeKV {
  constructor() { this.data = new Map(); }
  async get(key, type) {
    const value = this.data.get(key);
    if (value === undefined) return null;
    return type === 'json' ? JSON.parse(value) : value;
  }
  async put(key, value) { this.data.set(key, value); }
  async delete(key) { this.data.delete(key); }
  async list({ prefix }) {
    return { keys: [...this.data.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })), list_complete: true };
  }
}

let env;
beforeEach(() => { env = { TESTIMONIAL_SECRET: SECRET, GALLERY_ORIGIN: ORIGIN, TESTIMONIALS: new FakeKV() }; });

const call = (method, path, { body, headers = {} } = {}) =>
  worker.fetch(new Request(`https://w.test${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) }), env);
const send = (fields = {}, origin = ORIGIN) => call('POST', '/submissions', {
  headers: { Origin: origin, 'Content-Type': 'application/json' },
  body: { gallery: GALLERY, key: KEY, name: 'Ann + Bo', text: 'Lovely session.', share: true, ...fields },
});
const admin = (method, path, body) => call(method, `/admin/${path}`, { body, headers: { Authorization: `Bearer ${SECRET}` } });
const queue = async () => (await admin('GET', 'submissions')).json();
const site = async () => (await (await call('GET', '/testimonials')).json()).testimonials;

test('a real gallery can submit, and nothing shows on the site until approved', async () => {
  assert.equal((await send()).status, 201);
  const { pending } = await queue();
  assert.equal(pending.length, 1);
  assert.equal(pending[0].name, 'Ann + Bo');
  assert.deepEqual(await site(), []);
});

test('a forged key, missing key, or other gallery is refused', async () => {
  assert.equal((await send({ key: 'f'.repeat(64) })).status, 403);
  assert.equal((await send({ key: undefined })).status, 403);
  assert.equal((await send({ gallery: 'zzzzzzzzzzzzzzzzzzzzzzzzzz' })).status, 403);
  assert.equal((await queue()).pending.length, 0);
});

test('submissions from other websites are refused', async () => {
  assert.equal((await send({}, 'https://evil.test')).status, 403);
  assert.equal((await queue()).pending.length, 0);
});

test('blank or overlong words are refused', async () => {
  assert.equal((await send({ text: '   ' })).status, 400);
  assert.equal((await send({ name: '' })).status, 400);
  assert.equal((await send({ text: 'x'.repeat(1501) })).status, 400);
  assert.equal((await send({ name: 'x'.repeat(81) })).status, 400);
});

test('one gallery can only send so many', async () => {
  for (let i = 0; i < 5; i += 1) assert.equal((await send()).status, 201);
  assert.equal((await send()).status, 429);
});

test('approving posts it with any edits, and the public list never includes the private link', async () => {
  await send();
  const { id } = (await queue()).pending[0];
  assert.equal((await admin('POST', 'approve', { id, name: 'Ann S.', text: 'Lovely session!' })).status, 200);
  const shown = await site();
  assert.equal(shown.length, 1);
  assert.deepEqual(Object.keys(shown[0]).sort(), ['id', 'name', 'text']);
  assert.equal(shown[0].name, 'Ann S.');
  assert.equal(shown[0].text, 'Lovely session!');
  const raw = await (await call('GET', '/testimonials')).text();
  assert.ok(!raw.includes(GALLERY));
  assert.equal((await queue()).pending.length, 0);
});

test('the newest approved comes first', async () => {
  await send({ text: 'first' });
  await send({ text: 'second' });
  const { pending } = await queue();
  for (const { id } of pending) await admin('POST', 'approve', { id });
  assert.equal((await site())[0].text, pending[1].text);
});

test('private feedback can never be posted', async () => {
  await send({ share: false });
  const { id } = (await queue()).pending[0];
  assert.equal((await admin('POST', 'approve', { id })).status, 400);
  assert.deepEqual(await site(), []);
  assert.equal((await queue()).pending.length, 1);
});

test('permission has to be given outright', async () => {
  await send({ share: 'false' });
  assert.equal((await queue()).pending[0].share, false);
});

test('removing from the site puts it back in the queue, and it can be deleted', async () => {
  await send();
  const { id } = (await queue()).pending[0];
  await admin('POST', 'approve', { id });
  assert.equal((await admin('POST', 'unpublish', { id })).status, 200);
  assert.deepEqual(await site(), []);
  assert.equal((await queue()).pending[0].id, id);
  assert.equal((await admin('POST', 'delete', { id })).status, 200);
  assert.equal((await queue()).pending.length, 0);
});

test('admin actions need the secret', async () => {
  await send();
  const { id } = (await queue()).pending[0];
  assert.equal((await call('GET', '/admin/submissions')).status, 401);
  const wrong = { Authorization: 'Bearer nope' };
  assert.equal((await call('GET', '/admin/submissions', { headers: wrong })).status, 401);
  assert.equal((await call('POST', '/admin/approve', { headers: wrong, body: { id } })).status, 401);
  assert.deepEqual(await site(), []);
});

test('an odd id is refused', async () => {
  assert.equal((await admin('POST', 'delete', { id: '../published' })).status, 400);
  assert.equal((await admin('POST', 'approve', {})).status, 400);
});

test('with no secret set, nothing works', async () => {
  env.TESTIMONIAL_SECRET = '';
  assert.equal((await send()).status, 500);
  assert.equal((await call('GET', '/admin/submissions', { headers: { Authorization: 'Bearer ' } })).status, 500);
});

test('galleries are allowed to send across sites, and the site to read', async () => {
  const preflight = await call('OPTIONS', '/submissions');
  assert.equal(preflight.headers.get('Access-Control-Allow-Origin'), ORIGIN);
  assert.equal((await send()).headers.get('Access-Control-Allow-Origin'), ORIGIN);
  assert.equal((await call('GET', '/testimonials')).headers.get('Access-Control-Allow-Origin'), '*');
});
