import MemberGate from "@/components/MemberGate";
import PostJobForm from "./Client";

export const metadata = { title: "Post a job · CDTM Community" };

export default function PostJobPage() {
    return (
        <MemberGate requireMember next="/jobs/new">
            <PostJobForm />
        </MemberGate>
    );
}
