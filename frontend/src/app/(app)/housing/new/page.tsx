import MemberGate from "@/components/MemberGate";
import NewHousingBody from "./Client";

export const metadata = { title: "Post a listing · CDTM Community" };

export default function NewHousingPage() {
    return (
        <MemberGate requireMember next="/housing/new">
            <NewHousingBody />
        </MemberGate>
    );
}
