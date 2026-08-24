import MemberGate from "@/components/MemberGate";
import DirectoryClient from "./Client";

export const metadata = { title: "Directory · CDTM Community" };

/**
 * The name-first way into the community. Ask (at /network) turns a sentence
 * into filters; this is the other door: a search box over names, companies,
 * studies and places, for when you already know who you want.
 */
export default function DirectoryPage() {
    return (
        <MemberGate next="/directory">
            <DirectoryClient />
        </MemberGate>
    );
}
