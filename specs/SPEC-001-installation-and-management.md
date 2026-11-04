# SPEC-001 — Installation & Management Structure of the Quality Plugin

## 0. Document control

| | |
|---|---|
| **Organization** | Instituto Sonho Grande |
| **Plugin** | `isg-model-alignment` *(decided)* |
| **Marketplace / repository name** | `isg-plugins` *(decided; fallback `instituto-sonho-grande-plugins`, see Q1)* |
| **GitHub owner** | `<org>` in this spec = the final owner, the **Instituto's GitHub account**. **Interim host (2026-11-04):** `Lecabe-Tech-Company/isg-plugins` (private), to be **transferred** to the Instituto's account later (Q2, P-44) |
| **Code host** | GitHub, **Free plan**, private repository *(decided)* |
| **Release owners** | GitHub collaborators with write access *(decided)* |
| **Supported surfaces** | Claude Code (terminal, IDE, **Desktop Code tab**, **Claude Code on the web**), **claude.ai web chat**, **Desktop chat**, **Cowork** *(decided, see 1.6)* |
| **Supported Claude plans** | Pro, Max, Ultra, Team, Enterprise. **Claude Free is not supported** *(decided, see 1.6)* |
| **Cost constraint** | **Zero additional cost.** Only free tools and free-plan limits; users use the Claude plan they already have *(decided, see 1.3)* |
| **Risk acceptance** | Free-plan risks accepted by the Instituto and managed by process, not pricing *(decided, see 1.4)* |
| **Language** | Everything Claude reads or writes for the user is **PT-BR** (skill text, messages, generated content, CHANGELOG, user guides). Spec, code, code comments, identifiers, maintainer docs and commit messages are **English** *(decided, see REQ-LNG)* |
| **Status** | v0.9 — design approved; **implementation T1, T3–T7 done in the repo `C:\dev\isg-plugins` (not yet committed or published)**; T2, T8 and T0 Part 2 need people and accounts (see 7.1). R1 must not be offered to users until A15 is confirmed. |
| **Date** | 2026-11-04 |
| **Scope of this spec** | Distribution, access control, install, upgrade, release process, `configure` and `upgrade` commands, support on every surface |
| **Out of scope (next spec)** | Agent improvement system (SPEC-002) and domain skills of the quality process (SPEC-003+). Both must follow REQ-SRF-02 (portable core) and REQ-LNG. |

> **Method: Spec-Driven Development.** This document is the source of truth. Code is written only to satisfy a numbered requirement. A requirement is "done" only when its acceptance criteria (AC, section 3) pass through the validation steps (VAL/UAT, section 6). **If the spec is wrong or incomplete, fix the spec first (in a PR), then the code.** Never let code and spec disagree.

### 0.1 Revision history

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-11-04 | First draft from research of the Claude Code plugin docs |
| v0.2 | 2026-11-04 | Plugin name, GitHub Free, release owners, PT-BR, zero cost, risk acceptance |
| v0.3 | 2026-11-04 | Consistency review: `stable` delivery branch; release PR + Release workflow; CHANGELOG in plugin folder in PT-BR; script contract; `configure` checks and `upgrade` algorithm; VAL-10 manual; assumptions list and T0; implementer notes |
| v0.4 | 2026-11-04 | Instituto approved the v0.3 design choices (D5, D6, D8, REQ-LNG-04, REQ-ACC-07). Approved to start T0. |
| v0.5 | 2026-11-04 | **Support for every surface** (Desktop Code tab and chat, Claude Code on the web, claude.ai chat, Cowork). New: section 1.6 (surfaces, plans, install routes R1–R4); D11 `stable` is the repo **default branch**; D12 the **claude.ai account route (R1) is primary**; REQ-SRF group (portable core, no required `userConfig`, surface-aware commands); assumptions A10–A17; sections 4.11–4.12; new AC, VAL-13, UAT-14..20, P-32..P-41. Changed: D3, D8, REQ-INS-01/08, REQ-CMD-03, C-09, 4.3, 4.4, 4.7, 4.10. **Approved by the Instituto on 2026-11-04.** |
| v0.5.1 | 2026-11-04 | Answers to open questions: marketplace/repo renamed to `isg-plugins` (Q1); GitHub org to be created in T2 (Q2); Q9 and Q10 decided; Q3 and Q11 still open. |
| v0.9 | 2026-11-04 | For SPEC-003: scripts may be **Python ≥ 3.11 with vendored libraries** (4.8); prerequisite Python 3.11+ for `cfp` only (REQ-INS-08); new check **C-14**; skill `cfp` is the declared exception to the portable core (it runs a script and is not `disable-model-invocation`); `scripts/cfp/` and checks VAL-C09/C10 added; `.py` files covered by the LF/BOM rule. |
| v0.8 | 2026-11-04 | Repository pushed to the **interim host** `Lecabe-Tech-Company/isg-plugins` (private); ownership to be transferred to the Instituto's account later (Q2, P-44, transfer checklist in `docs/RELEASING.md`). |
| v0.7 | 2026-11-04 | For SPEC-002: REQ-SRF-03 and VAL-13 amended to allow a **remote** MCP server with a fixed URL (the bundled Notion connection); new check C-13; out-of-scope line now points to SPEC-002 / SPEC-003+. |
| v0.6 | 2026-11-04 | **Implementation.** Repo created at `C:\dev\isg-plugins` (outside OneDrive, P-26): scaffold, `configure`/`upgrade` skills and scripts, CI check scripts, 31 tests, `validate.yml`, `release.yml`, docs. New spec text: 7.1 status; file list in 4.1; test-only hooks and `redact()` in 4.8; REQ-CST-02 (no path filters); VAL-03 method verified. The repo copy of `specs/` is canonical from now on. |
| v0.5.2 | 2026-11-04 | **T0 Part 1** (this machine): results in `SPEC-001-T0-results.md`; 1.5 status table; CLI resolution via `CLAUDE_CODE_EXECPATH` and script-file quoting rule (4.8); C-03; P-42, P-43; `MIN_CLAUDE_VERSION` = 2.1.317 provisional. Part 2 (GitHub, claude.ai, cloud) pending. |

### 0.2 Glossary

| Term | Meaning in this spec |
|---|---|
| **User** | A person who installs and uses the plugin. GitHub collaborator with **Read** access, with a Claude Pro, Max, Ultra, Team or Enterprise plan. |
| **Maintainer** (= **release owner**) | GitHub collaborator with **Write** access. Can open/approve PRs and run the Release workflow. |
| **Org owner** | Owner of the free GitHub organization. Manages collaborators and the Claude GitHub App installation. At least two people. |
| **Marketplace** | The repository `<org>/isg-plugins`, which contains `.claude-plugin/marketplace.json`. |
| **Plugin** | The folder `plugins/isg-model-alignment/` inside the marketplace. |
| **Release** | A version that the Release workflow has validated, tagged `isg-model-alignment--vX.Y.Z`, published as a GitHub Release and promoted to the `stable` branch. **Nothing else is a release.** |
| **`main`** | Integration branch. Maintainers merge PRs here. **Users never install from `main`.** |
| **`stable`** | Delivery branch **and the repository's default branch**. Every install route reads it. Only the Release workflow moves it. |
| **Surface** | A place where the user talks to Claude: S1–S6 in 1.6. |
| **Route** | A way the plugin reaches a surface: R1–R4 in 1.6. |
| **Synced plugin** | A plugin added to the user's claude.ai account, which Claude Code downloads as `isg-model-alignment@synced`. |
| **Plugins root** | `~/.claude/plugins` on the user's machine, or the value of `CLAUDE_CODE_PLUGIN_CACHE_DIR` if set. |
| **Skill** | A `SKILL.md` folder under `skills/`. In Claude Code and Cowork it is also a command: `/isg-model-alignment:<skill>`. |
| **Portable core** | Skill behavior that works on every surface: instructions only, no shell, no scripts (REQ-SRF-02). |

---

## 1. Context and goals

The Instituto needs a Claude plugin that helps one of its many quality processes. The plugin's domain skills come later (SPEC-002+). First we need the **delivery system** around it:

1. **Easy to install**, and only **authorized people** can reach it (private).
2. **Easy to upgrade**, through a repeatable **release system**.
3. **Easy commands** for users: `configure` (auto-configure the plugin) and `upgrade` (move to the newest version).
4. **Works everywhere the team uses Claude**: Claude Code (including the Desktop Code tab and Claude Code on the web), claude.ai chat, Desktop chat and Cowork.

### 1.1 Platform facts this design relies on

Read in the official docs on 2026-11-04 (sources in section 10). Items marked ⚠ are also listed in 1.5 to be confirmed by hand in T0.

**Plugins and marketplaces**
- A plugin is a directory with an optional manifest at `.claude-plugin/plugin.json`. Components (skills, agents, hooks, MCP servers) live at the plugin root, **not** inside `.claude-plugin/`.
- A **marketplace** is a git repo with `.claude-plugin/marketplace.json`. It can be private.
- A plugin's **version** comes from `plugin.json` first, then the marketplace entry, else the git commit SHA. Claude Code updates a copy **only when that version changes**.
- Plugin names that start with `claude-`, `anthropic-`, etc. are reserved and rejected.

**The same plugin folder works on every surface, but each surface loads a different subset**

| Component | claude.ai chat / Desktop chat | Cowork | Claude Code (all) |
|---|---|---|---|
| Skills | Loads | Loads | Loads |
| Commands | Loads **as a skill** (Claude uses it when it fits) | Loads; run as `/plugin:command` | Loads |
| Agents | Ignored | Loads | Loads |
| Hooks | Ignored | Loads | Loads |
| Remote MCP (fixed URL) | Via the plugin's Connectors tab | Loads | Loads |
| Local MCP / `.mcpb` | Ignored | Only when Cowork runs on the computer | Loads |
| `userConfig` values | Not prompted | Not prompted | Prompted |
| Top-level `bin/` | **Plugin refused** | **Plugin refused** | Loads |

**Claude Code (terminal, IDE, Desktop Code tab)**
- The terminal, the Desktop app's Code tab (local and SSH sessions) and the IDE extensions read the **same settings files**; a plugin installed at user scope in one is available in the others.
- CLI install: `claude plugin marketplace add <owner>/<repo>[#ref]`, then `claude plugin install <plugin>@<marketplace>`. A GitHub marketplace can be pinned with `#<ref>`.
- Claude Code has **no git token of its own**: it uses the git credentials already on the machine, with prompts off. For `owner/repo` it tries SSH first; in-session installs and updates do not fall back to HTTPS, so machines without an SSH key need `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`.
- Background auto-update is **off by default** for third-party marketplaces; against a private repo it needs a **stored** credential (`gh auth login` + `gh auth setup-git`). `GITHUB_TOKEN` alone does not work.
- `${CLAUDE_PLUGIN_ROOT}` is the folder of the installed version; it changes on every update and old folders are deleted after 14 days. It is **substituted inline in skill text**, not exported to the Bash tool. Only the **plugin folder** is copied to the cache.
- After an update the running session keeps the old version until `/reload-plugins` or a restart.
- `claude plugin tag` creates annotated tags `<plugin>--v<version>`.

**claude.ai account (chat, Desktop chat, Cowork, and synced into Claude Code)**
- Users add plugins in **Customize > Plugins** in claude.ai or the Desktop app. **Add > Add marketplace** accepts a GitHub repo (`owner/repo`). For a **private** repo the user connects their GitHub account and gives the **Claude GitHub App** access to the repo.
- A plugin added to the account is available in chat (web, desktop, mobile) and Cowork, and is **downloaded by Claude Code as a synced plugin** (`<name>@synced`) at the next start, when Claude Code is signed in with that claude.ai account.
- Updates: "Check for updates" pulls the latest from the source; for a github.com marketplace the user added, **Sync automatically** can be turned on. ⚠ (which branch: A10)
- Account limits: up to 25 self-added marketplaces; a plugin up to 5,000 files and 200 MB.
- On Team/Enterprise, an Owner controls which sources members see and whether they can add their own, and can sync a private repo for the whole organization (**Organization settings > Plugins & skills**), which rejects a plugin with a top-level `bin/`.

**Claude Code on the web (cloud sessions)**
- Available on Pro, Max, Ultra and Team, and Enterprise premium / Chat + Claude Code seats. Started from claude.ai/code, the Desktop app, mobile, or `claude --cloud`.
- Runs on a fresh **Ubuntu VM** with the repo cloned. It does **not** load plugins installed on the user's machine, and does **not** install plugins that a repo's `.claude/settings.json` enables. It does receive server-managed settings (Team/Enterprise) and **skills enabled on claude.ai**. ⚠ (synced plugins: A11)
- An environment can have a **setup script** (Bash, root, < 5 min, cached ~7 days). GitHub traffic goes through a **GitHub proxy** scoped to the repositories attached to the session. ⚠ (A12)

