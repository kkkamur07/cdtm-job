"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

/**
 * The line above the query bar that types out example questions.
 *
 * It exists to answer "what am I allowed to ask" without a paragraph of
 * instructions. It is decoration, so the text itself is hidden from assistive
 * technology, and it stops entirely under `prefers-reduced-motion`, where the
 * first example is simply printed.
 *
 * WCAG 2.2.2: it moves by itself, it runs for more than five seconds, and it
 * loops, so there has to be a way to stop it. The button beside it does that,
 * and unlike the text it is not hidden: somebody who finds the movement
 * distracting is exactly the person who has to be able to reach the control.
 * Stopping leaves the current example in place rather than blanking the line.
 */
const TYPE_MS = 45;
const DELETE_MS = 22;
const HOLD_MS = 1600;
const REDUCED = "(prefers-reduced-motion: reduce)";

type Step = { index: number; length: number; deleting: boolean };

const START: Step = { index: 0, length: 0, deleting: false };

export default function Typewriter({ phrases }: { phrases: string[] }) {
    const [step, setStep] = useState<Step>(START);
    const [paused, setPaused] = useState(false);
    const animate = !useReducedMotion() && !paused && phrases.length > 0;
    const visible = useDocumentVisible();

    /**
     * One timer at a time, and every state change happens inside its callback.
     * Advancing from the effect body instead would re-render immediately and
     * schedule again, which is the cascade the rule against it exists to stop.
     *
     * A hidden tab schedules nothing: twenty-odd re-renders a second for a page
     * nobody is looking at is pure background cost, and the effect picks the
     * animation back up where it left off when the tab returns. Only the timer
     * stops; what is on screen is unchanged, so nothing moves on the way back.
     */
    useEffect(() => {
        if (!animate || !visible) return;
        const phrase = phrases[step.index % phrases.length];
        const full = !step.deleting && step.length >= phrase.length;
        const delay = full ? HOLD_MS : step.deleting ? DELETE_MS : TYPE_MS;
        const timer = setTimeout(() => setStep((current) => advance(current, phrases)), delay);
        return () => clearTimeout(timer);
    }, [animate, visible, phrases, step]);

    if (phrases.length === 0) return null;
    const phrase = phrases[step.index % phrases.length];
    // Paused mid-word, the honest thing to show is what had been typed so far.
    const text = paused ? phrase.slice(0, step.length) || phrase : animate ? phrase.slice(0, step.length) : phrase;

    return (
        <span className="tw-line">
            <span className="tw" aria-hidden="true">
                {text}
                {animate && <span className="cursor" />}
            </span>
            <button
                type="button"
                className="tw-stop"
                aria-pressed={paused}
                onClick={() => setPaused((current) => !current)}
            >
                {paused ? "Play examples" : "Stop examples"}
            </button>
        </span>
    );
}

function advance(step: Step, phrases: string[]): Step {
    const phrase = phrases[step.index % phrases.length];
    if (!step.deleting && step.length >= phrase.length) return { ...step, deleting: true };
    if (step.deleting && step.length <= 0) {
        return { index: (step.index + 1) % phrases.length, length: 0, deleting: false };
    }
    return { ...step, length: step.length + (step.deleting ? -1 : 1) };
}

/**
 * All four arguments below are module scope, not inline.
 *
 * `useSyncExternalStore` compares `subscribe` by identity and re-subscribes
 * whenever it changes, and this component re-renders every 45 ms while it
 * types. Inline arrows would tear down and rebuild both listeners twenty times
 * a second. The `MediaQueryList` is built once for the same reason: reading
 * `matchMedia` fresh on every snapshot is a lookup React makes on every render.
 *
 * `null` until asked for, because this module is evaluated on the server too.
 */
let reducedMotionQuery: MediaQueryList | null = null;

function reducedMotion(): MediaQueryList {
    reducedMotionQuery ??= window.matchMedia(REDUCED);
    return reducedMotionQuery;
}

function subscribeReducedMotion(onChange: () => void): () => void {
    const query = reducedMotion();
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
}

const getReducedMotion = () => reducedMotion().matches;
const getReducedMotionOnServer = () => false;

function subscribeVisibility(onChange: () => void): () => void {
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
}

const getVisible = () => !document.hidden;
const getVisibleOnServer = () => true;

/**
 * Subscribed rather than read in an effect, so the first client render matches
 * the server's and the preference is still followed if it changes mid-session.
 */
function useReducedMotion(): boolean {
    return useSyncExternalStore(
        subscribeReducedMotion,
        getReducedMotion,
        getReducedMotionOnServer,
    );
}

/** Same subscription shape, for the tab's visibility. Server renders visible. */
function useDocumentVisible(): boolean {
    return useSyncExternalStore(subscribeVisibility, getVisible, getVisibleOnServer);
}
