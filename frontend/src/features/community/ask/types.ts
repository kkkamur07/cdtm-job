import type { components } from "@/api/schema";

/**
 * Ask, in the shapes the backend actually returns.
 *
 * These were hand-written against the API design while `/ask` was being
 * finished; the endpoints are in the committed `openapi/openapi.json` now, so
 * every alias below points at the generated schema and nothing here restates a
 * field. A backend rename shows up as one compile error in this file.
 */

type S = components["schemas"];

export type AskAnswer = S["AskAnswerPublic"];
export type AskInterpretation = S["AskInterpretationPublic"];
export type AskSchema = S["AskSchemaPublic"];
export type MemberQuery = S["MemberQuery"];

export type JobAskAnswer = S["JobAskAnswerPublic"];
export type JobAskInterpretation = S["JobAskInterpretationPublic"];
export type JobQuery = S["JobQuery"];

export type HousingAskAnswer = S["HousingAskAnswerPublic"];
export type HousingAskInterpretation = S["HousingAskInterpretationPublic"];
export type HousingQuery = S["HousingQuery"];

/** The three interpretations differ only in their filter object. */
export type AnyInterpretation = {
    summary: string;
    filters: Record<string, unknown>;
    confidence: number;
    unresolved?: string[];
    source: "llm" | "rules";
};
