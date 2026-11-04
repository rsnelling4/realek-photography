// Receives client testimonials from galleries, holds them for Robert's approval, and gives the
// main website only the ones he has approved. Kept in KV because the gallery bucket deletes
// everything after a month.
//
//   POST /submissions          from a gallery page, with that gallery's signed key
//   GET  /testimonials         public: approved testimonials only
//   GET  /admin/submissions    the rest need the secret, and are only called by the approval page
//   POST /admin/approve        { id, name, text }
//   POST /admin/unpublish      { id }
//   POST /admin/delete         { id }

const MAX_BODY = 10_000;
const MAX_NAME = 80;
const MAX_TEXT = 1500;
const MAX_PER_GALLERY = 5; // a leaked link can't fill the store
const PUBLISHED_KEY = 'published';
const GALLERY_PATTERN = /^[A-Za-z0-9_-]{20,}$/;
const ID_PATTERN = /^[A-Za-z0-9_-]{20,}:[0-9a-f-]{36}$/;
const encoder = new TextEncoder();

class BadRequest extends Error {}

const respond = (status, data, headers = {}) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ...headers } });

const hmacKey = (secret, usage) =>
  crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, [usage]);

const hexBytes = (hex) => Uint8Array.from(hex.match(/../g), (pair) => parseInt(pair, 16));

// The key is written into each gallery when it's published, so a key proves the gallery is real.
async function validGalleryKey(secret, gallery, key) {
  if (typeof key !== 'string' || !/^[0-9a-f]{64}$/.test(key)) return false;
  const verifying = await hmacKey(secret, 'verify');
  return crypto.subtle.verify('HMAC', verifying, hexBytes(key), encoder.encode(`gallery:${gallery}`));
}

// Comparing signatures rather than the secret itself means timing reveals nothing about it.
async function isAdmin(request, secret) {
  const given = request.headers.get('Authorization') || '';
  const signing = await hmacKey(secret, 'sign');
  const signature = await crypto.subtle.sign('HMAC', signing, encoder.encode(given));
  const verifying = await hmacKey(secret, 'verify');
  return crypto.subtle.verify('HMAC', verifying, signature, encoder.encode(`Bearer ${secret}`));
}

async function readJson(request) {
  const body = await request.text();
  if (body.length > MAX_BODY) throw new BadRequest('That message is too long.');
  try {
    const data = JSON.parse(body);
    if (data && typeof data === 'object') return data;
  } catch { /* falls through */ }
  throw new BadRequest('That request could not be read.');
}

function cleanWords(name, text) {
  name = typeof name === 'string' ? name.trim() : '';
  text = typeof text === 'string' ? text.trim() : '';
  if (!name) throw new BadRequest('Please add a name to show.');
  if (!text) throw new BadRequest('Please share a few words first.');
  if (name.length > MAX_NAME) throw new BadRequest(`Please keep the name under ${MAX_NAME} characters.`);
  if (text.length > MAX_TEXT) throw new BadRequest(`Please keep your message under ${MAX_TEXT} characters.`);
  return { name, text };
}

