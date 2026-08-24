/**
 * Submit-time validation that puts the cursor where the problem is.
 *
 * Two gaps the browser leaves open, both of which end with a form that refuses
 * to send and gives no clue why:
 *
 * 1. `required` counts a space as a value, so a title of "   " passes, reaches
 *    the API and comes back as a 422 with nothing focused. These forms trim
 *    before sending, so they decide which field is really empty.
 * 2. A form that fails its own check after `preventDefault` gets no bubble and
 *    no focus move at all.
 *
 * Everything here runs in the browser only, from a submit handler.
 */

type Control = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

function isControl(node: unknown): node is Control {
    return (
        node instanceof HTMLInputElement ||
        node instanceof HTMLTextAreaElement ||
        node instanceof HTMLSelectElement
    );
}

/** Focus a control and bring it on screen, without fighting the smooth scroll. */
function reveal(control: Control): void {
    control.focus({ preventScroll: true });
    control.scrollIntoView({ block: "center", behavior: "smooth" });
}

/**
 * Complain about one named field, in the browser's own bubble.
 *
 * The message is attached with `setCustomValidity` and cleared on the next
 * keystroke, so the field does not stay stuck invalid after it is fixed.
 */
export function reportField(form: HTMLFormElement, name: string, message: string): void {
    const control = form.elements.namedItem(name);
    if (!isControl(control)) return;
    control.setCustomValidity(message);
    control.reportValidity();
    reveal(control);
    const clear = () => {
        control.setCustomValidity("");
        control.removeEventListener("input", clear);
    };
    control.addEventListener("input", clear);
}

/** Focus the first control the browser rejects. True when the form is usable. */
export function focusFirstInvalid(form: HTMLFormElement): boolean {
    if (form.checkValidity()) return true;
    for (const element of Array.from(form.elements)) {
        if (!isControl(element) || element.disabled) continue;
        if (element.checkValidity()) continue;
        element.reportValidity();
        reveal(element);
        return false;
    }
    form.reportValidity();
    return false;
}

/**
 * The gate a submit handler runs before it sends anything.
 *
 * `text` names the fields that must hold more than whitespace, in the order
 * they appear on screen, so the first empty one is the one focused.
 */
export function readyToSubmit(
    form: HTMLFormElement,
    text: { name: string; value: string; label: string }[] = [],
): boolean {
    if (!focusFirstInvalid(form)) return false;
    for (const field of text) {
        if (field.value.trim()) continue;
        reportField(form, field.name, `${field.label} cannot be blank.`);
        return false;
    }
    return true;
}
