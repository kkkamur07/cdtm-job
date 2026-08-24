import { Suspense } from "react";

import MemberGate from "@/components/MemberGate";
import { LoadingBlock } from "@/components/placeholders";
import EditBody from "./Client";

export const metadata = { title: "Edit listing · CDTM Community" };

export default async function EditHousingPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    return (
        <MemberGate requireMember next={`/housing/${id}/edit`}>
            {/* A real skeleton, so the form does not appear out of nowhere. */}
            <Suspense
                fallback={
                    <div className="shell py-4 pb-12">
                        <div className="card p-6">
                            <LoadingBlock label="Loading listing" rows={5} />
                        </div>
                    </div>
                }
            >
                <EditBody id={id} />
            </Suspense>
        </MemberGate>
    );
}
