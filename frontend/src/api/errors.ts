/**
 * The backend answers every failure with the same envelope:
 *
 *   { "error": { "code", "message", "ref", "details"? } }
 *
 * plus an `X-Error-ID` header. Everything the UI shows about a failure comes
 * from here, so error copy is written once rather than per call site.
 */

export type ErrorEnvelope = {
    code: string;
    message: string;
    ref: string;
    details?: unknown;
};

export class ApiError extends Error {
    readonly status: number;
    readonly code: string;
    readonly ref: string | null;
    readonly errorId: string | null;
    readonly details: unknown;

    constructor(init: {
        status: number;
        code: string;
        message: string;
        ref?: string | null;
        errorId?: string | null;
        details?: unknown;
    }) {
        super(init.message);
        this.name = "ApiError";
        this.status = init.status;
        this.code = init.code;
        this.ref = init.ref ?? null;
        this.errorId = init.errorId ?? null;
        this.details = init.details;
    }

    /** Signed in with the wrong account, or not signed in at all. */
    get isAuth(): boolean {
        return this.status === 401;
    }

    /** Signed in, but the backend will not let this account do this. */
    get isForbidden(): boolean {
        return this.status === 403;
    }

    /**
     * The account exists but is not bound to a member row yet. Every write
     * endpoint answers this way, and the UI has a dedicated screen for it.
     */
    get isUnlinked(): boolean {
        return this.status === 403 && /member/i.test(`${this.code} ${this.message}`);
    }

    get isNotFound(): boolean {
        return this.status === 404;
    }

    /** Too many questions in a row. Ask answers 429 with a `rate_limited` code. */
    get isRateLimited(): boolean {
        return this.status === 429;
    }

    /** The body was rejected before anything ran: a question too short or too long. */
    get isInvalid(): boolean {
        return this.status === 422;
    }
}

function readEnvelope(body: unknown): ErrorEnvelope | null {
    if (!body || typeof body !== "object") return null;
    const error = (body as { error?: unknown }).error;
    if (!error || typeof error !== "object") return null;
    const { code, message, ref, details } = error as Record<string, unknown>;
    if (typeof message !== "string") return null;
    return {
        code: typeof code === "string" ? code : "unknown",
        message,
        ref: typeof ref === "string" ? ref : "",
        details,
    };
}

export function toApiError(response: Response, body: unknown): ApiError {
    const envelope = readEnvelope(body);
    return new ApiError({
        status: response.status,
        code: envelope?.code ?? `http_${response.status}`,
        message: envelope?.message ?? fallbackMessage(response.status),
        ref: envelope?.ref,
        errorId: response.headers.get("X-Error-ID"),
        details: envelope?.details,
    });
}

function fallbackMessage(status: number): string {
    if (status === 401) return "Sign in to continue.";
    if (status === 403) return "You do not have access to this.";
    if (status === 404) return "We could not find that.";
    if (status === 422) return "Some of the details were not accepted.";
    if (status === 429) return "That is a lot of questions at once. Give it a few seconds.";
    if (status >= 500) return "The service is having trouble. Try again in a moment.";
    return "Something went wrong.";
}

/** One place that turns anything thrown by a query into copy for a human. */
export function errorMessage(error: unknown): string {
    if (error instanceof ApiError) return error.message;
    if (error instanceof TypeError) {
        return "Could not reach the API. Check that the backend is running.";
    }
    if (error instanceof Error && error.message) return error.message;
    return "Something went wrong.";
}
