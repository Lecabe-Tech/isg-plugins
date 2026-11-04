// Test harness: runs configure.mjs / upgrade.mjs with fake claude/gh/git and an isolated config folder.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const SCRIPTS = path.join(HERE, '..', 'plugins', 'isg-model-alignment', 'scripts');
const STUBS = path.join(HERE, 'stubs');

export const LIST_R2 = (version = '0.1.0') => [{ id: 'isg-model-alignment@isg-plugins', version, scope: 'user', enabled: true }];
export const LIST_R1 = (version = '0.1.0') => [{ id: 'isg-model-alignment@synced', version, scope: 'user', enabled: true }];
export const LIST_BOTH = (version = '0.1.0') => [...LIST_R2(version), ...LIST_R1(version)];

export function tmpDir(prefix = 'isg-test-') {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

/** Creates a fake marketplace checkout + known_marketplaces.json inside `pluginsRoot`. */
export function fakeMarketplace(pluginsRoot, version, changelog) {
  const mkt = path.join(pluginsRoot, 'marketplaces', 'isg-plugins');
  const pdir = path.join(mkt, 'plugins', 'isg-model-alignment');
  fs.mkdirSync(path.join(pdir, '.claude-plugin'), { recursive: true });
  fs.writeFileSync(path.join(pdir, '.claude-plugin', 'plugin.json'), JSON.stringify({ name: 'isg-model-alignment', version }));
  fs.writeFileSync(path.join(pdir, 'CHANGELOG.md'), changelog);
  fs.writeFileSync(path.join(pluginsRoot, 'known_marketplaces.json'), JSON.stringify({ 'isg-plugins': { installLocation: mkt } }));
  return mkt;
}

export const CHANGELOG = (extra020 = '### Adicionado\n- Novidade.\n') =>
  `# Changelog\n\n## [0.2.0] - 2026-12-01\n\n${extra020}\n## [0.1.0] - 2026-11-04\n\n### Adicionado\n- Primeira versão.\n`;

/**
 * Runs a script. opts: { cfg, settings, withClaude, withGh, withGit, env, args }
 * Returns { status, stdout, stderr, json, calls, dirs, ms }.
 */
export function runScript(script, args, opts = {}) {
  const dir = tmpDir();
  const configHome = path.join(dir, 'claude');
  const pluginsRoot = path.join(dir, 'plugins');
  fs.mkdirSync(configHome, { recursive: true });
  fs.mkdirSync(pluginsRoot, { recursive: true });
  if (opts.settings) fs.writeFileSync(path.join(configHome, 'settings.json'), JSON.stringify(opts.settings, null, 2));
  if (opts.settingsRaw !== undefined) fs.writeFileSync(path.join(configHome, 'settings.json'), opts.settingsRaw);
  if (opts.market) fakeMarketplace(pluginsRoot, opts.market.version, opts.market.changelog);
  const log = path.join(dir, 'calls.log');
  const state = path.join(dir, 'state');
  fs.writeFileSync(log, '');

  const env = {
    SystemRoot: process.env.SystemRoot,
    TEMP: process.env.TEMP,
    TMP: process.env.TMP,
    PATH: '', // real claude/gh/git must never be found
    CLAUDE_CONFIG_DIR: configHome,
    CLAUDE_CODE_PLUGIN_CACHE_DIR: pluginsRoot,
    STUB_CFG: JSON.stringify(opts.cfg ?? {}),
    STUB_LOG: log,
    STUB_STATE: state,
    ...(opts.withClaude === false ? {} : { ISG_TEST_CLAUDE_STUB: path.join(STUBS, 'claude.mjs') }),
    ...(opts.withGh === false ? {} : { ISG_TEST_GH_STUB: path.join(STUBS, 'gh.mjs') }),
    ...(opts.withGit === false ? {} : { ISG_TEST_GIT_STUB: path.join(STUBS, 'git.mjs') }),
    ...(opts.withPython === false ? {} : { ISG_TEST_PYTHON_STUB: path.join(STUBS, 'python.mjs') }),
    ...(opts.env ?? {}),
  };
  const t0 = Date.now();
  const r = spawnSync(process.execPath, [path.join(SCRIPTS, script), ...args], {
    env,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'], // stdin closed: a script that waits for input would hang (REQ-CMD-13)
    timeout: opts.timeoutMs ?? 60_000,
  });
  let json = null;
  try {
    json = JSON.parse(r.stdout);
  } catch {
    /* human mode */
  }
  const calls = fs.readFileSync(log, 'utf8').split('\n').filter(Boolean);
  return { status: r.status, stdout: r.stdout, stderr: r.stderr, json, calls, dirs: { dir, configHome, pluginsRoot }, ms: Date.now() - t0, timedOut: r.error?.code === 'ETIMEDOUT' };
}

export const listCfg = (list) => ({ claude: { 'plugin list --json': { code: 0, stdout: JSON.stringify(list) } } });
