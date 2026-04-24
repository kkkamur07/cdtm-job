## Database setup 

We are using `supabase` to manage our postgres instance. For that you need to create the directory supabase and have the `\migrations` folder in it where you have all your migrations as `*.sql`. 

Then in terminal you have the commands

```bash
supabase login # to login
supabase link --project-ref <YOUR PROJECT REF>
supabase db push
```
