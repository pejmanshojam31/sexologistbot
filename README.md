# Sex Research → Telegram + Blog bot

Daily pipeline: searches PubMed for new papers in a set list of journals,
keeps ones matching your keywords, picks one, summarizes it, translates the
summary to Farsi, and posts it to your Telegram channel + writes a blog post.

## How it works

```
fetch_papers.py   -> queries PubMed for the last N days, filters by keyword
summarize.py      -> Claude summarizes the abstract + translates to Farsi
post_telegram.py  -> posts the result to your Telegram channel
post_blog.py      -> writes a markdown post (or posts to WordPress)
main.py           -> runs the above in order, skips papers already posted
```

## One-time setup

1. **Install dependencies** into a virtualenv (keeps them out of system Python):
   ```
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
   Run everything below with `.venv/bin/python` instead of `python`.

2. **Get an Anthropic API key**: console.anthropic.com -> API Keys.
   (Separate from a claude.ai subscription — this is pay-per-use, usually
   a few cents per run.)

3. **Create a Telegram bot**: message **@BotFather** on Telegram, run
   `/newbot`, follow the prompts, copy the token it gives you.

4. **Add the bot to your channel as an admin.** A bot *cannot* join through an
   invite link — invite links only work for human accounts. You have to add it
   from inside the channel:

   Open the channel -> tap the channel name -> **Edit** (pencil) ->
   **Administrators** -> **Add Admin** -> type your bot's `@username` ->
   select it -> make sure **Post Messages** is on -> **Done**.

   If the bot doesn't show up in that search, you have the wrong username —
   check the exact `@name` BotFather gave you (it always ends in `bot`).

5. **Get your channel ID**: if your channel is public, it's just
   `@your_channel_name`. If private (invite link looks like `t.me/+AbCd...`),
   you need the numeric ID:

   - Post any message in the channel, forward it to `@userinfobot`, and it
     replies with an ID like `-1001234567890`. Include the leading `-100`.
   - Or, once the bot is an admin, post a message in the channel and open
     `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser —
     the ID is under `channel_post.chat.id`.

6. Copy `.env.example` to `.env` and fill in the values from steps 2-5.

7. Edit `config/settings.yaml` — check the journal list and, importantly,
   **replace the keyword list with your actual keywords.**

8. Test it locally:
   ```
   .venv/bin/python main.py
   ```
   Check your Telegram channel and the `posts/` folder. If it prints
   "Nothing new to post", raise `lookback_days` in `config/settings.yaml`
   to 30 for the first run — the target journals publish a few papers a week,
   not daily.

## Posting a specific paper

Useful for launching the channel, or reposting something notable:

```
.venv/bin/python main.py --pmid 42479982 --dry-run    # preview, sends nothing
.venv/bin/python main.py --pmid 42479982              # summarize + post
```

If you don't have Anthropic API credit yet, you can supply the summary
yourself and skip the API entirely:

```
.venv/bin/python main.py --pmid 42479982 --summary-file examples/42479982.json
```

The file is just `{"summary_en": "...", "summary_fa": "..."}`. See
`examples/42479982.json`.

## Running it daily (pick one)

**Option A — GitHub Actions (recommended, free, no server needed)**
1. Push this folder to a new GitHub repo.
2. Repo -> Settings -> Secrets and variables -> Actions -> add:
   `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`
   (and `NCBI_API_KEY` if you got one).
3. That's it — `.github/workflows/daily.yml` runs it every day at 09:00 UTC
   and commits new posts back to the repo automatically. Edit the cron line
   to change the time.
4. You can also trigger a run manually from the repo's "Actions" tab.

**Option B — your own server/cron**
Add this line to `crontab -e`:
```
0 9 * * * cd /path/to/sexresearch-bot && /usr/bin/python3 main.py >> run.log 2>&1
```

## Getting an actual blog out of `posts/`

The `posts/` folder fills up with dated markdown files with frontmatter —
that's the format Hugo, Jekyll, Astro, and Eleventy all expect. Cheapest
path: point a free Hugo/Jekyll site at this repo and host it on GitHub
Pages — zero monthly cost, updates automatically since the Action commits
new posts. If you already run WordPress, set `publish_target: "wordpress"`
in `config/settings.yaml` and fill in the `WORDPRESS_*` values in `.env`
instead.

## Tuning

- `config/settings.yaml`: journals, keywords, lookback window, posts/run.
- `summarize.py`: swap `MODEL` to `claude-haiku-4-5-20251001` for a
  cheaper/faster run, or edit `SYSTEM_PROMPT` to change tone/length.
- `data/posted_ids.json`: tracks what's already been posted, so reruns
  don't duplicate. Delete it to reset.
