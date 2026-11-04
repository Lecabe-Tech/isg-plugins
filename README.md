# isg-plugins

Marketplace of Claude plugins of the **Instituto Sonho Grande** (private repository).
Currently one plugin: **`isg-model-alignment`** (support for a quality process).

- Users: start at [`docs/INSTALL.pt-BR.md`](docs/INSTALL.pt-BR.md) ([English](docs/INSTALL.md)).
- Maintainers: [`docs/RELEASING.md`](docs/RELEASING.md). The rules there are mandatory.
- Design and requirements (source of truth): [`specs/SPEC-001-installation-and-management.md`](specs/SPEC-001-installation-and-management.md). T0 results: [`specs/SPEC-001-T0-results.md`](specs/SPEC-001-T0-results.md).

## Branches

| Branch | Purpose |
|---|---|
| `main` | Integration. Pull requests go here. **Never** push directly. |
| `stable` | What users install. Default branch. Moved only by the `release` workflow. |

## Working on it (maintainers)

Clone **outside OneDrive** (for example `C:\dev\isg-plugins`), editor set to UTF-8 without BOM and LF.

```bash
npm run check        # all local checks and tests (Node 20+; no dependencies to install)
claude plugin validate . --strict
claude plugin validate ./plugins/isg-model-alignment --strict
claude --plugin-dir ./plugins/isg-model-alignment     # try the plugin without installing it
```

Layout:

```text
.claude-plugin/marketplace.json          catalog
plugins/isg-model-alignment/             THE PLUGIN (only this folder reaches users)
  .claude-plugin/plugin.json             version lives only here
  skills/{configure,upgrade}/SKILL.md    PT-BR, surface-aware
  scripts/                               Node.js (built-ins only), used where a terminal exists
  CHANGELOG.md                           PT-BR
scripts/ci/                              CI checks (not shipped)
test/                                    tests and fake claude/gh/git
.github/workflows/                       validate.yml (PRs), release.yml (manual)
```

Rules of thumb (full list: SPEC section 8): PT-BR for everything users or Claude read, English for code and identifiers; no paid service or key; no scripts in domain skills (portable core); quote every path; never print tokens.
