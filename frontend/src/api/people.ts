import type { Avatar, Member, NetworkMember } from "./types";

/**
 * Adapters between the two member shapes the API returns.
 *
 * The directory and profile endpoints send a nested `avatar: {sm, lg, blur}`.
 * The network endpoints (saved, intros) and the paths endpoints send the same
 * three values flattened onto the row as `avatar_sm_url` and friends, because
 * those responses are built to be small. Rather than teach every list about
 * both, the lists hand the member here.
 */

type AnyMemberAvatar = {
    avatar?: Avatar | null;
    avatar_sm_url?: string | null;
    avatar_lg_url?: string | null;
    avatar_blur?: string | null;
};

/** The avatar for a member row, whichever of the two shapes it arrived in. */
export function avatarOf(member: AnyMemberAvatar): Avatar | null {
    if (member.avatar) return member.avatar;
    const sm = member.avatar_sm_url ?? member.avatar_lg_url;
    const lg = member.avatar_lg_url ?? member.avatar_sm_url;
    if (!sm || !lg) return null;
    return { sm, lg, blur: member.avatar_blur ?? null };
}

/**
 * A directory member as the network endpoints would have returned it.
 *
 * Saving somebody writes their row into the saved list before the server
 * answers, and that list holds network members. This is the one place that
 * conversion happens, so an optimistic row cannot drift from a real one.
 */
export function toNetworkMember(member: Member): NetworkMember {
    return {
        id: member.id,
        slug: member.slug,
        name: member.name,
        title: member.title ?? null,
        company: member.company ?? null,
        headline: member.headline ?? null,
        class_label: member.class_label ?? null,
        location: member.location ?? null,
        major: member.major ?? null,
        is_ca: member.is_ca ?? false,
        avatar_sm_url: member.avatar?.sm ?? null,
        avatar_lg_url: member.avatar?.lg ?? null,
        avatar_blur: member.avatar?.blur ?? null,
    };
}
