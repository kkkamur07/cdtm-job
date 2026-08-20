#!/usr/bin/env node
/**
 * ingest.mjs — turns a flat folder of scraped LinkedIn JSON files plus four
 * roster CSVs into the static artifacts the Next.js app reads.
 *
 * Expected input layout:
 *
 *   data/
 *     profiles/            all LinkedIn JSON files, flat, no subfolders
 *     people.csv           id, name, student[], center_assistant[]
 *     classes.csv          id, season, year, location, students[]
 *     students.csv         id, person, image, class, major
 *     cas.csv              id, person, alumni, image, about, responsibilities,
 *                          research_fields, alternative_email
 *     overrides.csv        (optional) linkedin_id, person_id
 *
 * Joins:
 *   students.id  === the enrollment ids inside people.student[]
 *   cas.id       === the ids inside people.center_assistant[]
 *   students.person / cas.person === people.id
 *   students.class === classes.id   (classes.csv supplies season/year/location)
 *
 * LinkedIn JSON is joined to a roster row BY NAME — no LinkedIn id exists in
 * the CSVs. Failures are reported in unmatched.json and can be pinned with
 * overrides.csv.
 *
 * Avatars come from the CDTM CMS (stable URLs, no expiry), NOT from LinkedIn,
 * whose photoUrl/logo links are signed and expire within weeks. Company and
 * school logos are not downloaded at all — the UI shows names as text.
 *
 * Output:
 *   public/data/index.json        tile data, one small record per member
 *                                 (in public/, not src/, so the app fetches it
 *                                 after sign-in instead of bundling it; under
 *                                 data/ because a bare public/index.json
 *                                 collides with the root route's own output)
 *   src/generated/unmatched.json  join diagnostics
 *   public/profiles/<id>.json     full profile, fetched on modal open
 *   public/avatars/<id>-sm.webp   160px, for grid tiles
 *   public/avatars/<id>.webp      400px, for the modal
 *
 * Usage:
 *   node scripts/ingest.mjs
 *   node scripts/ingest.mjs --limit 5 --skip-images
 *
 * Run from the project root. Requires Node 18+ and `sharp` (npm i -D sharp).
 */

import fs from 'node:fs/promises';
import path from 'node:path';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const args = process.argv.slice(2);
const flag = (name) => args.includes(`--${name}`);
const value = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i !== -1 && args[i + 1] ? args[i + 1] : fallback;
};

const ROOT = process.cwd();
const DATA_DIR = path.resolve(ROOT, value('data', 'data/profiles'));
const PEOPLE_CSV = path.resolve(ROOT, value('people', 'data/people.csv'));
const CLASSES_CSV = path.resolve(ROOT, value('classes', 'data/classes.csv'));
const STUDENTS_CSV = path.resolve(ROOT, value('students', 'data/students.csv'));
const CAS_CSV = path.resolve(ROOT, value('cas', 'data/cas.csv'));
const OVERRIDES_CSV = path.resolve(ROOT, value('overrides', 'data/overrides.csv'));

const INDEX_FILE = path.resolve(ROOT, 'public/data/index.json');
const UNMATCHED_FILE = path.resolve(ROOT, 'src/generated/unmatched.json');
const REVIEW_FILE = path.resolve(ROOT, 'src/generated/review.csv');
const PROFILES_DIR = path.resolve(ROOT, 'public/profiles');
const AVATARS_DIR = path.resolve(ROOT, 'public/avatars');

const SKIP_IMAGES = flag('skip-images');
const LIMIT = Number(value('limit', 0)) || 0;
const CONCURRENCY = 10;

/** CMS asset base. These URLs are unsigned and do not expire. */
const CMS_BASE = 'https://cms.cdtm.com/assets';

/**
 * Two renditions per person. `sm` is what the grid loads; `lg` is fetched only
 * when a modal opens.
 *
 * `sm` is 360px because the tile photo renders at roughly 190px, and anything
 * under ~2x that visibly softens on a retina display. At q72 a real portrait
 * lands around 8-10 KB, so a full 1000-member grid is well under 10 MB.
 */
const AVATAR_RENDITIONS = [
  { key: 'sm', suffix: '-sm', px: 360, quality: 72 },
  { key: 'lg', suffix: '', px: 400, quality: 80 },
];

/**
 * Nine people have both a student and a CA photo. 'student' uses the class
 * photo; flip to 'ca' to prefer the staff portrait.
 */
const AVATAR_PREFERENCE = 'student';

/**
 * Size of the inline placeholder baked into index.json as a data URI.
 *
 * Filtering the grid swaps in members whose photo has never loaded, and a
 * lazy 360px WebP over a slow link leaves the tile visibly empty first. This
 * costs no request at all, so something is on screen the instant the tile
 * mounts and the real photo resolves on top of it.
 *
 * 32px rather than 16px: at these sizes the WebP header dominates, so the
 * larger placeholder costs ~47KB more across the whole roster while looking
 * close enough to the real photo that catching a glimpse of it on a slow
 * connection reads as the image sharpening, not as a different image.
 */
const BLUR_PX = 32;
const BLUR_QUALITY = 50;

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

const clean = (v) => {
  if (typeof v !== 'string') return v ?? null;
  const t = v.trim();
  return t.length ? t : null;
};

const arr = (v) => (Array.isArray(v) ? v : []);

const deaccent = (s) =>
  String(s || '')
    .replace(/ß/g, 'ss').replace(/ø/gi, 'o')
    .replace(/đ/gi, 'd').replace(/ł/gi, 'l')
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '');

const safeId = (s) => String(s).replace(/[^a-zA-Z0-9._-]/g, '_');

