/** Where the FastAPI backend lives. Read on both the server and the client. */
export const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ?? "http://localhost:8000";

export const API_PREFIX = "/api/v1";
