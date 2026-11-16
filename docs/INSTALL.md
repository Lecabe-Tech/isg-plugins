# Installing the ISG Model Alignment plugin

> English copy of `INSTALL.pt-BR.md` (the PT-BR guide is the one end users read; keep both in sync, REQ-LNG-03).
> Each route fits on one page. Read section 1 first to pick yours.

## 1. Before you start

**You need (all free):**

- A Claude **Pro, Max, Ultra, Team or Enterprise** plan. **Claude Free is not supported.**
- A **personal GitHub account**. Tip: add and verify your institutional email on it so we can tell who is who. **No shared accounts.**
- To be **invited** to the repository `Lecabe-Tech-Company/isg-plugins` (ask one of the owners: **<owner names>**) and to **accept the invitation** that arrives by email.

| Where you use Claude | Route |
|---|---|
| claude.ai chat, Desktop chat, Cowork | **Route A** (claude.ai account) |
| Claude Code (terminal, Desktop Code tab) | **Route A** (recommended) or **Route B** |
| Claude Code on the web (claude.ai/code) | **Route A** |

Use **one route per computer**. Installing through both can make versions diverge.

## 2. Route A — through your claude.ai account (recommended)

One install covers chat, Cowork and Claude Code.

1. In **claude.ai** (or the Desktop app) open **Customize > Plugins**.
2. **Add > Add marketplace**.
3. Enter `Lecabe-Tech-Company/isg-plugins` and confirm.
4. If asked, **connect your GitHub account** and authorize the **Claude** GitHub app. If it says you have no access, your invitation is not accepted yet, or the Claude app has no access to the repository: ask the owners.
5. Open the **isg-plugins** marketplace, pick **ISG Model Alignment**, click **Add**.
6. Turn on **"Sync automatically"**.
7. **Claude Code:** restart it, signed in with the **same claude.ai account** (not an API key). The plugin shows up as `isg-model-alignment@synced`.

**Check:** type `/` in a conversation and look for `isg-model-alignment`; in Claude Code run `/isg-model-alignment:configure`.

**Update:** automatic with "Sync automatically"; or **Customize > Plugins > Check for updates**, then restart Claude Code.

## 3. Route B — through Claude Code on this computer

For people who use Claude Code and cannot use Route A, and for maintainers.

**Once — install:** Claude Code (2.1.317 or newer), Git, GitHub CLI (`gh`), Node.js LTS 20 or newer.

**Once — set up access:**

```bash
gh auth login
gh auth setup-git
```

Choose **GitHub.com** and **HTTPS**. Then set the environment variable `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` (or let `/isg-model-alignment:configure` do it).

**Install (2 commands):**

```bash
claude plugin marketplace add Lecabe-Tech-Company/isg-plugins#stable
claude plugin install isg-model-alignment@isg-plugins
```

Open Claude Code and run `/isg-model-alignment:configure`.

**Update:** `/isg-model-alignment:upgrade`, then restart Claude Code or run `/reload-plugins`.

## 3a. Python (only to process PDFs)

`/isg-model-alignment:cfp` (large-PDF processing) uses a program in **Python 3.11 or newer** (free, https://www.python.org/downloads/; on Windows tick **"Add python.exe to PATH"**). The PDF library is already inside the plugin. If you will not process PDFs you do not need Python. Check with `/isg-model-alignment:configure` (item C-14). Usage guide: `docs/CFP.pt-BR.md`.

## 3b. Connect Notion (every route, once)

The plugin already includes the Notion connection (where the agent's shared memory lives). You only **authenticate**:

- **Claude Code:** `/mcp` → `plugin:isg-model-alignment:notion` → **Authenticate** → in the browser pick the **Instituto Sonho Grande** workspace and allow.
- **claude.ai, Desktop app, Cowork:** Customize > Plugins > **ISG Model Alignment** > **Connectors** tab > **Connect** on **notion**, same workspace choice.

You must be a **member** of the Instituto's Notion workspace (guests cannot connect). Check with `/isg-model-alignment:configure` (item C-13).

## 4. Route C — Team/Enterprise organization owners

If your Claude organization owner blocked "add marketplace", they can sync this repo in **Organization settings > Plugins & skills**. **All members** of that Claude organization then get the plugin, GitHub access or not. Use only if that is acceptable (see `docs/RELEASING.md`).

## 5. Leaving the team

Remove the plugin from your claude.ai account. Owners remove your repository access. Installed copies keep working at their last version but get no updates.

## 6. Problems?

See `docs/TROUBLESHOOTING.md`.
