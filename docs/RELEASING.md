# Releasing and maintaining (maintainers)

Source of truth: `specs/SPEC-001-installation-and-management.md`. This page is the operating manual. English on purpose (REQ-LNG-03).

## The rules (read once, follow always)

1. **Never** push to `main` or `stable`. **Never** force-push. **Never** create, move or delete a tag by hand. GitHub Free would let you; the process does not. (REQ-ACC-03, risk acceptance 1.4)
2. Every change goes through a **pull request to `main`** with **one approval from a maintainer who is not the author**, and green checks. GitHub suggests `stable` as the base because it is the default branch: **change the base to `main`**. A PR to `stable` fails the check `pr-must-target-main`.
3. **Users get what is on `stable`**, on every route. Merging to `main` ships nothing. The **Release workflow** is the only thing that moves `stable`.
4. A release = **release PR** (bump `version` in `plugins/isg-model-alignment/.claude-plugin/plugin.json` **and** add the `## [X.Y.Z] - AAAA-MM-DD` section to `plugins/isg-model-alignment/CHANGELOG.md`, in PT-BR) → merge → run the **release** workflow.
5. Versions are SemVer. Breaking change = MAJOR (MINOR while `0.x`) and a `### Quebra de compatibilidade` section. **Never reuse a version number.**
6. Zero cost: no paid action, service, key or plan. **Never add an Anthropic API key to this repo.** (REQ-CST)
7. Keep **Write access to few people** (at least two maintainers, REQ-ACC-07); everyone else gets Read.

## Releasing

1. Open a branch, change what you need, then in a **release PR** bump `version` and add the CHANGELOG section (PT-BR, format in SPEC 4.6). Run `npm run check` locally.
2. Get one approval from another maintainer. Merge (squash or merge commit) into `main`.
3. GitHub > **Actions** > **release** > **Run workflow** > branch **main**.
4. The workflow checks, in order: (a) you have Write access; (b) it runs on the tip of `main`; (c) the commit comes from a merged PR approved by someone other than its author; (d) the version is valid and greater than the latest tag; (e) the CHANGELOG has that version; (f) validate, consistency, language, portable-core checks and tests; (g) a Windows smoke test; then (h) tag `isg-model-alignment--vX.Y.Z`, (i) a GitHub Release whose notes are the CHANGELOG section, (j) `stable` fast-forwarded. A failed step stops everything after it.
5. **Announce** the release to users (REQ-REL-10): version + the PT-BR highlights. Channel: *to be decided (Q11)*; until then the Release page is the announcement and you also tell users directly. Remind route-A users that "Sync automatically" or "Check for updates" brings it.
6. If the workflow stopped halfway (for example after the tag): **do not delete the tag**. Fix the cause and run the workflow again; finished steps are skipped.

### First release (one-time, by an org owner)

`stable` must exist before the workflow can move it, and a workflow is only visible in the Actions tab when its file is on the **default branch**:

1. Create the organization and the private repo `isg-plugins` (SPEC T2); push `main`.
2. Set the real organization in `plugins/isg-model-alignment/scripts/lib/constants.mjs` (`GITHUB_ORG`) and in `plugin.json` (`repository`); open a PR, get approval, merge. `npm run check:release` must pass.
3. Create `stable` from that commit: `git push origin main:stable`.
4. **Settings > General > Default branch: `stable`.** Then check Actions shows the **release** workflow.
5. Run the **release** workflow (version `0.1.0`). Install it from `#stable` on two machines (route B) and through claude.ai (route A) before announcing.
6. Do the manual tests of SPEC section 6.2.

After this, the default branch is `stable` forever and PRs target `main`.

## Transfer to the Instituto's account (SPEC-001 P-44)

The repository lives temporarily at `Lecabe-Tech-Company/isg-plugins`. **Do not onboard users before the transfer.** When the Instituto's GitHub account exists:

1. In `Lecabe-Tech-Company/isg-plugins`: Settings > General > Danger zone > **Transfer ownership** → the Instituto's account (an owner of both accounts does it; the name stays `isg-plugins`).
2. In the new location, check: visibility **Private**; collaborators and access levels (re-invite if needed); default branch `stable` (if it already exists); Actions enabled; the **Claude** GitHub App installed on the new account with access to this repository only.
3. In a release PR, set the new owner in `plugins/isg-model-alignment/scripts/lib/constants.mjs` (`GITHUB_ORG`) and in `plugin.json` (`repository`); replace the owner in `docs/INSTALL*.md`; run `npm run check:release`.
4. Locally: `git remote set-url origin https://github.com/<new owner>/isg-plugins.git`.
5. Maintainers who already added the marketplace: remove and add it again with the new URL (this also reinstalls the plugin).
6. **Never** create a new repository named `isg-plugins` under `Lecabe-Tech-Company` (it would break GitHub's redirect).
7. Record the transfer in the quarterly log below.

## Rollback

Revert the bad change on `main` through a normal PR and release a **new PATCH**. Do not move `stable` backwards, do not delete tags or releases. (REQ-REL-06)

## Manual release fallback (when Actions minutes run out or Actions is down)

Same checks, run by a maintainer on a clean checkout of the tip of `main` after the release PR is merged:

```bash
npm run check:release        # consistency, changelog, org set
npm run check                # all local checks and tests
claude plugin validate . --strict
claude plugin validate ./plugins/isg-model-alignment --strict
node scripts/ci/release-notes.mjs X.Y.Z > notes.md
claude plugin tag plugins/isg-model-alignment --push
gh release create isg-model-alignment--vX.Y.Z --verify-tag --title "ISG Model Alignment X.Y.Z" --notes-file notes.md
git push origin HEAD:refs/heads/stable      # fast-forward only; it must succeed without --force
```

Record in the quarterly log below that a manual release was made and why. Never use this to skip a failed check.

## Offboarding someone

Remove them from the repository collaborators the same day (REQ-ACC-02). Ask them to remove the plugin from their claude.ai account. Add a line to the log.

## Claude organizations that use route C (org sync)

Route C gives the plugin to **every member** of that Claude organization (not only GitHub collaborators). Default decision (Q10): members use **route A**. Use route C only as an exception when that organization's owner blocks members from adding marketplaces **and** all its members may have the plugin. Record each decision here:

| Date | Claude organization | Decision | Decided by |
|---|---|---|---|
| | | | |

## Quarterly review (REQ-ACC-06, VAL-10) and log

Every quarter and after each offboarding, an org owner checks and records:

- [ ] Plan is **Free** and the amount due is **0** (Settings > Billing and plans); Actions minutes used are below the free quota (budget: PR check ≈ 3 min Linux; release ≈ 5 min Linux + ≈ 5 min Windows).
- [ ] Collaborators list and access levels: only the named maintainers have Write; everyone else Read; nobody who left.
- [ ] The **Claude** GitHub app has access to **this repository only**.
- [ ] Every tag and every move of `stable` since the last review was made by `github-actions[bot]` from the release workflow (Releases page and `git log --format='%an %s' stable`). Investigate anything else.
- [ ] Free-plan terms still match SPEC section 1.3 (github.com/pricing). Re-read SPEC section 10 (platform docs) for changes.

| Date | Reviewer | Collaborators (Write / Read) | Actions minutes used | Notes |
|---|---|---|---|---|
| | | | | |

## Actions minutes budget (REQ-CST-02)

PR check ≈ 3 min (Linux); release ≈ 10 billed minutes (Linux + Windows ×2). With ~20 PRs and 2 releases a month that is well under the free quota. The checks cancel superseded runs (`concurrency`). If the quota is ever exhausted, use the manual fallback above; **never buy minutes**.
