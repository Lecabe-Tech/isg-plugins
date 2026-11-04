// Shared helpers for configure.mjs and upgrade.mjs: how to talk to the marketplace repository.

import { Buffer } from 'node:buffer';
import { MARKETPLACE_NAME, NETWORK_TIMEOUT_MS, ORG_IS_PLACEHOLDER, PLUGIN_DIR_IN_REPO, REPO_SLUG, STABLE_BRANCH } from './constants.mjs';
import { parseJson, redact, runClaude, runGh, runGit } from './run.mjs';
import { pluginsRoot, readJsonFile } from './settings.mjs';
import path from 'node:path';
import fs from 'node:fs';

export const repoUrl = () => `https://github.com/${REPO_SLUG}.git`;

/** Lists installed plugins: { ok, list, error }. Uses `claude plugin list --json` (A2). */
export function listPlugins() {
  const r = runClaude(['plugin', 'list', '--json']);
  if (r.notFound) return { ok: false, list: [], notFound: true, error: 'CLAUDE_CLI_NOT_FOUND' };
  const list = parseJson(r.stdout);
  if (!r.ok || !Array.isArray(list)) return { ok: false, list: [], error: redact(r.stderr || r.stdout).trim().split('\n')[0] || 'plugin list falhou' };
  return { ok: true, list };
}

export function listMarketplaces() {
  const r = runClaude(['plugin', 'marketplace', 'list', '--json']);
  const list = parseJson(r.stdout);
  if (!r.ok || !Array.isArray(list)) return { ok: false, list: [] };
  return { ok: true, list };
}

/** Best effort: the git ref a marketplace entry follows. The JSON shape for GitHub sources is confirmed in T0 G3. */
export function marketplaceRef(entry) {
  if (!entry) return null;
  const candidates = [entry.ref, entry.source?.ref, entry.sourceRef];
  for (const c of candidates) if (typeof c === 'string' && c) return c;
  for (const c of [entry.source, entry.path, entry.url, entry.repo]) {
    if (typeof c === 'string' && c.includes('#')) return c.split('#').pop();
  }
  return null;
}

/** Classifies a failed git/claude message as NO_ACCESS or OFFLINE (REQ-CMD-09). */
export function classifyFailure(text, timedOut = false) {
  const t = String(text ?? '').toLowerCase();
  if (timedOut) return 'OFFLINE';
  if (/could not resolve host|network is unreachable|connection (timed out|refused|reset)|timed out|unable to connect|temporary failure|no route to host|ssl|proxy/.test(t)) return 'OFFLINE';
  if (/authentication|auth failed|permission denied|403|404|not found|could not read username|repository not found|access denied|invalid credentials|terminal prompts disabled|denied/.test(t)) return 'NO_ACCESS';
  return 'UNKNOWN';
}

/** C-06: can this machine read the repository without any prompt? */
export function checkRepoAccess() {
  if (ORG_IS_PLACEHOLDER) return { status: 'skip', reason: 'ORG_PLACEHOLDER' };
  const r = runGit(['ls-remote', '--heads', repoUrl(), STABLE_BRANCH], { timeoutMs: NETWORK_TIMEOUT_MS });
  if (r.notFound) return { status: 'fail', reason: 'GIT_NOT_FOUND' };
  if (r.ok && r.stdout.includes(`refs/heads/${STABLE_BRANCH}`)) return { status: 'ok' };
  if (r.ok) return { status: 'fail', reason: 'NO_STABLE_BRANCH' };
  return { status: 'fail', reason: classifyFailure(`${r.stderr}\n${r.stdout}`, r.timedOut), detail: redact(r.stderr).trim().split('\n')[0] };
}

/** Reads <plugin>/.claude-plugin/plugin.json and CHANGELOG.md from a local marketplace checkout. */
export function readLatestFromCheckout(installLocation) {
  const dir = path.join(installLocation, ...PLUGIN_DIR_IN_REPO.split('/'));
  const pj = readJsonFile(path.join(dir, '.claude-plugin', 'plugin.json'));
  let changelog = '';
  try {
    changelog = fs.readFileSync(path.join(dir, 'CHANGELOG.md'), 'utf8');
  } catch {
    /* no changelog available */
  }
  return pj?.version ? { version: pj.version, changelog } : null;
}

/** Where the local checkout of our marketplace is (R2/R4). Reads known_marketplaces.json, falls back to the CLI. */
export function marketplaceInstallLocation(env = process.env) {
  const known = readJsonFile(path.join(pluginsRoot(env), 'known_marketplaces.json'));
  const fromFile = known?.[MARKETPLACE_NAME]?.installLocation;
  if (fromFile && fs.existsSync(fromFile)) return fromFile;
  const m = listMarketplaces();
  const entry = m.list.find((e) => e.name === MARKETPLACE_NAME);
  return entry?.installLocation && fs.existsSync(entry.installLocation) ? entry.installLocation : null;
}

/** R1: reads the latest released version from `stable` through the GitHub API, only if `gh` is logged in. */
export function readLatestViaGh() {
  if (ORG_IS_PLACEHOLDER) return { ok: false, reason: 'ORG_PLACEHOLDER' };
  const get = (file) =>
    runGh(['api', `repos/${REPO_SLUG}/contents/${PLUGIN_DIR_IN_REPO}/${file}?ref=${STABLE_BRANCH}`, '--jq', '.content'], { timeoutMs: NETWORK_TIMEOUT_MS });
  const pj = get('.claude-plugin/plugin.json');
  if (pj.notFound) return { ok: false, reason: 'GH_NOT_FOUND' };
  if (!pj.ok) return { ok: false, reason: classifyFailure(`${pj.stderr}`, pj.timedOut) === 'UNKNOWN' ? 'GH_FAILED' : classifyFailure(pj.stderr, pj.timedOut) };
  const decode = (b64) => Buffer.from(String(b64).replace(/\s/g, ''), 'base64').toString('utf8');
  const parsed = parseJson(decode(pj.stdout));
  if (!parsed?.version) return { ok: false, reason: 'GH_BAD_RESPONSE' };
  const cl = get('CHANGELOG.md');
  return { ok: true, version: parsed.version, changelog: cl.ok ? decode(cl.stdout) : '' };
}
