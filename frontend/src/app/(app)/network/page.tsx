import { Suspense } from "react";

import MemberGate from "@/components/MemberGate";
import { LoadingBlock } from "@/components/placeholders";
import AskExplorer from "@/features/community/ask/AskExplorer";

export const metadata = { title: "Ask the network · CDTM Community" };

export default function NetworkPage() {
    return (
        <MemberGate next="/network">
            <div className="shell-wide">
                {/* AskExplorer reads the question out of the URL, so it has to
                    sit inside a Suspense boundary. The fallback is a skeleton
                    rather than nothing: a blank frame on a shared link reads as
                    a broken page. */}
                <Suspense
                    fallback={
                        <div className="card mt-4 p-6">
                            <LoadingBlock label="Loading the network" rows={4} />
                        </div>
                    }
                >
                    <AskExplorer />
                </Suspense>
            </div>
        </MemberGate>
    );
}
