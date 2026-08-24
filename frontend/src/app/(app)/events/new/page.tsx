import MemberGate from "@/components/MemberGate";
import NewEventForm from "./Client";

export const metadata = { title: "Create an event · CDTM Community" };

export default function NewEventPage() {
    return (
        <MemberGate requireMember next="/events/new">
            <NewEventForm />
        </MemberGate>
    );
}
