import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiError } from "@/api/errors";
import { loadMember, loadMemberPath } from "@/api/server";
import { getIdentity } from "@/auth/session";
import MemberGate, { gatedData } from "@/components/MemberGate";
import MemberProfileView from "@/features/community/members/MemberProfileView";
import { memberSubtitle } from "@/features/community/members/MemberRow";

type Params = { params: Promise<{ slug: string }> };

/**
 * `loadMember` is wrapped in `React.cache`, so naming the member in the title
 * costs the same one request the page below already makes. For a signed-out
 * visitor there is no request at all: the directory is members-only, so the
 * call could only come back 401 and the generic title is the answer either way.
 */
export async function generateMetadata({ params }: Params) {
    const { slug } = await params;
    const { accessToken } = await getIdentity();
    if (!accessToken) return { title: "Member · CDTM Community" };

    try {
        const member = await loadMember(slug);
        return {
            title: `${member.name} · CDTM Community`,
            description:
                memberSubtitle(member) ??
                `${member.name} in the CDTM community directory.`,
        };
    } catch {
        // Signed out, or no such member. The page itself says which.
        return { title: "Member · CDTM Community" };
    }
}

export default async function MemberPage({ params }: Params) {
    const { slug } = await params;

    // Awaiting the route params costs nothing; awaiting the gate would. The
    // reads are started here so they run alongside the gate's own /auth/me
    // rather than a round trip behind it.
    const data = gatedData(() => loadProfile(slug));

    return (
        <MemberGate next={`/members/${slug}`}>
            <Profile data={data} />
        </MemberGate>
    );
}

/**
 * The profile and the path are independent reads, so they go out together. A
 * missing path is normal (it is derived, and not every member has one), a
 * missing profile is a 404.
 */
function loadProfile(slug: string) {
    return Promise.all([
        loadMember(slug).catch((error) => {
            if (error instanceof ApiError && error.isNotFound) return null;
            throw error;
        }),
        loadMemberPath(slug).catch(() => null),
    ]);
}

async function Profile({
    data,
}: {
    data: Promise<Awaited<ReturnType<typeof loadProfile>> | null>;
}) {
    const loaded = await data;
    // Only reachable signed in: the gate has shown the notice otherwise.
    if (!loaded) return null;
    const [profile, path] = loaded;

    if (!profile) notFound();

    return (
        <div className="shell grid gap-3 py-4 pb-12">
            <Link href="/network" className="w-fit text-[12.5px] font-medium text-blue hover:underline">
                Back to the network
            </Link>

            <div className="card overflow-hidden">
                {/* This view is the page here, so the member's name is its h1. */}
                <MemberProfileView profile={profile} path={path} nameAs="h1" />
            </div>
        </div>
    );
}
