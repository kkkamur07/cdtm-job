import type { components, operations } from "./schema";

/**
 * Readable aliases for the generated component schemas. Feature code imports
 * from here so a rename in the backend shows up as one compile error in this
 * file rather than a hundred across the app.
 */

type S = components["schemas"];

export type Me = S["MePublic"];
export type Account = S["AccountPublic"];

export type Member = S["MemberPublic"];
export type MemberProfile = S["MemberProfilePublic"];
export type SelfProfileCreate = S["SelfProfileCreate"];
export type MembersPage = S["MembersPublic"];
export type DirectoryFacets = S["DirectoryFacets"];
export type Avatar = S["Avatar"];
export type ClassRef = S["ClassRef"];
export type Position = S["Position"];
export type Education = S["Education"];
export type MemberPath = S["MemberPathPublic"];
export type PathMember = S["PathMemberPublic"];
export type Role = S["Role"];

export type Entry = S["EntryPublic"];
export type EntryUpsert = S["EntryUpsert"];
export type ContactPreference = S["ContactPreference"];
export type Visibility = S["Visibility"];

export type Intents = S["IntentsPublic"];
export type IntentsUpsert = S["IntentsUpsert"];

/** One row of the saved list: the member, plus the note and when it was saved. */
export type SavedMemberRow = S["SavedMemberPublic"];
export type SavedMember = S["SavedMember"];
/**
 * The trimmed member the network endpoints return: same person, avatar flattened
 * onto the row instead of nested. `avatarOf` in `./people` reads either shape.
 */
export type NetworkMember = S["NetworkMemberPublic"];
export type IntroRequest = S["IntroRequest"];
export type IntroRequestPublic = S["IntroRequestPublic"];
export type IntroStatus = S["IntroStatus"];

export type CommunityEvent = S["EventPublic"];
export type EventCreate = S["EventCreate"];
export type EventUpdate = S["EventUpdate"];
export type EventKind = S["EventKind"];
export type RsvpStatus = S["RsvpStatus"];

export type Announcement = S["AnnouncementPublic"];
export type AnnouncementCreate = S["AnnouncementCreate"];

export type HousingListing = S["HousingListingPublic"];
export type HousingCreate = S["HousingCreate"];
export type HousingUpdate = S["HousingUpdate"];
export type HousingKind = S["HousingKind"];
export type HousingStatus = S["HousingStatus"];

export type PathFlow = S["PathFlowPublic"];
export type PathGroups = S["PathGroupsPublic"];
export type PathNode = S["PathNode"];
export type PathLink = S["PathLink"];

export type MediaUploadResult = S["MediaUploadPublic"];
export type DevMemberOption = S["DevMemberOption"];

export type Company = S["CompanyPublic"];
/** One member who works at a named company, from the batched at-company lookup. */
export type CompanyContact = S["CompanyContactPublic"];
export type CompanyContacts = S["CompanyContactsPublic"];
export type CompanyCreate = S["CompanyCreate"];
export type Job = S["JobPublic"];
export type JobCreate = S["JobCreate"];
export type JobStatus = S["JobStatus"];
export type EmploymentType = S["EmploymentType"];
export type ExperienceLevel = S["ExperienceLevel"];
export type WorkArrangement = S["WorkArrangement"];
export type CompanySizeBand = S["CompanySizeBand"];
export type SalaryPeriod = S["SalaryPeriod"];

/** Query params, taken from the operation rather than restated by hand. */
export type MemberSearchParams = NonNullable<
    operations["search_members_api_v1_members__get"]["parameters"]["query"]
>;
export type JobSearchParams = NonNullable<
    operations["list_jobs_api_v1_jobs__get"]["parameters"]["query"]
>;
export type HousingSearchParams = NonNullable<
    operations["list_listings_api_v1_housing__get"]["parameters"]["query"]
>;
