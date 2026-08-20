## Database setup

Supabase CLI project root: **`infra/supabase/supabase/`** (see [`infra/supabase/README.md`](./infra/supabase/README.md)).

```bash
supabase login
supabase --workdir infra/supabase/supabase link --project-ref YOUR_20_CHAR_REF
supabase --workdir infra/supabase/supabase db push
```

Do not wrap the project ref in `<` `>`.
