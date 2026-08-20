#!/usr/bin/env node
/**
 * set-password.mjs — writes src/generated/auth.json for the temporary gate.
 *
 *   node scripts/set-password.mjs "correct horse battery staple"
 *
 * Stores a PBKDF2-SHA256 hash with a random salt. The plaintext is never
 * written anywhere and never reaches the browser.
 *
 * NOTE: this file ships to the client, so the hash is public. PBKDF2 at a high
 * iteration count makes guessing slow, not impossible — use a long, random
 * password, and treat Vercel Deployment Protection as the real access control.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const password = process.argv[2];
if (!password || password.length < 12) {
  console.error("usage: node scripts/set-password.mjs \"<password>\"");
  console.error("       (at least 12 characters; longer and random is better)");
  process.exit(1);
}

// OWASP's current floor for PBKDF2-SHA256. Roughly 0.3-0.8s in a browser,
// which is unnoticeable once but expensive across a wordlist.
const ITERATIONS = 600_000;

const salt = crypto.randomBytes(16);
const hash = crypto.pbkdf2Sync(password, salt, ITERATIONS, 32, "sha256");

const out = path.resolve(process.cwd(), "src/generated/auth.json");
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(
  out,
  JSON.stringify(
    {
      algorithm: "PBKDF2-SHA256",
      iterations: ITERATIONS,
      salt: salt.toString("base64"),
      hash: hash.toString("base64"),
    },
    null,
    2
  ) + "\n"
);

console.log(`Wrote ${path.relative(process.cwd(), out)}`);
console.log(`  ${ITERATIONS.toLocaleString()} iterations, 16-byte salt`);
console.log("  The plaintext was not stored. Commit this file.");
