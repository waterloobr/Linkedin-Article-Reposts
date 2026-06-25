# WBR LinkedIn Auto-Poster

Every Friday: picks an evergreen Waterloo Business Review article, finds a current
news story related to it, has Claude write a LinkedIn post tying them together,
and opens a GitHub issue with the draft. You review, then click one button to publish
to the WBR company page.

```
generate_post.py   Friday: pick article -> pull news -> Claude writes post -> draft.json
publish.py         Manual: posts the approved draft to LinkedIn
linkedin_auth.py   One-time, local: gets your LinkedIn refresh token
articles.json      Your curated evergreen article pool (edit this)
.github/workflows/ generate.yml (Friday cron) + publish.yml (manual approve)
```

## Build order

### Phase 1 — content pipeline (works without LinkedIn approval)

1. **Create the repo.** New GitHub repo, drop these files in.
2. **Edit `articles.json`** — replace the samples with real WBR evergreen pieces.
   Each needs `title`, real `url`, a one-line `summary`, and 1-2 `themes`
   (the themes become the news search queries, so make them specific).
3. **Get an Anthropic API key** at https://console.anthropic.com — add credit.
4. **Add the key as a secret:** repo → Settings → Secrets and variables → Actions
   → New repository secret → `ANTHROPIC_API_KEY`.
5. **Test it:** Actions tab → "Generate Friday WBR post" → Run workflow.
   It opens an issue with the drafted post. At this point you can copy-paste to
   LinkedIn manually and you already have 90% of the value.

### Phase 2 — auto-posting (do once Phase 1 looks good)

6. **Create a LinkedIn developer app** at https://developer.linkedin.com/apps,
   linked to the WBR company page. You must be an **admin** of that page.
7. **Request the "Share on LinkedIn" + "Sign In with LinkedIn (OpenID)" products**
   on the app's Products tab. Lighter review than full partner access, but can
   take a few days.
8. On the **Auth** tab, add redirect URL `http://localhost:8000/callback` and
   note the **Client ID** and **Client Secret**.
9. **Find the org ID:** it's the number in the WBR page admin URL
   (`linkedin.com/company/<ID>/admin`).
10. **Run the OAuth bootstrap locally:**
    ```
    pip install -r requirements.txt
    LINKEDIN_CLIENT_ID=xxx LINKEDIN_CLIENT_SECRET=yyy python linkedin_auth.py
    ```
    Follow the prompts; it prints a **refresh token**.
11. **Add four more secrets:** `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`,
    `LINKEDIN_REFRESH_TOKEN`, `LINKEDIN_ORG_ID`.
12. **Publish flow:** after the Friday issue appears and you're happy with it,
    Actions tab → "Publish WBR post" → Run workflow. Done.

## Notes
- **Model:** defaults to `claude-sonnet-4-6`. Bump to `claude-opus-4-8` in
  `generate_post.py` for stronger copy.
- **Schedule:** cron is `0 13 * * 5` (UTC). That's ~9am Eastern in summer; nudge
  the hour if you care about DST.
- **LinkedIn-Version header:** set to a recent `YYYYMM` in `publish.py`; LinkedIn
  rotates these. If you get a version error, set it to the current month.
- **Token refresh:** access tokens die after 60 days, but `publish.py` mints a
  fresh one from the refresh token each run. Refresh tokens last ~365 days, so
  re-run `linkedin_auth.py` about once a year.
- **Editing a draft before posting:** just edit `draft.json` in the repo (or the
  issue is only a notification — the published text comes from `draft.json`).
