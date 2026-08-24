import Link from "next/link";

import { loadHousing, loadMemberIndex } from "@/api/server";
import MemberGate from "@/components/MemberGate";
import HousingBrowser from "@/features/community/housing/HousingBrowser";
import type { HousingCardData } from "@/features/community/housing/HousingCard";

export const metadata = { title: "Housing · CDTM Community" };

export default function HousingPage() {
    return (
        <MemberGate next="/housing">
            <Listings />
        </MemberGate>
    );
}

async function Listings() {
    const listings = await loadHousing({ status: "open", limit: 100 });

    // The posters' ids come off the listings, so this is a second request
    // rather than a parallel one. Without it the cards lose their byline.
    const members = await loadMemberIndex(
        listings.items.map((listing) => listing.member_id),
    ).catch(() => null);

    const cards: HousingCardData[] = listings.items.map((listing) => {
        const poster = listing.member_id ? members?.get(listing.member_id) : null;
        return {
            id: listing.id,
            kind: listing.kind,
            title: listing.title,
            area: listing.area,
            city: listing.city,
            price: listing.price_eur,
            rooms: listing.rooms,
            from: listing.available_from,
            until: listing.available_until,
            photos: listing.photo_urls ?? [],
            closed: listing.status === "closed",
            postedBy: poster
                ? {
                      name: poster.name,
                      slug: poster.slug,
                      avatar: poster.avatar?.sm ?? null,
                      classLabel: poster.class_label,
                  }
                : null,
        };
    });

    return (
        <div className="shell-wide pb-14">
            <div className="bhead border-0 pt-3 pb-2">
                <div className="flex flex-wrap items-end justify-between gap-4">
                    <div>
                        <p className="eyebrow">Between members</p>
                        <h1>Housing</h1>
                        <p className="desc">
                            Rooms, sublets and couches, posted by people you can look up.
                        </p>
                    </div>
                    <Link href="/housing/new" className="btn btn-primary">
                        Post a listing
                    </Link>
                </div>
            </div>

            <HousingBrowser listings={cards} />
        </div>
    );
}
