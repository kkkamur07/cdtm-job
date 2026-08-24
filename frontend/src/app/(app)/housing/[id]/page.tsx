import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ApiError } from "@/api/errors";
import { mediaUrl } from "@/api/media";
import { loadHousing, loadHousingListing, loadMe, loadMemberIndex, loadMembers } from "@/api/server";
import { getIdentity } from "@/auth/session";
import MemberGate, { gatedData } from "@/components/MemberGate";
import { AvatarCircle } from "@/components/MemberAvatar";
import HousingOwnerActions from "@/features/community/housing/HousingOwnerActions";
import { dateRange, formatDate, formatPrice, paragraphs, roomsLabel } from "@/lib/format";

type Params = { params: Promise<{ id: string }> };

/**
 * `loadHousingListing` is `React.cache`d, so titling the tab costs no extra
 * request: the page body reads the same cached listing a moment later. Housing
 * is members-only, so for a signed-out visitor there is no request at all.
 */
export async function generateMetadata({ params }: Params) {
    const { id } = await params;
    const { accessToken } = await getIdentity();
    if (!accessToken) return { title: "Listing · CDTM Community" };

    try {
        const listing = await loadHousingListing(id);
        const where = [listing.area, listing.city].filter(Boolean).join(", ");
        const price = formatPrice(listing.price_eur);
        return {
            title: `${listing.title} · CDTM Community`,
            description:
                [listing.kind === "offer" ? "Room offered" : "Member looking", where, price]
                    .filter(Boolean)
                    .join(" · ") || undefined,
        };
    } catch {
        return { title: "Listing · CDTM Community" };
    }
}

export default async function HousingListingPage({ params }: Params) {
    const { id } = await params;

    // Awaiting the route params costs nothing; awaiting the gate would. The
    // reads are started here so they run alongside the gate's own /auth/me
    // rather than a round trip behind it.
    const data = gatedData(() => loadListing(id));

    return (
        <MemberGate next={`/housing/${id}`}>
            <Listing data={data} />
        </MemberGate>
    );
}

function loadListing(id: string) {
    return Promise.all([
        loadHousingListing(id).catch((error) => {
            if (error instanceof ApiError && error.isNotFound) return null;
            throw error;
        }),
        loadMe().catch(() => null),
    ]);
}

