# Housing

Members post rooms they have and rooms they want. A Listing is a short-lived classified ad
between two people who already know each other by name, so this board is about what is
free, where, when and for how much, and it stops there: the conversation that follows
happens off the platform.

Code: `backend/housing/`. Related decisions:
[ADR 0007](../../docs/adr/0007-bounded-contexts-follow-the-product-boards.md) for why the
board is a context of its own, and
[ADR 0006](../../docs/adr/0006-natural-language-ask-translates-to-filters.md) for the Ask.

## Language

**Listing**:
One classified ad by one member: a Kind, a title, a city, and whatever else they chose to fill in (area, price, rooms, Furnished, dates, Photos). Deliberately loose, because half of it is written at midnight from a phone; only the Kind, the title and the city are required.
_Avoid_: post, ad, offer (an offer is one of the two Kinds), property (nobody here is selling real estate), job listing (that is the job board's, and it is a Job)

**Kind**:
Which way round the ad points: `offer` for a room somebody has, `looking` for a room somebody wants. One board, two directions, because the same person is on both sides of it within a year.
_Avoid_: type, direction, demand/supply

**Owner**:
The member who posted the Listing. Only the Owner or an admin may edit, renew or delete it, and the Owner is taken from the caller rather than from the request body.
_Avoid_: author, poster (the job board uses Poster for a Job), landlord (they are usually subletting their own room)

**Status**:
Whether the Listing is still live: `open` or `closed`. Closed means the member took it down themselves. Ask never sees a closed Listing.
_Avoid_: active, archived, deleted (deleting is a real delete)

**Expiry**:
The moment a Listing drops off the board on its own, sixty days after it was posted or last renewed. Nothing is deleted at Expiry and the Status does not change: the board simply stops showing it, because a room that was free in March is not news in September.
_Avoid_: TTL in prose (that is the constant's name), deactivation, timeout

**Renew**:
The Owner saying the ad is still true. It pushes Expiry out by another sixty days from now and reopens the Listing if it had been closed, which is why "my listings" is the one view that shows expired rows: there would otherwise be nothing left to renew.
_Avoid_: bump, repost, refresh

**Furnished**:
Whether the room comes with furniture, as three states rather than two: yes, no, and null for "the owner did not say". Null is the interesting one. Listings written before the column existed all answer null, so a search for furnished rooms falls back to the words in the title and the description (`furnished`, `möbliert` and its unaccented spellings) for exactly those rows. A Listing that answered the question is taken at its word and never word-matched.
_Avoid_: has_furniture, equipped, `false` meaning unknown (that conflation is what the third state exists to prevent)

**View count**:
How many other members have opened the Listing. It exists so an Owner deciding whether to Renew can see whether anybody looked, so it counts other people looking and not the Owner refreshing their own page, and not an admin opening the Listing to moderate it. The board's list and detail replies fill it in for the Owner and an admin and return null to everybody else: "you are not being told" and "nobody has looked" are different answers, and a public popularity number would only push members towards whatever is already busy.
_Avoid_: views, popularity, impressions, hits

**Photos**:
Up to ten image URLs on a Listing. The images live in a private Storage bucket that only the API reads, so a photo URL points back at the media context and not at Supabase; the column is a plain array of those URLs and holds no upload state of its own.
_Avoid_: images in prose where Photos will do, attachments, gallery

**Ask**:
A plain-words housing question turned into the same filter object the board already queries with. Housing questions are the most formulaic of the three boards (a Kind, a place, a ceiling and a date), which is why the keyword translator is genuinely competitive here and the language model is optional rather than assumed.
_Avoid_: search (the ordinary filters are the search), query, natural language search

## Relationships

- A **Listing** belongs to exactly one **Owner**; deleting the member deletes their Listings (`ON DELETE CASCADE`)
- A **Listing** has exactly one **Kind** and one **Status**, both constrained in the database, and at most one **Expiry**
- **Renew** sets **Expiry** to sixty days from now and forces **Status** back to `open`; it is the only thing that reopens a closed Listing
- A **Listing** past its **Expiry** is hidden from the board and from **Ask**, and is shown only when somebody asks for one member's listings
- **View count** is incremented by a signed-in viewer who is neither the **Owner** nor an admin, in a write of its own that must never fail the read that caused it
- **Furnished** is answered by the **Owner** or left null; only null rows are word-matched
- A **Listing** has no messages, no replies and no applications. There is no messaging anywhere on this platform: members contact each other by e-mail, LinkedIn or Slack, all of which are outside it, so there is nothing for a message count to count
- **Ask** reads Listings and writes none, and only ever sees `open` ones

## Example dialogue

> **Dev:** "The Listing expired. Do we set the **Status** to `closed`?"
> **Domain expert:** "No. `closed` means the member took it down, usually because the room is gone. Expired means nobody has touched it in two months and we do not believe it any more. If they **Renew** it, we believe it again, and those two facts want to stay separate."

> **Dev:** "Should I default **Furnished** to false when the owner leaves it blank?"
> **Domain expert:** "Never. Someone searching for an unfurnished flat would then be shown every ad nobody bothered to fill in. Blank means we do not know, and for those we read the title and the description instead, which is the best guess we can honestly make."

> **Dev:** "Can we show the **View count** on the board so people can see what is popular?"
> **Domain expert:** "No. It is a number for the person deciding whether their ad is worth renewing. Showing it to everyone turns the board into a leaderboard, and the busy rooms get busier while a good room posted yesterday looks dead."

## Flagged ambiguities

- "listing" collided with the job board once the two products merged. Resolved: a **Listing** is housing, a Job is the job board's, and neither is called a posting.
- "offer" was used both for the **Kind** and for "a room that is available at all". Resolved: **Kind** is `offer` or `looking`, and availability is **Status** plus **Expiry**.
- "expired" and "closed" were used interchangeably in the UI copy. Resolved: **Expiry** is time passing, **Status** is a decision the **Owner** made.
- "views" suggested analytics. Resolved: **View count** is one integer on the row, shown to the **Owner** and an admin, and there is no event log, no session and no viewer identity kept anywhere.

## Where the language lives in the code

| Term | Code |
| --- | --- |
| Listing | `domain/housing.py` (`HousingListing`), table `housing_listings` |
| Kind | `domain/housing.py` (`HousingKind`), `housing_listings.kind` with a CHECK constraint |
| Owner | `housing_listings.member_id`, taken from the `Actor` in `application/housing_service.py` |
| Status | `domain/housing.py` (`HousingStatus`), `housing_listings.status` with a CHECK constraint |
| Expiry | `domain/housing.py` (`LISTING_TTL`, sixty days), `housing_listings.expires_at`, hidden by `HousingFilters.include_expired` |
| Renew | `HousingService.renew`, `POST /api/v1/housing/{listing_id}/renew` |
| Furnished | `housing_listings.furnished` (nullable boolean); `_FURNISHED_WORDS` and the fallback in `infrastructure/housing_repository.py` |
| View count | `housing_listings.view_count` (integer, default 0, CHECK `>= 0`), `HousingService.view` and `_for_viewer`, `SqlHousingRepository.record_view` |
| Photos | `housing_listings.photo_urls`, uploaded through `POST /api/v1/media` (`housing-photo`) |
| Ask | `domain/ask.py` (`HousingQuery`), `application/housing_ask_service.py`, `infrastructure/housing_ask_translator_rules.py` and `..._llm.py`, `POST /api/v1/housing/ask/` |
| Board | `GET /api/v1/housing/`, `application/ports.py` (`HousingFilters`) |
