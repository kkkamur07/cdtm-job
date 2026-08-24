# Network

The edge between two Members: the people someone keeps a list of, and the introductions
they ask for. This context stores two member ids, a private note and a message, and nothing
else about either person. The names and faces it shows are read out of the member tables
through a port, because a saved row is about a relationship, not about a copy of somebody.

Code: `backend/network/`. Related decision:
[ADR 0007](../../docs/adr/0007-bounded-contexts-follow-the-product-boards.md).

## Language

**Saved member**:
A Member that another Member has put on their own list, with an optional private note. One row per pair, owned by whoever saved. Saving again replaces the note rather than adding a second row.
_Avoid_: bookmark, favourite (a favourite ranks people, and nothing here does), follow (following implies the other person is told, and they are not), connection

**Note**:
A line the saver writes to themselves about a Saved member, such as why they saved them. Private to the saver and never shown to the person it is about.
_Avoid_: comment, message (a **Message** belongs to an Intro request and the other person reads it), description, tag

**Intro request**:
One Member asking to be introduced to another, with a message and a status. It is a request between two people, not a delivered introduction: this platform records that it was asked and how it was answered, and the introduction itself happens elsewhere.
_Avoid_: introduction (that is the outcome, and we do not observe it), connection request, invite, message thread (there is one message and one answer, never a conversation)

**Requester**:
The Member who asked for the Intro request. The only person who may withdraw it.
_Avoid_: sender, from, owner (both people have a claim on the row, so "owner" decides nothing)

**Target**:
The Member the Intro request is about. The only person who may accept or decline it.
_Avoid_: recipient (nothing is delivered), receiver, to, requestee

**Intro status**:
Where a request stands: `pending`, `accepted`, `declined`, `withdrawn`. It moves out of `pending` exactly once; answering an already resolved request is a conflict, not an update.
_Avoid_: state, active (a `declined` and a `withdrawn` request are both inactive and say different things), reply

**Member card**:
The little this context is allowed to know about a Member: id, slug, name, headline, avatar, location, class label, major, current company and title, and whether they are a CA. Enough to draw someone in a list and no more.
_Avoid_: member, profile (the profile is `GET /api/v1/members/{slug}`, and it belongs to the members context), user, snapshot (nothing is stored; a card is read fresh every time)

**Member directory**:
The read port this context gets Member cards through. Implemented with raw `text()` queries against the member tables, the same seam identity uses to read `members.email`, so no ORM crosses the boundary.
_Avoid_: member service, repository (this context's repository owns its own two tables), client, API (nothing goes over the wire)

**Unknown member**:
The placeholder card shown when a saved row or an intro request points at a Member who is no longer in the directory. The row is still real and somebody really did save somebody, so it is shown as an unknown person rather than dropped or turned into a 500.
_Avoid_: deleted member, missing, error, null

## Relationships

- A **Saved member** row is one pair, keyed on the two ids: the saver and the saved. Saving somebody twice updates the **Note**
- Nobody may save themselves, and nobody may request an intro to themselves; both are refused by this context and again by a database CHECK
- An **Intro request** has exactly one **Requester**, one **Target**, one message, and one **Intro status**
- Only the **Requester** may withdraw; only the **Target** may accept or decline; an admin may do either
- An **Intro status** leaves `pending` once and never returns to it
- Saving somebody is one-sided and silent: the **Saved member** is not told, and no row is created on their side
- An **Intro request** is not a **Saved member** and neither creates the other
- This context stores no name, no face and no headline. Every **Member card** it shows is read through the **Member directory** at request time, and a card that cannot be read becomes the **Unknown member**
- Deleting a **Member** cascades: their saved rows and their intro requests go with them, in both directions

## Example dialogue

> **Dev:** "I will denormalise the name and avatar onto the saved row so the list is one query."
> **Domain expert:** "No. Then somebody changes jobs and their old title follows them around your saved list forever. The row is the fact that I saved them. Who they are is the directory's answer, and it should be today's answer."

> **Dev:** "Should saving somebody notify them?"
> **Domain expert:** "Definitely not. A saved list is my own note-keeping about people I want to remember. The moment the other person is told, it stops being that and becomes a friend request, which is a different product."

> **Dev:** "The **Target** ignored the request for a month. Should it expire to `declined`?"
> **Domain expert:** "No. `declined` means they answered no, and inferring an answer nobody gave is worse than leaving it `pending`. If the **Requester** has moved on they can withdraw it."

## Flagged ambiguities

- "connection" was used for both a saved row and an accepted intro. Resolved: a **Saved member** is one-sided and private; an **Intro request** is an ask with an answer. Neither is a mutual connection, and this platform has no such thing.
- "message" meant both the private **Note** and the intro **Message**. Resolved: the Note is written to yourself and nobody else reads it; the Message is written to the **Target** and they do.
- "member" in this package meant a full Member. Resolved: it is a **Member card**, a read shape, and the members context owns the person. The same distinction as identity's `domain/directory.py`.
- "my saved people" lived under `/community/me/*`, next to the entry and the intents. Resolved: those are things a Member maintains about themselves, and these are edges between two people, with two parties and their own rules about who may answer. That is a different board, so it moved to `/api/v1/network/*` under ADR 0007.

## Where the language lives in the code

| Term | Code |
| --- | --- |
| Saved member | `domain/social.py` (`SavedMember`), table `saved_members`, `GET/PUT/DELETE /api/v1/network/saved` |
| Note | `saved_members.note`, `application/commands.py` (`SaveMember`) |
| Intro request | `domain/social.py` (`IntroRequest`), table `intro_requests`, `POST /api/v1/network/intros` |
| Requester | `intro_requests.requester_member_id`, taken from the caller in `application/network_service.py` |
| Target | `intro_requests.target_member_id`, `application/commands.py` (`IntroRequestCreate`) |
| Intro status | `domain/social.py` (`IntroStatus`), `intro_requests.status` with a CHECK constraint, `POST /api/v1/network/intros/{id}/respond` |
| Who may answer | `application/network_service.py` (`respond_intro`) |
| Member card | `domain/card.py` (`MemberCard`), `api/schemas.py` (`NetworkMemberPublic`) |
| Member directory | `application/ports.py` (`MemberDirectory`), `infrastructure/member_directory.py` (`SqlMemberDirectory`, `_EXISTS`, `_CARDS`) |
| Unknown member | `application/network_service.py` (`_UNKNOWN`, `_cards`) |
| Not yourself | `network_service.py` (`save`, `request_intro`) and the `not_self` CHECK on both tables |
