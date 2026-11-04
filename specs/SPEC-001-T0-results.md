# SPEC-001 — T0 results (spike)

| | |
|---|---|
| **Spec** | SPEC-001 v0.5.2, section 1.5 |
| **Date** | 2026-11-04 |
| **Machine** | Windows 11, Claude Code **2.1.317** (inside the Claude Desktop app, Code tab), Node.js 22.23.4, Git 2.49.0 for Windows, PowerShell 5.1. `gh` **not installed**. |
| **Method** | A minimal test marketplace `isg-plugins` with a plugin `isg-model-alignment` 0.1.0 (two PT-BR skills `configure`, `upgrade`, one optional `userConfig`) was built in a scratch folder. Every `claude plugin …` command ran in a **clean environment** (`env -i`, no Claude auth variables, no login) with its own `CLAUDE_CONFIG_DIR` and `CLAUDE_CODE_PLUGIN_CACHE_DIR`. The real `~/.claude` was **not touched**. |
| **Status of T0** | **Part 1 (this machine) done. Part 2 (GitHub, claude.ai, Desktop chat, Cowork, cloud) needs people and accounts** — checklist in section 3. |

## 1. Result per assumption

| ID | Result | Evidence and notes |
|---|---|---|
| A1 | **Confirmed locally; CI still to run** | In a clean environment with no login: `plugin validate . --strict` and `plugin validate ./plugins/isg-model-alignment --strict` print `✔ Validation passed`; `plugin marketplace add <dir>`, `plugin install`, `plugin list --json` all work. Validation prints one **warning** about a missing icon (a directory-listing check; it does not fail `--strict`). Still to prove: the same in a GitHub Actions job (Part 2, G4). |
| A2 | **Confirmed** | `plugin list --json` returns `id`, `version`, `scope`, `enabled`, `installPath`, `readFromFolder`, `folderVersion`, `installedAt`, `lastUpdated`, `projectEnabled`, `hasUserConfig`. `plugin marketplace list --json` returns `name`, `source`, `path`, `installLocation` (for a directory source). **Not yet seen:** the JSON of a GitHub-sourced marketplace (ref field) and of a `@synced` plugin; capture them in Part 2. |
| A3 | **Not testable locally** | `plugin marketplace add file:///…/repo.git#stable` is refused: *"Invalid marketplace source format. Try: owner/repo, https://..., or ./path"*. A plain path is a *directory* source (reads the working tree, not a branch). Needs a real GitHub repo (G3). |
| A4 | **Confirmed** | Optional `userConfig` values are stored in `settings.json` at `pluginConfigs["<id>"].options.<key>`, e.g. `pluginConfigs["isg-model-alignment@isg-plugins"].options.user_name`. `claude plugin install` prints a notice when an option is not set (and does not fail). A CLI exists to set values: `claude plugin configure <id> --values-stdin` (JSON object of single-line strings; accents survived: `José da Conceição`), and `--config KEY=VALUE` on install. It prints *"Restart Claude Code to apply it"*. **Not yet tested:** that `${user_config.user_name}` is substituted in skill text inside a session (G1). |
| A5 | **Partly** | `claude plugin update <plugin>` exists, help says *"restart required to apply"*. Not yet run from inside a session, and a local *directory* marketplace loads the plugin **in place** (`readFromFolder`), so it cannot show a real update. Needs a git-sourced marketplace (G3, G5). |
| A6 | **Partly confirmed** | `claude plugin tag plugins/isg-model-alignment --dry-run` works: reads version `0.1.0` from `plugin.json`, finds the marketplace entry, would run `git tag -a isg-model-alignment--v0.1.0 -m "isg-model-alignment 0.1.0"` and `git push origin refs/tags/isg-model-alignment--v0.1.0`. Still to prove: `--push` in Actions with `GITHUB_TOKEN` and the tag author (G4). |
| A7 | **Not tested** | Needs github.com and the real organization (G2, G6). |
| A8 | **Not tested** | Needs an interactive session to observe background auto-update (G5). The setting itself is accepted in `extraKnownMarketplaces` format seen in `settings.json`. |
| A9 | **Confirmed on Windows** | Node output has correct UTF-8 bytes (`c3 a3` for `ã`) through the Bash tool and through PowerShell 5.1 (console encoding `utf-8`), and a file written by Node is UTF-8 without BOM. **Pitfall found:** PowerShell 5.1 strips quotes in `node -e "…"` arguments, so inline scripts break. Rule: always run a **script file** (`node "path\script.mjs" --flag`). macOS/Linux not tested yet (UAT-02). |
| A10–A12 | **Not tested** | claude.ai / cloud (G7–G10). |
| A13 | **Partly** | In this session (Desktop app, local) the environment has `CLAUDE_CODE_ENTRYPOINT=claude-desktop`, `CLAUDE_CODE_DESKTOP_APP_VERSION=4.16336.0`, `CLAUDE_CODE_REMOTE` empty. The value in a **cloud** session is unknown (G9). |
| A14–A17 | **Not tested** | Need chat, Cowork and the claude.ai UI (G7, G8, G10, G11). |

