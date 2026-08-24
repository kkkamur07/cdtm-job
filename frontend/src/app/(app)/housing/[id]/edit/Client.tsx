"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useHousingListing, useUpdateHousing } from "@/api/hooks/community";
import Panel from "@/components/Panel";
import { ErrorState } from "@/components/states";
import { LoadingBlock } from "@/components/placeholders";
import HousingForm from "@/features/community/housing/HousingForm";

export default function EditBody({ id }: { id: string }) {
    const router = useRouter();
    const listing = useHousingListing(id);
    const update = useUpdateHousing(id);

    return (
        <div className="shell grid gap-3 py-4 pb-12">
            <Link href={`/housing/${id}`} className="w-fit text-[12.5px] font-medium text-blue hover:underline">
                Back to the listing
            </Link>

            <Panel title="Edit listing">
                {listing.isPending && <LoadingBlock label="Loading listing" rows={4} />}
                {listing.error && <ErrorState error={listing.error} onRetry={() => listing.refetch()} />}
                {listing.data && (
                    <HousingForm
                        listing={listing.data}
                        submitLabel="Save changes"
                        pending={update.isPending}
                        error={update.error}
                        onSubmit={(values) => {
                            // Kind is fixed once posted: an offer does not turn
                            // into a search without confusing everyone watching.
                            const { kind, ...body } = values;
                            void kind;
                            update.mutate(body, { onSuccess: () => router.push(`/housing/${id}`) });
                        }}
                        footer={
                            <Link href={`/housing/${id}`} className="btn btn-ghost">
                                Cancel
                            </Link>
                        }
                    />
                )}
            </Panel>
        </div>
    );
}
