"use client";

import { useEffect, useRef } from "react";
import type { Profile } from "@/lib/types";
import MemberAvatar from "./MemberAvatar";

/**
 * Renders an already-loaded profile. It deliberately does NOT fetch: the grid
 * resolves the data first and only then opens this, so the whole panel appears
 * in one frame instead of a shell followed by text.
 */
export default function MemberModal({
                                        profile,
                                        onClose,
                                    }: {
    profile: Profile | null;
    onClose: () => void;
}) {
    const ref = useRef<HTMLDialogElement>(null);
    const panelRef = useRef<HTMLDivElement>(null);

    // Native <dialog> gives focus trapping, Escape handling, and inert
    // background for free — all things a hand-rolled modal gets wrong.
    useEffect(() => {
        const el = ref.current;
        if (!el) return;

        if (profile && !el.open) {
            el.showModal();
            // <dialog> otherwise autofocuses its first focusable descendant, which
            // is the close button — so it opened wearing a focus ring that vanished
            // the moment you clicked anything. Moving focus to the panel keeps
            // Escape and tab order working with nothing visibly highlighted.
            panelRef.current?.focus();
        }

        if (!profile && el.open) el.close();
    }, [profile]);

    // showModal() makes the page behind inert for clicks but leaves it
    // scrollable, so the wheel still moved the grid whenever the cursor sat
    // outside the panel. Locking the body is the only reliable fix.
    //
    // The padding compensates for the scrollbar the lock removes; without it
    // the whole page — including the sticky toolbar — jumps sideways by ~15px
    // the instant a profile opens.
    useEffect(() => {
        if (!profile) return;

        const { body } = document;
        const gutter = window.innerWidth - document.documentElement.clientWidth;
        const previousOverflow = body.style.overflow;
        const previousPadding = body.style.paddingRight;

        body.style.overflow = "hidden";
        if (gutter > 0) body.style.paddingRight = `${gutter}px`;

        return () => {
            body.style.overflow = previousOverflow;
            body.style.paddingRight = previousPadding;
        };
    }, [profile]);

    return (
        <dialog
            ref={ref}
            onClose={onClose}
            onClick={(e) => {
                // Clicking the backdrop closes; clicking the panel does not.
                if (e.target === ref.current) ref.current?.close();
            }}
            className="m-auto w-[min(680px,calc(100vw-2rem))] rounded-[var(--radius-card)] border border-line bg-white p-0 text-ink backdrop:backdrop-blur-[2px]"
        >
            {profile && (
                <div
                    ref={panelRef}
                    tabIndex={-1}
                    className="max-h-[85vh] overflow-y-auto overscroll-contain focus:outline-none"
                >
                    <header className="flex items-start gap-4 border-b border-line p-6">
                        <div className="h-20 w-20 shrink-0 overflow-hidden rounded-[16px] bg-cream">
                            <MemberAvatar name={profile.name} avatar={profile.avatar} size="lg" />
                        </div>

                        <div className="min-w-0 flex-1">
                            <h2 className="text-xl leading-tight font-semibold tracking-tight">
                                {profile.name}
                            </h2>
                            {profile.headline && (
                                <p className="mt-1 text-sm leading-snug text-muted">{profile.headline}</p>
                            )}

                            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                                {profile.classLabel && (
                                    <span className="rounded-[var(--radius-pill)] bg-blue-soft px-2.5 py-1 text-[11px] leading-none font-medium text-blue">
                    {profile.classLabel}
                  </span>
                                )}
                                {profile.isCA && (
                                    <span className="rounded-[var(--radius-pill)] bg-green px-2.5 py-1 text-[11px] leading-none font-semibold text-ink">
                    {profile.caAlumni === false ? "Center Assistant" : "CA alumn"}
                  </span>
                                )}
                                {profile.location && (
                                    <span className="text-[11px] text-muted">{profile.location}</span>
                                )}
                            </div>
                        </div>

                        <button
                            type="button"
                            onClick={() => ref.current?.close()}
                            aria-label="Close"
                            className="-mt-1 -mr-1 rounded-full p-2 text-muted transition-colors hover:bg-cream hover:text-ink"
                        >
                            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                                <path
                                    d="M4 4l8 8M12 4l-8 8"
                                    stroke="currentColor"
                                    strokeWidth="1.6"
                                    strokeLinecap="round"
                                />
                            </svg>
                        </button>
                    </header>

                    <div className="space-y-6 p-6">
                        {profile.major && <Field label="Studied">{profile.major}</Field>}

                        <>
                            {profile.ca?.about && (
                                <Section title="At CDTM">
                                    <p className="text-sm leading-relaxed whitespace-pre-line text-ink/80">
                                        {profile.ca.about}
                                    </p>
                                    {profile.ca.responsibilities.length > 0 && (
                                        <ChipRow items={profile.ca.responsibilities} />
                                    )}
                                    {profile.ca.researchFields.length > 0 && (
                                        <Field label="Research">
                                            {profile.ca.researchFields.join(" · ")}
                                        </Field>
                                    )}
                                </Section>
                            )}

                            {profile.summary && (
                                <Section title="About">
                                    <p className="text-sm leading-relaxed whitespace-pre-line text-ink/80">
                                        {profile.summary}
                                    </p>
                                </Section>
                            )}

                            {profile.positions.length > 0 && (
                                <Section title="Experience">
                                    <ul className="space-y-3">
                                        {profile.positions.map((p, i) => (
                                            <li key={i} className="flex gap-3">
                          <span
                              className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                                  p.current ? "bg-green" : "bg-line"
                              }`}
                          />
                                                <div className="min-w-0">
                                                    <p className="text-sm leading-snug font-medium">
                                                        {p.title ?? "—"}
                                                        {p.company && (
                                                            <span className="font-normal text-muted"> · {p.company}</span>
                                                        )}
                                                    </p>
                                                    {p.dateRange && (
                                                        <p className="text-xs text-muted">{p.dateRange}</p>
                                                    )}
                                                </div>
                                            </li>
                                        ))}
                                    </ul>
                                </Section>
                            )}

                            {profile.schools.length > 0 && (
                                <Section title="Education">
                                    <ul className="space-y-2">
                                        {profile.schools.map((s, i) => (
                                            <li key={i}>
                                                <p className="text-sm leading-snug font-medium">{s.school}</p>
                                                <p className="text-xs text-muted">
                                                    {[s.degree, s.dateRange].filter(Boolean).join(" · ")}
                                                </p>
                                            </li>
                                        ))}
                                    </ul>
                                </Section>
                            )}

                            {profile.skills.length > 0 && (
                                <Section title="Skills">
                                    <ChipRow items={profile.skills.slice(0, 14)} />
                                </Section>
                            )}
                        </>

                        {profile.linkedInUrl && (
                            <a
                                href={profile.linkedInUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 text-sm font-medium text-blue hover:underline"
                            >
                                Open LinkedIn profile
                                <span aria-hidden="true">↗</span>
                            </a>
                        )}
                    </div>
                </div>
            )}
        </dialog>
    );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section className="space-y-2.5">
            <h3 className="text-[11px] font-semibold tracking-wider text-muted uppercase">
                {title}
            </h3>
            {children}
        </section>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <p className="text-sm">
            <span className="text-muted">{label}: </span>
            {children}
        </p>
    );
}

function ChipRow({ items }: { items: string[] }) {
    return (
        <div className="flex flex-wrap gap-1.5">
            {items.map((item) => (
                <span
                    key={item}
                    className="rounded-[var(--radius-pill)] bg-cream px-2.5 py-1 text-xs text-ink/70"
                >
          {item}
        </span>
            ))}
        </div>
    );
}