const TITLE_RE = new RegExp(
  String.raw`\b(prof|dr|ph\.?\s?d|dipl|ing|rer|nat|pol|oec|med|habil|h\.?\s?c` +
  String.raw`|mba|m\.?\s?sc|b\.?\s?sc|msc|bsc|mag|emeritus)\b\.?`,
  'gi'
);

function nameKey(s) {
  return deaccent(s).toLowerCase()
    .replace(TITLE_RE, ' ')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const nameKeyTight = (s) => nameKey(s).replace(/\s/g, '');

/**
 * Collapses German digraph transliterations so "Goerres" and "Görres" — or
 * "Doerr" and "Dörr" — land on the same key. Measured against this roster it
 * introduces zero new collisions, because deaccent has already run.
 */
const foldKey = (s) => nameKey(s).replace(/oe/g, 'o').replace(/ue/g, 'u').replace(/ae/g, 'a');

/**
 * Alternate readings of a name. Each is keyed independently, and a match is
 * only accepted when every variant together points at exactly one roster row.
 */
function nameVariants(raw) {
  const out = new Set();
  const base = String(raw || '').trim();
  if (!base) return [];
  out.add(base);

  // "Anna (Antje) Seider" -> "Anna Seider" and "Antje Seider".
  // The parenthetical is often the name the roster actually uses.
  const paren = base.match(/^(.*?)\s*\(([^)]+)\)\s*(.*)$/);
  if (paren) {
    out.add(`${paren[1]} ${paren[3]}`.trim());
    out.add(`${paren[2]} ${paren[3]}`.trim());
  }

  for (const v of [...out]) {
    const t = nameKey(v).split(' ').filter(Boolean);
    // Drop middle names and initials: "Agustin N. Coppari Hollmann".
    if (t.length > 2) out.add(`${t[0]} ${t[t.length - 1]}`);
    // Married / double-barrelled surnames: "Haslbeck-Zumkeller" -> each half.
    const hy = v.match(/^(.*?)\s+(\S+)-(\S+)$/);
    if (hy) { out.add(`${hy[1]} ${hy[2]}`); out.add(`${hy[1]} ${hy[3]}`); }
  }
  return [...out].filter(Boolean);
}

/** LinkedIn's privacy truncation: "Ahmed R." -> { first: 'ahmed', initial: 'r' } */
function truncatedName(raw) {
  const m = nameKey(raw).match(/^(\S+)\s+([a-z])$/);
  return m ? { first: m[1], initial: m[2] } : null;
}

/** Match methods, ordered most to least trustworthy. */
const MATCH_METHODS = [
  'override', 'exact', 'variant', 'fold', 'truncated-surname', 'firstname-prefix',
  'claim-elimination', 'ranked', 'arbitrary',
];

/** Anything below this needs a human to sign off before you trust it. */
const REVIEW_BELOW = 'fold';

/**
 * Richness score, used to break a tie between roster rows that no other
 * signal can separate. A row with a photo beats one without.
 */
