# Events

Something is happening at a time and a place, and Members say whether they are coming. This
context owns the calendar and the answers to it, and nothing else: it records intentions,
never attendance, and it knows a Member only as an id.

Code: `backend/events/`. Route prefix `/api/v1/events`, which was `/api/v1/community/events`
before the split. Related decisions:
[ADR 0007](../../docs/adr/0007-bounded-contexts-follow-the-product-boards.md),
[ADR 0002](../../docs/adr/0002-one-backend-for-community-and-job-board.md).

## Language

**Event**:
One occasion with a start: a title, when it starts, optionally when it ends, optionally where, optionally a link. Everything else about it is a description.
_Avoid_: meetup, session, activity, posting (the job board posts things; this one happens)

**Kind**:
Who is behind the Event: `cdtm` (the school itself), `community` (a Member organised it) or `external` (someone else's event worth knowing about). It changes how the Event is labelled and nothing about how it behaves.
_Avoid_: type, category, source

**Organiser**:
The Member who created the Event, kept so the page can say who to ask and so the right person may edit it. Optional: an Event outlives the Member row it came from, and a deleted Member leaves the Event standing with no Organiser.
_Avoid_: host (nobody is hosting anything in the data, and an external Event has an organiser we did not record), owner, creator, author

**Published**:
Whether the Event appears in the calendar at all. An unpublished Event is a draft that stays out of the list; it is not a cancellation and not a past Event.
_Avoid_: active, live, visible, draft as a status word (there is no status column, only this flag)

**Upcoming**:
An Event that has not finished yet: its end, or its start when it has no end, is still in the future. The calendar asks for upcoming Events by default and shows them soonest first; asking for the rest shows them most recent first.
_Avoid_: future (an Event running right now is upcoming and is not in the future), current, active

**RSVP**:
One Member's answer about one Event. There is exactly one per pair, so answering again replaces the previous answer rather than adding to it, and clearing it removes the answer entirely.
_Avoid_: registration, ticket, signup, booking (none of those exist; nothing is reserved by answering)

**RSVP status**:
What the answer says: `going`, `interested` or `declined`. Absent is a fourth, different thing: it means they have not answered, which is not the same as `declined`.
_Avoid_: yes/no/maybe, attending (see **Attendance**)

**Going count** and **Interested count**:
How many Members currently say `going`, and how many say `interested`. Counted live from the RSVPs, never stored on the Event. `declined` is counted nowhere, on purpose: the page has no use for how many people said no.
_Avoid_: attendee count, headcount, capacity used

**My RSVP**:
The signed-in Member's own answer, resolved per request and attached to the Event they are reading. It is the same data as the RSVP, seen from one viewer; a caller with no Member behind their Account always sees null.
_Avoid_: user RSVP, current RSVP, status (that is the answer's own word)

**Attendance**:
Not a thing here. Nobody checks in, nothing is scanned, and no Event records who actually turned up. `going` is a stated intention on the day someone stated it.
_Avoid_: attendee, checked in, turnout

**Capacity**:
Also not a thing here. An Event has no seat limit, no waitlist and no cut-off, so an RSVP can never be refused and `going` is never a seat.
_Avoid_: spots, seats, limit, sold out

**Location**:
Free text describing where: a room, an address, a city, or a sentence about a video call. It is not a structured place, is not matched against anything, and is not the **URL**.
_Avoid_: venue, address, place

## Relationships

- An **Event** has at most one **Organiser**, held as a member id; deleting that Member sets the id to null and keeps the Event
- An **Event** has many **RSVPs**, at most one per Member, keyed on the pair; deleting either the Event or the Member removes the RSVP
- An **RSVP** has exactly one **RSVP status**; removing the RSVP is how a Member takes their answer back, and it is not a status
- **Going count** and **Interested count** are derived from the RSVPs on every read; **My RSVP** is derived from the same rows for one viewer
- Only the **Organiser** or an **Admin** may edit or delete an **Event**; any signed-in Member with a Member behind their Account may RSVP to one
- Reading the calendar requires being signed in, the same as Housing: both boards are for Members, not the internet
- An **Event** knows a Member only as an id. It never joins to `members`, and the UI turns the Organiser id into a name and a face through `GET /api/v1/members/lookup?ids=`, which is the ADR 0007 rule for every row that belongs to a Member
- An **Event** has no **Capacity** and records no **Attendance**, so nothing about it can be full, closed or missed

## Example dialogue

> **Dev:** "Forty people are `going`. Is that the turnout?"
> **Domain expert:** "No, that is forty people who said they meant to come, some of them weeks ago. We have no idea who walked in. If we ever want turnout, that is a new thing to record on the day, not this number read later."

> **Dev:** "Can we cap the workshop at twenty and refuse the twenty-first RSVP?"
> **Domain expert:** "Not with what we have. There is no **Capacity** here, so an RSVP is never refused and `going` is not a seat. Organisers cap things in the description today and sort it out themselves."

> **Dev:** "Someone answered `declined` and now wants to un-answer. Do we set it back to `declined`?"
> **Domain expert:** "They already did that. Send no status at all and the **RSVP** disappears, which is different: `declined` is a stated no, and nothing at all is no answer. The organiser reads those two differently."

## Flagged ambiguities

- "host" and "organiser" were both used for whoever created an Event. Resolved: **Organiser**, and it is a member id we happen to have, not a role anyone holds. An `external` Event has a real-world organiser who is not in this data at all.
- "published" collides with the job board, where **Status** `published` is one of four values on a Job. Resolved: an Event is **Published** or not, one boolean, and the word never means a lifecycle step here.
- "attendee" was used for anyone with a `going` RSVP. Resolved: there are no attendees, only answers. See **Attendance**.
- "community" is both an Event **Kind** and the name of the context this one was carved out of. Resolved: the context is gone, so the word is free; `community` on an Event means a Member organised it.

## Where the language lives in the code

| Term | Code |
| --- | --- |
| Event | `domain/events.py` (`Event`), table `events` |
| Kind | `domain/events.py` (`EventKind`), `events.kind` with a CHECK constraint |
| Organiser | `events.created_by_member_id`, `ON DELETE SET NULL`; filled from the caller in `application/event_service.py` |
| Published | `events.is_published`; the list filters on it, a direct read by id does not |
| Upcoming | `infrastructure/events_repository.py`, `coalesce(ends_at, starts_at) >= now()`, and the sort order that follows from it |
| RSVP | `domain/events.py` (`Rsvp`), table `event_rsvps`, primary key `(event_id, member_id)` |
| RSVP status | `domain/events.py` (`RsvpStatus`), `event_rsvps.status` with a CHECK constraint |
| Clearing an RSVP | `application/commands.py` (`RsvpSet`, null status), `infrastructure/events_repository.py` (`set_rsvp`) |
| Going count, Interested count | correlated subqueries in `infrastructure/events_repository.py` (`_with_counts`) |
| My RSVP | `Event.my_rsvp`, resolved from `viewer_member_id` in the same query |
| Location | `events.location`, free text, distinct from `events.url` |
| Who may edit | `application/event_service.py` (`update`, `delete`), Organiser or Admin |
