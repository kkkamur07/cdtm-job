import Link from "next/link";

import type { Member } from "@/api/types";
import { AvatarCircle } from "@/components/MemberAvatar";

/** Four faces, for "people like you". Names truncate rather than wrap. */
export default function PeopleStrip({ members }: { members: Member[] }) {
    return (
        <div className="people-strip">
            {members.map((member) => (
                <Link key={member.id} href={`/members/${member.slug}`} className="mini">
                    <span className="mx-auto mb-1.5 block w-fit">
                        <AvatarCircle name={member.name} avatar={member.avatar} px={56} />
                    </span>
                    <span className="n block truncate">{member.name}</span>
                    <span className="s block truncate">{member.company ?? member.class_label}</span>
                </Link>
            ))}
        </div>
    );
}