## 2. New findings that change the spec (applied in v0.5.2)

| # | Finding | Change |
|---|---|---|
| F1 | **`claude` is not on `PATH`** in the Bash tool of a Desktop-app session. Only `CLAUDE_CODE_EXECPATH` points to it (`…\claude-code\2.1.317\…\claude.exe`). A script that runs `claude …` by name fails with "command not found". | Section 4.8: scripts locate the CLI with `process.env.CLAUDE_CODE_EXECPATH`, falling back to `claude` on `PATH`. New check inside C-03. New pitfall P-42. |
| F2 | **Git for Windows has `core.autocrlf=true` by default** (system gitconfig). Creating files printed *"LF will be replaced by CRLF"* warnings. | Confirms REQ-REP-06 and P-27: `.gitattributes` is mandatory in T1; implementer note about `core.autocrlf`. |
| F3 | A **directory** marketplace loads plugins **in place** (`readFromFolder`), with no cache copy and no version logic. | Local tests of upgrade/versions must use a **git** marketplace (GitHub). Note added to 8.2. |
| F4 | `plugin validate` has `--profile directory` (stricter, for Anthropic's directory) and warns about a missing icon by default. | No action; we do not submit to the directory. Documented so nobody "fixes" the warning. |
| F5 | The CLI can set `userConfig` values (`plugin configure … --values-stdin`). | **Option** for the future: `configure` could offer to save `user_name`. Kept out of v1 (REQ-CMD-03 unchanged) because values are applied only after restart; decide in T5. |
| F6 | `gh` is **not installed** on this machine, yet the spec makes it a prerequisite for R2. | Confirms REQ-INS-08; the install guide must say how to install `gh` on Windows (free). |
| F7 | Claude Code **2.1.317** is the version tested. | **`MIN_CLAUDE_VERSION` = `2.1.317`** provisional (Q7); lower it only after testing an older version. |

## 3. Part 2 — what people must do (checklist)

Most items need a person with an account; none costs money. Use a **throwaway private repo** in a personal GitHub account and delete it afterwards. The test plugin is in the scratch folder `…\scratchpad\t0\mkt` (or recreate it from `specs/`); it contains no secrets.

| ID | Who | Do | Answers |
|---|---|---|---|
| G1 | Anyone, Claude Code | Start `claude --plugin-dir <test plugin>`, run `/isg-model-alignment:configure`; fill `user_name` first. Does the skill text show the name and the plugin root path? | A4 (substitution), A14 |
| G2 | A GitHub account owner | Create a free **organization** (or use a personal account), a **private** repo `isg-plugins`; invite a second account as collaborator (Read). Read github.com/pricing for Free-plan limits. | A7 |
| G3 | Same | Push the test marketplace with branches `main` and `stable` (stable = default). Add it in Claude Code with `claude plugin marketplace add <org>/isg-plugins#stable` (needs `gh auth login` and `gh auth setup-git` first). Push a new commit to `stable` with version `0.1.1`; run `claude plugin marketplace update isg-plugins` and `claude plugin update isg-model-alignment@isg-plugins`. Push `0.2.0` to `main` only; confirm nothing changes. Save the JSON of `marketplace list --json` and `list --json`. | A2, A3, A5 |
| G4 | Same | Add a workflow with no secrets that runs the `validate` commands and `claude plugin tag --push` on a test tag. Install Claude Code in the job from npm. Check the tag author. | A1, A6 |
| G5 | Same | Turn on auto-update for the marketplace in `/plugin` > Marketplaces; push a new version; start a new session; see whether it updates. | A8 |
| G6 | Org owner | Install the **Claude GitHub App** on the org for this repo only. Check the Billing page is Free/0. | A7 |
| G7 | A **collaborator** and a **non-collaborator** (two GitHub accounts) | claude.ai > Customize > Plugins > Add > Add marketplace > `<org>/isg-plugins`. The collaborator must succeed; the **non-collaborator must fail** (this is **A15, blocking for R1**). Note the exact UI labels in Portuguese. | A10, A15, A17 |
| G8 | The collaborator | In claude.ai chat, Desktop chat and Cowork: type `/` and find the skills; run `configure` and `upgrade`; check what Claude says without a terminal; check the plugin is accepted (no `bin/`). Is a command with `disable-model-invocation: true` still shown/used? | A14, A16 |
| G9 | The collaborator, plan with cloud sessions | Open a **Claude Code on the web** session (claude.ai/code). Run `/isg-model-alignment:`; run `claude plugin list`; run `printenv \| grep -i CLAUDE_CODE_` (hide values of tokens). | A11, A13 |
| G10 | Same | In a cloud environment add a setup script that runs the R2 commands against the private repo. Does it clone? Is the plugin there in a new session? | A12 |
| G11 | The collaborator | After G7, restart Claude Code signed in with the same claude.ai account: is `isg-model-alignment@synced` listed? Push `0.1.1` to `stable`, use "Check for updates" or "Sync automatically" and see what the account gets. | A10, A2 |

**Step-by-step runbook with exact commands, pass criteria and a results table: `docs/dev/T0-part2-runbook.md`.**

Record each result in this file (replace "Not tested") and update section 1.5 of the spec. If **A15 fails**, stop: R1 is not offered, and the spec changes first (REQ-ACC-01).

## 4. Sample outputs

Captured with Claude Code 2.1.317 in the clean environment. Paths shortened.

`claude plugin list --json`
```json
[
  {
    "id": "isg-model-alignment@isg-plugins",
    "version": "0.1.0",
    "scope": "user",
    "enabled": true,
    "installPath": "…\\cache\\cache\\isg-plugins\\isg-model-alignment\\0.1.0",
    "readFromFolder": "…\\mkt\\plugins\\isg-model-alignment",
    "folderVersion": "0.1.0",
    "installedAt": "2026-11-04T14:26:18.219Z",
    "lastUpdated": "2026-11-04T14:26:18.219Z",
    "projectEnabled": false,
    "hasUserConfig": true
  }
]
```

`claude plugin marketplace list --json` (directory source)
```json
[ { "name": "isg-plugins", "source": "directory", "path": "…\\mkt", "installLocation": "…\\mkt" } ]
```

`settings.json` after install and `plugin configure --values-stdin`
```json
{
  "enabledPlugins": { "isg-model-alignment@isg-plugins": true },
  "extraKnownMarketplaces": { "isg-plugins": { "source": { "source": "directory", "path": "…\\mkt" } } },
  "pluginConfigs": { "isg-model-alignment@isg-plugins": { "options": { "user_name": "José da Conceição" } } }
}
```

`claude plugin tag plugins/isg-model-alignment --dry-run`
```text
Plugin:  isg-model-alignment
Version: 0.1.0 (from plugin.json)
Tag:     isg-model-alignment--v0.1.0
  git tag -a isg-model-alignment--v0.1.0 -m "isg-model-alignment 0.1.0"
  git push origin refs/tags/isg-model-alignment--v0.1.0
```
