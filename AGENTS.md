## Agent skills

### Issue tracker

Issues live as local Markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five canonical labels. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repo with root `GLOSSARY.md` and `docs/adr/`. See `docs/agents/domain.md`.

### Wire protocol

When changing packet construction, parsing, discovery, checksums, AES, or live connectivity, read `PROTOCOL.md` and the relevant protocol tests before editing. Record new hardware observations in `PROTOCOL.md` with an evidence label, and keep captured fixtures separate from synthetic fixtures.
