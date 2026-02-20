# Bug & Issue Backlog — Sales Coach

Non-blocking bugs and issues discovered during development. Don't fix these inline —
log them here and address in a dedicated fix session.

## Open

## Resolved

### 2026-02-19
- **test_consistency.py AST parsing errors** — 4 test errors caused by `linkedin_names` and `avatar_script_slugs` fixtures using AST parsing on hardcoded list literals, but both scripts were refactored to load dynamically from the registry. Fixed by rewriting fixtures to mirror script logic (load from `influencers.json`).