### 1.2 Design decisions

| # | Decision | Why |
|---|---|---|
| D1 | **One private GitHub repository** holds the marketplace and the plugin (`plugins/isg-model-alignment/`, relative-path source). | One place to manage, one access list. |
| D2 | Access control = **repository collaborators** in a **free GitHub organization** owned by the Instituto. Users get Read, maintainers get Write. | Every route reads the repo with the user's own GitHub identity; free. |
| D3 | For the **CLI route (R2)** users authenticate once with `gh auth login` + `gh auth setup-git` (HTTPS) and set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`. For the **account route (R1)** they connect GitHub on claude.ai instead. | Each route uses the credential it supports. |
| D4 | **Explicit SemVer `version` in `plugin.json` only.** | Predictable upgrades, auditable history. |
| D5 | **Two branches.** `main` = integration. `stable` = delivery. Only the Release workflow fast-forwards `stable`. | On Free we cannot protect `main`; this keeps unreleased pushes away from users. |
| D6 | **Release = release PR + Release workflow.** The workflow only checks, tags, publishes and promotes. It never commits. | Every released commit came through an approved PR. |
| D7 | CI on **GitHub Actions, Linux runners**. One Windows smoke test per release. macOS by hand. | Stays inside free minutes. |
| D8 | `configure` and `upgrade` are **surface-aware skills**. Where a shell and `node` exist (Claude Code), they call **Node.js scripts** shipped in the plugin. Where they don't (chat, Cowork), the skill gives PT-BR manual steps. Scripts never prompt; Claude asks the user. | One code base; works on every surface. |
| D9 | Paid repository controls are replaced by **process + workflow checks + gitleaks**. | Zero cost (1.3, 1.4). |
| D10 | Fleet rollout via **managed settings** is optional and documented only (Q4). | Not required for v1. |
| D11 | **`stable` is the repository's default branch.** PRs target `main`. | claude.ai, org sync and `owner/repo` without `#ref` all read the default branch, so every route sees releases only (A10). |
| D12 | **Primary install route = claude.ai account (R1).** One install reaches chat, Desktop chat, Cowork, Claude Code (synced, including the Desktop Code tab) and, if A11 holds, Claude Code on the web. The CLI route (R2) is for maintainers, testers, and users who cannot use R1. | Simplest for users; one place to update; covers all surfaces. |

### 1.3 Zero-cost constraint (decided)

The Instituto has no paid GitHub account and the plugin must add no cost.

**What the GitHub Free plan gives us** (re-verify on github.com/pricing in T0, assumption A7)
- Unlimited **private repositories** with unlimited **collaborators**.
- **Pull requests and reviews** (reviews can be given, but not *required*).
- **GitHub Actions** for private repos with a monthly free minute quota (about 2,000 min/month). Windows minutes count 2x and macOS 10x.
- GitHub Releases, tags, Issues, `gh` CLI. Installing the **Claude GitHub App** on the organization is free.

**What the Free plan does *not* give us on private repos**
- Enforced branch protection / rulesets, required reviews, required status checks, CODEOWNERS enforcement, protected tags, environment approvals.
- Native secret scanning / push protection.
- Any collaborator with Write access can push to any branch, create tags and run workflows.

**Free-only rules**
- No paid service anywhere: no paid CI, registry, hosting, signing service, paid GitHub App, paid Marketplace action, or paid API key.
- **CI never uses an Anthropic API key.** CI runs only Claude Code CLI commands that need no model call (assumption A1).
- Users use the **Claude plan they already have** (Pro, Max, Ultra, Team or Enterprise). Supporting a surface must never require buying a plan or upgrading a seat. A user whose plan lacks a surface (for example an Enterprise standard seat without Claude Code on the web) simply does not get that surface.
- The plugin calls no external paid API.
- If something needs a paid feature, it is replaced by a documented manual procedure or a CI check. Never by buying a plan.

### 1.4 Risk acceptance (decided 2026-11-04)

The Instituto understands the risks of managing the plugin on a free GitHub account (no enforced branch protection, required reviews or protected tags; limited Actions minutes; plan limits set by GitHub; see P-19 to P-25) and **explicitly accepts them**. They are managed **through process, not pricing**.

- Process controls are **mandatory**: PR-only changes to `main` (REQ-ACC-03), Release workflow gates (REQ-REL-03), `stable` moved only by the workflow (REQ-REL-09), at least two maintainers (REQ-ACC-07), quarterly review (REQ-ACC-06, VAL-10).
- The release owners own the process. Each quarterly review is recorded in `docs/RELEASING.md` (date, reviewer, collaborators list, Actions minutes used).
- A risk that happens is handled by the documented procedure (rollback REQ-REL-06, manual release fallback in `docs/RELEASING.md`), **never by buying a plan**. Changing this decision needs an explicit new decision by the Instituto and a new version of this spec.
- **Accepted residual risk:** a maintainer can technically bypass the process (push to `stable`, create a tag by hand). Detection relies on the quarterly review and on checking that every tag and every `stable` move was made by `github-actions[bot]` from the Release workflow (P-25).

### 1.5 Assumptions to verify before coding (task T0)

These come from the docs but must be **tried by hand** before T1. If one fails, **update this spec first**, then build. Each row names the fallback if it fails.

| ID | Assumption | How to check | Affects | If it fails |
|---|---|---|---|---|
| A1 | `claude plugin validate`, `marketplace add <local path>`, `install`, `list` run in CI with **no login and no API key**. | GitHub Actions Linux job with no secrets. | VAL-01, 02, 05; REQ-CST-04 | Run them locally in the release PR checklist |
| A2 | `claude plugin list --json` and `claude plugin marketplace list --json` exist and return id (incl. `@synced`), version, enabled state, source/ref. | Run locally, save samples in `docs/dev/cli-samples/`. | REQ-CMD-01, 07, 4.11 | Parse human output |
| A3 | `marketplace add <org>/<repo>#stable` follows `stable` on update and auto-update. | Move `stable`, update, check version. | REQ-REL-09 | Rely on D11 (default branch) only |
| A4 | Where `pluginConfigs` stores `userConfig` values and that `${user_config.user_name}` is substituted in skill text in Claude Code. | Inspect `~/.claude/settings.json`. | REQ-CMD-03 | Drop C-09 |
| A5 | `claude plugin update …` works from Claude's Bash tool in a session; the session keeps the old version until `/reload-plugins`. | Manual run. | REQ-CMD-08 | Tell the user to run it in their own terminal |
| A6 | `claude plugin tag --push` works in Actions with `GITHUB_TOKEN`; tag author is `github-actions[bot]`. | Test repo. | REQ-REL-03 | Plain `git tag -a` with the same name |
| A7 | GitHub Free: private repo, collaborators, PR reviews, Actions quota, commit→PR API, Claude GitHub App install — all at no cost. | Pricing page; real org. | 1.3, REQ-ACC-03 | Spec change needed |
| A8 | `autoUpdate: true` on the `extraKnownMarketplaces` entry in `~/.claude/settings.json` turns auto-update on. | Set, restart, check `/plugin`. | REQ-CMD-05 | UI instructions only |
| A9 | PT-BR accents print correctly from Node scripts through the Bash tool (Windows Git Bash and PowerShell 5.1, macOS, Linux). | Print a test string. | REQ-LNG-01 | Force UTF-8 output in `run.mjs` |
| A10 | **claude.ai "Add marketplace" reads the repository default branch** (or accepts a ref), and "Check for updates" / "Sync automatically" pick up a new commit on that branch. | Add the repo on claude.ai, move `stable`, check. | D11, R1 | Users use R2 for Claude Code; chat users told to re-check after each release announcement |
| A11 | **Claude Code on the web loads plugins from the user's claude.ai account** (synced plugins). | Add plugin via R1, open a cloud session, type `/isg-model-alignment:`. | S3, R1 | Use R4 |
| A12 | A cloud **environment setup script** can clone the private marketplace (repo attached to the session or through the GitHub proxy) and run `claude plugin marketplace add … && claude plugin install …`; the install survives via the environment cache. | Real cloud environment. | S3, R4 | Claude Code on the web supported only through R1 (if A11) — else documented as not supported |
| A13 | A script can detect a cloud session (for example an environment variable such as `CLAUDE_CODE_REMOTE`) and the route (`@synced` vs `@isg-plugins` in `claude plugin list`). | Print env in a cloud session. | 4.11 | Ask the user which surface they are on |
| A14 | `disable-model-invocation: true` is respected in chat and Cowork (commands loaded as skills are not auto-run). | Chat test. | REQ-CMD-14, P-39 | Skill text forbids action unless the user typed the command |
| A15 | **On claude.ai, a person whose GitHub account is not a collaborator cannot add the private marketplace**, even though the Claude GitHub App is installed on the organization. | Test with a non-collaborator account. | REQ-ACC-01, R1 | **Blocking:** if anyone can add it, R1 is restricted to Team/Enterprise R3 or dropped; spec change |
| A16 | In Cowork, skills cannot run the `claude` CLI (and whether they can run shell/`node` at all). | Cowork test. | 4.11 | Adjust Cowork column of 4.11 |
| A17 | Exact PT-BR labels of the claude.ai / Desktop UI ("Customize > Plugins", "Add marketplace", "Check for updates", "Sync automatically"). | Open the UI in Portuguese. | Docs, skill text | Write labels in English with a PT-BR explanation |

**T0 status (2026-11-04, Claude Code 2.1.317 on Windows)** — details, evidence and the Part 2 checklist (G1–G11) are in [SPEC-001-T0-results.md](SPEC-001-T0-results.md).

| Status | Assumptions |
|---|---|
| **Confirmed** | A2 (`--json` outputs), A4 (storage path `pluginConfigs.<id>.options.<key>`), A9 on Windows (UTF-8 through Bash and PowerShell 5.1) |
| **Confirmed locally, still to prove elsewhere** | A1 (CI), A6 (`plugin tag` dry-run OK; `--push` in Actions pending) |
| **Partly** | A5 (command exists; not run in a session), A13 (`CLAUDE_CODE_ENTRYPOINT=claude-desktop` locally; cloud value unknown) |
| **Needs GitHub / claude.ai / cloud / people (Part 2)** | A3, A7, A8, A10, A11, A12, A14, A15 (**blocking for R1**), A16, A17 |

**Findings that changed this spec (v0.5.2):** F1 `claude` is **not on `PATH`** in Desktop-app sessions (use `CLAUDE_CODE_EXECPATH`, see 4.8, C-03, P-42); F2 Git for Windows defaults to `core.autocrlf=true` (confirms REQ-REP-06); F3 a *directory* marketplace loads in place, so version tests need a git marketplace; F6 `gh` is not installed by default (guide must cover it); F7 `MIN_CLAUDE_VERSION` = `2.1.317` (tested; Q7).

### 1.6 Supported surfaces, plans and install routes (decided 2026-11-04)

**Plans:** Claude Pro, Max, Ultra, Team, Enterprise. Claude **Free is not supported** (no directory, no cloud sessions, and plugin features are limited). A Team/Enterprise organization owner may restrict which sources members can add; then that organization uses R3.

**Surfaces**

| ID | Surface | Main route | Plugin parts that work | `configure` / `upgrade` |
|---|---|---|---|---|
| S1 | Claude Code in a **terminal or IDE** (local) | R1 (synced) or R2 | All | Full (scripts) |
| S2 | **Desktop app, Code tab** (local or SSH session) | Same as S1 (same settings files) | All | Full (scripts) |
| S3 | **Claude Code on the web** (cloud session; from claude.ai/code, Desktop, mobile) | R1 if A11, else R4 | All (Linux VM) | Reduced checks (4.11) |
| S4 | **claude.ai web chat** | R1 (or R3) | Skills, commands as skills | Manual steps, no scripts |
| S5 | **Desktop app chat** | R1 (or R3) | Skills, commands as skills | Manual steps, no scripts |
| S6 | **Cowork** (Desktop) | R1 (or R3) | Skills, commands, agents, hooks | Manual steps (A16) |

**Install routes**

| ID | Route | Who | How | Reaches |
|---|---|---|---|---|
| **R1** | **claude.ai account (primary)** | Every user | claude.ai or Desktop: **Customize > Plugins > Add > Add marketplace** → `<org>/isg-plugins` → connect GitHub / give the Claude GitHub App access → add **ISG Model Alignment** → turn on **Sync automatically** | S1–S6 (S3 if A11) |
| **R2** | Claude Code CLI | Maintainers, testers, users who cannot use R1 | `claude plugin marketplace add <org>/isg-plugins#stable` → `claude plugin install isg-model-alignment@isg-plugins` | S1, S2 |
| **R3** | Organization sync (optional) | A Team/Enterprise **Claude org Owner** | **Organization settings > Plugins & skills**: sync `<org>/isg-plugins`, set the plugin to *Installed by default* or *Required* | Members of that Claude org: S1–S6 |
| **R4** | Cloud setup script (fallback) | User, per cloud environment | Environment setup script runs the R2 commands (A12) | S3 |

