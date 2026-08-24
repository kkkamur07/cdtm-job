# Ask: questions in plain words

Ask lets a Member type "who studied at Stanford and then went into VC" instead of learning
which filter box means what. There are three of them, one per board: the directory, housing
and the job board.

The Paths explorer and the Ask interaction are inspired by Henri Bayer's
[cdtm-paths](https://cdtm-paths.up.railway.app/), which showed what this should feel like
before this repository had anything like it.

> The model never sees a Member, a Job or a listing. It sees the question and answers with a
> filter object. Why that is the whole design is [ADR 0006](adr/0006-natural-language-ask-translates-to-filters.md).

## How it works

```text
  "who studied at Stanford and then went into VC"
                    |
                    v
   +-------------------------------------+
   |  AskService                         |
   |    validate (3..300 characters)     |
   |    meter    (ask_quota UPSERT, 429) |
   |    viewer   (class, year, location) |
   +------------------+------------------+
                      |
                      v
        QueryTranslator (a port, two implementations)
        +----------------------+       +------------------------+
        | LlmQueryTranslator   |  ...  | RulesQueryTranslator   |
        | strict JSON schema   | 503 ->| regexes, keyword tables|
        +----------+-----------+       +-----------+------------+
                   |                               |
                   +---------------+---------------+
                                   v
                    MemberQuery  (pydantic, extra="forbid")
                                   |
                                   v
                    MemberFilters -> SqlMemberRepository.search
                                   |
                                   v
      { interpretation, members, total }   (members context)
                                   |
                 every matching member id, not the page
                                   v
      PathFilters(member_ids=...) -> SqlPathRepository.flow
                                   |
                                   v
      { interpretation, members, total, flow }   (composed in api/ask.py)
```

The last two steps are the one place two contexts meet. `AskAnswer` in the members domain
has no flow in it; `AskAnswerPublic` in `backend/members/api/schemas.py` does, and
`backend/members/api/ask.py` calls the members service and then the paths service to fill it.
Nothing under `application/` or `domain/` knows the other board exists.

The interpretation goes back with the results, so the UI can show what was understood:

```json
{
  "summary": "Members studied at Stanford, now in Venture Capital.",
  "filters": { "school": "Stanford", "current_group": "Venture Capital" },
  "confidence": 0.7,
  "unresolved": [],
  "source": "rules"
}
```

`unresolved` is the honest part: phrases the translator could not map to anything. Show them.
A search box that quietly drops half the question is worse than one that says it did.

## The two translators

| | `LlmQueryTranslator` | `RulesQueryTranslator` |
| --- | --- | --- |
| Runs when | a provider is configured | always, as the fallback |
| Handles paraphrase | yes | no |
| `source` in the response | `llm` | `rules` |
| Cost | one completion per question | none |
| Where | `backend/{members,jobboard}/infrastructure/ask_translator_llm.py`, `backend/housing/.../housing_ask_translator_llm.py` | the same names ending `_rules.py` |

If the provider errors or times out, `LlmUnavailableError` is caught and the rules translator
answers instead, with `"LLM unavailable, keyword interpretation used"` appended to `unresolved`.
A search does not turn into a 503 because a third party is having a bad day.

The rules translator normalises the question, splits it into clauses on `,` / `who` / `and` /
`then` / `with`, and walks each clause through keyword tables (schools, cities, career groups,
study groups, intents) and a handful of regexes (`class of 2019`, `spring 2021`, `paying over
80k`, `posted this week`, `under 900`, `from October`). Anything a clause could not explain
lands in `unresolved`. Its confidence starts at 0.5 and rises 0.1 per mapped clause, capped at
0.9: it is never certain, and it says so.

## Viewer context

Four facts about the person asking are passed to the translator so that relative wording means
something. Nothing else about them is, and nothing about anybody else is.

| Field | Used for |
| --- | --- |
| `class_label` | "people from my class" |
| `class_year` | "everyone who came after me" |
| `location` | "founders near me" |
| `current_group` | "others doing what I do" |
| `today` | "posted this week", "free from October" |

With no viewer (an Account not yet bound to a Member), "my class" is reported as unresolved
rather than guessed.

## Answering in another language

Every request body takes an optional `language`, a short BCP-47 tag validated against
`LANGUAGE_PATTERN` in `backend/core/llm/ask.py` (`de`, `en-GB`, `pt-BR`). It is a pattern
rather than a closed list because the value is only ever interpolated into one prompt line,
and a closed list would mean shipping a release to answer somebody in Portuguese.

It decides the language of the `summary` and nothing else. Filter values stay in the
spellings the database uses, or "Wer arbeitet in Muenchen" would search for a city that is in
no row. Omit it and the model answers in the language the question was asked in.

The rules translator has no sentences beyond the ones in its own `describe()`, which are
English. Asked for anything else it says so, adding `summary language de` to `unresolved`
rather than pretending to translate.

```json
{ "question": "Wer arbeitet bei BMW und ist offen fuer Mentoring?", "language": "de" }
```

```json
{
  "summary": "Mitglieder, die aktuell bei BMW arbeiten und offen für Mentoring sind.",
  "filters": { "company": "BMW", "intents": ["mentoring"], "sort": "relevance" },
  "source": "llm"
}
```

## The three boards

Every field is optional. Enums are the ones the domain already had, so the values in
`GET .../ask/schema` are the values the filters accept.

### Directory: `POST /api/v1/members/ask/`

`q`, `school`, `degree`, `major`, `company`, `past_company`, `title`, `location`,
`class_label`, `class_year_min`, `class_year_max`, `study_group`, `first_step_group`,
`current_group`, `skills[]`, `languages[]`, `intents[]`, `roles[]`, `is_ca`, `limit`, `sort`.

`skills`, `languages` and `roles` match any of the values given; `intents` must all be true of
the same person, because "open to mentoring and investing" is one person who does both.

`study_group`, `first_step_group` and `current_group` take the names the path classifier
produces (`Venture Capital`, `Big Tech`, `Consulting`, ...). They are plain strings here: the
names belong to the Paths read model and the members context has no word for a career group.
`STUDY_GROUP_NAMES` and `CAREER_GROUP_NAMES` are injected into both translators as
constructor arguments (see `backend/members/api/deps.py`), go into the system prompt, and come
back out to be matched against `member_paths` as text. A name that is not in the injected list
is dropped from the filters rather than guessed at, so a renamed group can never turn into a
filter that silently matches nobody.

Answers carry a `flow` computed over the whole match set, not the returned page, so the Sankey
matches the number of results. It has four stages: `study`, `first_step`, `current` and
`intent`.

### Job board: `POST /api/v1/jobs/ask/`

`q`, `employment_type[]`, `work_arrangement[]`, `experience_level[]`, `city`, `country`,
`remote_only`, `company`, `is_cdtm_startup`, `salary_min`, `posted_within_days`, `limit`,
`sort`.

Reading the board is public; asking is not. A question costs money, so this endpoint is behind
`PrincipalDep` and metered per account. Only published jobs are ever searched.

### Housing: `POST /api/v1/housing/ask/`

`kind`, `city`, `district`, `min_price`, `max_price`, `available_from`, `available_until`,
`min_rooms`, `furnished`, `q`, `limit`.

Only open listings are searched. `furnished` is a real nullable column now: a listing that
answered the question is taken at its word. Null means the owner did not say, and only those
rows fall back to the words "furnished" / "möbliert" in the title and description, so the
guess is confined to the rows that predate the column instead of standing in for all of them.

### Every board also has

- `POST .../ask/explain` translates without searching, for a live "this is how I read it"
  preview. It shares the rate limit, because it costs the same call.
- `GET .../ask/schema` returns the strict JSON schema plus the allowed enum values, so the UI
  can render editable chips without hard-coding a list that will drift.

## Configuration

All in `backend/core/settings/llm.py`, prefix `LLM_`. An empty value counts as unset.

| Variable | Default | Meaning |
| --- | --- | --- |
| `LLM_PROVIDER` | `none` | `none`, `openai` or `anthropic`. `none` means the rules translator answers everything. |
| `LLM_API_KEY` | unset | Without it the provider is treated as unconfigured, whatever `LLM_PROVIDER` says. |
| `LLM_MODEL` | per provider | `gpt-5.6-luna` for `openai`, `claude-opus-5` for `anthropic`. |
| `LLM_BASE_URL` | per provider | Point `openai` at any OpenAI-compatible gateway (vLLM, OpenRouter, Azure) to run a local or cheaper model. |
| `LLM_TIMEOUT_S` | `20` | Per request. One retry on a 5xx or a transport error, then the rules fallback. |
| `LLM_MAX_QUESTIONS_PER_MINUTE` | `20` | Questions per caller per minute, counted in Postgres and shared by every instance. Over it is a 429 `rate_limited`. |

`openai` speaks Chat Completions with `response_format: json_schema, strict: true`;
`anthropic` speaks Messages with a forced tool call. Both are plain `httpx`, roughly a hundred
lines each, no SDK: the request shape is stable, and a dependency that ships its own HTTP
client and retry policy is not worth it for one endpoint.

### The rate limit

The limit protects a spend ceiling on one shared provider account, so it is counted where
every instance can see it. `SqlQuestionMeter` (`backend/core/llm/quota.py`) writes one UPSERT
per question into `ask_quota` and reads the new count back in the same round trip:

```sql
insert into ask_quota (member_key, window_start, asked)
values (:key, date_trunc('minute', now()), 1)
on conflict (member_key) do update
   set asked = case when ask_quota.window_start = date_trunc('minute', now())
                    then ask_quota.asked + 1 else 1 end,
       window_start = date_trunc('minute', now())
returning asked
```

`date_trunc` makes it a fixed window rather than a sliding one. A caller can therefore ask
twice the limit across a minute boundary, which is a rounding error against a spend ceiling
and buys a statement with no read-modify-write race in it. The meter commits on its own,
because the count has to survive a question that then fails validation.

The in-process token bucket is still there as the fallback: if the write fails,
`ask_limiter` answers instead. A per-worker bucket is wrong when several instances are
running, and it is much better than no limit at all while the database is unwell.

ADR 0006 carries an "Amended 2026-08-22" note recording this, since the ADR as written
described the per-process bucket as the whole story.

### Cost

A question is roughly 700 to 1200 prompt tokens (the system prompt carries the field list and
the group names) and under 100 completion tokens. Measured against `gpt-5.6-luna` in August
2026, a question took 1.5 to 5 seconds end to end, most of it the completion. At current small-model prices that is a
fraction of a cent per question, and a member asking all day is still noise. The thing to watch
is not the per-question cost but a UI calling `/explain` on every keystroke, which is why
`/explain` shares the meter with `/ask`.

## Working on it without credits

Nothing in the test suite reaches a provider. `tests/integration/conftest.py` sets
`LLM_PROVIDER=none` by assignment, not `setdefault`, precisely so a repository `.env` holding a
real key cannot make the suite spend money.

```bash
uv run poe test-fast                      # translators, adapters against a mock transport, schemas
uv run poe test-integration               # the endpoints, answering from keywords
uv run pytest tests/unit/test_ask_golden.py -q
```

To exercise a real provider by hand, set the variables and use `/explain`, which does not touch
the database:

```bash
LLM_PROVIDER=anthropic LLM_API_KEY=sk-... uv run poe serve
curl -s localhost:8000/api/v1/members/ask/explain \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"question":"who studied at Stanford and then went into VC"}' | jq
```

`LLM_BASE_URL` with `LLM_PROVIDER=openai` also points at a local server, so a laptop-sized model
is enough to develop against.

## Evaluating a change to the prompt

`tests/unit/test_ask_golden.py` holds thirty questions and the filters each must produce, one
of them asked in German. The rules translator must get all thirty right, always: it is what
answers when no provider is configured, and a regression there is a regression in the default
experience. The file injects `STUDY_GROUP_NAMES` and `CAREER_GROUP_NAMES` exactly the way
`backend/members/api/deps.py` does, so a group renamed in Paths and not here fails the suite,
which is the point.

The same set doubles as the provider evaluation, opt-in because it spends tokens:

```bash
ASK_EVAL_LLM=1 LLM_PROVIDER=openai LLM_API_KEY=sk-... \
  uv run pytest tests/unit/test_ask_golden.py -q
```

The bar is 80%: a model paraphrases, and one debatable reading in five is still a useful
feature. Below that, the prompt has regressed. When you change a system prompt, run it before
and after and compare the failure list, which the assertion prints.

A mocked transport proves the adapter parses a response; it does not prove the provider reads
questions. The evidence for that is a live call. On 2026-08-22, `gpt-5.6-luna` answered all
three boards with `"source": "llm"` against the development database: "who studied computer
science and works in venture capital in Munich?" became
`{"location": "Munich", "study_group": "Computer Science", "current_group": "Venture Capital"}`,
"furnished room in Schwabing under 900 euros from October" became
`{"kind": "offer", "district": "Schwabing", "max_price": 900, "available_from": "2026-10-01", "furnished": true}`,
and "working student roles in machine learning in Munich" became
`{"q": "machine learning", "employment_type": ["working_student"], "city": "Munich"}`. Re-run
that check after any prompt change.

Add a case whenever a question comes up that Ask reads wrongly. Thirty is a floor, not a target.

## Reading the logs

One line per question, on logger `backend.ask`, JSON, keys sorted:

```json
{"actor":"7f3c...","board":"members","filters":{"current_group":"Venture Capital","school":"Stanford"},
 "latency_ms":412,"model":"gpt-5.6-luna","question_length":44,"source":"llm","total":6,"unresolved":[]}
```

`board` is `members`, `housing` or `jobs`, one per Ask endpoint.

`question_length`, not the question. The filters are in there because they are the useful thing
to aggregate: which fields people actually reach for, how often `unresolved` is non-empty, how
often `source` falls back to `rules`. No member data is ever logged, and the question text is
not either, because the log is the one place the question and a member row could otherwise end
up side by side.

Useful things to watch:

- `source: "rules"` while a provider is configured means the provider is failing.
- A rising rate of non-empty `unresolved` is a list of features people are asking for.
- `total: 0` with high `confidence` means the filters are right and the directory is thin.
