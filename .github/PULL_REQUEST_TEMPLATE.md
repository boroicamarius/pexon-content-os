## Summary

<!-- one paragraph: what changed and why -->

## Architecture

- [ ] no service imports a concrete adapter
- [ ] no new hardcoded threshold (or setting + `.env.example` added)
- [ ] prompts remain in `config/prompts.py`
- [ ] four frame names preserved
- [ ] no mock or fabricated metric added

## Provider impact

<!-- ports/providers added or changed, required env vars -->

## Verification

```bash
ruff check src
python -m compileall -q src
./pexon inspect providers
# affected CLI path
```

## Evidence

- [ ] observational measurement only
- [ ] causal claim explicitly avoided
- [ ] docs updated

## Notes for the reviewer

<!-- limitations, follow-ups, migration notes -->
