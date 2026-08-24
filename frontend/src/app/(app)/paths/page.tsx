import { loadFacets, loadPathFlow, loadPathGroups } from "@/api/server";
import MemberGate from "@/components/MemberGate";
import PathsExplorer from "@/features/community/paths/PathsExplorer";

export const metadata = { title: "Paths · CDTM Community" };

export default function PathsPage() {
    return (
        <MemberGate next="/paths">
            <Paths />
        </MemberGate>
    );
}

async function Paths() {
    // Three independent reads. The facets are only the class list for the
    // filter, so a failure there costs the filter and nothing else.
    const [flow, groups, facets] = await Promise.all([
        loadPathFlow({}),
        loadPathGroups(),
        loadFacets().catch(() => null),
    ]);

    return (
        <div className="shell-wide pb-14">
            <div className="bhead border-0 pt-3 pb-2">
                <p className="eyebrow">Where CDTM people go</p>
                <h1>Paths</h1>
                <p className="desc">
                    Drawn from {flow.members_counted.toLocaleString("en-GB")} career histories.
                    What members studied, the first thing they did after CDTM, and where they are
                    now. Pick a group to see who is in it.
                </p>
            </div>

            <PathsExplorer initialFlow={flow} groups={groups} facets={facets} />

            <p className="mt-8 border-t border-line pt-4 text-[12px] text-muted">
                Paths explorer inspired by Henri Bayer&rsquo;s{" "}
                <a
                    href="https://cdtm-paths.up.railway.app/"
                    target="_blank"
                    rel="noreferrer noopener"
                    className="font-medium text-blue hover:underline"
                >
                    cdtm-paths
                </a>
                .
            </p>
        </div>
    );
}
