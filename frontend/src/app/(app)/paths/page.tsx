import { loadFacets, loadPathFlow, loadPathGroups } from "@/api/server";
import MemberGate, { gatedData } from "@/components/MemberGate";
import PathsExplorer from "@/features/community/paths/PathsExplorer";

export const metadata = { title: "Paths · CDTM Community" };

/**
 * Synchronous on purpose: the reads are started here, before the gate suspends
 * on `/auth/me`, so the flow is already in flight while the gate decides.
 */
export default function PathsPage() {
    const data = gatedData(loadPaths);
    return (
        <MemberGate next="/paths">
            <Paths data={data} />
        </MemberGate>
    );
}

/**
 * Three independent reads. The facets are only the class list for the filter,
 * so a failure there costs the filter and nothing else.
 */
function loadPaths() {
    return Promise.all([loadPathFlow({}), loadPathGroups(), loadFacets().catch(() => null)]);
}

async function Paths({ data }: { data: Promise<Awaited<ReturnType<typeof loadPaths>> | null> }) {
    const loaded = await data;
    // Only reachable signed in: the gate has shown the notice otherwise.
    if (!loaded) return null;
    const [flow, groups, facets] = loaded;

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