function candidateScore(p) {
  let s = 0;
  if (p.imageId) s += 4;
  if (p.classes.length) s += 2;
  if (!p.roles.includes('faculty')) s += 1;
  return s;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

let regionNames = null;
try { regionNames = new Intl.DisplayNames(['en'], { type: 'region' }); } catch {}

function formatLocation(city, country) {
  const c = clean(city);
  let k = clean(country);
  if (k && /^[A-Z]{2}$/.test(k) && regionNames) {
    try { k = regionNames.of(k) || k; } catch {}
  }
  const parts = [c, k].filter(Boolean);
  return parts.length ? parts.join(', ') : null;
}

function isoish(d) {
  if (!d || !d.year) return null;
  return d.month ? `${d.year}-${String(d.month).padStart(2, '0')}` : String(d.year);
}

function formatMonthRange(range) {
  const one = (d) => {
    if (!d || !d.year) return null;
    return d.month ? `${MONTHS[d.month - 1]} ${d.year}` : String(d.year);
  };
  const from = one(range?.start);
  const to = one(range?.end);
  if (!from && !to) return null;
  if (!from) return to;
  return `${from} – ${to || 'Present'}`;
}

function formatYearRange(range) {
  const from = range?.start?.year || null;
  const to = range?.end?.year || null;
  if (!from && !to) return null;
  if (from && to) return from === to ? String(from) : `${from} – ${to}`;
  return String(from || to);
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 ** 2).toFixed(1)} MB`;
}

async function pool(items, limit, worker) {
  const queue = [...items];
  const results = [];
  const runners = Array.from(
    { length: Math.min(limit, queue.length) },
    async () => { while (queue.length) results.push(await worker(queue.shift())); }
  );
  await Promise.all(runners);
  return results;
}

// ---------------------------------------------------------------------------
// Phase 0 — roster
// ---------------------------------------------------------------------------

/**
 * Minimal RFC-4180 parser. Needed because cells hold JSON arrays and CA bios
 * with embedded newlines and doubled quotes.
 */
function parseCsv(text) {
  const rows = [];
  let row = [], field = '', inQuotes = false;
  const src = text.replace(/^\uFEFF/, '');

  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (inQuotes) {
      if (ch === '"') {
        if (src[i + 1] === '"') { field += '"'; i++; } else inQuotes = false;
      } else field += ch;
      continue;
    }
    if (ch === '"') inQuotes = true;
    else if (ch === ',') { row.push(field); field = ''; }
    else if (ch === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
    else if (ch !== '\r') field += ch;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }

  const header = rows.shift() || [];
  return rows
    .filter((r) => r.some((c) => c.trim().length))
    .map((r) => Object.fromEntries(header.map((h, i) => [h.trim(), r[i] ?? ''])));
}

function parseIdArray(cell) {
  const t = String(cell || '').trim();
  if (!t || t === '[]') return [];
  try {
    const v = JSON.parse(t);
    return Array.isArray(v) ? v.filter((n) => n !== null && n !== '') : [];
  } catch {
    return t.replace(/[[\]]/g, '').split(',')
      .map((s) => Number(s.trim())).filter(Number.isFinite);
  }
}

/** '["A","B"]' -> ['A','B']; tolerates plain comma-separated text. */
function parseStringArray(cell) {
  const t = String(cell || '').trim();
  if (!t || t === '[]') return [];
  try {
    const v = JSON.parse(t);
    if (Array.isArray(v)) return v.map(clean).filter(Boolean);
  } catch {}
  return t.split(',').map(clean).filter(Boolean);
}

const num = (v) => {
  const n = Number(String(v ?? '').trim());
  return Number.isFinite(n) && String(v ?? '').trim() !== '' ? n : null;
};

const bool = (v) => String(v ?? '').trim().toLowerCase() === 'true';

/** Local rendition paths for a member id. */
function avatarPaths(id) {
  return {
    ...Object.fromEntries(
      AVATAR_RENDITIONS.map((r) => [r.key, `/avatars/${id}${r.suffix}.webp`])
    ),
    // Filled in during phase 4; always present so the shape never varies.
    blur: null,
  };
}

const SEASON_ORDER = { Winter: 0, Spring: 1, Summer: 2, Fall: 3 };
const classLabel = (r) => (r.season ? `${r.season} ${r.year}` : String(r.year));
const classSortKey = (r) => r.year * 10 + (SEASON_ORDER[r.season] ?? 9);

async function readCsv(file, label, required = true) {
  try {
    return parseCsv(await fs.readFile(file, 'utf8'));
  } catch {
    if (required) throw new Error(`${label} CSV not found: ${file}`);
    return [];
  }
}

async function loadRoster() {
  const [peopleRaw, classesRaw, studentsRaw, casRaw, overridesRaw] =
    await Promise.all([
      readCsv(PEOPLE_CSV, 'people'),
      readCsv(CLASSES_CSV, 'classes'),
      readCsv(STUDENTS_CSV, 'students'),
      readCsv(CAS_CSV, 'cas'),
      readCsv(OVERRIDES_CSV, 'overrides', false),
    ]);

  // --- classes -------------------------------------------------------------
  const classById = new Map();
  const allClasses = [];
  for (const r of classesRaw) {
    const meta = {
      id: num(r.id),
      label: classLabel({ season: clean(r.season), year: num(r.year) }),
      season: clean(r.season),
      year: num(r.year),
      location: num(r.location),
    };
    classById.set(meta.id, meta);
    allClasses.push({ ...meta, sortKey: classSortKey(meta) });
  }
  allClasses.sort((a, b) => b.sortKey - a.sortKey);

  // --- students ------------------------------------------------------------
  const studentByPerson = new Map();
  const orphanEnrollments = [];
  for (const r of studentsRaw) {
    const personId = num(r.person);
    const classId = num(r.class);
    const cls = classId !== null ? classById.get(classId) : null;
    if (!cls) {
      orphanEnrollments.push({ enrollmentId: num(r.id), personId, classId });
    }
    studentByPerson.set(personId, {
      enrollmentId: num(r.id),
      class: cls ?? null,
      major: clean(r.major),
      image: clean(r.image),
    });
  }

  // --- CAs -----------------------------------------------------------------
  const caByPerson = new Map();
  for (const r of casRaw) {
    caByPerson.set(num(r.person), {
      caId: num(r.id),
      alumni: bool(r.alumni),
      image: clean(r.image),
      about: clean(r.about),
      responsibilities: parseStringArray(r.responsibilities),
      researchFields: parseStringArray(r.research_fields),
      email: clean(r.alternative_email),
    });
  }

  // --- people --------------------------------------------------------------
  let people = peopleRaw.map((r) => {
    const personId = num(r.id);
    const student = studentByPerson.get(personId) ?? null;
    const ca = caByPerson.get(personId) ?? null;

    // people.csv's arrays are the authority on membership; the detail CSVs
    // supply attributes. Trusting the arrays means a missing detail row can
    // never silently erase someone's role.
    const isStudent = parseIdArray(r.student).length > 0 || Boolean(student);
    const isCA = parseIdArray(r.center_assistant).length > 0 || Boolean(ca);

    const roles = [];
    if (isStudent) roles.push('student');
    if (isCA) roles.push('ca');
    if (!roles.length) roles.push('faculty');

    const preference = AVATAR_PREFERENCE === 'ca'
      ? [ca?.image, student?.image]
      : [student?.image, ca?.image];

    return {
      personId,
      rosterName: clean(r.name) || '',
      classes: student?.class ? [student.class] : [],
      major: student?.major ?? null,
      roles,
      isCA,
      caAlumni: ca ? ca.alumni : null,
      ca: ca
        ? {
            alumni: ca.alumni,
            about: ca.about,
            responsibilities: ca.responsibilities,
            researchFields: ca.researchFields,
            email: ca.email,
          }
        : null,
      imageId: preference.find(Boolean) ?? null,
    };
  });

  // --- shell rows ----------------------------------------------------------
  // Some names appear twice: one row carries the enrollment/CA ids, its twin
  // carries empty arrays. The empty one is a duplicate record, not a second
  // person, and dropping it removes every true name collision in the roster.
  // A lone row with empty arrays is faculty and is kept.
  const nameGroups = new Map();
  for (const p of people) {
    const k = nameKey(p.rosterName);
    if (!k) continue;
    if (!nameGroups.has(k)) nameGroups.set(k, []);
    nameGroups.get(k).push(p);
  }

  const shells = [];
  for (const group of nameGroups.values()) {
    if (group.length < 2) continue;
    const real = group.filter((p) => !p.roles.includes('faculty'));
    if (!real.length || real.length === group.length) continue;
    for (const p of group) {
      if (p.roles.includes('faculty')) shells.push({ personId: p.personId, name: p.rosterName });
    }
  }
  const shellIds = new Set(shells.map((s) => s.personId));
  people = people.filter((p) => !shellIds.has(p.personId));

  // --- lookups -------------------------------------------------------------
  const byId = new Map(people.map((p) => [p.personId, p]));
  const byName = new Map();
  const byTightName = new Map();
  const byFold = new Map();
  const byFirstName = new Map();

  for (const p of people) {
    const tokens = nameKey(p.rosterName).split(' ').filter(Boolean);
    for (const [map, key] of [
      [byName, nameKey(p.rosterName)],
      [byTightName, nameKeyTight(p.rosterName)],
      [byFold, foldKey(p.rosterName)],
      [byFirstName, tokens[0]],
    ]) {
      if (!key) continue;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(p);
    }
    p.surnameKey = tokens.length > 1 ? foldKey(tokens[tokens.length - 1]) : null;
    // Every token after the given name. A truncated "Philipp R." must be able
    // to reach "Rösch-Schlanderer", whose final token starts with S.
    p.surnameKeys = tokens.slice(1).map(foldKey);
    p.firstNameKey = tokens[0] ?? null;
  }

  const overrides = new Map();
  for (const row of overridesRaw) {
    const lid = clean(row.linkedin_id);
    const pid = num(row.person_id);
    if (lid && pid !== null) overrides.set(safeId(lid), pid);
  }

  return {
    people, byId, byName, byTightName, byFold, byFirstName,
    overrides, orphanEnrollments, shells,
    allClasses: allClasses.map(({ sortKey, ...rest }) => rest),
  };
}

const ambiguous = (label, hits, fullName) => ({
  person: null,
  reason: `ambiguous via ${label} — ${hits.length} roster rows match "${fullName}" ` +
          `(person_ids ${hits.map((p) => p.personId).join(', ')})`,
  candidates: hits,          // full roster rows; later passes score them
});

/**
 * Tiered match. Each tier is tried in turn and only accepted when it yields
 * exactly one roster row; more than one stops the search rather than guessing,
 * because a wrong match silently puts the wrong class on someone's tile.
 */
function matchPerson(roster, linkedInId, fullName) {
  const forced = roster.overrides.get(linkedInId);
  if (forced !== undefined) {
    const p = roster.byId.get(forced);
    return p
      ? { person: p, method: 'override' }
      : { person: null, reason: `override points at unknown person_id ${forced}` };
  }
  if (!clean(fullName)) return { person: null, reason: 'profile has no name' };

  const variants = nameVariants(fullName);

  /** Collect distinct roster rows across every variant for one key function. */
  const gather = (keyFn, map) => {
    const hits = new Map();
    for (const v of variants) {
      for (const p of map.get(keyFn(v)) || []) hits.set(p.personId, p);
    }
    return [...hits.values()];
  };

  // Tier 1 — exact, on the name as written.
  const exact = roster.byName.get(nameKey(fullName)) ?? [];
  if (exact.length === 1) return { person: exact[0], method: 'exact' };
  if (exact.length > 1) return ambiguous('exact name', exact, fullName);

  // Tier 2 — variants: parentheticals, dropped middle names, split surnames.
  const viaVariant = gather(nameKey, roster.byName);
  if (viaVariant.length === 1) return { person: viaVariant[0], method: 'variant' };
  if (viaVariant.length > 1) return ambiguous('name variant', viaVariant, fullName);

  // Tier 3 — German transliteration fold (Goerres/Görres), plus tight keys.
  const viaFold = gather(foldKey, roster.byFold);
  if (viaFold.length === 1) return { person: viaFold[0], method: 'fold' };
  if (viaFold.length > 1) return ambiguous('transliteration fold', viaFold, fullName);

  const tight = roster.byTightName.get(nameKeyTight(fullName)) ?? [];
  if (tight.length === 1) return { person: tight[0], method: 'fold' };

  // Tier 4 — LinkedIn privacy truncation: "Ahmed R." -> unique Ahmed R*.
  const trunc = truncatedName(fullName);
  if (trunc) {
    const hits = (roster.byFirstName.get(trunc.first) ?? [])
      .filter((p) => (p.surnameKeys ?? []).some((k) => k.startsWith(trunc.initial)));
    if (hits.length === 1) return { person: hits[0], method: 'truncated-surname' };
    if (hits.length > 1) return ambiguous('truncated surname', hits, fullName);
  }

  // Tier 5 — short forms: "Alex Popp" -> "Alexander Popp". Surname must match
  // exactly under fold; the given name may be a prefix in either direction.
  const tokens = nameKey(fullName).split(' ').filter(Boolean);
  if (tokens.length >= 2) {
    const first = tokens[0];
    const surname = foldKey(tokens[tokens.length - 1]);
    const hits = roster.people.filter((p) => {
      if (!p.surnameKey || p.surnameKey !== surname) return false;
      const rf = p.firstNameKey ?? '';
      return (rf.startsWith(first) || first.startsWith(rf))
        && Math.min(rf.length, first.length) >= 3;
    });
    if (hits.length === 1) return { person: hits[0], method: 'firstname-prefix' };
    if (hits.length > 1) return ambiguous('first-name prefix', hits, fullName);
  }

  return { person: null, reason: 'no roster row with this name' };
}

/**
 * Second and third resolution passes, run once every profile has had a first
 * attempt.
 *
 * Elimination: "Erik M." has two candidates, but if another profile already
 * matched Erik Muttersbach exactly, only Erik Mahler is still free — so the
 * ambiguity resolves itself. This runs to a fixpoint because each resolution
 * can free up the next.
 *
 * Ranking: whatever is still contested is settled by candidateScore, and if
 * that ties too, by lowest personId. Deterministic rather than left for a
 * human, but tagged so it shows up in review.csv.
 */
function resolveContested(attempts, claimedBy) {
  const stats = { 'claim-elimination': 0, ranked: 0, arbitrary: 0, exhausted: 0 };

  const contested = () => attempts.filter(
    (a) => !a.match.person && a.match.candidates?.length
  );

  let progress = true;
  while (progress) {
    progress = false;
    for (const a of contested()) {
      const free = a.match.candidates.filter((c) => !claimedBy.has(c.personId));
      if (free.length !== 1) continue;
      a.match = {
        person: free[0], method: 'claim-elimination',
        priorReason: a.match.reason, candidates: a.match.candidates,
      };
      claimedBy.set(free[0].personId, a);
      stats['claim-elimination']++;
      progress = true;
    }
  }

  for (const a of contested()) {
    const free = a.match.candidates.filter((c) => !claimedBy.has(c.personId));
    if (!free.length) {
      a.match = {
        person: null,
        reason: `${a.match.reason} — and every candidate is already claimed`,
        candidates: a.match.candidates,
      };
      stats.exhausted++;
      continue;
    }

    const scored = free
      .map((p) => ({ p, score: candidateScore(p) }))
      .sort((x, y) => y.score - x.score || x.p.personId - y.p.personId);

    const method = scored.length === 1 || scored[1].score < scored[0].score
      ? 'ranked' : 'arbitrary';

    a.match = {
      person: scored[0].p, method,
      priorReason: a.match.reason, candidates: a.match.candidates,
    };
    claimedBy.set(scored[0].p.personId, a);
    stats[method]++;
  }

  return stats;
}

// ---------------------------------------------------------------------------
// Phase 1 — wipe
// ---------------------------------------------------------------------------

async function wipe() {
  for (const dir of [PROFILES_DIR, AVATARS_DIR]) {
    if (!dir.startsWith(ROOT + path.sep)) {
      throw new Error(`Refusing to delete outside project root: ${dir}`);
    }
    await fs.rm(dir, { recursive: true, force: true });
    await fs.mkdir(dir, { recursive: true });
  }
  await fs.rm(INDEX_FILE, { force: true });
  await fs.mkdir(path.dirname(INDEX_FILE), { recursive: true });
  await fs.rm(UNMATCHED_FILE, { force: true });
  await fs.rm(REVIEW_FILE, { force: true });
  await fs.mkdir(path.dirname(INDEX_FILE), { recursive: true });
}

// ---------------------------------------------------------------------------
// Phase 2 — walk and parse
// ---------------------------------------------------------------------------

async function walk() {
  let files;
  try {
    files = (await fs.readdir(DATA_DIR))
      .filter((f) => f.toLowerCase().endsWith('.json')).sort();
  } catch {
    throw new Error(`Profile folder not found: ${DATA_DIR}`);
  }
  if (!files.length) throw new Error(`No .json files in ${DATA_DIR}`);
  if (LIMIT) files = files.slice(0, LIMIT);

  const parsed = [], failures = [];
  for (const file of files) {
    const full = path.join(DATA_DIR, file);
    try {
      parsed.push({
        raw: JSON.parse(await fs.readFile(full, 'utf8')),
        file: path.relative(ROOT, full),
      });
    } catch (err) {
      failures.push({ file: path.relative(ROOT, full), error: err.message });
    }
  }
  return { parsed, failures, total: files.length };
}

// ---------------------------------------------------------------------------
// Phase 3 — normalize
// ---------------------------------------------------------------------------

/** member id -> CMS image uuid, for people who made it into the output. */
const avatarTasks = new Map();

function normalizePositions(person) {
  const list = arr(person?.positions?.positionHistory).map((p) => ({
    title: clean(p.title),
    company: clean(p.companyName),
    companyUrl: clean(p.linkedInUrl),
    description: clean(p.description),
    location: clean(p.companyLocation),
    start: isoish(p.startEndDate?.start),
    end: isoish(p.startEndDate?.end),
    dateRange: formatMonthRange(p.startEndDate),
    current: !p.startEndDate?.end?.year,
  }));

  list.sort((a, b) => {
    if (a.current !== b.current) return a.current ? -1 : 1;
    return String(b.start || '').localeCompare(String(a.start || ''));
  });
  return list;
}

function normalizeSchools(person) {
  return arr(person?.schools?.educationHistory).map((s) => {
    const degree = clean(s.degreeName);
    const field = clean(s.fieldOfStudy);
    return {
      school: clean(s.schoolName),
      degree: degree && field && !degree.includes(field)
        ? `${degree}, ${field}` : degree || field,
      dateRange: formatYearRange(s.startEndDate),
    };
  });
}

function normalizeLanguages(person) {
  const withProf = arr(person?.languagesWithProficiency);
  const source = withProf.length ? withProf : arr(person?.languages);
  return source
    .map((l) => clean(typeof l === 'string' ? l : l?.language || l?.name))
    .filter(Boolean);
}

function normalizeCompany(company) {
  if (!company || !clean(company.name)) return null;
  const hq = company.headquarter || arr(company.locations)[0] || {};
  return {
    name: clean(company.name),
    tagline: clean(company.tagline),
    description: clean(company.description),
    industry: clean(company.industry),
    website: clean(company.websiteUrl),
    linkedInUrl: clean(company.linkedInUrl),
    employeeCount: company.employeeCount ?? null,
    foundedYear: company.foundedOn?.year ?? null,
    location: formatLocation(hq.city, hq.country),
    specialities: arr(company.specialities).map(clean).filter(Boolean),
  };
}

function normalize(raw, match) {
  const person = raw?.person;
  if (!person) throw new Error('missing "person" object');

  const id = safeId(
    clean(person.publicIdentifier) || clean(person.linkedInIdentifier)
    || clean(person.memberIdentifier) || ''
  );
  if (!id) throw new Error('missing publicIdentifier');

  const firstName = clean(person.firstName);
  const lastName = clean(person.lastName);
  const name = [firstName, lastName].filter(Boolean).join(' ') || id;

  const roster = match.person;

  // Avatars come from the CMS only. person.photoUrl is a signed LinkedIn URL
  // that expires within weeks of the scrape and is deliberately ignored.
  let avatar = null;
  if (roster?.imageId) {
    avatarTasks.set(id, roster.imageId);
    avatar = avatarPaths(id);
  }

  const positions = normalizePositions(person);
  const cp = person.currentPosition;
  const current = clean(cp?.companyName) ? cp : positions.find((p) => p.current) || null;

  const shared = {
    id,
    name,
    headline: clean(person.headline),
    avatar,
    location: formatLocation(
      person.location?.city,
      person.location?.country || person.location?.countryCode
    ),
    linkedInUrl: clean(person.linkedInUrl),
    personId: roster?.personId ?? null,
    classes: roster?.classes ?? [],
    classLabel: roster?.classes?.[0]?.label ?? null,
    major: roster?.major ?? null,
    roles: roster?.roles ?? [],
    isCA: roster?.isCA ?? false,
    caAlumni: roster?.caAlumni ?? null,
    matched: Boolean(roster),
    matchMethod: match.method ?? null,
    needsReview: Boolean(roster)
      && MATCH_METHODS.indexOf(match.method) > MATCH_METHODS.indexOf(REVIEW_BELOW),
  };

  return {
    index: {
      ...shared,
      firstName,
      lastName,
      company: clean(current?.companyName ?? current?.company) || null,
      title: clean(current?.title) || null,
    },
    profile: {
      ...shared,
      rosterName: roster?.rosterName ?? null,
      ca: roster?.ca ?? null,
      summary: clean(person.summary),
      positions,
      schools: normalizeSchools(person),
      skills: arr(person.skills).map(clean).filter(Boolean),
      languages: normalizeLanguages(person),
      company: normalizeCompany(raw.company),
    },
  };
}

// ---------------------------------------------------------------------------
// Phase 4 — avatars
// ---------------------------------------------------------------------------

async function loadSharp() {
  try {
    return (await import('sharp')).default;
  } catch {
    throw new Error(
      'sharp is required to resize avatars. Run: npm i -D sharp\n' +
      '(or pass --skip-images to generate JSON only)'
    );
  }
}

async function downloadAvatars() {
  const sharp = await loadSharp();
  const tasks = [...avatarTasks.entries()].map(([id, imageId]) => ({ id, imageId }));
  const failures = [];
  const blurs = new Map();
  let bytes = 0;
  let blurBytes = 0;

  await pool(tasks, CONCURRENCY, async ({ id, imageId }) => {
    const url = `${CMS_BASE}/${imageId}.jpg`;
    try {
      const res = await fetch(url, {
        signal: AbortSignal.timeout(20000),
        headers: { 'user-agent': 'Mozilla/5.0 (ingest script)' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const buf = Buffer.from(await res.arrayBuffer());
      if (!buf.length) throw new Error('empty response');

      for (const r of AVATAR_RENDITIONS) {
        const out = await sharp(buf)
          .rotate()                                    // honour EXIF orientation
          .resize(r.px, r.px, { fit: 'cover', position: 'attention' })
          .webp({ quality: r.quality })
          .toBuffer();
        await fs.writeFile(path.join(AVATARS_DIR, `${id}${r.suffix}.webp`), out);
        bytes += out.length;
      }

      // Inline placeholder — never written to disk, it ships inside index.json.
      const tiny = await sharp(buf)
        .rotate()
        .resize(BLUR_PX, BLUR_PX, { fit: 'cover', position: 'attention' })
        .webp({ quality: BLUR_QUALITY })
        .toBuffer();
      const uri = `data:image/webp;base64,${tiny.toString('base64')}`;
      blurs.set(id, uri);
      blurBytes += uri.length;
    } catch (err) {
      failures.push({ id, imageId, url, error: err.message });
    }
  });

  return { total: tasks.length, failures, bytes, blurs, blurBytes };
}

/** Blank out avatars whose download failed so the UI falls back to initials. */
function pruneMissingAvatars(records, failedIds) {
  for (const rec of records) {
    if (rec.avatar && failedIds.has(rec.id)) rec.avatar = null;
  }
}

/** Attach the inline placeholder produced during download. */
function attachBlurs(records, blurs) {
  for (const rec of records) {
    if (rec.avatar) rec.avatar.blur = blurs.get(rec.id) ?? null;
  }
}

// ---------------------------------------------------------------------------
// Phase 5 — write
// ---------------------------------------------------------------------------

async function writeOutput(members, profiles, roster, diagnostics, reviewRows) {
  const populated = new Set(members.flatMap((m) => m.classes.map((c) => c.id)));

  // Display order is decided here, not in the browser: the grid's filter
  // preserves array order, so sorting once at build time costs the client
  // nothing. Photos first (a wall of initials at the top reads as broken),
  // then newest class, then surname.
  const orderKey = (m) => {
    const c = m.classes[0];
    return c ? c.year * 10 + (SEASON_ORDER[c.season] ?? 9) : -1;
  };

  const index = {
    generatedAt: new Date().toISOString(),
    counts: {
      members: members.length,
      matched: members.filter((m) => m.matched).length,
      withAvatar: members.filter((m) => m.avatar).length,
      ca: members.filter((m) => m.isCA).length,
      rosterRows: roster.people.length,
    },
    classes: roster.allClasses.filter((c) => populated.has(c.id)),
    majors: [...new Set(members.map((m) => m.major).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b)),
    members: members.sort((a, b) => {
      if (Boolean(a.avatar) !== Boolean(b.avatar)) return a.avatar ? -1 : 1;
      const byClass = orderKey(b) - orderKey(a);
      if (byClass) return byClass;
      return (a.lastName || a.name).localeCompare(b.lastName || b.name, 'de');
    }),
  };

  const indexJson = JSON.stringify(index, null, 2);
  await fs.writeFile(INDEX_FILE, indexJson);
  await fs.writeFile(UNMATCHED_FILE, JSON.stringify(diagnostics, null, 2));

  // review.csv is shaped exactly like overrides.csv, with the audit columns
  // commented out by a leading '#'. Delete the wrong rows, drop the rest into
  // data/overrides.csv, and the next run pins them.
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const reviewCsv = [
    'linkedin_id,person_id,#method,#linkedin_name,#roster_name',
    ...reviewRows
      .sort((a, b) => a.method.localeCompare(b.method) || a.name.localeCompare(b.name))
      .map((r) => [r.linkedInId, r.personId, r.method, r.name, r.rosterName].map(esc).join(',')),
  ].join('\n');
  await fs.writeFile(REVIEW_FILE, reviewCsv + '\n');

  let profileBytes = 0;
  for (const profile of profiles) {
    const json = JSON.stringify(profile, null, 2);
    profileBytes += Buffer.byteLength(json);
    await fs.writeFile(path.join(PROFILES_DIR, `${profile.id}.json`), json);
  }

  return { indexBytes: Buffer.byteLength(indexJson), profileBytes };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const started = Date.now();
  console.log('Ingesting…\n');

  await wipe();

  const roster = await loadRoster();
  const students = roster.people.filter((p) => p.roles.includes('student')).length;
  const cas = roster.people.filter((p) => p.isCA).length;
  const withImage = roster.people.filter((p) => p.imageId).length;
  console.log(
    `Roster:      ${roster.people.length} people, ${roster.allClasses.length} classes ` +
    `(${students} students, ${cas} CAs)`
  );
  console.log(`             ${withImage} have a CMS image id`);
  if (roster.shells.length) {
    console.log(
      `             ${roster.shells.length} shell rows dropped ` +
      `(duplicate name, no enrollment): ${roster.shells.map((x) => x.name).join(', ')}`
    );
  }
  if (roster.overrides.size) {
    console.log(`             ${roster.overrides.size} manual overrides loaded`);
  }

  const { parsed, failures: parseFailures, total } = await walk();
  console.log(`Parsed:      ${parsed.length} ok, ${parseFailures.length} failed (of ${total} files)`);

  // --- pass 1: one match attempt per profile -------------------------------
  const attempts = parsed.map(({ raw, file }) => {
    const person = raw?.person;
    const linkedInId = safeId(clean(person?.publicIdentifier) || '');
    const fullName = [clean(person?.firstName), clean(person?.lastName)]
      .filter(Boolean).join(' ');
    return {
      raw, file, linkedInId, fullName,
      match: matchPerson(roster, linkedInId, fullName),
    };
  });

  // --- pass 2/3: elimination against claims, then ranked tiebreak ----------
  const claimedBy = new Map();
  for (const a of attempts) {
    const pid = a.match.person?.personId;
    if (pid !== undefined && !claimedBy.has(pid)) claimedBy.set(pid, a);
  }
  const contestedStats = resolveContested(attempts, claimedBy);

  // --- normalize -----------------------------------------------------------
  const members = [], profiles = [];
  const seen = new Map();
  const normFailures = [], unmatchedProfiles = [], reviewRows = [];
  const matchedPersonIds = new Set();
  const methods = Object.fromEntries(MATCH_METHODS.map((m) => [m, 0]));

  for (const attempt of attempts) {
    const { raw, file, linkedInId, fullName, match } = attempt;
    try {
      if (match.person) {
        methods[match.method] = (methods[match.method] || 0) + 1;
        matchedPersonIds.add(match.person.personId);
        if (MATCH_METHODS.indexOf(match.method) > MATCH_METHODS.indexOf(REVIEW_BELOW)) {
          reviewRows.push({
            linkedInId, name: fullName, method: match.method,
            personId: match.person.personId, rosterName: match.person.rosterName,
          });
        }
      } else {
        unmatchedProfiles.push({
          file, linkedInId, name: fullName, reason: match.reason,
          candidates: (match.candidates ?? []).map((c) => ({
            personId: c.personId, name: c.rosterName,
          })),
        });
        for (const c of match.candidates ?? []) {
          reviewRows.push({
            linkedInId, name: fullName, method: 'UNRESOLVED',
            personId: c.personId, rosterName: c.rosterName,
          });
        }
      }

      const { index, profile } = normalize(raw, match);

      if (seen.has(index.id)) {
        console.warn(`  ! duplicate id "${index.id}" — ${file} overwrites ${seen.get(index.id)}`);
        const i = members.findIndex((m) => m.id === index.id);
        if (i !== -1) { members.splice(i, 1); profiles.splice(i, 1); }
      }
      seen.set(index.id, file);
      members.push(index);
      profiles.push(profile);
    } catch (err) {
      normFailures.push({ file, error: err.message });
    }
  }

  console.log(
    `Matched:     ${members.filter((m) => m.matched).length}/${members.length} to roster`
  );
  for (const m of MATCH_METHODS) {
    if (!methods[m]) continue;
    const risky = MATCH_METHODS.indexOf(m) > MATCH_METHODS.indexOf(REVIEW_BELOW);
    console.log(`               ${String(methods[m]).padStart(4)}  ${m}${risky ? '   <- review' : ''}`);
  }
  const contestedTotal = Object.values(contestedStats).reduce((a, b) => a + b, 0);
  if (contestedTotal) {
    console.log(
      `Contested:   ${contestedStats['claim-elimination']} by elimination, ` +
      `${contestedStats.ranked} by photo/richness, ` +
      `${contestedStats.arbitrary} arbitrary, ${contestedStats.exhausted} exhausted`
    );
  }
  console.log(
    `             ${members.filter((m) => m.isCA).length} CAs, ` +
    `${members.filter((m) => m.classLabel).length} with a class, ` +
    `${members.filter((m) => m.major).length} with a major`
  );

  let imageResult = { total: 0, failures: [], bytes: 0, blurs: new Map(), blurBytes: 0 };
  if (SKIP_IMAGES) {
    console.log(`Avatars:     skipped (--skip-images) — ${avatarTasks.size} would download`);
  } else {
    imageResult = await downloadAvatars();
    const failedIds = new Set(imageResult.failures.map((f) => f.id));
    console.log(
      `Avatars:     ${imageResult.total - failedIds.size} downloaded, ${failedIds.size} failed ` +
      `(${AVATAR_RENDITIONS.length} renditions each)`
    );
    pruneMissingAvatars(members, failedIds);
    pruneMissingAvatars(profiles, failedIds);
    attachBlurs(members, imageResult.blurs);
    attachBlurs(profiles, imageResult.blurs);
    console.log(
      `             ${imageResult.blurs.size} inline ${BLUR_PX}px placeholders ` +
      `(+${formatBytes(imageResult.blurBytes)} in index.json)`
    );
  }

  const withAvatar = members.filter((m) => m.avatar).length;
  console.log(
    `             ${withAvatar}/${members.length} members have a photo ` +
    `(${members.length - withAvatar} fall back to initials)`
  );

  const rosterWithoutProfile = roster.people
    .filter((p) => !matchedPersonIds.has(p.personId))
    .map((p) => ({
      personId: p.personId, name: p.rosterName,
      classLabel: p.classes[0]?.label ?? null, roles: p.roles,
    }));

  const diagnostics = {
    generatedAt: new Date().toISOString(),
    profilesWithoutRosterRow: unmatchedProfiles,
    rosterRowsWithoutProfile: rosterWithoutProfile,
    orphanEnrollments: roster.orphanEnrollments,
    shellRowsDropped: roster.shells,
    parseFailures, normalizeFailures: normFailures,
    avatarFailures: imageResult.failures,
  };

  const { indexBytes, profileBytes } = await writeOutput(members, profiles, roster, diagnostics, reviewRows);

  console.log();
  console.log(`Wrote ${path.relative(ROOT, INDEX_FILE).padEnd(34)} (${members.length} members, ${formatBytes(indexBytes)})`);
  console.log(`Wrote ${(path.relative(ROOT, PROFILES_DIR) + '/').padEnd(34)} (${profiles.length} files, ${formatBytes(profileBytes)})`);
  if (!SKIP_IMAGES) {
    const okFiles = (imageResult.total - imageResult.failures.length) * AVATAR_RENDITIONS.length;
    console.log(`Wrote ${(path.relative(ROOT, AVATARS_DIR) + '/').padEnd(34)} (${okFiles} files, ${formatBytes(imageResult.bytes)})`);
  }
  console.log(`Wrote ${path.relative(ROOT, UNMATCHED_FILE).padEnd(34)} (${unmatchedProfiles.length} unmatched, ${rosterWithoutProfile.length} without profile)`);
  console.log(`Wrote ${path.relative(ROOT, REVIEW_FILE).padEnd(34)} (${reviewRows.length} rows to audit)`);

  const report = (label, list, fmt) => {
    if (!list.length) return;
    console.log(`\n${label}:`);
    list.slice(0, 15).forEach((x) => console.log(`  ${fmt(x)}`));
    if (list.length > 15) console.log(`  … and ${list.length - 15} more (see unmatched.json)`);
  };

  report('Parse failures', parseFailures, (f) => `${f.file}  ${f.error}`);
  report('Normalize failures', normFailures, (f) => `${f.file}  ${f.error}`);
  report('Unmatched profiles', unmatchedProfiles, (u) => `${(u.name || u.linkedInId).padEnd(32)} ${u.reason}`);
  report('Avatar failures', imageResult.failures, (f) => `${f.id}  ${f.error}`);

  console.log(`\nDone in ${((Date.now() - started) / 1000).toFixed(1)}s`);
  if (!members.length) process.exitCode = 1;
}

main().catch((err) => {
  console.error(`\nIngest failed: ${err.message}`);
  process.exitCode = 1;
});
