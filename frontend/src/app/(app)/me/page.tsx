import MemberGate from "@/components/MemberGate";
import MeBody from "./Client";

export const metadata = { title: "You · CDTM Community" };

export default function MePage() {
    return (
        <MemberGate requireMember next="/me">
            <MeBody />
        </MemberGate>
    );
}
