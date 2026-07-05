/** Resolve company logo URLs for the browser (same-origin dev assets). */
export function companyLogoSrc(logoUrl: string | null | undefined): string | null {
  if (!logoUrl) return null;
  if (logoUrl.startsWith("/")) return logoUrl;
  try {
    const url = new URL(logoUrl);
    if (url.hostname === "localhost" || url.hostname === "127.0.0.1") {
      return `${url.pathname}${url.search}`;
    }
  } catch {
    return null;
  }
  return logoUrl;
}
