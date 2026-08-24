import { loadMe, loadMyMember } from "@/api/server";
import MemberGate, { gatedData } from "@/components/MemberGate";
import MeBody from "./Client";

export const metadata = { title: "You · CDTM Community" };

/**
 * Your own account.
 *
 * Both reads are already in hand for this render: the gate awaited `/auth/me`
 * and the shell awaited `/members/me`, and both loaders are `React.cache`d, so
 * asking for them here costs nothing. They are handed to the client as initial
 * data because the page used to arrive with an empty header and then fetch both
 * again from the browser, behind the session restore that gates every client
 * query.
 */
export default function MePage() {
    const data = gatedData(loadAccount);
    return (
        <MemberGate requireMember next="/me">
            <Me data={data} />
        </MemberGate>
    );
}

function loadAccount() {
    return Promise.all([loadMe().catch(() => null), loadMyMember().catch(() => null)]);
}

async function Me({ data }: { data: Promise<Awaited<ReturnType<typeof loadAccount>> | null> }) {
    const [me, member] = (await data) ?? [null, null];
    return <MeBody me={me ?? undefined} member={member ?? undefined} />;
}
