"use client";

import { useEffect, useState } from "react";

/**
 * Holds a value still for `delay` ms. Used for search inputs so typing does not
 * fire a request per keystroke, while the input itself stays fully controlled
 * and responsive.
 */
export function useDebounced<T>(value: T, delay = 250): T {
    const [settled, setSettled] = useState(value);

    useEffect(() => {
        const timer = setTimeout(() => setSettled(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);

    return settled;
}