async function listKeys(kv, prefix) {
  const names = [];
  let cursor;
  do {
    const page = await kv.list({ prefix, cursor });
    names.push(...page.keys.map((k) => k.name));
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return names;
}

const readPublished = async (kv) => (await kv.get(PUBLISHED_KEY, 'json')) || [];

function checkedId(data) {
  if (typeof data.id !== 'string' || !ID_PATTERN.test(data.id)) throw new BadRequest('That testimonial id is not valid.');
  return data.id;
}

async function submit(request, env) {
  const data = await readJson(request);
  const { gallery } = data;
  if (typeof gallery !== 'string' || !GALLERY_PATTERN.test(gallery)
      || !(await validGalleryKey(env.TESTIMONIAL_SECRET, gallery, data.key))) {
    return { status: 403, body: { error: 'This gallery link could not be confirmed.' } };
  }
  const { name, text } = cleanWords(data.name, data.text);
  const existing = await listKeys(env.TESTIMONIALS, `sub:${gallery}:`);
  if (existing.length >= MAX_PER_GALLERY) {
    return { status: 429, body: { error: 'This gallery has already sent several messages. Thank you!' } };
  }
  const id = `${gallery}:${crypto.randomUUID()}`;
  await env.TESTIMONIALS.put(`sub:${id}`, JSON.stringify({
    id, gallery, name, text, share: data.share === true, submitted: new Date().toISOString(),
  }));
  return { status: 201, body: { ok: true } };
}

async function adminList(env) {
  const names = await listKeys(env.TESTIMONIALS, 'sub:');
  const pending = await Promise.all(names.map((name) => env.TESTIMONIALS.get(name, 'json')));
  return {
    pending: pending.filter(Boolean).sort((a, b) => a.submitted.localeCompare(b.submitted)),
    published: await readPublished(env.TESTIMONIALS),
  };
}

async function approve(data, env) {
  const id = checkedId(data);
  const item = await env.TESTIMONIALS.get(`sub:${id}`, 'json');
  if (!item) throw new BadRequest('That testimonial is no longer waiting.');
  // Without the client's permission it stays private, however it's asked for.
  if (!item.share) throw new BadRequest('This client did not agree to have it posted.');
  const { name, text } = cleanWords(data.name ?? item.name, data.text ?? item.text);
  const published = (await readPublished(env.TESTIMONIALS)).filter((p) => p.id !== id);
  // Saved to the site before it leaves the queue, so a failure between the two can't lose it.
  const entry = { ...item, name, text, approved: new Date().toISOString() };
  await env.TESTIMONIALS.put(PUBLISHED_KEY, JSON.stringify([entry, ...published]));
  await env.TESTIMONIALS.delete(`sub:${id}`);
}

async function unpublish(data, env) {
  const id = checkedId(data);
  const published = await readPublished(env.TESTIMONIALS);
  const item = published.find((p) => p.id === id);
  if (!item) throw new BadRequest('That testimonial is no longer on the website.');
  const { approved, ...waiting } = item;
  await env.TESTIMONIALS.put(`sub:${id}`, JSON.stringify(waiting));
  await env.TESTIMONIALS.put(PUBLISHED_KEY, JSON.stringify(published.filter((p) => p.id !== id)));
}

const ADMIN_ACTIONS = {
  '/admin/approve': approve,
  '/admin/unpublish': unpublish,
  '/admin/delete': async (data, env) => { await env.TESTIMONIALS.delete(`sub:${checkedId(data)}`); },
};

async function route(request, env) {
  const { pathname } = new URL(request.url);
  const { method } = request;
  const galleryCors = {
    'Access-Control-Allow-Origin': env.GALLERY_ORIGIN,
    'Access-Control-Allow-Methods': 'POST',
    'Access-Control-Allow-Headers': 'Content-Type',
    Vary: 'Origin',
  };

  if (method === 'GET' && pathname === '/testimonials') {
    // Named field by field: the gallery token is the client's private link and must never appear here.
    const published = await readPublished(env.TESTIMONIALS);
    const items = published.map((p) => ({ id: p.id.split(':')[1], name: p.name, text: p.text }));
    return respond(200, { testimonials: items }, { 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'public, max-age=60' });
  }

  if (pathname === '/submissions') {
    if (method === 'OPTIONS') return new Response(null, { status: 204, headers: galleryCors });
    if (method !== 'POST') return respond(405, { error: 'Not allowed.' });
    if (request.headers.get('Origin') !== env.GALLERY_ORIGIN) return respond(403, { error: 'Not allowed.' });
    try {
      const { status, body } = await submit(request, env);
      return respond(status, body, galleryCors);
    } catch (err) {
      if (err instanceof BadRequest) return respond(400, { error: err.message }, galleryCors);
      throw err;
    }
  }

  if (pathname.startsWith('/admin/')) {
    if (!(await isAdmin(request, env.TESTIMONIAL_SECRET))) return respond(401, { error: 'Not allowed.' });
    if (method === 'GET' && pathname === '/admin/submissions') return respond(200, await adminList(env));
    if (method === 'POST' && ADMIN_ACTIONS[pathname]) {
      await ADMIN_ACTIONS[pathname](await readJson(request), env);
      return respond(200, { ok: true });
    }
  }
  return respond(404, { error: 'Not found.' });
}

export default {
  async fetch(request, env) {
    if (!env.TESTIMONIAL_SECRET) return respond(500, { error: 'Not set up yet.' });
    try {
      return await route(request, env);
    } catch (err) {
      if (err instanceof BadRequest) return respond(400, { error: err.message });
      console.error(err);
      return respond(500, { error: 'Something went wrong.' });
    }
  },
};
