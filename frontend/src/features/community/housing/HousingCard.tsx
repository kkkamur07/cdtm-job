import Image from "next/image";
import Link from "next/link";

import { mediaUrl } from "@/api/media";
import { AvatarCircle } from "@/components/MemberAvatar";
import { dateRange, formatPrice, roomsLabel } from "@/lib/format";

export type HousingCardData = {
    id: string;
    kind: string;
    title: string;
    area?: string | null;
    city?: string | null;
    price?: number | string | null;
    rooms?: number | string | null;
    from?: string | null;
    until?: string | null;
    photos: string[];
    closed: boolean;
    postedBy: {
        name: string;
        slug: string;
        avatar: string | null;
        classLabel?: string | null;
    } | null;
};

/**
 * One housing listing.
 *
 * Offers and searches share the card: the kind is a label rather than a
 * separate layout, because the useful comparison is between two rooms in the
 * same city, not between the two kinds. The photo leads, since that is what
 * people actually scan for.
 */
export default function HousingCard({
    listing,
    compact = false,
}: {
    listing: HousingCardData;
    compact?: boolean;
}) {
    const offer = listing.kind === "offer";
    const photo = listing.photos[0] ? mediaUrl(listing.photos[0]) : null;
    const price = formatPrice(listing.price);
    const dates = dateRange(listing.from, listing.until);
    const rooms = roomsLabel(listing.rooms);

    return (
        <Link href={`/housing/${listing.id}`} className="card hcard cv-card">
            <div className="photo">
                <span className={`kind-tag ${offer ? "offer" : "look"}`}>
                    {offer ? "Offering" : "Looking"}
                </span>
                {photo ? (
                    <Image
                        src={photo}
                        alt=""
                        fill
                        sizes="(min-width: 1100px) 360px, (min-width: 700px) 50vw, 100vw"
                        className="object-cover"
                    />
                ) : (
                    <NoPhoto looking={!offer} />
                )}
                {listing.photos.length > 1 && (
                    <span className="photos-pill">{listing.photos.length} photos</span>
                )}
            </div>

            <div className="hbody">
                <div className="top">
                    <div className="min-w-0">
                        <h3>{listing.title}</h3>
                        <p className="where truncate">
                            {[listing.area, listing.city].filter(Boolean).join(" · ") ||
                                "Location not given"}
                        </p>
                    </div>
                    {price && (
                        <p className="price">
                            {price}
                            <small>per month</small>
                        </p>
                    )}
                </div>

                <p className="facts">
                    {dates && <span>{dates}</span>}
                    {rooms && <span>{rooms}</span>}
                    {listing.closed && <span className="pill pill-muted">Closed</span>}
                </p>

                {!compact && listing.postedBy && (
                    <p className="via flex items-center gap-2 text-[12.5px] text-muted">
                        <AvatarCircle
                            name={listing.postedBy.name}
                            avatar={
                                listing.postedBy.avatar
                                    ? { sm: listing.postedBy.avatar, lg: listing.postedBy.avatar }
                                    : null
                            }
                            px={20}
                        />
                        <span className="truncate">
                            {listing.postedBy.name}
                            {listing.postedBy.classLabel ? ` · ${listing.postedBy.classLabel}` : ""}
                        </span>
                    </p>
                )}
            </div>
        </Link>
    );
}

/**
 * A listing with no photo still needs to fill the same block, or the grid goes
 * ragged. A drawn roofline reads as "no photo" without the apology of the words.
 */
function NoPhoto({ looking }: { looking: boolean }) {
    return (
        <span className="nophoto">
            <svg viewBox="0 0 64 40" aria-hidden="true" focusable="false">
                <path d="M6 22 L20 10 L34 22" />
                <path d="M10 22 V34 H30 V22" />
                <path d="M38 34 V16 H56 V34" />
                <path d="M44 34 V26 H50 V34" />
                <path d="M2 34 H62" />
            </svg>
            <span>{looking ? "Looking for a place" : "No photo yet"}</span>
        </span>
    );
}
