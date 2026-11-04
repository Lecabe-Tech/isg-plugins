# T0 Part 2 runbook — prove the assumptions that need GitHub, claude.ai and the cloud

Goal: confirm or refute assumptions A3, A5, A6, A7, A8, A10, A11, A12, A13, A14, A15, A16, A17 and the checks G1–G11 of `specs/SPEC-001-T0-results.md`.
Time: about 2–3 hours, split in two sittings. Cost: **zero**. Use throwaway repositories and delete them at the end.
Language: this page is for maintainers (English). Write down the exact **Portuguese** UI labels you see (A17).

> Safety: never paste tokens or passwords anywhere. When a step says "print the environment", use the commands given (they print names, not secrets). Do not test with the real Instituto repository.

## 0. What you need

| Who | Needs |
|---|---|
| **Person A** (tester) | A personal GitHub account (owner of the throwaway repos); a Claude Pro/Max/Team plan that includes Claude Code on the web (for G9, G10); Claude Code ≥ 2.1.317, `git`, Node.js 20+; `gh` (https://cli.github.com, free) **or** Git Credential Manager already logged in to GitHub. |
| **Person B** (second person) | A **different** personal GitHub account **and its own claude.ai account** (any plan that allows adding marketplaces). B must **not** be a collaborator at first (A15). Later A adds B as a collaborator with Write (G4). |

Record every result in the table of section 6 (copy it into a text file, or fill `specs/SPEC-001-T0-results.md`).

## 1. Create two throwaway repositories (A)

On github.com click **New repository**: **Private**, no README, names `t0-isg-update` and `t0-isg-ci`.
Then make copies of the real repo (so the real one is never touched):

```bash
git clone C:\dev\isg-plugins C:\dev\t0-isg-update
git clone C:\dev\isg-plugins C:\dev\t0-isg-ci
```

In **each** copy edit `plugins/isg-model-alignment/scripts/lib/constants.mjs`:
`GITHUB_ORG = '<account A login>'` and `REPO_NAME = 't0-isg-update'` (or `'t0-isg-ci'`), and in `plugin.json` set `"repository"` to the same URL. Commit, then:

```bash
git remote set-url origin https://github.com/<A>/t0-isg-update.git
git push -u origin main
git push origin main:stable          # stable = fast-forward of main
```

Settings > General > **Default branch → `stable`** (both repos). Keep the marketplace name `isg-plugins` (it is inside `marketplace.json`).
Git access for Claude Code over HTTPS (once): `gh auth login` (GitHub.com, HTTPS) then `gh auth setup-git`.

## 2. G1 — the skills run in a real Claude Code session (A)

```bash
cd C:\dev\isg-plugins
claude --plugin-dir .\plugins\isg-model-alignment
```
In the session type `/isg-model-alignment:configure`, then `/isg-model-alignment:configure --check`, then `/isg-model-alignment:upgrade`.

Pass if: Claude answers in **PT-BR** even if you write in English; it runs `node "<path with spaces>\scripts\configure.mjs" --check --json` (check the path was filled in and quoted); it shows the checklist; with `--check` it never offers changes. Record: did it ask for permission to run `node`? Was `$ARGUMENTS` replaced (does it know you typed `--check`)?

## 3. G3, G5 — update flow and auto-update, repo `t0-isg-update` (A)

```bash
claude plugin marketplace add <A>/t0-isg-update#stable
claude plugin install isg-model-alignment@isg-plugins
claude plugin marketplace list --json     # SAVE the output (C-07 needs the ref field name)
claude plugin list --json                  # SAVE
```
Then in a Claude Code session run `/isg-model-alignment:configure` (real C-06, C-07, C-04 results) and `/isg-model-alignment:upgrade --check` (expect UP_TO_DATE).

**Update path (A3, A5):** in the copy bump `version` to `0.1.1` and add a `## [0.1.1] - <date>` section to `plugins/isg-model-alignment/CHANGELOG.md`; commit on `main`; `git push origin main:stable` (fast-forward). Then:

```bash
claude plugin marketplace update isg-plugins
claude plugin update isg-model-alignment@isg-plugins
claude plugin list --json                  # version must be 0.1.1
```
Also run `/isg-model-alignment:upgrade` in a session **before** the commands above: it must show 0.1.0 → 0.1.1, ask "sim/não", update, and tell you to `/reload-plugins`. Note whether the running session keeps the old version until reload (A5).

**Unreleased changes stay away (A3):** commit version `0.2.0` on `main` only (do **not** push to stable). Run `claude plugin marketplace update isg-plugins` → the marketplace must stay on `0.1.1`.

**Auto-update (A8):** `/plugin` > Marketplaces > `isg-plugins` > **Enable auto-update**; push `0.1.2` to stable; start a new session, send one message, wait up to ~10 minutes; look for "Plugin updated". Then try the other way: run `/isg-model-alignment:configure --apply --only autoUpdate` on a fresh config and check that setting `extraKnownMarketplaces.isg-plugins.autoUpdate` in `settings.json` has the same effect.

## 4. G7, G11, A10, A15, A17 — claude.ai account route (A and B)

1. **A15 first (B):** B (not a collaborator of `t0-isg-update`) opens claude.ai > **Customize > Plugins > Add > Add marketplace**, enters `<A>/t0-isg-update`, connects GitHub if asked. **Expected: it fails.** Record exactly what happens, with a screenshot. *If B can add it, stop here and tell the team: Route A must not be offered (the spec changes first).*
2. **A adds it:** A installs the **Claude GitHub App** for the repo `t0-isg-update` only (when the dialog asks), adds the marketplace, adds **ISG Model Alignment**, turns on **Sync automatically**. Write down every Portuguese label you click (A17): "Customize", "Plugins", "Add", "Add marketplace", "Check for updates", "Sync automatically".
3. **A10 (default branch):** with default branch `stable`, push a new version to `stable`; on claude.ai use **Check for updates**; the plugin page must show the new version. Then push another version to `main` only; **Check for updates** must show **no** change.
4. **G11 (Claude Code, synced):** restart Claude Code signed in with A's claude.ai account → `claude plugin list --json` must show `isg-model-alignment@synced`. **SAVE it.** Run `/isg-model-alignment:upgrade` → expect `MANAGED_BY_ACCOUNT`, and check in the session that it did **not** run `claude plugin update`. Then also install through the CLI (G3) and run `/isg-model-alignment:configure` → check C-12 fails with the "uma rota só" message.

## 5. G8, G9, G10 — chat, Cowork, cloud (A)

**G8 — chat and Cowork (A14, A16).** In each of **claude.ai web chat**, **Desktop chat** and **Cowork**: type `/` and look for the skills; run `/isg-model-alignment:configure` and `/isg-model-alignment:upgrade`. Pass if Claude answers in PT-BR with the manual steps and **never says it ran or checked anything**. Also write (without the slash) "configure o plugin ISG" → Claude must **not** run the command on its own (A14). In Cowork ask Claude whether it can run `node` or `claude` commands at all (A16) and record the answer.

**G9 — Claude Code on the web (A11, A13).** Start a cloud session at claude.ai/code (attach `t0-isg-update`), with the plugin installed through step 4.2. Type `/isg-model-alignment:` and see if the skills appear. In the session ask Claude to run, and show you:

```bash
claude plugin list --json
env | grep -i '^CLAUDE' | cut -d= -f1          # names only, no values
echo "ENTRYPOINT=$CLAUDE_CODE_ENTRYPOINT REMOTE=$CLAUDE_CODE_REMOTE"
```
Record: is `isg-model-alignment@synced` there (A11)? Which variable names/values mark a cloud session (A13)?

**G10 — setup script fallback (A12).** Only if the plugin was **not** present in G9. In the cloud environment settings add this setup script, start a new session with `t0-isg-update` attached, and read the setup log:

```bash
#!/bin/bash
git ls-remote https://github.com/<A>/t0-isg-update.git stable || true
claude plugin marketplace add <A>/t0-isg-update#stable || true
claude plugin install isg-model-alignment@isg-plugins || true
claude plugin list || true
exit 0
```
Record whether the clone and the install worked and whether the plugin exists in a new session afterwards.

## 6. G4, A1, A6 — GitHub Actions, repo `t0-isg-ci` (A, with B as a Write collaborator)

1. A adds B as a **collaborator with Write** to `t0-isg-ci` (B accepts).
2. **PR checks (A1):** A creates a branch, changes a doc line, opens a **PR to `main`**. Pass if the `validate` workflow's `checks` job is green, including `npm install -g @anthropic-ai/claude-code`, `claude plugin validate --strict` and the install smoke test **with no secrets configured**. Record the run time (minutes). Then open a PR to `stable`: `pr-must-target-main` must fail with the PT-BR message.
3. **Secret scan:** push a branch with a file containing a realistic random fake token (`ghp_` + 36 random letters/digits, not sequential) → the `checks` job must fail at the secret scan. Delete the branch.
4. **Release (A6, VAL-09 positive path):** `plugin.json` must be `0.1.0` with a `## [0.1.0]` section. Make the last change through a **PR by A, approved by B, merged by A**. Then Actions > **release** > Run workflow (branch `main`). Pass if: all gates pass, the Windows job passes, tag `isg-model-alignment--v0.1.0` exists with author `github-actions[bot]` (A6), a GitHub Release with the PT-BR notes exists, `stable` moved, and the workflow made no commit.
5. **VAL-09 negative paths** (each must fail with a clear message and publish nothing): (a) run the workflow as a user with only Read access; (b) run it on a branch other than `main`; (c) merge a PR **without** approval and run it; (d) run again with the same version on a different commit (bump nothing); (e) set `version` to a value with no CHANGELOG section; (f) re-run for the same commit after a success → must skip finished steps.
6. Record Actions minutes used (Settings > Billing and plans > Usage) and confirm the plan is **Free**, the amount due **0** (A7).

## 7. Results table (copy and fill)

| Check | Assumption | Result (pass / fail / different) | Evidence (output, screenshot, run link) |
|---|---|---|---|
| G1 skill runs, PT-BR, path, `$ARGUMENTS` | A14 (partly) | | |
| G3 update 0.1.0 → 0.1.1, stays off 0.2.0 | A3, A5 | | |
| `marketplace list --json` for GitHub source | A2 (ref field) | | |
| G5 auto-update | A8 | | |
| G7-1 non-collaborator blocked on claude.ai | **A15 (blocking)** | | |
| G7 default branch read; Check for updates | A10 | | |
| UI labels in Portuguese | A17 | | |
| G11 `@synced` in Claude Code; upgrade → MANAGED_BY_ACCOUNT | A2, AC-SRF-2 | | |
| G8 chat web / Desktop chat / Cowork: skills, no false claims | A14, A16, AC-SRF-1 | | |
| G9 cloud session: plugin present? env markers | A11, A13 | | |
| G10 setup script (only if needed) | A12 | | |
| G4 PR checks green, no secrets, no API key | A1 | | |
| G4 release end to end, tag author | A6 | | |
| G4 negative paths (a–f) | VAL-09 | | |
| Billing Free / 0; Actions minutes | A7 | | |

Send the filled table (and the saved JSON outputs) back; the spec section 1.5 and the code (`C-07`, `surface.mjs`, R1/R4 messages) will be updated from the evidence.

## 8. Clean up

Delete `t0-isg-update` and `t0-isg-ci`; remove the test marketplace and plugin from claude.ai (Customize > Plugins) and from Claude Code (`claude plugin marketplace remove isg-plugins`, which also uninstalls its plugins); uninstall the Claude GitHub App from the throwaway repos; delete the cloud environment setup script; delete `C:\dev\t0-isg-update` and `C:\dev\t0-isg-ci`.
