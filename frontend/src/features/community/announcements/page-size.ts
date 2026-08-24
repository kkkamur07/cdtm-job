/**
 * How many announcements the board asks for.
 *
 * The server loader, the client query and the list component all have to agree
 * on this number. The query is keyed by the page size it was fetched with, so a
 * mismatch means the browser refetches the same board under a second key and
 * the server payload it was handed is never used. It lives in a module of its
 * own because `api/server.ts` is `server-only` and the list is a client
 * component; both can import a plain constant.
 */
export const ANNOUNCEMENTS_PAGE = 50;
