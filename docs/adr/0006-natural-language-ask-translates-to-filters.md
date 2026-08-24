# 0006. A natural-language question is translated into filters, never into a query

- Status: Accepted
- Date: 2026-08-22
- Scope of this record: where a language model sits in the Ask feature, what it is allowed to
  emit, and what it is never shown. It applies to all three boards that accept a question:
  the directory, the job board and housing.

## Context

Finding someone in the directory works well if you already know the vocabulary the filters
use. You have to know that the thing you want is `current_group=Venture Capital` and not a
company name, that cohorts are called `class_label` and are spelled `Fall 2019`, that a school
lives on an education row rather than on the member. People do not ask questions that way.
They ask "who studied at Stanford and then went into VC", and then give up when the filter
bar does not have a box for it.

Henri Bayer's [cdtm-paths](https://cdtm-paths.up.railway.app/) showed the shape of the answer
long before this repository had one: ask in plain words, see where people went. The Paths
explorer here and this Ask interaction are both inspired by it.

The obvious implementation is the wrong one. Handing a model a database connection, or letting
it write SQL, or feeding it member rows and asking it to pick, all put member data and the
database itself inside the blast radius of a prompt. This is a directory of real people's
careers, e-mail addresses and locations, most of whom never signed in and never agreed to
anything. And a model that writes queries is a model that can write a slow one, a wrong one,
or one that reads a table it was not supposed to.

## Decision

The model translates the question into a **filter object** and stops there.

```text
question -> translator -> MemberQuery (pydantic, extra="forbid") -> MemberFilters -> repository
```

Concretely:

- `MemberQuery`, `JobQuery` and `HousingQuery` live in `domain/ask.py` in their own contexts.
  Every field is optional, every enum field is a `StrEnum` the domain already had, `limit` is
  clamped to 100, and `extra="forbid"` means an invented field is a validation error rather
  than a silently ignored one.
- The provider is asked for exactly that object, in strict structured-output mode: OpenAI-shaped
  providers get `response_format: json_schema` with `strict: true`, Anthropic gets a forced
  tool call. `backend/core/llm/schema.py` derives both from the pydantic model, so the schema
  cannot drift from the type.
- The model never sees a member, a job or a listing. Its entire input is the question, plus a
  system prompt naming the fields and the allowed group names, plus a **viewer context** of
  four facts about the person asking (class label, class year, location, current career group)
  so that "my class" and "near me" mean something.
- Translation is a **port**, `QueryTranslator`, with two implementations: `LlmQueryTranslator`
  and `RulesQueryTranslator`. The rules translator is regular expressions and keyword tables.
  It is the fallback, and it is what runs when no provider is configured.
- The interpretation is returned to the caller alongside the results: summary, filters,
  confidence, and the phrases it could not map. The UI renders it as editable chips.

## Rationale

**The blast radius is a filter object.** The worst a hostile question can do is produce filters
that match nothing, or filters the asker can already set by hand in the UI. There is no query
to inject into, no row to exfiltrate, and no need to reason about what the model "saw", because
it saw a sentence.

**Determinism where it matters.** The same `MemberFilters` runs whether the filters came from a
model, from the rules translator or from the query string. Ask cannot return results the
directory endpoint would not, cannot rank differently, and cannot bypass visibility redaction,
because it does not have its own read path.

**It has to work with no credits and no network.** `LLM_PROVIDER=none` is the default and the
setting the whole test suite runs under. A contributor with no API key gets a working Ask box,
a slightly blunter one. That also means the feature degrades rather than breaks when a provider
is down: `LlmUnavailableError` falls back to keywords and says so in `unresolved`.

**Showing the interpretation is the product, not a debug affordance.** A search box that
silently reinterprets the question trains people to distrust it. Chips that say "Stanford",
"Venture Capital" and "could not read: in the AI space" tell the asker exactly what was
searched and let them fix it.

**Alternatives considered:**

- *Text to SQL.* Rejected. Every mitigation (read-only role, statement timeout, allow-listed
  tables, a parser in front) is machinery protecting against a risk we can simply not take.
- *Retrieval: embed member profiles, search by vector.* Rejected for now. It requires copying
  member data into an index, and it answers "who is similar to this description" rather than
  "who matches these facts". Questions here are mostly factual conjunctions, which is what a
  `WHERE` clause is for. Worth revisiting for "find someone like X".
- *Give the model the search results and let it pick.* Rejected: that is the design where
  member data reaches the provider, and it makes the answer unreproducible.
- *Rules only, no model.* Rejected as the whole feature, kept as the floor. Regular expressions
  cannot handle paraphrase, and the keyword tables would grow forever.

## Consequences

- **Adding a filter is a four-file change**: the field on the query model, the mapping to
  `XFilters`, the predicate in the repository, and a line in the system prompt. Forgetting the
  prompt means the model never emits the field; forgetting the mapping means it is emitted and
  ignored. The golden set in `tests/unit/test_ask_golden.py` catches the second.
- **The strict-mode schema is lossy.** Structured output rejects `minLength`, `maximum`,
  `pattern` and friends, so `strict_json_schema` strips them and every property is marked
  required and nullable. The pydantic model still enforces the real constraints on the way in;
  the schema is a hint to the model, not the validation.
- **Asking costs money, so asking is authenticated and metered.** Reading the job board stays
  public; `POST /jobs/ask` does not. An in-process token bucket
  (`LLM_MAX_QUESTIONS_PER_MINUTE`, one bucket per member) returns 429. It is per process, which
  is honest about what it is: a guard against a runaway UI, not a billing control. A second
  instance doubles the ceiling.
- **One structured log line per question**, on logger `backend.ask`, carrying the actor id, the
  question's length, the source, the model, latency and the resulting filters. Never the
  question text and never a member row, because that log is the one place the two could meet.
- **Housing "furnished" is matched on words in the title and description**, since no column
  records it. It is the one filter that is a guess rather than a fact, and it is documented as
  such in the repository.
- Filters are shared with the Paths flow: `PathFilters.members` carries a `MemberFilters` and is
  applied as a correlated `EXISTS`, so the Sankey an Ask answer draws is over the whole match
  set rather than the page.

## Amendments

Amended 2026-08-22: the per-process token bucket is now a fallback. The meter of record is the
`ask_quota` table, written by one UPSERT per question (`SqlQuestionMeter` in
`backend/core/llm/quota.py`), so the ceiling is the same however many API instances are
running; the in-process bucket takes over only when that write fails. Housing `furnished` is a
real nullable boolean column, and the word match on the title and description survives only as
the fallback for rows where nobody answered. The three Ask endpoints take an optional
`language` parameter that decides which language the summary comes back in; the filters are
unaffected by it. `PathFilters.members` is `PathFilters(member_ids=...)` since the Paths split:
the members context resolves its own match set and hands the ids over, because Paths may not
read `MemberFilters`.
