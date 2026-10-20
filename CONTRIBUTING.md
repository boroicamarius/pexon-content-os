# Contributing

Pexon is a prototype, but the architecture is intentional. Contributions should preserve
its constraints.

## Ground rules

1. **No mocks in the product path.** Empty data stays empty. Missing providers fail
   loudly in `doctor`.
2. **Services never import adapters.** Depend on a port. Build adapters in
   `main.py` / `registry.py`.
3. **No hardcoded thresholds.** Add a setting, document it in `.env.example`, expose it
   in `pexon inspect settings`.
4. **Prompts live in `config/prompts.py`.** No inline article-generation prompts.
5. **German output.** Blog content, titles and sections are German.
6. **Keep the four frame names.** Research, Generation, Intelligence, Reflection.
7. **No fabricated metrics.** Do not seed analytics, leads, GEO citations or revenue.
8. **Less production is intentional.** No Docker, CI, auth, queues or monitoring stack.

## Adding a provider

1. Create one file under `src/pexon/adapters/` implementing the port.
2. Export `AVAILABLE` and `UNAVAILABLE_REASON` if the package is optional.
3. Add one `_spec(...)` entry to the relevant dictionary in
   [registry.py](src/pexon/adapters/registry.py).
4. Add the env variable to [.env.example](.env.example).
5. Run `./pexon inspect providers` and `./pexon doctor`.
6. Do not modify a service, graph or subgraph.

## Development loop

```bash
# local launcher, no install
./pexon inspect providers
./pexon inspect settings

# editable install
pip install -e ".[providers]"
ruff check src
python -m compileall -q src
```

There is no test suite by design. Before a pull request, run the linter, compile the
package, and exercise the affected CLI path against a real local provider when possible.

## Pull requests

- explain the architectural change;
- list provider/port impact;
- include the exact commands used to verify;
- call out any new threshold and its `.env.example` entry;
- state whether the change is observational or causal.

## Commit style

Conventional prefixes are preferred:

```text
feat(geo): add openai web-search adapter
fix(review): rewrite frontmatter on approval
docs(adr): record measurement layer decision
```