async function Listing({
    data,
}: {
    data: Promise<Awaited<ReturnType<typeof loadListing>> | null>;
}) {
    const loaded = await data;
    // Only reachable signed in: the gate has shown the notice otherwise.
    if (!loaded) return null;
    const [listing, me] = loaded;

    if (!listing) notFound();

    const offer = listing.kind === "offer";
    const mine = Boolean(me?.member_id && me.member_id === listing.member_id);
    const photos = (listing.photo_urls ?? []).map(mediaUrl);
    const price = formatPrice(listing.price_eur);
    const rooms = roomsLabel(listing.rooms);

    return (
        <div className="shell-wide pb-14">
            <div className="py-3">
                <Link href="/housing" className="btn btn-ghost btn-sm">
                    ← All listings
                </Link>
            </div>

            <div className="hdetail">
                <div className="min-w-0">
                    {photos.length > 0 ? (
                        <div className="gallery">
                            {photos.slice(0, 3).map((photo, index) => (
                                <div key={photo} className="g">
                                    {index === 0 && (
                                        <span className={`kind-tag ${offer ? "offer" : "look"}`}>
                                            {offer ? "Offering" : "Looking"}
                                        </span>
                                    )}
                                    <Image
                                        src={photo}
                                        alt=""
                                        fill
                                        sizes={index === 0 ? "(min-width: 900px) 500px, 100vw" : "250px"}
                                        className="object-cover"
                                        priority={index === 0}
                                    />
                                    {index === 2 && photos.length > 3 && (
                                        <span className="photos-pill">All {photos.length} photos</span>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="card grid h-40 place-items-center text-[13px] text-muted">
                            {offer
                                ? "No photos on this listing. Ask the poster for some."
                                : "A member looking for a place, so there is nothing to show yet."}
                        </div>
                    )}

                    <div className="px-1 pt-5">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                            <div className="min-w-0">
                                <h1 className="text-[26px] leading-tight font-semibold">
                                    {listing.title}
                                </h1>
                                <p className="mt-1.5 text-[14.5px] text-muted">
                                    {[listing.area, listing.city].filter(Boolean).join(" · ")}
                                    {listing.created_at
                                        ? ` · posted ${formatDate(listing.created_at)}`
                                        : ""}
                                </p>
                            </div>
                            {price && (
                                <p className="text-right text-[24px] leading-none font-semibold">
                                    {price}
                                    <small className="mt-1 block text-[12px] font-normal text-muted">
                                        per month
                                    </small>
                                </p>
                            )}
                        </div>

                        <div className="kv2 mt-6">
                            <div>
                                <div className="k">Dates</div>
                                <div className="v">
                                    {dateRange(listing.available_from, listing.available_until) ??
                                        "Whenever suits"}
                                </div>
                            </div>
                            <div>
                                <div className="k">Size</div>
                                <div className="v">{rooms ?? "Not given"}</div>
                            </div>
                        </div>

                        {listing.description && (
                            <section className="prose mt-6">
                                <h2 className="label">About</h2>
                                {paragraphs(listing.description).map((part) => (
                                    <p key={part.key}>{part.text}</p>
                                ))}
                            </section>
                        )}
                    </div>
                </div>

                <aside className="side">
                    {mine && (
                        <HousingOwnerActions
                            id={listing.id}
                            closed={listing.status === "closed"}
                            posted={formatDate(listing.created_at)}
                            daysLeft={daysLeft(listing.expires_at ?? null)}
                        />
                    )}

                    <Suspense fallback={null}>
                        <PostedBy memberId={listing.member_id} />
                    </Suspense>

                    {listing.city && (
                        <Suspense fallback={null}>
                            <MembersInCity city={listing.city} exclude={listing.member_id} />
                        </Suspense>
                    )}

                    {listing.city && (
                        <Suspense fallback={null}>
                            <AlsoInCity city={listing.city} exclude={listing.id} />
                        </Suspense>
                    )}
                </aside>
            </div>
        </div>
    );
}

/**
 * The poster, in its own boundary.
 *
 * It used to be awaited above the return, which held the two city panels below
 * behind a lookup neither of them needs: they only want `listing.city`, which
 * is known the moment the listing arrives. Suspended here, all three start
 * together and race each other.
 */
async function PostedBy({ memberId }: { memberId: string | null }) {
    if (!memberId) return null;

    const members = await loadMemberIndex([memberId]).catch(() => null);
    const poster = members?.get(memberId);
    if (!poster) return null;

    return (
        <div className="card panel">
            <h2 className="label">Posted by</h2>
            <div className="insider mt-2">
                <AvatarCircle name={poster.name} avatar={poster.avatar} px={44} />
                <div className="min-w-0">
                    <div className="n truncate">{poster.name}</div>
                    <div className="s truncate">
                        {[poster.title, poster.company, poster.class_label]
                            .filter(Boolean)
                            .join(" · ")}
                    </div>
                </div>
            </div>
            <Link href={`/members/${poster.slug}`} className="btn mt-3.5 w-full">
                Open entry
            </Link>
        </div>
    );
}

/** Streams separately: it needs the city, which only arrives with the listing. */
async function MembersInCity({ city, exclude }: { city: string; exclude: string | null }) {
    const result = await loadMembers({ location: city, limit: 6 }).catch(() => null);
    const people = result?.items.filter((member) => member.id !== exclude) ?? [];
    if (!people.length) return null;

    return (
        <div className="card panel">
            <h2 className="label">Members in {city}</h2>
            <ul className="mt-2.5 grid gap-2">
                {people.slice(0, 5).map((member) => (
                    <li key={member.id}>
                        <Link
                            href={`/members/${member.slug}`}
                            className="insider rounded-2xl p-1 hover:bg-cream"
                        >
                            <AvatarCircle name={member.name} avatar={member.avatar} px={32} />
                            <span className="min-w-0">
                                <span className="n block truncate">{member.name}</span>
                                <span className="s block truncate">
                                    {[member.title, member.company].filter(Boolean).join(", ")}
                                </span>
                            </span>
                        </Link>
                    </li>
                ))}
            </ul>
            <p className="mt-2.5 text-[12px] text-muted">Ask them about the area.</p>
        </div>
    );
}

/**
 * The other listings in the same city, as thumbs. Someone reading one room is
 * usually comparing rooms, and the board is two clicks away otherwise.
 */
async function AlsoInCity({ city, exclude }: { city: string; exclude: string }) {
    const result = await loadHousing({ city, status: "open", limit: 5 }).catch(() => null);
    const others = (result?.items ?? []).filter((listing) => listing.id !== exclude).slice(0, 4);
    if (!others.length) return null;

    return (
        <div className="card panel">
            <h2 className="label">Also in {city}</h2>
            <ul className="also mt-2.5">
                {others.map((listing) => {
                    const thumb = listing.photo_urls?.[0] ? mediaUrl(listing.photo_urls[0]) : null;
                    const price = formatPrice(listing.price_eur);
                    return (
                        <li key={listing.id}>
                            <Link href={`/housing/${listing.id}`}>
                                <span className="thumb">
                                    {thumb ? (
                                        <Image
                                            src={thumb}
                                            alt=""
                                            fill
                                            sizes="64px"
                                            className="object-cover"
                                        />
                                    ) : (
                                        <span aria-hidden="true">·</span>
                                    )}
                                </span>
                                <span className="min-w-0">
                                    <span className="n block truncate">{listing.title}</span>
                                    <span className="s block truncate">
                                        {[listing.area, price].filter(Boolean).join(" · ") ||
                                            (listing.kind === "offer" ? "Offering" : "Looking")}
                                    </span>
                                </span>
                            </Link>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}

/**
 * Whole days from now until the expiry, rounded up, or null if there is none.
 *
 * It is worked out here rather than in the owner panel so the number is fixed
 * at render time. A client component reading `Date.now()` while rendering can
 * land on the other side of a day boundary from the server and rewrite itself
 * during hydration.
 */
function daysLeft(expiresAt: string | null): number | null {
    if (!expiresAt) return null;
    const at = Date.parse(expiresAt);
    if (Number.isNaN(at)) return null;
    return Math.ceil((at - Date.now()) / 86_400_000);
}