**Rules**
- A person uses **one** route per machine/account: **R1** unless there is a reason not to. Do not combine R1 and R2 on the same machine (P-33).
- **R3 changes who has access:** everyone in that Claude organization gets the plugin, whether or not they are GitHub collaborators. An org Owner may use R3 only if that matches the Instituto's access rule for that organization (Q10).
- Every route reads the **`stable`** branch (D11 default branch; R2 also writes `#stable` explicitly).

---

## 2. Requirements

Priority: **M** = must, **S** = should, **C** = could. IDs are stable. Every commit and PR references the IDs it implements. An ID is never reused for a different meaning; a dropped requirement is marked *withdrawn*, not deleted.

### 2.1 Installation (REQ-INS)

| ID | P | Requirement |
|---|---|---|
| REQ-INS-01 | M | **R2 (CLI):** after the one-time setup (REQ-INS-08), the plugin is installed with exactly two commands: `claude plugin marketplace add <org>/isg-plugins#stable` and `claude plugin install isg-model-alignment@isg-plugins`. |
| REQ-INS-02 | M | An **install guide** exists in PT-BR (`docs/INSTALL.pt-BR.md`) and English (`docs/INSTALL.md`). It starts with **R1**, then has short sections for R2, R3 and R4, and a "which surface am I on" table. Each route section fits on one printed page. It says how to ask for access. |
| REQ-INS-03 | M | The repository is **private**. Only invited collaborators can read it, on every route except R3 (REQ-INS-11). A user without access gets a failure, and the guide says whom to ask (the org owners, named in the guide). |
| REQ-INS-04 | M | R2 works on machines **without an SSH key**. The guide sets `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` as part of R2 setup. |
| REQ-INS-05 | S | R2 install scope defaults to **user**. The guide also explains **project** scope. |
| REQ-INS-06 | S | An optional **bootstrap script** (`install.ps1`, `install.sh`) at the repo root does the R2 setup and install. Users get it from the private repo, never from a public URL. |
| REQ-INS-07 | C | IT guide for fleet install through **managed settings** (Claude Code). Documentation only. |
| REQ-INS-08 | M | **Prerequisites**, all free. **Every route:** a personal GitHub account invited as collaborator (Q9) and a supported Claude plan. **R1:** claude.ai account; in Claude Code, signed in with that claude.ai account (not an API key). **R2:** Claude Code ≥ `MIN_CLAUDE_VERSION` (Q7), `git`, `gh`, Node.js LTS ≥ 20; one-time `gh auth login` (GitHub.com, HTTPS) → `gh auth setup-git` → `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`. **Scripts (S1, S2):** Node.js LTS ≥ 20. **PDF processing (`cfp`, SPEC-003):** Python 3.11 or newer (free); only needed for that skill. |
| REQ-INS-09 | M | `configure` runs **after** install (it is part of the plugin). Everything needed **before** install is covered by the guide or the bootstrap script. |
| REQ-INS-10 | M | **R1 (account route)** is the primary route. The guide gives the exact steps of 1.6 with the UI labels confirmed in A17. Once per GitHub org, an org owner installs the **Claude GitHub App** on the organization with access to `isg-plugins` only. |
| REQ-INS-11 | C | **R3 (organization sync)** is documented for Team/Enterprise Claude org Owners, including the warning that it grants access to every member of that Claude organization. |
| REQ-INS-12 | S | **R4 (cloud setup script)**: if A12 holds, the guide provides a ready setup script for a cloud environment. If A11 holds, R4 is listed only as a fallback. |

### 2.2 Access control (REQ-ACC)

| ID | P | Requirement |
|---|---|---|
| REQ-ACC-01 | M | Access is managed **only** in GitHub (collaborators on the repo) for R1, R2 and R4. No token, password, or URL with credentials is committed or shipped in the plugin. **R1 is allowed only if A15 holds.** |
| REQ-ACC-02 | M | Offboarding = remove the person from the collaborators. After that they cannot fetch updates. Copies already installed or already on their claude.ai account keep working until removed; the guide says so. For R3, offboarding also means removing them from that Claude organization. |
| REQ-ACC-03 | M | Changes reach `main` **only through a pull request** with at least one approval from a maintainer who is not the author (team rule, documented in `docs/RELEASING.md`). No direct pushes and no force-pushes on `main` or `stable`. PRs never target `stable`. |
| REQ-ACC-04 | S | A `CODEOWNERS` file documents who should review what. It is **not enforced** on Free; enforcement is the Release workflow (REQ-REL-03). |
| REQ-ACC-05 | S | The plugin contains **no secrets**. If a future user-specific value is secret, it uses `userConfig` with `sensitive: true` (Claude Code only; see REQ-SRF-05). |
| REQ-ACC-06 | S | **Quarterly review** by a release owner: collaborators and access levels, Claude GitHub App repository access, authors of all tags and `stable` moves since the last review, Actions minutes used. Also after every offboarding. Logged in `docs/RELEASING.md`. |
| REQ-ACC-07 | M | There are **at least two maintainers** (Write) and **two org owners**. |
| REQ-ACC-08 | M | The Claude GitHub App is installed on the GitHub organization with access to **only** the `isg-plugins` repository and read-only permissions where the app allows choosing. |

### 2.3 Release and versioning (REQ-REL)

| ID | P | Requirement |
|---|---|---|
| REQ-REL-01 | M | Versions follow **SemVer** `MAJOR.MINOR.PATCH`. `version` lives **only** in `plugins/isg-model-alignment/.claude-plugin/plugin.json`, never in the marketplace entry. First release is `0.1.0`. |
| REQ-REL-02 | M | There is **one** release procedure: (1) a **release PR** to `main` that bumps `version` and adds the CHANGELOG section, reviewed and merged per REQ-ACC-03; (2) a maintainer runs the **Release workflow** (`workflow_dispatch`, no inputs) with branch `main` selected. |
| REQ-REL-03 | M | The Release workflow **never commits**. In this order it: (a) checks the actor has Write access; (b) checks it runs on `main` HEAD; (c) checks the HEAD commit belongs to a merged PR with ≥ 1 approval from someone other than the author; (d) reads `version` from `plugin.json`, checks valid SemVer and **greater** than the latest `isg-model-alignment--v*` tag; (e) checks `CHANGELOG.md` has a section for exactly that version; (f) runs VAL-01..04, 11, 13; (g) runs the Windows smoke test (VAL-05 on Windows) and VAL-08; (h) creates the tag with `claude plugin tag --push` as `github-actions[bot]`; (i) publishes a GitHub Release whose notes are that CHANGELOG section; (j) fast-forwards `stable` to the tagged commit. Any failed step stops the workflow and **nothing after it runs**. |
| REQ-REL-04 | M | A release **cannot** be published if `claude plugin validate --strict` fails. |
| REQ-REL-05 | M | `plugins/isg-model-alignment/CHANGELOG.md` is written in **PT-BR** in the format of section 4.6. A breaking change goes under `### Quebra de compatibilidade` and requires a MAJOR bump (while `0.x`, a MINOR bump). |
| REQ-REL-06 | S | **Rollback** = revert the bad change on `main` and release a **new PATCH**. Never move `stable` backwards, never reuse a version number, never delete or move a published tag. |
| REQ-REL-07 | C | **Early access** for maintainers only: R2 with `#main` instead of `#stable`. Never recommended to users. Not available through R1. |
| REQ-REL-08 | C | Renaming or removing the plugin uses the marketplace `renames` map. Prefer changing only `displayName`. |
| REQ-REL-09 | M | `stable` is the **only** branch any route installs from and the repository **default branch** (D11). It is created from the `0.1.0` release commit and moved **only** by the Release workflow, **fast-forward only**. |
| REQ-REL-10 | M | After each release, a maintainer **announces** it to users (channel decided by the Instituto) with the version and the PT-BR highlights, and reminds R1 users that "Sync automatically" or "Check for updates" brings it. |

### 2.4 Commands (REQ-CMD)

Both commands are skills: `/isg-model-alignment:configure` and `/isg-model-alignment:upgrade`. Their behavior depends on the surface and route (section 4.11).

| ID | P | Requirement |
|---|---|---|
| REQ-CMD-01 | M | `configure` runs the checks of section 4.7 that apply to the current surface/route and shows a **pass/fail checklist in PT-BR** with a fix hint for every failure. All applicable checks run even when one fails. |
| REQ-CMD-02 | M | `configure` is **idempotent**: on a healthy machine, a second run changes nothing and reports the same result. |
| REQ-CMD-03 | S | `configure` reports whether the optional `userConfig` value `user_name` is set (Claude Code only). If not, it explains in PT-BR how to set it. It does **not** write `pluginConfigs` itself. Sensitive values are never printed. |
| REQ-CMD-04 | M | `configure` **asks before changing** anything, and shows exactly what will change (file, key, old value, new value). It changes only the items in REQ-CMD-05. It backs up a settings file before editing it (`settings.json.bak-<timestamp>`). |
| REQ-CMD-05 | S | On R2 only, `configure` may **offer** these changes to `~/.claude/settings.json`: (a) `autoUpdate: true` on the `isg-plugins` entry under `extraKnownMarketplaces`; (b) `CLAUDE_CODE_PLUGIN_PREFER_HTTPS: "1"` under `env`. If editing is not possible, it explains the UI path. |
| REQ-CMD-06 | S | `configure --check` is strictly **read-only**. |
| REQ-CMD-07 | M | `upgrade` shows the **installed version**, the **latest version on `stable`** (when it can find it), and the CHANGELOG sections in between, then asks for confirmation before any change. |
| REQ-CMD-08 | M | On **R2**, `upgrade` uses only the official CLI: `claude plugin marketplace update isg-plugins`, then `claude plugin update isg-model-alignment@isg-plugins`, confirms with `claude plugin list`, and tells the user to run `/reload-plugins` (or restart). On **R1/R3** it never runs `claude plugin update`; it explains how the account update works (4.11). |
| REQ-CMD-09 | M | `upgrade` gives distinct PT-BR messages for: already up to date, no access, offline/network error, update failed, update managed by the claude.ai account. The installed version is unchanged in every failure case. |
| REQ-CMD-10 | S | `upgrade --check` only reports whether an update exists (on R2 it refreshes the catalog but never updates the plugin). |
| REQ-CMD-11 | S | When the update contains `### Quebra de compatibilidade`, `upgrade` shows it first and asks for explicit confirmation. |
| REQ-CMD-12 | M | **Skill/script split.** Each skill is short: it tells Claude (in PT-BR) how to find out the surface, which script to run where scripts are possible, how to present the result, and what to say where they are not. All logic for S1–S3 is in Node scripts under `plugins/isg-model-alignment/scripts/`, following section 4.8. |
| REQ-CMD-13 | M | Scripts are **non-interactive**: they never read stdin, never wait for input, and run git with prompts disabled. Confirmation is always asked **by Claude in the conversation**, after which Claude runs the script again with `--apply`. |
| REQ-CMD-14 | S | `configure` and `upgrade` set `disable-model-invocation: true`. Their text also says: act only when the user typed the command (A14). |

### 2.5 Repository and quality gates (REQ-REP)

| ID | P | Requirement |
|---|---|---|
| REQ-REP-01 | M | Repo layout follows section 4.1. Component paths are relative, start with `./`, use forward slashes, and stay inside the plugin folder. |
| REQ-REP-02 | M | The marketplace entry `name` equals the `plugin.json` `name` (`isg-model-alignment`). |
| REQ-REP-03 | M | CI runs on every PR to `main`: VAL-01, 02, 03, 04, 07, 11, 12, 13. A PR with a red check is not merged (team rule). A PR that targets `stable` fails a check named `pr-must-target-main`. |
| REQ-REP-04 | S | A smoke test installs the plugin from the local checkout into an empty plugins root and checks it is enabled (VAL-05). |
| REQ-REP-05 | S | Scripts run unchanged on Windows, macOS and Linux (P-07, P-26 to P-29). |
| REQ-REP-06 | M | `.gitattributes` forces **LF** line endings (`* text=auto eol=lf`); all text files are **UTF-8 without BOM**. |
| REQ-REP-07 | M | Names and values used in more than one place (plugin name, marketplace name, repo URL, `stable`, `MIN_CLAUDE_VERSION`, tag prefix) are defined **once** in `scripts/lib/constants.mjs` and read from there by scripts and CI checks. |

### 2.6 Cost (REQ-CST)

