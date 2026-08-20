/**
 * Mirrors what scripts/ingest.mjs writes. Every field is either a required
 * primitive or explicitly nullable — the ingest script has already collapsed
 * empty strings and missing nested paths to null, so nothing downstream needs
 * to guard against `undefined`.
 */

export type ClassRef = {
    id: number;
    label: string;
    season: string | null;
    year: number;
    location: number | null;
};

export type Avatar = {
    sm: string;
    lg: string;
    /** 16px WebP data URI, inlined in index.json. Null if no photo was fetched. */
    blur: string | null;
};

export type Role = "student" | "ca" | "faculty";

export type MatchMethod =
    | "override"
    | "exact"
    | "variant"
    | "fold"
    | "truncated-surname"
    | "firstname-prefix"
    | "claim-elimination"
    | "ranked"
    | "arbitrary";

/** Tile-sized record. ~1000 of these ship in one file. */
export type Member = {
    id: string;
    name: string;
    firstName: string | null;
    lastName: string | null;
    headline: string | null;
    avatar: Avatar | null;
    location: string | null;
    linkedInUrl: string | null;
    personId: number | null;
    classes: ClassRef[];
    classLabel: string | null;
    major: string | null;
    roles: Role[];
    isCA: boolean;
    caAlumni: boolean | null;
    matched: boolean;
    matchMethod: MatchMethod | null;
    needsReview: boolean;
    company: string | null;
    title: string | null;
};

export type MemberIndex = {
    generatedAt: string;
    counts: {
        members: number;
        matched: number;
        withAvatar: number;
        ca: number;
        rosterRows: number;
    };
    classes: ClassRef[];
    majors: string[];
    members: Member[];
};

export type Position = {
    title: string | null;
    company: string | null;
    companyUrl: string | null;
    description: string | null;
    location: string | null;
    start: string | null;
    end: string | null;
    dateRange: string | null;
    current: boolean;
};

export type School = {
    school: string | null;
    degree: string | null;
    dateRange: string | null;
};

export type CaDetail = {
    alumni: boolean;
    about: string | null;
    responsibilities: string[];
    researchFields: string[];
    email: string | null;
};

/** Fetched on demand when a tile is opened. */
export type Profile = Omit<Member, "firstName" | "lastName" | "company" | "title"> & {
    rosterName: string | null;
    ca: CaDetail | null;
    summary: string | null;
    positions: Position[];
    schools: School[];
    skills: string[];
    languages: string[];
    company: {
        name: string | null;
        tagline: string | null;
        description: string | null;
        industry: string | null;
        website: string | null;
        linkedInUrl: string | null;
        employeeCount: number | null;
        foundedYear: number | null;
        location: string | null;
        specialities: string[];
    } | null;
};