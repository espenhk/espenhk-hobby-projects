# GitHub-side setup for mobile POC previews

Everything here can be done from a phone. Steps that need repo *settings*
use your phone's browser at github.com (the GitHub mobile app doesn't
expose Pages settings); starting Claude Code tasks and merging PRs can be
done in either the GitHub app or Claude's mobile app.

## 1. Make the repo public (one-time)

GitHub Pages needs either a public repo or a paid GitHub plan. To go public:

1. In your phone's browser, open `github.com/espenhk/espenhk-hobby-projects`.
2. **Settings** (bottom of the repo's tab bar, or the gear icon) → scroll to
   the **Danger Zone** at the very bottom → **Change visibility** →
   **Change to public**.
3. Type the repo name to confirm.

Do this once you've actually checked you're fine with the code and data
being public — there's no undo button that un-shows it from anyone who
already cloned it.

## 2. Turn on GitHub Pages (one-time)

1. Same **Settings** tab → **Pages** in the left sidebar (may be under a
   "Code and automation" group — scroll if it's collapsed).
2. Under **Build and deployment** → **Source**, choose **Deploy from a
   branch**.
3. Under **Branch**, pick `main` and folder `/docs`, then **Save**.
4. Wait about a minute. Reload the Pages settings page — a green box at
   the top will show your live URL:
   `https://espenhk.github.io/espenhk-hobby-projects/`
5. Open that URL and bookmark it (or "Add to Home Screen") — this is your
   permanent link to the landing page listing every published POC.

You only do steps 1 and 2 once. After this, Pages always serves whatever
is in `docs/` on `main` — no further settings changes needed for new
projects or updates.

## 3. Everyday workflow (mobile)

To add or update a POC frontend:

1. Open the Claude mobile app, start a task against this repo (or continue
   an existing session). Ask for what you want — e.g. *"build a POC
   frontend for `<project>`"* or *"publish the latest football-scheduler
   report"*. Claude Code creates a branch and a PR.
2. Review the PR (GitHub app or browser) and merge it.
3. Reload your bookmarked Pages URL — the change is live within about a
   minute of the merge, no extra deploy step.

`docs/README.md` in the repo has the convention Claude follows when asked
to add a new project's POC (vanilla JS, no build step, CDN dependencies —
or, if the project can already render itself to static HTML, publish that
directly, as `football-scheduler` does).

## Previewing before merging (optional)

Merging is normally cheap enough for a POC repo that you can just merge
and look. If you'd rather see a branch live *before* merging it:

1. Settings → Pages → change **Branch** to the `claude/...` branch Claude
   Code created, folder `/docs`, Save.
2. Preview at the same URL as before.
3. When happy, merge the PR, then switch Branch back to `main` in Pages
   settings (otherwise Pages keeps serving the now-stale feature branch).

This is a few extra taps each time, so it's worth it mainly for a change
you're unsure about before committing to it.
