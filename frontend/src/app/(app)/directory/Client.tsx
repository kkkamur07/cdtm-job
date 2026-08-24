"use client";

import Link from "next/link";
import { useState } from "react";

import { useMemberSearch } from "@/api/hooks/directory";
import type { Member } from "@/api/types";
import { AvatarCircle } from "@/components/MemberAvatar";
import SearchIcon from "@/components/SearchIcon";
import { EmptyState, LoadingBlock } from "@/components/placeholders";
import { useDebounced } from "@/lib/useDebounced";
import IntentPills from "@/features/community/IntentPills";
import SaveButton from "@/features/community/SaveButton";

/**
 * The directory: one search box over the whole community. Typing is debounced
 * so the list settles rather than flickering on every keystroke, and an empty
 * box shows the first page of everyone so there is always something to browse.
 */
export default function DirectoryClient() {
    const [draft, setDraft] = useState("");
    const q = useDebounced(draft, 250);
    const search = useMemberSearch(q);

    const members = search.data?.items ?? [];
    const total = search.data?.total ?? 0;

    return (
        <div className="shell-wide explore">
            <div className="explore-head">
                <p className="eyebrow">Directory</p>
                <h1>Find someone by name.</h1>
                <p className="desc">
                    Search the whole community by name, company, study or city. Looking for a kind
                    of person rather than a name?{" "}
                    <Link href="/network" className="text-blue hover:underline">
                        Ask the network
                    </Link>{" "}
                    instead.
                </p>
            </div>

            <form className="card qbar" role="search" onSubmit={(event) => event.preventDefault()}>
                <SearchIcon />
                <label className="sr-only" htmlFor="directory-search">
                    Search the directory
                </label>
                <input
                    id="directory-search"
                    name="q"
                    value={draft}
                    maxLength={128}
                    autoComplete="off"
                    autoFocus
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder="Search by name, company, study or city…"
                />
            </form>

            <div className="results">
                {search.isLoading && <LoadingBlock label="Loading the directory" rows={5} />}

                {!search.isLoading && members.length === 0 && (
                    <EmptyState
                        title={q ? `No one matches "${q}".` : "No members to show."}
                        hint="Try a different name, or a company or study."
                    />
                )}

                {members.length > 0 && (
                    <>
                        <p className="mb-2.5 text-[13px] text-muted">
                            {total} {total === 1 ? "person" : "people"}
                            {q ? " matched" : " in the directory"}
                            {total > members.length ? ` · showing the first ${members.length}` : ""}.
                        </p>
                        <ul className="card overflow-hidden [content-visibility:auto]">
                            {members.map((member) => (
                                <DirectoryRow key={member.id} member={member} />
                            ))}
                        </ul>
                    </>
                )}
            </div>
        </div>
    );
}

/** One person in the directory. The whole row links to the entry; Save sits to the side. */
function DirectoryRow({ member }: { member: Member }) {
    const subtitle = [member.title, member.company, member.location, member.class_label]
        .filter(Boolean)
        .join(" · ");

    return (
        <li className="cv-row relative">
            <Link href={`/members/${member.slug}`} className="rrow rrow-actions w-full text-left">
                <AvatarCircle name={member.name} avatar={member.avatar} px={48} />
                <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold">{member.name}</span>
                    <span className="s block truncate">{subtitle}</span>
                </span>
                <span className="hidden sm:block">
                    <IntentPills intents={member.intents} max={2} />
                </span>
            </Link>
            <span className="rowacts">
                <SaveButton memberId={member.id} label={false} />
            </span>
        </li>
    );
}
