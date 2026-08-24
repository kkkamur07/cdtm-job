/**
 * The one line under a member's name, everywhere one is drawn.
 *
 * There used to be a `MemberRow` component here too, for a result list that
 * opened people in a side panel. Ask the network answers that question now with
 * its own row, so only the subtitle is left, and it is a pure function that
 * server and client code both call.
 */
export function memberSubtitle(member: {
    title?: string | null;
    company?: string | null;
    headline?: string | null;
}): string | null {
    if (member.title && member.company) return `${member.title}, ${member.company}`;
    return member.title ?? member.company ?? member.headline ?? null;
}
