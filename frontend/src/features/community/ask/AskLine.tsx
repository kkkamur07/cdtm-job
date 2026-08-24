"use client";

import { useId, useState } from "react";

import SearchIcon from "@/components/SearchIcon";

/**
 * The one-line Ask bar that sits above Jobs, Housing and Paths.
 *
 * It is a form, not a live-as-you-type box: a question costs a model call of a
 * few seconds, so it runs when it is submitted. Clearing it is a real button
 * rather than an empty submit, because "how do I get the whole list back" is
 * the question the first empty answer raises.
 *
 * The examples underneath are buttons that ask the question, so nobody has to
 * retype one to find out what it does.
 */
export default function AskLine({
    placeholder,
    examples,
    value,
    onAsk,
    onClear,
    busy = false,
    children,
}: {
    placeholder: string;
    examples: string[];
    value: string;
    onAsk: (question: string) => void;
    onClear: () => void;
    busy?: boolean;
    /** The interpretation box, when there is an answer to show. */
    children?: React.ReactNode;
}) {
    const [draft, setDraft] = useState(value);
    const inputId = useId();

    return (
        <section className="mb-5" aria-label="Ask in plain words">
            <form
                className="card askline mb-0"
                onSubmit={(event) => {
                    event.preventDefault();
                    if (busy) return;
                    const question = draft.trim();
                    if (question.length >= 3) onAsk(question);
                }}
            >
                <div className="flex items-center gap-2.5">
                    <SearchIcon />
                    <label className="sr-only" htmlFor={inputId}>
                        Ask in plain words
                    </label>
                    <input
                        id={inputId}
                        name="ask"
                        value={draft}
                        maxLength={300}
                        autoComplete="off"
                        onChange={(event) => setDraft(event.target.value)}
                        placeholder={placeholder}
                    />
                    {value && (
                        <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => {
                                setDraft("");
                                onClear();
                            }}
                        >
                            Clear
                        </button>
                    )}
                    {/* Busy counts as well as too short, so hitting Enter twice
                        cannot put two questions in flight at once. */}
                    <button
                        type="submit"
                        className="btn btn-blue btn-sm"
                        disabled={busy || draft.trim().length < 3}
                    >
                        {busy ? "Asking…" : "Ask"}
                    </button>
                </div>

                <p className="text-[12px] text-muted">
                    Plain words become filters: a model reads the question, the database answers it.
                    Try:{" "}
                    {examples.map((example, index) => (
                        <span key={example}>
                            {index > 0 && " · "}
                            <button
                                type="button"
                                className="font-medium text-ink underline decoration-line underline-offset-2 hover:text-blue hover:decoration-blue disabled:no-underline disabled:opacity-50"
                                disabled={busy}
                                onClick={() => {
                                    setDraft(example);
                                    onAsk(example);
                                }}
                            >
                                {example}
                            </button>
                        </span>
                    ))}
                </p>
            </form>

            {children}
        </section>
    );
}