| ID | P | Requirement |
|---|---|---|
| REQ-CST-01 | M | The whole delivery system runs on **free tiers only**: GitHub Free, the free Claude GitHub App, open-source tools, no paid service or secret. |
| REQ-CST-02 | M | Actions usage stays **under the free monthly quota**. Budget: PR check ≈ 3 min Linux; release ≈ 5 min Linux + ≈ 5 min Windows (= 10 billed min). `concurrency` cancels superseded runs. **No path filters:** the secret scan must run on every change, docs included (v0.6). Estimate in `docs/RELEASING.md`. |
| REQ-CST-03 | M | No requirement may be met by buying a plan, seat or service. If no free route exists, it is met by a documented manual procedure or the surface is documented as unsupported for that user. |
| REQ-CST-04 | M | Workflows use **no Anthropic API key and no paid secret**. Third-party actions are free, open source, and **pinned to a commit SHA**. Prefer official `actions/*`. |

### 2.7 Language (REQ-LNG)

| ID | P | Requirement |
|---|---|---|
| REQ-LNG-01 | M | Everything the user sees or Claude is told to produce is **PT-BR**: `SKILL.md` body and `description`, script messages, `userConfig` `title`/`description`, `plugin.json` `description`, marketplace `description`, generated content. Each `SKILL.md` contains the instruction in section 4.9. |
| REQ-LNG-02 | S | Technical identifiers stay **English**: plugin and command names, file names, paths, CLI flags, JSON keys, check IDs, error codes. |
| REQ-LNG-03 | S | Maintainer material is **English** (`specs/`, `docs/RELEASING.md`, code, comments, commit messages, PR titles). End-user material is **PT-BR first** with an English copy (`docs/INSTALL*.md`, `docs/TROUBLESHOOTING*.md`). |
| REQ-LNG-04 | M | `CHANGELOG.md`, GitHub Release notes and release announcements are **PT-BR**. |

### 2.8 Surfaces (REQ-SRF)

