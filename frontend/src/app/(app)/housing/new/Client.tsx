"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useCreateHousing } from "@/api/hooks/community";
import Panel from "@/components/Panel";
import HousingForm from "@/features/community/housing/HousingForm";

export default function NewHousingBody() {
    const router = useRouter();
    const create = useCreateHousing();

    return (
        <div className="shell grid gap-3 py-4 pb-12">
            <Link href="/housing" className="w-fit text-[12.5px] font-medium text-blue hover:underline">
                Back to housing
            </Link>

            <Panel title="Post a listing">
                <HousingForm
                    submitLabel="Publish listing"
                    pending={create.isPending}
                    error={create.error}
                    onSubmit={(values) => {
                        // A new listing is always open; status is only editable
                        // once the listing exists.
                        const { status, ...body } = values;
                        void status;
                        create.mutate(body, {
                            onSuccess: (listing) => router.push(`/housing/${listing.id}`),
                        });
                    }}
                    footer={
                        <Link href="/housing" className="btn btn-ghost">
                            Cancel
                        </Link>
                    }
                />
            </Panel>
        </div>
    );
}
