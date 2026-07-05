const ALLOWED_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

export function isSafeUrl(url: string): boolean {
  try {
    return ALLOWED_PROTOCOLS.has(new URL(url).protocol);
  } catch {
    return false;
  }
}

export function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  return isSafeUrl(trimmed) ? trimmed : null;
}

export function parseOptionalHttpUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return trimmed;
    }
  } catch {
    // ignore invalid URLs
  }
  return null;
}
