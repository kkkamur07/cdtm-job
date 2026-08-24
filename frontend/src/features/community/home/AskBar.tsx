"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import SearchIcon from "@/components/SearchIcon";

const SUGGESTIONS = [
    "co-founders in Berlin",
    "who went from informatics to VC",
    "mentors for a first PM job",
];

/** The one interactive thing on the home page: a question, then /network. */
export default function AskBar() {
    const router = useRouter();
    const [text, setText] = useState("");

    const go = (question: string) =>
        router.push(question.trim() ? `/network?q=${encodeURIComponent(question)}` : "/network");

    return (
        <>
            <form
                className="card feed-ask mt-2.5 border-0"
                onSubmit={(event) => {
                    event.preventDefault();
                    go(text);
                }}
            >
                <SearchIcon />
                <input
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    aria-label="Ask the network"
                    placeholder="Ask the network: who can I ask about YC?"
                />
                <button type="submit" className="btn btn-blue btn-sm">
                    Ask
                </button>
            </form>
            <div className="suggest">
                {SUGGESTIONS.map((suggestion) => (
                    <button key={suggestion} type="button" onClick={() => go(suggestion)}>
                        {suggestion}
                    </button>
                ))}
            </div>
        </>
    );
}
