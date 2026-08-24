# Announcements

The school tells the community something, once, and the community reads it. This context owns
what was said, when it should be on the board, and who has seen it. Writing is an Admin act;
reading is every Member's, and a read is recorded as a fact rather than a preference.

Code: `backend/announcements/`. Route prefix `/api/v1/announcements`, which was
`/api/v1/community/announcements` before the split. Related decisions:
[ADR 0007](../../docs/adr/0007-bounded-contexts-follow-the-product-boards.md),
[ADR 0001](../../docs/adr/0001-google-workspace-account-is-the-identity.md).

## Language

**Announcement**:
One thing the school is telling everyone: a title and a body, with a window during which it belongs on the board. It is addressed to the whole community, never to a person or a class.
_Avoid_: post, notice, message (a message has a recipient and an answer; this has neither), news item

**Author**:
The Member behind the Admin who wrote it, kept so the board can say who is speaking. Optional, and it survives them: deleting the Member leaves the Announcement with no Author rather than removing it.
_Avoid_: admin (the Admin flag is on an Account in `identity`, and what is stored here is a member id), sender, owner, publisher

**Published at**:
The moment the Announcement is due on the board. Unset means it is a draft that only an Admin can see; set in the future means it is scheduled and appears when that moment passes; set in the past is the ordinary case, and creating one without saying otherwise stamps it now.
_Avoid_: publish date, live at, status (there is no status column; this timestamp is the whole answer)

**Expires at**:
When it should come off the board. Optional, and it is about the feed rather than the record: an expired Announcement stops being listed and stops counting as unread, and it is neither deleted nor edited by expiring.
_Avoid_: deleted at, archived at, valid until

**Visible**:
The state of being on the board right now: published, that moment has passed, and it has not expired. Drafts and scheduled ones are visible to an Admin listing them, and to nobody else.
_Avoid_: active, live, current, public (everything here is community-wide already)

**Pinned**:
Held at the top of the board regardless of its date. A flag on the Announcement, not a separate kind of Announcement, and it changes only the order.
_Avoid_: featured, sticky, important, priority

**Read receipt**:
The fact that one Member opened one Announcement, with the moment it happened. Written once and never rewritten: reading again changes nothing, and there is no way to make something unread again.
_Avoid_: read status, read flag, seen (a receipt is an event that happened, not a switch)

**Read count**:
How many Members have a **Read receipt** for this Announcement. Everyone's number, the same for every caller, and it is what tells an Admin whether anything landed.
_Avoid_: views, reach, opens

**Is read**:
Whether the signed-in Member has a receipt for this one. The same rows as **Read count**, seen from one viewer; a caller with no Member behind their Account always sees false.
_Avoid_: my read, seen by me, unread (that is the absence of this, and it has its own count)

**Unread count**:
How many **Visible** Announcements this Member has no receipt for. It travels on the list rather than on any single Announcement, because it is a fact about the board, and it is zero for an Account with no Member.
_Avoid_: badge, notifications, inbox count

## Relationships

- An **Announcement** has at most one **Author**, held as a member id; deleting that Member sets the id to null and keeps the Announcement
- An **Announcement** has many **Read receipts**, at most one per Member, keyed on the pair; deleting either side removes the receipt
- Only an **Admin** may create, edit or delete an **Announcement**; any signed-in Member with a Member behind their Account may mark one read
- Marking read requires the Announcement to be readable by that caller in the first place, so nobody collects a receipt for a draft
- **Visible** is decided by **Published at** and **Expires at** together, and only Admins are shown anything outside that window
- **Pinned** Announcements sort first; everything else sorts by **Published at**, most recent first, falling back to when the row was created
- **Read count** and **Is read** come from the same receipts, one counted for everyone and one tested for the viewer; **Unread count** counts **Visible** Announcements with no receipt for this Member
- An **Announcement** knows a Member only as an id. It never joins to `members`, and the UI turns the **Author** id into a name and a face through `GET /api/v1/members/lookup?ids=`, which is the ADR 0007 rule for every row that belongs to a Member
- Reading the board requires being signed in

## Example dialogue

> **Dev:** "A Member wants to announce their startup is hiring. Do they get write access?"
> **Domain expert:** "No. An **Announcement** is the school speaking to everyone, and that is why people read them. If Members could write here it would become a feed and stop being read. Hiring goes on the job board, and asking a person goes through the network."

> **Dev:** "Should marking something read be a toggle, so people can flag it to come back to?"
> **Domain expert:** "No, a **Read receipt** is a thing that happened. They did open it. What you are describing is saving something for later, which is a different feature and would be their own list, not our record."

> **Dev:** "This one expired last week. Delete the row?"
> **Domain expert:** "Never. **Expires at** is about the board, not the archive. It leaves the list and stops counting as unread, and the announcement still exists, still has its receipts, and a link someone kept still opens it."

## Flagged ambiguities

- "published" collides with the job board, where **Status** `published` is one of four values on a Job. Resolved: an Announcement has no status. It has **Published at**, a moment, which also carries the draft and the scheduled cases.
- "author" was used for both the Admin's Account and the Member. Resolved: the row stores a member id, so the **Author** is a Member. Whether that person is still an Admin is `identity`'s business and is not frozen here.
- "read" is both the verb and the record. Resolved: a Member reads an Announcement, and the record of it is a **Read receipt**. `is_read` is the viewer's answer, `read_count` is everyone's.
- "unread count" was briefly a per-announcement number. Resolved: it is a fact about the board for one Member, so it lives on the list envelope and on no Announcement.
- "pinned" and "featured" were used for the same flag. Resolved: **Pinned**, and it only changes the order.

## Where the language lives in the code

| Term | Code |
| --- | --- |
| Announcement | `domain/announcements.py` (`Announcement`), table `announcements` |
| Author | `announcements.author_member_id`, `ON DELETE SET NULL`; filled from the caller in `application/announcement_service.py` |
| Published at | `announcements.published_at`; defaulted to now on create in `infrastructure/announcements_repository.py` |
| Expires at | `announcements.expires_at` |
| Visible | `infrastructure/announcements_repository.py` (`_visible`), the one place the window is spelled out |
| Pinned | `announcements.is_pinned`, first key in the list's `ORDER BY` |
| Read receipt | table `announcement_reads`, primary key `(announcement_id, member_id)`, written once in `mark_read` |
| Read count | correlated subquery in `infrastructure/announcements_repository.py` (`_select`) |
| Is read | `Announcement.is_read`, an `EXISTS` for `viewer_member_id` in the same query |
| Unread count | `unread_count` in the repository, `AnnouncementsPublic.unread` on the list response |
| Who may write | `application/announcement_service.py`, `actor.is_admin` on create, update and delete |