| ID | P | Requirement |
|---|---|---|
| REQ-SRF-01 | M | The plugin installs and its skills load on **S1–S6** through R1, and on S1–S2 through R2. S3 is supported through R1 if A11 holds, else through R4 if A12 holds; if neither holds, S3 is documented as not supported until the platform allows it. |
| REQ-SRF-02 | M | **Portable core.** Every user-facing skill (now and in SPEC-002+) must deliver its main value on **every** surface using **instructions only**: no shell, no scripts, no hooks, no agents, no local MCP, no `userConfig`, no `${CLAUDE_PLUGIN_ROOT}`. Scripts, agents and hooks may only add **optional** extras where the surface supports them, and the skill must say what to do when they are absent. `configure` and `upgrade` are the only skills whose main path uses scripts, and they also have a no-script path (4.11). |
| REQ-SRF-03 | M | The plugin has **no top-level `bin/`** (it would be refused on S4–S6) and **no hooks, no agents, no local MCP servers, no LSP, no output styles**. **Amended v0.7:** a **remote** MCP server with a fixed `https://` URL and no headers, tokens, environment variables or `${user_config}` is allowed in `.mcp.json`, because it works on every surface (Claude Code loads it; chat and Cowork show it on the plugin's Connectors tab). Today only the Notion server of SPEC-002 REQ-MCP-01. Adding anything else still requires a spec change that states its behavior per surface. |
| REQ-SRF-04 | M | `configure` and `upgrade` **detect the surface and route** (4.11) and follow the matching column. Where they cannot run commands, Claude **never claims** to have run or checked something; it gives the manual PT-BR steps. |
| REQ-SRF-05 | M | `userConfig` fields are **optional** (no `required: true`). A skill that uses a value must ask the user in the conversation when the value is not available (S4–S6 never prompt for it). |
| REQ-SRF-06 | M | The plugin fits claude.ai limits: < 200 MB and < 5,000 files (in practice a few hundred KB). |
| REQ-SRF-07 | M | The guide states plainly: Claude **Free** is not supported; Claude Code on the web needs a plan/seat that includes it; R1 in Claude Code needs Claude Code signed in with the claude.ai account. |
| REQ-SRF-08 | S | Skill text never relies on a UI element of one surface (for example "click the + button") without saying which surface it is for. |

---

## 3. Acceptance criteria

Given / When / Then. "Authorized user" = collaborator with Read access, on a supported Claude plan, who has done the setup of their route.

**AC-INS-1 — R2 happy path (REQ-INS-01, 02, 08)**
- Given an authorized user on a clean machine with the R2 prerequisites,
- When they follow the R2 section of `docs/INSTALL.pt-BR.md`,
- Then `claude plugin list` shows `isg-model-alignment@isg-plugins` enabled at the latest released version, and `/isg-model-alignment:configure` is available in a new session.

**AC-INS-2 — No SSH key (REQ-INS-04)**
- Given a machine with no GitHub SSH key and `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`,
- When the user adds the marketplace and installs, from the shell and from `/plugin` in a session,
- Then both succeed over HTTPS and no prompt appears.

**AC-INS-3 — R1 happy path (REQ-INS-10, REQ-SRF-01)**
- Given an authorized user whose GitHub account is connected on claude.ai and the Claude GitHub App installed on the org,
- When they follow the R1 section of the guide,
- Then the plugin appears in **Customize > Plugins**, its skills are listed with `/` in claude.ai chat and Desktop chat, it is available in Cowork, and after restarting Claude Code (signed in with the same account) `claude plugin list` shows `isg-model-alignment@synced`.

**AC-ACC-1 — Unauthorized user is blocked (REQ-INS-03, REQ-ACC-01)**
- Given a person who is not a collaborator,
- When they try R2 (marketplace add) **and** R1 (Add marketplace on claude.ai with their own GitHub account connected),
- Then both fail, nothing is added, and `docs/TROUBLESHOOTING.pt-BR.md` has an entry for each error that says whom to ask. (R1 depends on A15.)

**AC-ACC-2 — Offboarding (REQ-ACC-02)**
- Given a user removed from the collaborators,
- When a new version is released and their machine / account refreshes,
- Then the refresh fails, the copy they have keeps working at its old version, and no newer version reaches them.

**AC-ACC-3 — No secrets (REQ-ACC-01, 05)**
- When gitleaks runs over the full history of any commit,
- Then it reports zero findings.

**AC-REL-1 — Release works end to end (REQ-REL-01..05, 09)**
- Given a merged and approved release PR that sets `version` to `0.2.0` and adds `## [0.2.0]`,
- When a maintainer runs the Release workflow on `main`,
- Then tag `isg-model-alignment--v0.2.0` exists (author `github-actions[bot]`), a GitHub Release with the PT-BR notes exists, `stable` points to the tagged commit, and the workflow made **no commit**.

**AC-REL-2 — Invalid plugin blocks the release (REQ-REL-04)**
- Given `main` where `claude plugin validate --strict` fails,
- When the Release workflow runs,
- Then it fails, and no tag, no Release and no `stable` move happen.

**AC-REL-3 — Version must increase and match CHANGELOG (REQ-REL-01, 03)**
- Given the latest tag is `isg-model-alignment--v0.2.0`,
- When the workflow runs with `plugin.json` at `0.2.0`, or `0.1.9`, or `0.3.0` without `## [0.3.0]`,
- Then each run fails with a clear message and nothing is published.

**AC-REL-4 — Users actually receive the release (REQ-REL-01, 09)**
- Given a user on `0.1.0` and a released `0.2.0`,
- When an R2 user runs `/isg-model-alignment:upgrade` (or auto-update runs) and an R1 user uses "Check for updates" (or "Sync automatically" runs),
- Then both have `0.2.0`: R2 in `claude plugin list`, R1 in **Customize > Plugins** and, after restarting Claude Code, as the synced copy.

**AC-REL-5 — Release authorization (REQ-ACC-03, REQ-REL-03)**
- When the Release workflow is started (a) by someone without Write access, (b) on a branch other than `main`, or (c) when the HEAD commit's PR has no approval from someone other than the author,
- Then (a) GitHub does not allow the run or the workflow fails at step (a); (b) and (c) fail before tagging; nothing is published.

**AC-REL-6 — Unreleased changes never reach users (REQ-REL-09, D5, D11)**
- Given users on the latest release through R1 and R2,
- When a maintainer merges a PR to `main` (even one that changes `version`) without running the Release workflow,
- Then neither R1 ("Check for updates") nor R2 (`upgrade --check`, auto-update) shows a new version.

**AC-CMD-1 — `configure` on a healthy machine (REQ-CMD-01, 02)**
- When `/isg-model-alignment:configure` runs twice on a correctly set up S1 machine (R2),
- Then both runs show all applicable checks passed in PT-BR and the second run changes nothing.

**AC-CMD-2 — `configure` diagnoses problems (REQ-CMD-01)**
- Given an R2 machine where `gh` is not logged in,
- When `configure` runs,
- Then check C-04 fails with the fix commands `gh auth login` and `gh auth setup-git`, and the remaining checks still run.

**AC-CMD-3 — `configure` is safe (REQ-CMD-03..06)**
- When `configure` would change a settings value,
- Then Claude shows the file, key, old and new value, and waits for "sim"; only REQ-CMD-05 items can change; a backup is created; `--check` changes nothing; no secret is printed.

**AC-CMD-4 — `upgrade` flow on R2 (REQ-CMD-07, 08, 11)**
- Given an older version installed through R2,
- When `/isg-model-alignment:upgrade` runs,
- Then it shows installed vs latest and the CHANGELOG sections in between (breaking first), asks to confirm, updates, shows the new version, and tells the user to run `/reload-plugins`.

**AC-CMD-5 — `upgrade` failure modes (REQ-CMD-09)**
- Given (a) already up to date, (b) no access, (c) offline,
- When `upgrade` runs on R2,
- Then each case shows a different PT-BR message, the script exits `0` for (a) and non-zero for (b) and (c), and the installed version is unchanged.

**AC-CMD-6 — Scripts never hang (REQ-CMD-13)**
- When every script is run with stdin closed and a 60-second timeout, in every mode, with `gh` logged out,
- Then every run finishes before the timeout; none waits for input.

**AC-SRF-1 — Commands without a terminal (REQ-SRF-04, REQ-CMD-12)**
- When a user types `/isg-model-alignment:configure` and then `/isg-model-alignment:upgrade` in claude.ai chat (S4), Desktop chat (S5) and Cowork (S6),
- Then Claude answers in PT-BR with the manual steps of 4.11 for that surface, and never says it ran, checked or changed anything.

**AC-SRF-2 — Synced copy in Claude Code (REQ-SRF-04, REQ-CMD-08)**
- Given the plugin reached Claude Code through R1 (`@synced`),
- When the user runs `/isg-model-alignment:upgrade`,
- Then it shows the installed version, the latest version on `stable` if it can read it, explains that updates come from the claude.ai account, and **does not** run `claude plugin update`.

**AC-SRF-3 — Claude Code on the web (REQ-SRF-01)**
- Given an authorized user with a plan that includes cloud sessions,
- When they start a Claude Code on the web session (from claude.ai/code and from the Desktop app),
- Then `/isg-model-alignment:configure` is available and runs its cloud checks (4.11), through R1 if A11 holds or R4 if A12 holds.

**AC-SRF-4 — Portable core (REQ-SRF-02, 03, 05)**
- Given the plugin at any release,
- When VAL-13 runs,
- Then there is no `bin/`, no hooks, agents, MCP, LSP or output styles, no `required: true` in `userConfig`, and no `${CLAUDE_PLUGIN_ROOT}` outside `configure` and `upgrade`.

**AC-CST-1 — Zero cost (REQ-CST-01..04)**
- After the first month of use,
- When an org owner opens *Settings > Billing and plans* and the Actions usage page,
- Then the plan is Free, the amount due is 0, Actions minutes are below the quota, and no paid app, action or secret is configured; no user had to change their Claude plan.

**AC-LNG-1 — PT-BR output (REQ-LNG-01, 02, 04)**
- When a user writes to Claude in English and then runs `configure` and `upgrade`, on S1, S4 and S6,
- Then every message, question and summary is in PT-BR with correct accents; command names, paths and flags stay English.

**AC-REP-1 — CI gate (REQ-REP-03, 06, 07)**
- Given a PR,
- When CI runs,
- Then VAL-01, 02, 03, 04, 07, 11, 12, 13 run on Linux, any failure shows a red check, and a PR targeting `stable` fails `pr-must-target-main`.

---

## 4. Design details

### 4.1 Repository structure

```text
isg-plugins/                      # private repo <org>/isg-plugins (marketplace root)
│                                          # default branch: stable   integration branch: main
├── .claude-plugin/
│   └── marketplace.json                   # catalog
├── plugins/
│   └── isg-model-alignment/               # THE PLUGIN (only this folder reaches users)
│       ├── .claude-plugin/
│       │   └── plugin.json                # name, version (single source of truth), optional userConfig
│       ├── skills/
│       │   ├── configure/SKILL.md         # /isg-model-alignment:configure   (PT-BR, surface-aware)
│       │   ├── upgrade/SKILL.md           # /isg-model-alignment:upgrade     (PT-BR, surface-aware)
│       │   └── cfp/SKILL.md               # /isg-model-alignment:cfp         (PT-BR; SPEC-003 PDF processing)
│       ├── scripts/                       # used only where a shell and node exist (S1–S3)
│       │   ├── configure.mjs
│       │   ├── upgrade.mjs
│       │   └── lib/
│       │       ├── constants.mjs          # REQ-REP-07
│       │       ├── run.mjs                # safe child-process wrapper (no prompts, timeouts, UTF-8)
│       │       ├── surface.mjs            # detects S1/S2/S3 and route R1/R2/R4 (4.11)
│       │       ├── io.mjs                 # argument parsing, JSON/human output, exit codes (4.8)
│       │       ├── settings.mjs           # config/plugins-root paths; the ONLY file that writes (REQ-CMD-04)
│       │       ├── repo.mjs               # marketplace/GitHub helpers shared by configure and upgrade
│       │       ├── semver.mjs
│       │       └── changelog.mjs          # parses section 4.6 format
│       ├── CHANGELOG.md                   # PT-BR, inside the plugin so every copy has it
│       └── README.md                      # PT-BR, short
├── scripts/ci/                            # CI-only, not shipped: check-*.mjs (VAL-04, 07, 11, 12, 13), release-gates.mjs, release-notes.mjs, run-all.mjs
├── test/                                  # node:test suites + fake claude/gh/git (stubs/), harness
├── package.json                           # private; scripts only (npm test, npm run check); NO dependencies
├── specs/                                 # SDD source of truth (English)
├── docs/
│   ├── INSTALL.pt-BR.md   INSTALL.md      # R1 first, then R2, R3, R4
│   ├── TROUBLESHOOTING.pt-BR.md   TROUBLESHOOTING.md
│   ├── RELEASING.md                       # English: PR rule, release steps, announcement, manual fallback, quarterly log, minutes estimate
│   ├── cloud-setup.sh                     # R4 setup script (only if A12 holds)
│   └── dev/cli-samples/                   # outputs captured in T0
├── install.ps1   install.sh               # optional R2 bootstrap (REQ-INS-06)
├── .github/
│   ├── workflows/validate.yml             # PR checks (Linux) + pr-must-target-main
│   ├── workflows/release.yml              # workflow_dispatch, no inputs
│   └── CODEOWNERS                         # documentation only on Free
├── .gitattributes                         # * text=auto eol=lf
├── .gitignore
└── README.md                              # English, for maintainers
```

- No top-level `bin/`, no `hooks/`, no `agents/`, no `.mcp.json`, no `.lsp.json` inside the plugin (REQ-SRF-03).
- No Git LFS anywhere. No `CLAUDE.md` inside the plugin folder.
- `workflow_dispatch` workflows appear in the Actions UI only when the file exists on the **default branch** (`stable`). So a change to `release.yml` becomes usable only after it is released once. The very first `stable` is created by hand from the first green `main` commit, by an org owner, as the single documented exception (P-37).
- Quality-process skills from SPEC-002+ go under `plugins/isg-model-alignment/skills/` and follow REQ-SRF-02 and REQ-LNG.

### 4.2 `marketplace.json`

```json
{
  "name": "isg-plugins",
  "description": "Plugins do Instituto Sonho Grande",
  "owner": { "name": "Instituto Sonho Grande" },
  "plugins": [
    {
      "name": "isg-model-alignment",
      "source": "./plugins/isg-model-alignment",
      "description": "Apoio ao processo de qualidade do Instituto Sonho Grande"
    }
  ]
}
```

No `version` in the entry (REQ-REL-01). The relative-path source must be confirmed as accepted by R3 org sync (part of A10 test for R3).

### 4.3 `plugin.json`

```json
{
  "name": "isg-model-alignment",
  "displayName": "ISG Model Alignment",
  "version": "0.1.0",
  "description": "Apoio ao processo de qualidade do Instituto Sonho Grande",
  "author": { "name": "Instituto Sonho Grande" },
  "repository": "https://github.com/<org>/isg-plugins",
  "userConfig": {
    "user_name": {
      "type": "string",
      "title": "Seu nome",
      "description": "Nome usado nos documentos de qualidade gerados pelo plugin (opcional)"
    }
  }
}
```

`user_name` is **optional** (REQ-SRF-05).

### 4.4 User journeys

```text
R1 — claude.ai account (primary)
  once per GitHub org : org owner installs the Claude GitHub App on <org>, access: isg-plugins only
  once per user       : be invited as collaborator (Read) and accept the invitation on github.com
  install             : claude.ai or Desktop → Customize > Plugins > Add > Add marketplace
                        → <org>/isg-plugins → connect GitHub if asked
                        → add "ISG Model Alignment" → turn on "Sync automatically"
  use                 : chat (web/desktop), Cowork, and Claude Code after restart (signed in with the same account)
  check               : /isg-model-alignment:configure
  updates             : automatic sync, or Customize > Plugins > Check for updates; in Claude Code, restart or /reload-plugins

R2 — Claude Code CLI
  once      : install Claude Code, git, gh, Node.js LTS
              gh auth login (GitHub.com, HTTPS) → gh auth setup-git → set CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1
  install   : claude plugin marketplace add <org>/isg-plugins#stable
              claude plugin install isg-model-alignment@isg-plugins
  setup     : /isg-model-alignment:configure   (checks + offers auto-update)
  updates   : auto-update (if on) or /isg-model-alignment:upgrade
```

### 4.5 Branch and release model

```text
feature PR ──review──► main ─────────────────────────────────►
release PR (version + CHANGELOG) ──review──► main (commit X)
                                              │
               maintainer runs Release workflow on main
                                              │ checks (a)–(g) pass
                                              ▼
                            tag isg-model-alignment--vX.Y.Z on X
                            GitHub Release (PT-BR notes)
                            stable (default branch) ──fast-forward──► X
                                              │
   R1 claude.ai sync / R2 marketplace update / R3 org sync / R4 setup script
                                              │
                         maintainer announces the release (REQ-REL-10)
```

- Users only ever see commits that are on `stable`.
- `main` can be ahead of `stable` at any time. That is normal.
- If the workflow fails halfway (for example after tagging but before moving `stable`), **do not delete the tag**. Fix the cause and re-run; the workflow skips steps already done for that exact version and continues. *This is the only exception to "version must be greater than the latest tag": a re-run for a tag that points to the same commit.*

### 4.6 CHANGELOG format (PT-BR)

Based on Keep a Changelog. The parser in `scripts/lib/changelog.mjs` and the no-script path of `upgrade` both depend on this exact format.

```markdown
# Changelog

Todas as mudanças relevantes deste plugin são registradas aqui.

## [0.2.0] - 2026-12-01

### Quebra de compatibilidade
- ...

### Adicionado
- ...

### Alterado
- ...

### Corrigido
- ...

### Removido
- ...
```

- Version headings: `## [X.Y.Z] - AAAA-MM-DD`, newest first. No `[Unreleased]` section at release time.
- Allowed subsection headings, exactly: `Quebra de compatibilidade`, `Adicionado`, `Alterado`, `Corrigido`, `Removido`, `Segurança`. Omit empty ones.

### 4.7 `configure` checks

Each check has an ID, a result (`ok`, `fail`, `warn`, `skip`), a PT-BR message and, on failure, a PT-BR fix hint. Git commands run with `GIT_TERMINAL_PROMPT=0` and `GCM_INTERACTIVE=never`. The column "Applies" says on which surface/route the check runs (others report `skip` with the reason).

| ID | Check | Applies | Pass when | Fix hint (summary) |
|---|---|---|---|---|
| C-01 | Surface and route detected | S1–S3 | always (informational) | — |
| C-02 | Node.js | S1–S3 | `node --version` ≥ 20 | install Node.js LTS |
| C-03 | Claude Code | S1–S3 | the CLI is found (4.8, `CLAUDE_CODE_EXECPATH` first) and `--version` ≥ `MIN_CLAUDE_VERSION` (`2.1.317`, tested in T0) | update Claude Code |
| C-04 | GitHub CLI login | R2 | `gh auth status` ok for github.com | `gh auth login`, `gh auth setup-git` |
| C-05 | Git credential helper | R2 | a helper is configured for https://github.com | `gh auth setup-git` |
| C-06 | Repo access | R2, R4 | `git ls-remote https://github.com/<org>/isg-plugins.git stable` succeeds without a prompt | ask an org owner for access |
| C-07 | Marketplace registered on `stable` | R2, R4 | `isg-plugins` exists with ref `stable` | re-add with `#stable` |
| C-08 | Plugin installed and enabled | S1–S3 | enabled as `@isg-plugins` (R2/R4) or `@synced` (R1/R3) | install via the guide |
| C-09 | Optional `user_name` | S1–S3 | set → `ok`; empty → `warn` | `/plugin` > ISG Model Alignment > Configure options |
| C-10 | HTTPS preference | R2 | `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` | offer change (b) of REQ-CMD-05 |
| C-11 | Auto-update | R2 | on for `isg-plugins` (`warn` if off) | offer change (a) of REQ-CMD-05 |
| C-12 | One route only | S1, S2 | not both `@synced` and `@isg-plugins` enabled | disable one (P-33) |
| C-14 | Python for PDF processing (SPEC-003 REQ-CDP-02) | S1–S3 | `python3`, `python` or `py -3` reports ≥ 3.11 **and** the vendored pypdf imports. Missing or old Python → **warn** (only `cfp` needs it); pypdf not loading → **fail** | install Python 3.11+ (python.org); reinstall/upgrade the plugin |
| C-13 | Notion connection (SPEC-002 REQ-MCP-03) | S1–S3 | reported by the skill (not the script): Claude checks whether Notion tools are available and the "ISG — Agente" teamspace is reachable | `/mcp` → notion → Authenticate; choose the Instituto workspace |

Exit code of `configure --check`: `0` if no `fail`, `1` if at least one `fail`.

### 4.8 Script contract

Applies to `configure.mjs`, `upgrade.mjs` and every future script.

- **Invocation** (written in the skill text so the path is substituted):
  `node "${CLAUDE_PLUGIN_ROOT}/scripts/upgrade.mjs" --check --json`
  Always double-quote the path (user folders can contain spaces).
- **Modes:** `--check` (read-only, default), `--apply` (only after the user confirmed in the conversation), `--json` (one JSON object on stdout; human text otherwise).
- **No stdin, no prompts, no TTY assumptions.** Child processes get `stdio: ['ignore', 'pipe', 'pipe']`, a timeout (default 60 s) and the git no-prompt variables.
- **JSON output shape:**
  ```json
  { "ok": true, "command": "upgrade", "mode": "check",
    "surface": "S1", "route": "R2",
    "code": "UPDATE_AVAILABLE",
    "message": "Há uma nova versão disponível: 0.2.0 (você tem 0.1.0).",
    "data": { "installed": "0.1.0", "latest": "0.2.0", "breaking": false, "changelog": "..." },
    "checks": [] }
  ```
  `code` is an English identifier (REQ-LNG-02); `message` is PT-BR.
- **Exit codes:** `0` success or nothing to do; `1` expected failure; `2` wrong usage; `3` unexpected error. Never exit `0` after a failure.
- **Finding the Claude CLI (T0, F1):** never assume `claude` is on `PATH`. In a Desktop-app session it is not. `lib/run.mjs` resolves it once: (1) `process.env.CLAUDE_CODE_EXECPATH` if set and the file exists; (2) else `claude` from `PATH`; (3) else fail with code `CLAUDE_CLI_NOT_FOUND` and a PT-BR message. All scripts call it through `run.mjs`. The same applies to `gh` and `git` (resolve from `PATH`; if missing, report with a PT-BR fix hint, do not crash).
- **Quoting (T0, A9):** the skill text always runs a script **file** with simple flags. Never inline code (`node -e "…"`): PowerShell 5.1 strips quotes in arguments.
- **Never print** tokens, credential helper output, `gh auth token`, or sensitive values.
- **Never write** under `${CLAUDE_PLUGIN_ROOT}` or under the plugins root. Reading is allowed. Own persistent state goes in the plugin's application-data folder `<appdata>` (SPEC-003 REQ-COU-01), which survives updates and uninstall.
- **Only Node built-ins.** No npm dependencies. **Amended v0.9 (SPEC-003):** scripts may also be written in **Python ≥ 3.11 using only the standard library plus libraries vendored inside the plugin** (today: pypdf, unmodified, with its license and a SHA-256 manifest checked by VAL-C09). No `pip install` at runtime, no network. Python scripts follow the same contract (non-interactive, `--json`, exit codes, PT-BR messages) and never write inside the plugin folder (VAL-C10).
- **Test-only hooks** (documented so nobody mistakes them for features): `ISG_TEST_CLAUDE_STUB`, `ISG_TEST_GH_STUB`, `ISG_TEST_GIT_STUB` (a `.mjs` file run with Node instead of the real tool) and `ISG_TEST_TIMEOUT_MS` (caps every timeout). They exist only so `test/` and VAL-12 can run without the real tools. Users never set them.
- **Secrets in output:** every text taken from another program's stderr/stdout passes through `redact()` before it is shown.

### 4.9 Skill text rules

- Frontmatter: `name`, a short **PT-BR** `description`, and `disable-model-invocation: true` for `configure` and `upgrade`.
- First line of the body, exactly: **`Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.`** (VAL-11 looks for it.)
- `configure` and `upgrade` bodies have three labeled parts, in this order: **(1) Descobrir o ambiente** — how Claude decides the surface (4.11); **(2) Com terminal** — run the script with `--check --json`, show `message` and the checklist, ask "Deseja aplicar? (sim/não)", only on "sim" run `--apply --json`; **(3) Sem terminal** — the manual PT-BR steps of 4.11 for S4–S6, and the rule "não diga que executou ou verificou algo".
- Skills of SPEC-002+ follow REQ-SRF-02: the main path is instructions only.

### 4.10 `upgrade` algorithm (R2 and R4, with a shell)

1. Read the installed version and id: `claude plugin list --json` (A2). If the id ends in `@synced`, go to 4.11 (R1).
2. Refresh the catalog: `claude plugin marketplace update isg-plugins`. On failure, run `git ls-remote` (as in C-06) to tell **no access** from **offline**. Report and stop.
3. Read the latest version from the marketplace checkout: `installLocation` of `isg-plugins` in `<plugins root>/known_marketplaces.json` (read-only), then `plugins/isg-model-alignment/.claude-plugin/plugin.json` and `CHANGELOG.md` there.
4. Compare. Equal → `UP_TO_DATE`, exit 0. Latest lower than installed → `NEWER_THAN_STABLE` (maintainer on `#main`), report, change nothing.
5. Extract CHANGELOG sections with installed < version ≤ latest. Flag `breaking` if any has `### Quebra de compatibilidade`.
6. Return `UPDATE_AVAILABLE` (end of `--check`). Claude shows it and asks.
7. With `--apply`: `claude plugin update isg-model-alignment@isg-plugins --scope <installed scope>`; re-read `claude plugin list --json`; version now `latest` → `UPDATED`, else `UPDATE_FAILED`.
8. Claude tells the user (PT-BR) to run `/reload-plugins` or restart.

The running script lives in the **old** version folder; updating is safe because the old folder stays 14 days.

### 4.11 Surface and route behavior of `configure` and `upgrade`

**How the surface is decided**
1. If Claude has **no tool to run shell commands** → S4/S5 (chat) or S6 (Cowork). Claude follows the "Sem terminal" part. (A16 may move Cowork to a partial terminal case; the rule stays: if `claude` CLI is not available, use "Sem terminal".)
2. If it can run shell commands, the script `surface.mjs` decides: cloud session (A13) → **S3**; else **S1/S2** (the Desktop Code tab and the terminal behave the same).
3. Route: from `claude plugin list --json` (A2): `@synced` → **R1/R3**; `@isg-plugins` → **R2** (or **R4** on S3).

**Behavior table**

| | S1/S2 + R2 | S1/S2 + R1/R3 (synced) | S3 cloud | S4/S5 chat, S6 Cowork |
|---|---|---|---|---|
| `configure` | All checks C-01..C-12 | C-01..03, C-08, C-09, C-12; reminds to keep "Sync automatically" on in claude.ai | C-01..03, C-08, C-09 (+ C-06, C-07 on R4) | Manual checklist: GitHub connected on claude.ai; plugin present and enabled in Customize > Plugins; "Sync automatically" on; how to ask for access |
| `upgrade` | 4.10 | Shows installed version; reads latest from `stable` with `gh api repos/<org>/isg-plugins/contents/plugins/isg-model-alignment/.claude-plugin/plugin.json?ref=stable` **only if `gh` is logged in**; explains: Customize > Plugins > Check for updates, then restart Claude Code or `/reload-plugins`. Never runs `claude plugin update`. | R1: like synced, and "start a new session"; R4: 4.10 inside the session, and note the environment cache keeps the old version until the setup script runs again | Explains: updates come from the claude.ai account; Customize > Plugins > Check for updates; where to see the version (plugin page); never claims a version it cannot see |

### 4.12 Account-route (R1) operations for org owners

- Install the **Claude GitHub App** on `<org>` with access to **only** `isg-plugins` (REQ-ACC-08). Approve it once; review it quarterly.
- If a Team/Enterprise Claude organization blocks members from adding their own marketplaces, its Claude org Owner chooses: allow this one source, or use R3 (Q10).
- Offboarding on R1: remove the GitHub collaborator **and** ask the person to remove the plugin from their claude.ai account (it keeps working at the last synced version otherwise; accepted residual risk P-06).

---

## 5. Pitfalls and mitigations

| ID | Pitfall | Impact | Mitigation | Verified by |
|---|---|---|---|---|
| P-01 | **Version pinned but not bumped.** | "Released but nobody got it" | Release PR bumps `version`; workflow check (d). | AC-REL-3, 4 |
| P-02 | **`version` in both `plugin.json` and marketplace entry.** | Confusion | Only in `plugin.json`; VAL-04. | VAL-04 |
| P-03 | **Auto-update off by default** (R2). | Users stay old | C-11 offers it; `upgrade`; R1 "Sync automatically". | AC-CMD-4 |
| P-04 | **Private-repo auto-update needs a stored credential** (R2); `GITHUB_TOKEN` alone does not work. | Silent staleness | `gh auth login` + `gh auth setup-git`; C-04..C-06. | AC-CMD-2 |
| P-05 | **No SSH key** (R2): in-session installs/updates do not fall back to HTTPS. | Works in shell, fails in session | `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`; C-10. | AC-INS-2 |
| P-06 | **Offboarding gap:** installed copies and claude.ai account copies keep working. | Residual access | Accepted; no secrets in the plugin; ask removal (4.12). | AC-ACC-2, 3 |
| P-07 | **Windows vs Unix** paths and shells. Team works on Windows. | One OS only | Forward slashes; Node only; quoted paths; Windows smoke test per release; manual macOS check before `0.1.0`. | VAL-05, UAT-01/02 |
| P-08 | **State under `${CLAUDE_PLUGIN_ROOT}`** lost on update. | Lost data | `<appdata>` (SPEC-003 REQ-COU-01); VAL-07. | VAL-07 |
| P-09 | **Reserved or duplicate names.** | Install fails | `isg-` prefix; unique marketplace name; `validate`. | VAL-01, 02 |
| P-10 | **Entry name ≠ manifest name.** | "Not found" | REQ-REP-02; VAL-04. | VAL-04 |
| P-11 | **Renaming breaks installs.** | Broken installs | `displayName` only; else `renames`. | Review |
| P-12 | **Wrong relative path** passes `validate` but fails install. | Late failure | VAL-05. | VAL-05 |
| P-13 | **Git LFS** files arrive as pointers. | Broken files | No LFS. | Review |
| P-14 | **Update needs reload** (Claude Code). | "Nothing changed" | `upgrade` step 8; synced: restart. | AC-CMD-4 |
| P-15 | **Context cost** of skill descriptions. | Wasted tokens | Short descriptions; `disable-model-invocation`. | Review per release |
| P-16 | **Unsafe side effects** of `configure`/`upgrade`. | Loss of trust | Check-then-apply; only REQ-CMD-05 changes; backups; official CLI only. | AC-CMD-3, 5 |
| P-17 | **Docs/CLI/UI drift.** | Steps break | `MIN_CLAUDE_VERSION`; T0 samples; A17 labels; quarterly re-read of section 10. | VAL-08 |
| P-18 | **Malicious or careless change** (plugins run as the user). | Harm | PR + approval; workflow gates; quarterly review. | AC-REL-5 |
| P-19 | **No enforced protection on Free.** | Bad change reaches users | `stable` delivery branch; workflow gates; few writers; review tag/`stable` authors. | AC-REL-6, VAL-10 |
| P-20 | **Actions minutes quota.** | CI stops | Linux PR checks; Windows only on release; `concurrency`; path filters; manual fallback. | AC-CST-1 |
| P-21 | **Paid secret scanning.** | Hidden cost | gitleaks **binary**, pinned + checksum. | VAL-03 |
| P-22 | **Repo in a personal account.** | Depends on one person | Free organization, two owners. | Q2 |
| P-23 | **Free-plan terms change.** | Surprise cost | Quarterly check. | VAL-10 |
| P-24 | **Claude answers in the wrong language.** | Mixed output | Fixed PT-BR instruction; PT-BR script messages; VAL-11. | AC-LNG-1 |
| P-25 | **Manual tag or `stable` push** bypasses checks. | Unvalidated release | Only the workflow publishes; investigate anything not by `github-actions[bot]`. | VAL-10 |
| P-26 | **Repo checkout inside OneDrive** corrupts `.git`. | Broken repo | Clone outside OneDrive (for example `C:\dev\isg-plugins`). | Note 8.2 |
| P-27 | **Encoding and line endings.** | Garbled text, broken scripts | `.gitattributes` LF; UTF-8 no BOM; A9. | REQ-REP-06 |
| P-28 | **Claude's Bash tool cannot answer prompts.** | Hanging commands | Non-interactive contract; AC-CMD-6. | VAL-12 |
| P-29 | **Node.js missing** on S1/S2. | Scripts cannot run | Listed prerequisite; C-02; skill explains in PT-BR. | C-02 |
| P-30 | **Workflow token cannot read billing.** | No automatic cost check | VAL-10 manual. | VAL-10 |
| P-31 | **Half-finished release.** | Inconsistent state | Idempotent re-run; never delete tags. | VAL-09 |
| P-32 | **Cloud sessions ignore local and repo-declared plugins.** Installing on the laptop or adding `enabledPlugins` to a repo does nothing in Claude Code on the web. | "Plugin missing in the cloud" | R1 (A11) or R4 (A12); guide explains per surface. | AC-SRF-3 |
| P-33 | **Two routes on one machine** (R1 synced + R2 installed): the R2 copy wins silently, versions differ, hooks of one copy are skipped. | Confusing versions | One route per machine; C-12 detects it; guide says so. | UAT-17 |
| P-34 | **Features silently missing on chat/Cowork** (agents, hooks, local MCP, `userConfig` ignored). | Skills "half work" | Portable core (REQ-SRF-02); v1 has none of these (REQ-SRF-03); VAL-13. | AC-SRF-4 |
| P-35 | **Claude GitHub App not approved** on the GitHub org, or given access to all repos. | R1 fails, or over-broad access | Org owner installs it once with access to this repo only (REQ-ACC-08); quarterly review. | UAT-19 |
| P-36 | **Team/Enterprise owner blocks personal marketplaces.** | R1 impossible for that org's members | Owner allows the source or uses R3 (Q10); R2 for Claude Code. | UAT-20 |
| P-37 | **`stable` as default branch side effects:** PRs open against `stable` by default; `workflow_dispatch` only sees workflow files on the default branch. | PR merged into `stable`; release workflow change not visible | Guide tells maintainers to pick `main` as base; `pr-must-target-main` check; release-workflow changes take effect after one release; first `stable` created by hand once. | REQ-REP-03 |
| P-38 | **claude.ai might read a different branch than expected** (A10). | Unreleased code reaches chat users | Verify in T0; D11 makes default branch = `stable`; AC-REL-6 tests R1. | AC-REL-6 |
| P-39 | **Claude in chat pretends it ran commands** (no terminal). | Wrong information | "Sem terminal" part with the explicit rule; AC-SRF-1. | AC-SRF-1 |
| P-40 | **Synced plugins need Claude Code signed in with the claude.ai account.** API-key sessions, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, bare/safe mode do not sync. | Plugin missing in Claude Code | Guide states it (REQ-SRF-07); C-08 hint. | UAT-17 |
| P-41 | **Cloud GitHub proxy is scoped to attached repos;** a setup script may not clone the private marketplace. | R4 fails | Verify A12; prefer R1 (A11). | AC-SRF-3 |
| P-42 | **`claude` is not on `PATH`** in Desktop-app sessions (found in T0). A script calling `claude …` by name fails. | `configure`/`upgrade` "command not found" | Resolve the CLI with `CLAUDE_CODE_EXECPATH` first (4.8); `CLAUDE_CLI_NOT_FOUND` message in PT-BR; VAL-12 stubs both cases. | VAL-12, UAT-17 |
| P-43 | **PowerShell 5.1 strips quotes** from native-command arguments, so `node -e "…"` and arguments with quotes break (found in T0). | Garbled commands on Windows | Skills run script **files** with simple flags only (4.8); paths always double-quoted. | VAL-12, UAT-01 |
| P-44 | **Repository transfer** from the interim host (`Lecabe-Tech-Company`) to the Instituto's account changes the URL. GitHub redirects the old URL, but the redirect **breaks** if a new repo with the old name is ever created there; installed marketplaces, the Claude GitHub App grant and the claude.ai marketplace entry all point to the old URL; Actions minutes and settings (default branch) belong to whoever hosts the repo. | Users silently lose updates | **Do not onboard users (R1, R2) before the transfer.** Until then, only maintainers test. Run the transfer checklist in `docs/RELEASING.md` ("Transfer to the Instituto's account"). Never create a new `isg-plugins` repo under `Lecabe-Tech-Company` after the transfer. | Transfer checklist |

---

## 6. Validation

### 6.1 Automated checks

| ID | Check | Method | Where / when | Covers |
|---|---|---|---|---|
| VAL-01 | Marketplace valid | `claude plugin validate . --strict` | Linux, every PR; release (f) | REQ-REP-03, REQ-REL-04 |
| VAL-02 | Plugin valid | `claude plugin validate ./plugins/isg-model-alignment --strict` | Linux, every PR; release (f) | REQ-REP-03, REQ-REL-04 |
| VAL-03 | Secret scan | gitleaks **binary** v8.30.1 pinned by SHA-256, `gitleaks git --redact --no-banner --exit-code 1 .` over full history. Verified in v0.6: clean repo exits 0; a repo with a realistic random `ghp_…` token exits 1 (note: gitleaks is entropy-based, an obviously sequential fake token is NOT flagged) | Linux, every PR | AC-ACC-3 |
| VAL-04 | Names and version | `scripts/ci/check-consistency.mjs`: entry name = manifest name = constant; no `version` in entry; SemVer; CHANGELOG headings follow 4.6 | Linux, every PR; release (f) | REQ-REL-01, 05, REQ-REP-02, 07 |
| VAL-05 | Install smoke test | Empty `CLAUDE_CODE_PLUGIN_CACHE_DIR`: `marketplace add <checkout>`, `install`, `list --json` shows enabled | Linux every PR (if A1); **Windows** in release (g) | REQ-REP-04, P-07, P-12 |
| VAL-06 | *(withdrawn in v0.3 — OS coverage is part of VAL-05)* | | | |
| VAL-07 | State location | `scripts/ci/check-no-root-writes.mjs` | Linux, every PR | P-08 |
| VAL-08 | Minimum Claude Code | VAL-01, 02, 05 with `MIN_CLAUDE_VERSION` | Release (g) | P-17 |
| VAL-09 | Release gates | Run the workflow in a free private **test fork** for each failure case of AC-REL-2, 3, 5 and the re-run case | Once in T4, then after any `release.yml` change | AC-REL-1..5, P-31 |
| VAL-10 | Quarterly review (manual) | Org owner: billing = 0 and Free plan, minutes, collaborators, Claude GitHub App scope, authors of tags and `stable` moves; logged in `docs/RELEASING.md` | Every quarter and after offboarding | AC-CST-1, REQ-ACC-06, P-19, 23, 25, 30, 35 |
| VAL-11 | Language | `scripts/ci/check-language.mjs`: 4.9 first line in every `SKILL.md`; PT-BR `description`, `userConfig` texts, `plugin.json` `description` | Linux, every PR | REQ-LNG-01, P-24 |
| VAL-12 | Non-interactive | `scripts/ci/check-non-interactive.mjs`: each script mode with stdin closed and 60 s timeout, `claude` and `gh` stubbed | Linux, every PR | AC-CMD-6, P-28 |
| VAL-13 | Portable core | `scripts/ci/check-portable.mjs`: no `bin/`, `hooks/`, `agents/`, `.lsp.json`, `output-styles/` in the plugin and no such keys in `plugin.json`; `.mcp.json` only with remote `type: http` servers on a fixed `https://` URL, no headers/env/command/`${…}` (amended v0.7); no `required: true` in `userConfig`; `${CLAUDE_PLUGIN_ROOT}` only in `configure`/`upgrade`; both have "Sem terminal" and "Com terminal" parts; size < 200 MB and < 5,000 files | Linux, every PR; release (f) | REQ-SRF-02, 03, 05, 06, AC-SRF-4 |

### 6.2 Manual tests (UAT) — before `0.1.0`, and again for every MAJOR

| ID | Scenario | Pass when |
|---|---|---|
| UAT-01 | Fresh Windows 11, R2, only reads `INSTALL.pt-BR.md` | AC-INS-1 in ≤ 15 min without help |
| UAT-02 | Same on macOS | AC-INS-1 |
| UAT-03 | No SSH key, R2 from shell and from `/plugin` | AC-INS-2 |
| UAT-04 | Non-collaborator tries R2 and R1 | AC-ACC-1 |
| UAT-05 | Remove a collaborator, release a new version (R1 and R2 users) | AC-ACC-2 |
| UAT-06 | Release `0.1.1`; R2 user uses `upgrade`, another R2 relies on auto-update, an R1 user uses "Check for updates" | AC-REL-4, AC-CMD-4 |
| UAT-07 | `configure` on healthy and broken R2 machines | AC-CMD-1, 2, 3 |
| UAT-08 | `upgrade` up to date, no access, offline (R2) | AC-CMD-5 |
| UAT-09 | Rollback drill: bad PATCH, then fixing PATCH | Users end on the fix without touching caches |
| UAT-10 | Release workflow by Read-only user, and on a PR without approval | AC-REL-5 |
| UAT-11 | Merge to `main` without releasing; R1 and R2 users check | AC-REL-6 |
| UAT-12 | Write in English, run `configure`/`upgrade` on S1, S4, S6 | AC-LNG-1 |
| UAT-13 | First quarterly review after the first month | AC-CST-1 |
| UAT-14 | R1 install, then `configure` and `upgrade` in **claude.ai web chat** (S4) | AC-INS-3, AC-SRF-1 |
| UAT-15 | Same in **Desktop chat** (S5) | AC-INS-3, AC-SRF-1 |
| UAT-16 | Same in **Cowork** (S6) | AC-INS-3, AC-SRF-1 |
| UAT-17 | R1 user opens the **Desktop Code tab** and the terminal (S2, S1): synced copy present; `upgrade` behaves as synced; then also install via R2 and confirm C-12 warns | AC-INS-3, AC-SRF-2, P-33 |
| UAT-18 | **Claude Code on the web** started from claude.ai/code and from Desktop (S3) | AC-SRF-3 |
| UAT-19 | Claude GitHub App scope: only `isg-plugins` listed | REQ-ACC-08 |
| UAT-20 | *(only if a Team/Enterprise org exists)* R3 org sync, or a blocked-sources org following 4.12 | REQ-INS-11, P-36 |

### 6.3 Definition of done for SPEC-001

- Assumptions A1–A17 confirmed (or the spec updated), with **A15 confirmed** before R1 is offered to anyone.
- Every **M** requirement implemented and traced in 6.4.
- VAL-01..05, 07, 11, 12, 13 green on Linux; VAL-05 and VAL-08 green on Windows in the release workflow; VAL-09 done.
- UAT-01..19 passed (UAT-20 when applicable), UAT-13 scheduled.
- `docs/INSTALL*`, `docs/TROUBLESHOOTING*`, `docs/RELEASING.md` reviewed by someone who did not write them.
- Release `isg-model-alignment--v0.1.0` published by the workflow, installed through R1 by two people other than its author, and through R2 by one.

### 6.4 Traceability

| Requirement | Acceptance | Validation |
|---|---|---|
| REQ-INS-01, 02, 08, 09 | AC-INS-1 | VAL-05, UAT-01, 02 |
| REQ-INS-03 | AC-ACC-1 | UAT-04 |
| REQ-INS-04 | AC-INS-2 | UAT-03 |
| REQ-INS-10 | AC-INS-3 | UAT-14..17 |
| REQ-INS-05, 06, 07, 11, 12 | — (docs / optional) | Doc review, UAT-18, 20 |
| REQ-ACC-01, 05 | AC-ACC-1, 3 | VAL-03, UAT-04 |
| REQ-ACC-02 | AC-ACC-2 | UAT-05 |
| REQ-ACC-03, 07 | AC-REL-5 | VAL-09, UAT-10 |
| REQ-ACC-04, 06 | — (process) | VAL-10 |
| REQ-ACC-08 | — | UAT-19, VAL-10 |
| REQ-REL-01..05 | AC-REL-1, 2, 3, 4 | VAL-01, 02, 04, 09, UAT-06 |
| REQ-REL-06 | — | UAT-09 |
| REQ-REL-07, 08 | — (optional) | Doc review |
| REQ-REL-09 | AC-REL-1, 4, 6 | VAL-09, UAT-11 |
| REQ-REL-10 | — (process) | Release checklist |
| REQ-CMD-01, 02 | AC-CMD-1, 2 | UAT-07 |
| REQ-CMD-03..06 | AC-CMD-3 | UAT-07 |
| REQ-CMD-07, 08, 10, 11 | AC-CMD-4, AC-SRF-2 | UAT-06, 08, 17 |
| REQ-CMD-09 | AC-CMD-5 | UAT-08 |
| REQ-CMD-12, 13, 14 | AC-CMD-6, AC-SRF-1 | VAL-12, UAT-14..16 |
| REQ-REP-01, 02, 04, 05 | AC-INS-1 | VAL-01, 02, 04, 05 |
| REQ-REP-03, 06, 07 | AC-REP-1 | VAL-04, CI run |
| REQ-CST-01..04 | AC-CST-1 | VAL-10, UAT-13 |
| REQ-LNG-01..04 | AC-LNG-1 | VAL-11, UAT-12 |
| REQ-SRF-01 | AC-INS-3, AC-SRF-3 | UAT-14..18 |
| REQ-SRF-02, 03, 05, 06 | AC-SRF-4 | VAL-13 |
| REQ-SRF-04 | AC-SRF-1, 2 | UAT-14..17 |
| REQ-SRF-07, 08 | — (docs) | Doc review |

---

## 7. Implementation plan

Do the tasks **in order**. Each task ends with a PR that names the requirement IDs it closes. A task is finished only when its gate passes.

| Task | What | Closes | Gate |
|---|---|---|---|
| **T0** | **Spike:** confirm A1–A17 by hand (Claude Code locally, claude.ai, Desktop chat, Cowork, Claude Code on the web) using a throwaway private repo and a minimal test plugin; record outputs and screenshots in `docs/dev/`; set `MIN_CLAUDE_VERSION` (Q7); update the spec where anything differs. **No production code.** **A15 is blocking for R1.** | 1.5 | Spec PR merged with results |
| **T1** | Repo scaffold (4.1), `.gitattributes`, `marketplace.json`, `plugin.json` `0.1.0`, `constants.mjs`, PT-BR skills with the three-part structure (4.9) and the "Sem terminal" text, CHANGELOG with `## [0.1.0]`. | REQ-REP-01, 02, 06, 07, REQ-SRF-03, 05 | VAL-01, 02, 04, 13 pass **locally** |
| **T2** | Free GitHub org (2 owners), private repo, collaborators (Read users, ≥ 2 Write maintainers), Claude GitHub App on this repo only, CODEOWNERS, `docs/RELEASING.md` (PR rule, announcement, quarterly review template). | REQ-ACC-01..04, 06..08, REQ-INS-03, REQ-CST-01 | UAT-04 (R2 part), UAT-19 |
| **T3** | `validate.yml` (Linux): VAL-01..05, 07, 11, 12, 13, `pr-must-target-main`, `concurrency`, path filters, actions pinned by SHA. | REQ-REP-03, 04, REQ-CST-02, 04 | AC-REP-1 |
| **T4** | `release.yml`: steps (a)–(j), idempotent re-run, Windows smoke test, VAL-08. Create `stable` (first time by hand, 4.1) and set it as default branch. Manual fallback in `docs/RELEASING.md`. | REQ-REL-01..06, 09, 10 | VAL-09 |
| **T5** | `configure` skill + `configure.mjs` + `surface.mjs` + libs (4.7, 4.8, 4.9, 4.11). | REQ-CMD-01..06, 12..14, REQ-SRF-04, REQ-LNG-01, 02 | AC-CMD-1..3, 6, AC-SRF-1 (configure) |
| **T6** | `upgrade` skill + `upgrade.mjs` (4.10, 4.11). | REQ-CMD-07..14, REQ-SRF-04, REQ-LNG-01, 04 | AC-CMD-4..6, AC-SRF-1, 2 |
| **T7** | Docs: INSTALL (R1 first; R2; R3; R4 if A12) and TROUBLESHOOTING, PT-BR + EN; per-surface table; README files; `docs/cloud-setup.sh` if A12. | REQ-INS-02, 04, 05, 08, 10..12, REQ-SRF-07, 08, REQ-LNG-03 | Doc review |
| **T8** | First release `0.1.0` through the workflow, announcement, then UAT-01..19 (+20 if applicable). | 6.3 | Definition of done |
| **T9** | Optional: bootstrap scripts (REQ-INS-06), IT managed-settings guide (REQ-INS-07), early-access notes (REQ-REL-07). | — | Doc review |

After T8, start **SPEC-002**: documentation and skills for the quality process itself, under the portable-core rule.

### 7.1 Implementation status (v0.6, 2026-11-04)

Code is in `C:\dev\isg-plugins` (a local git repository, **nothing committed, nothing pushed**). "Verified" means run locally on Windows with Claude Code 2.1.317; "needs GitHub" means it can only be proven after the repository exists on GitHub.

| Task | Status | What is proven | What is still open |
|---|---|---|---|
| T0 | Part 1 done | A1 (local), A2, A4 (storage), A9, A6 (dry-run) | Part 2 (G1–G11): A3, A5 in session, A7, A8, A10–A17 |
| T1 | **Done** | `claude plugin validate . --strict` and for the plugin: passed; VAL-04, VAL-13 pass; LF/UTF-8 enforced | — |
| T2 | **Not started** (needs people) | — | Free organization, 2 owners, collaborators (Q2, Q3, Q9), Claude GitHub App (REQ-ACC-08), real `GITHUB_ORG` |
| T3 | **Written, not run on GitHub** | YAML parses; every step's command was run locally; gitleaks flags verified (clean exit 0, leak exit 1); actions pinned to verified commit SHAs; VAL-04 checks pins and the Claude version | First run on a real PR (needs GitHub); `claude` CLI installation from npm in Actions (A1) |
| T4 | **Written, not run on GitHub** | YAML parses; `release-notes.mjs` and `check-consistency --release` verified (the latter correctly refuses while `<org>` is a placeholder) | `release-gates.mjs` (needs the GitHub API), tag with `GITHUB_TOKEN` (A6), VAL-09 in a test fork |
| T5 | **Done** | 18 tests incl. AC-CMD-1, 2, 3, 6; real run against the real CLI: C-01..C-12 report correctly | In-session run of the skill text (G1); R4/cloud detection (A13) |
| T6 | **Done** | 13 tests incl. AC-CMD-4, 5, AC-SRF-2 (never updates a synced copy); real run: `UP_TO_DATE` | In-session run (G1); R1 latest-version lookup via `gh` and the JSON of a GitHub marketplace (A2, G3) |
| T7 | **Written** | INSTALL, TROUBLESHOOTING (PT-BR + EN), RELEASING, READMEs | UI labels (A17), owner names, reviewed by someone who did not write it |
| T8 | **Not started** | — | First release, announcement (Q11), UAT-01..20 |
| T9 | Not started | — | Bootstrap `install.ps1`/`install.sh` (REQ-INS-06, S), `docs/cloud-setup.sh` (only if A12), IT guide (REQ-INS-07, C) |

Automated results at v0.6: `npm run check` = VAL-04, 07, 11, 13, 31 tests, VAL-12 (30 script-mode runs including a "tools hang" scenario) — all green.

Known limitations to review (not hidden): `surface.mjs` reports a cloud session as S3 only if `CLAUDE_CODE_REMOTE` is set (A13 unconfirmed); `C-07` can only warn about the marketplace branch until the JSON of a GitHub-sourced marketplace is known; `$ARGUMENTS` and `${CLAUDE_PLUGIN_ROOT}` substitution inside the skill text has been designed from the docs but not yet observed in a live session (G1).

---

## 8. Implementer notes — saying the obvious

These are easy to forget. They are rules, not suggestions.

### 8.1 Working method
1. Read this whole spec before writing code. Read it again before each task.
2. No code without a requirement ID. If you need something the spec does not say, **stop and change the spec first** (PR to `specs/`), then code.
3. One task = one branch = one PR **to `main`**. The PR description lists the IDs it closes and how you tested them.
4. When you open a PR on GitHub, **change the base branch to `main`** — GitHub suggests `stable` because it is the default branch.
5. A PR is merged only with green CI and an approval from another maintainer. You never approve your own PR. You never merge a red PR "because it's only docs".
6. Never push directly to `main` or `stable`. Never force-push. Never delete or move a tag. Even though GitHub Free would let you.
7. The Release workflow is the only way to publish. If it is broken, fix it or use the manual fallback in `docs/RELEASING.md`. Do not "just tag it by hand".
8. Users get what is on `stable`, on **every** route. Merging to `main` ships nothing. Running the Release workflow does.
9. Bump `version` **and** write the CHANGELOG section in the **same** release PR.
10. After a release, announce it (REQ-REL-10). R1 users may not notice otherwise.

### 8.2 Your machine
11. Clone the code repository **outside OneDrive** (for example `C:\dev\isg-plugins`). OneDrive sync breaks `.git` folders.
12. Editor: **UTF-8 without BOM** and **LF**. `git config core.autocrlf` is `false` or `input`; `.gitattributes` is the rule.
13. Test on **Windows first** — it is what the team uses — then Linux CI. Before `0.1.0`, someone tests macOS once.
14. Paths with spaces exist (`OneDrive - NTT DATA EMEAL`, `Documentos`). Quote every path in every command and script.
15. To try the plugin locally without a release: `claude --plugin-dir ./plugins/isg-model-alignment`, and `/reload-plugins` after edits. Do not install your working copy through the real marketplace, and disable your own R1 synced copy while testing (or it will be confusing which copy runs).

### 8.3 Surfaces
16. **There is no terminal in claude.ai chat or Desktop chat.** Anything that needs a command must have a "Sem terminal" text. Test every skill there, not only in Claude Code.
17. **Claude Code on the web does not see what you installed on your laptop.** It is a fresh Linux VM.
18. The Desktop **Code tab is Claude Code**: same settings and plugins as the terminal. Desktop **chat** is not.
19. Chat and Cowork **ignore** `userConfig` prompts, chat ignores agents and hooks, and both **refuse** a plugin with a top-level `bin/`. Keep v1 free of them (REQ-SRF-03).
20. A skill's main value must work with instructions only (REQ-SRF-02). If you find yourself writing a script for a domain skill, stop and ask whether it is an optional extra.
21. Never write "click X" without saying on which surface X exists.
22. Use one route per machine yourself. If `claude plugin list` shows both `@synced` and `@isg-plugins`, you are testing the wrong copy.

### 8.4 Money
23. Zero cost means zero. Before adding any GitHub Action, service, library, app or tool, check it is free **for a private repo in an organization**. If in doubt, don't add it — ask.
24. Never add an Anthropic API key (or any paid key) to the repo, to Actions secrets, or to a script. CI does not call any model.
25. No matrix builds, no Windows/macOS jobs on every PR, no scheduled jobs without a reason.
26. Never tell a user to upgrade their Claude plan to use the plugin. If their plan lacks a surface, that surface is unsupported for them.

### 8.5 Secrets and safety
27. Never commit tokens, passwords, `.env` files, or URLs with credentials. Add `.env*` to `.gitignore`.
28. Scripts never print a token, never call `gh auth token`, never echo credential helper output.
29. Scripts never edit `~/.claude/plugins/**`. Use the `claude plugin` CLI. The only file `configure` may edit is `~/.claude/settings.json`, only the two keys of REQ-CMD-05, only on R2, only after "sim", only after a backup.
30. Never run a destructive command (`rm -rf`, uninstall, remove marketplace) from a script.
31. The Claude GitHub App gets access to **this repository only**. Never "All repositories".

### 8.6 Scripts and skills
32. Claude's Bash tool has **no keyboard**. A command that asks a question hangs or fails. Scripts never prompt; Claude asks the user.
33. `${CLAUDE_PLUGIN_ROOT}` works **inside `SKILL.md` text**, not as a shell variable. Write the full command in the skill.
34. The installed copy contains **only** `plugins/isg-model-alignment/`. Anything needed at runtime must be inside it.
35. Only Node built-in modules. No `npm install`.
36. Every user-facing string is PT-BR **with correct accents** (`não`, `versão`, `configuração`). Every identifier is English. Do not mix.
37. Error messages say what happened **and** what to do next, in PT-BR, in one or two sentences.
38. Exit codes matter. Never exit `0` after a failure.
39. Keep skill `description` lines short. They are loaded into every conversation on every surface.

### 8.7 Users and support
40. A user needs their **own** GitHub account invited as collaborator, and must **accept the invitation** on github.com before any route works. Shared accounts are not allowed.
41. When someone leaves, remove them from the collaborators the same day, ask them to remove the plugin from their claude.ai account, and record it in the quarterly log.
42. "It doesn't update" checklist: which route (R1 or R2)? Was the Release workflow actually run? R1: is "Sync automatically" on / did they "Check for updates" / did they restart Claude Code? R2: on `#stable`? does `gh auth status` work? auto-update on? `/reload-plugins`?
43. "It's missing in the cloud" checklist: plan includes Claude Code on the web? R1 synced (A11)? Otherwise R4 setup script present in that environment?

---

## 9. Open questions

| # | Question | Needed by |
|---|---|---|
| Q2 | **Interim decision (2026-11-04):** the repository lives temporarily at `Lecabe-Tech-Company/isg-plugins` (private). The Instituto will **transfer the ownership** to its own GitHub account later. Still open: the Instituto account's name and the transfer date. Until the transfer, follow P-44 (no user onboarding). | Before onboarding users |
| Q3 | Named list of **maintainers** (≥ 2, Write) and **org owners** (2) — **to be defined later by the Instituto**, before T2. | T2 |
| Q4 | Does Instituto IT use managed settings / MDM? Only for the optional T9 guide. | T9 |
| Q7 | `MIN_CLAUDE_VERSION` — **provisional `2.1.317`** (the only version tested in T0). Lower it only after testing an older version. | T1 |
| Q11 | Which channel is used for **release announcements** (REQ-REL-10)? *Not decided yet.* Until decided, the GitHub Release page is the announcement and maintainers also tell users directly. | T4 |
| ~~Q1~~ | Marketplace and repository name — **decided**: `isg-plugins`. Marketplace names are not global: the only checks are (a) the repository name is free inside our own new organization (it is, the org is new), and (b) it is not a reserved name (it is not). **Fallback** if (a) or (b) ever fails: `instituto-sonho-grande-plugins` — change it in `constants.mjs` and in this spec before T1, never after users have installed (P-11). | — |
| ~~Q9~~ | GitHub accounts — **decided (assumed)**: every user has or can create a **personal GitHub account**, invited as collaborator; no shared accounts. Recommendation for the email: the person's own account, with their **institutional email added and verified** in GitHub, so the Instituto can identify who each account is during the quarterly review and offboarding. | — |
| ~~Q10~~ | Team/Enterprise Claude organizations — **decided (recommended default)**: use **R1**, members add the marketplace themselves, because access then stays controlled by GitHub collaborators, the same rule as for Pro/Max users. Use **R3 (org sync) only as an exception**, when that Claude organization's Owner blocks members from adding marketplaces **and** every member of that Claude organization is allowed to have the plugin. The decision per organization is recorded in `docs/RELEASING.md`. | — |
| ~~Q5~~ | Claude plans — **decided**: Pro, Max, Ultra, Team, Enterprise; Free not supported (1.6). | — |
| ~~Q6~~ | Language — **decided** (REQ-LNG). | — |
| ~~Q8~~ | Early-access channel — **decided**: optional `#main` for maintainers on R2 only (REQ-REL-07). | — |

---

## 10. Sources (re-read every quarter, P-17)

- Plugins overview — https://code.claude.com/docs/en/plugins
- Install and manage plugins (terminal, Desktop, VS Code, cloud session tabs) — https://code.claude.com/docs/en/plugins/install.md
- Create a marketplace — https://code.claude.com/docs/en/plugins/create-marketplace.md
- Host and maintain a marketplace — https://code.claude.com/docs/en/plugins/host-marketplace.md
- Plugin manifest reference — https://code.claude.com/docs/en/plugins/manifest-reference
- Plugin loading reference (synced plugins, versions) — https://code.claude.com/docs/en/plugins/loading.md
- Plugin commands reference — https://code.claude.com/docs/en/plugins/cli-reference.md
- Manage plugins for your organization (Claude Code) — https://code.claude.com/docs/en/plugins/org.md
- Cloud environments (what carries over, setup scripts, GitHub proxy) — https://code.claude.com/docs/en/cloud-environments.md
- Plugins on claude.ai, Desktop and Cowork — https://claude.com/docs/plugins/overview
- Plugin feature support across platforms — https://claude.com/docs/plugins/platform-support
- Sync your organization's plugins from a repository — https://claude.com/docs/plugins/org-sync
- GitHub pricing and Actions billing — https://github.com/pricing, https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions *(to confirm in T0, A7)*
- Keep a Changelog (pt-BR) — https://keepachangelog.com/pt-BR/1.1.0/
