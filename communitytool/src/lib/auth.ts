"use client";

import config from "@/generated/auth.json";

/**
 * Temporary password gate, standing in until Google SSO is wired up.
 *
 * IMPORTANT: this is a UX gate, not a security boundary. The site is a static
 * export, so /index.json, /profiles/*.json and every avatar are fetchable
 * directly regardless of what this returns. Real access control belongs at the
 * edge — Vercel Deployment Protection — or in a Google SSO flow that gates a
 * server. Treat this as "keeps the URL from being self-serve", nothing more.
 *
 * The hash below is public by necessity. PBKDF2 at 600k iterations makes an
 * offline guess slow; it does not make a weak password safe.
 */

const SESSION_KEY = "cdtm-community-auth";

/** Returns a Uint8Array backed by a plain ArrayBuffer, which is what the
 *  WebCrypto types require (a generic Uint8Array may sit on a SharedArrayBuffer). */
function fromBase64(value: string): Uint8Array<ArrayBuffer> {
  const binary = atob(value);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/** Length-independent compare, so timing gives nothing away. */
function equal(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

export async function verifyPassword(password: string): Promise<boolean> {
  if (!password) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"]
  );

  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      salt: fromBase64(config.salt),
      iterations: config.iterations,
      hash: "SHA-256",
    },
    key,
    256
  );

  return equal(new Uint8Array(bits), fromBase64(config.hash));
}

/** Survives a refresh but not a new tab session. */
export function rememberSession(): void {
  try {
    sessionStorage.setItem(SESSION_KEY, "1");
  } catch {
    // Private mode or storage disabled — the user just signs in again.
  }
}

export function hasSession(): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) === "1";
  } catch {
    return false;
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    /* nothing to do */
  }
}
