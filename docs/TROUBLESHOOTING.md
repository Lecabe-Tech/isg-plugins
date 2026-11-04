# Troubleshooting

English copy of `TROUBLESHOOTING.pt-BR.md`. First run `/isg-model-alignment:configure`: it tells you what is wrong and how to fix it.

## "No access" when adding the marketplace or updating
- You must be **invited** to the repository and **accept the invitation** (GitHub email). Ask the owners.
- Route B: run `gh auth login` and `gh auth setup-git` (GitHub.com, HTTPS).
- Route A: in claude.ai check that GitHub is connected and the **Claude** app can access `isg-plugins`.

## The plugin does not update
1. Which route (A = claude.ai account, B = Claude Code on this computer)?
2. Was a new version released? Check the repository **Releases** page. Only releases reach users.
3. Route A: is "Sync automatically" on? Try **Check for updates**, then restart Claude Code.
4. Route B: `gh auth status`; auto-update on? Run `/isg-model-alignment:upgrade`, then `/reload-plugins`.

## Two versions / both `@synced` and `@isg-plugins` listed
Installed through both routes. Keep one: `claude plugin disable isg-model-alignment@synced`.

## "Without shared memory" / Notion does not connect
Authenticate Notion (`/mcp` → `plugin:isg-model-alignment:notion` → Authenticate, or the plugin's Connectors tab on claude.ai), pick the **Instituto Sonho Grande** workspace, and make sure you are a **member** (guests cannot connect).

## "node: command not found"
Install Node.js LTS (20+). Only `configure` and `upgrade` need Node.

## `CLAUDE_CLI_NOT_FOUND`
Use Claude Code's own terminal or install/update Claude Code. In the Desktop app `claude` is not always on PATH; the plugin looks for it via `CLAUDE_CODE_EXECPATH`.

## Chat and Cowork
No terminal: `configure` and `upgrade` print manual steps. Use Claude Code for full checks.

## Not visible in Claude Code on the web / after Route A
Needs a plan that includes Claude Code on the web and Route A. Claude Code must be signed in with the claude.ai account (not an API key). Start a new session or run `/reload-plugins`.

## Still stuck?
Contact the owners with: route, OS, version (`claude plugin list`) and the message you saw.
