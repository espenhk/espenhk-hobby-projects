# football-scheduler-frontend

The presentation layer for [`football-scheduler`](../football-scheduler) —
the "overview/calendar rendering" half of that project, separated out here
per [issue #37](https://github.com/espenhk/espenhk-hobby-projects/issues/37)
so it can eventually be handed off to Lovable for further development.

## Current state: prep only, still plain Jinja2

This folder is a **staging step**, not the final shape. Right now it's
exactly what it was before the split — one Jinja2 template
(`templates/season.html.j2`) rendered server-side into a single
self-contained HTML file by `render.py` — just physically moved out of
`football-scheduler/` so the frontend/backend boundary is explicit. There's
no `package.json`, no React, no Vite yet.

That's deliberate: Lovable can't import an arbitrary existing repo (it
expects a Vite/React/TypeScript project with a single `package.json` at
root — see `football-scheduler/CONTRACT.md` for the full explanation), so
the actual tech-stack conversion is bigger, separate work, tracked in its
own follow-up issue rather than bundled into this structural move.

```
football-scheduler-frontend/
├── render.py             # Jinja2 -> one self-contained HTML file
├── templates/
│   └── season.html.j2
└── data/                 # published JSON fixtures (see below), committed —
                           # this is the actual data a frontend reads
```

`render.py` depends on `football-scheduler/` being its sibling directory in
this same checkout (it imports `terminliste.report.views` for the shared
view-model logic — resolved names, weekday strings, dual-club colors, the
`paired` back-to-back-home-day flag). That's fine while both live in one
monorepo; it's exactly what changes once this folder is extracted into its
own repo.

## Where the data comes from

This folder never runs the scheduling engine itself. `football-scheduler`'s
`cli.py export-frontend` command solves a season, builds the documented JSON
contract (`football-scheduler/CONTRACT.md`), and writes it to
`data/{season}.frontend.json` here — see that command's `--help` and
`CONTRACT.md` for the full shape and regeneration story.

## Next steps

See the follow-up GitHub issue for converting this into a real
Vite/React/TypeScript/Tailwind project and extracting it into its own repo
via Lovable's "reverse sync" workaround, at which point it stops being a
subdirectory of `espenhk-hobby-projects` entirely.
