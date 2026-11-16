import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { CHANGELOG, LIST_BOTH, LIST_R1, LIST_R2, listCfg, runScript } from './_harness.mjs';
import { REPO_SLUG } from '../plugins/isg-model-alignment/scripts/lib/constants.mjs';

const UPDATE_CMD = 'plugin update isg-model-alignment@isg-plugins --scope user';
const MKT_UPDATE = 'plugin marketplace update isg-plugins';
const sha = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const noCall = (calls, prefix) => assert.equal(calls.some((c) => c.includes(prefix)), false, `unexpected call: ${prefix}`);

// ---------- upgrade ----------

test('upgrade: already up to date', () => {
  const r = runScript('upgrade.mjs', ['--check', '--json'], { cfg: listCfg(LIST_R2('0.2.0')), market: { version: '0.2.0', changelog: CHANGELOG() } });
  assert.equal(r.status, 0);
  assert.equal(r.json.code, 'UP_TO_DATE');
  assert.match(r.json.message, /versão mais recente/);
  noCall(r.calls, UPDATE_CMD);
});

test('upgrade --check: update available shows versions and changelog, changes nothing', () => {
  const r = runScript('upgrade.mjs', ['--check', '--json'], { cfg: listCfg(LIST_R2('0.1.0')), market: { version: '0.2.0', changelog: CHANGELOG() } });
  assert.equal(r.status, 0);
  assert.equal(r.json.code, 'UPDATE_AVAILABLE');
  assert.equal(r.json.data.installed, '0.1.0');
  assert.equal(r.json.data.latest, '0.2.0');
  assert.equal(r.json.data.breaking, false);
  assert.match(r.json.data.changelog, /Novidade/);
  assert.equal(r.json.route, 'R2');
  assert.ok(r.calls.some((c) => c.endsWith(MKT_UPDATE)), 'refreshes the catalog');
  noCall(r.calls, UPDATE_CMD);
});

test('upgrade --check: breaking changes are flagged first (REQ-CMD-11)', () => {
  const r = runScript('upgrade.mjs', ['--check', '--json'], {
    cfg: listCfg(LIST_R2('0.1.0')),
    market: { version: '0.2.0', changelog: CHANGELOG('### Quebra de compatibilidade\n- O comando X mudou.\n\n### Adicionado\n- Y.\n') },
  });
  assert.equal(r.json.data.breaking, true);
  assert.match(r.json.data.breakingText, /O comando X mudou/);
  assert.match(r.json.message, /quebram a compatibilidade/);
});

test('upgrade --apply: updates with the official CLI and confirms the new version', () => {
  const r = runScript('upgrade.mjs', ['--apply', '--json'], {
    cfg: { ...listCfg(LIST_R2('0.1.0')), listAfterUpdate: LIST_R2('0.2.0'), claude: { 'plugin list --json': { code: 0, stdout: JSON.stringify(LIST_R2('0.1.0')) }, [UPDATE_CMD]: { code: 0, stdout: 'ok' } } },
    market: { version: '0.2.0', changelog: CHANGELOG() },
  });
  assert.equal(r.status, 0);
  assert.equal(r.json.code, 'UPDATED');
  assert.match(r.json.message, /0\.1\.0 → 0\.2\.0/);
  assert.match(r.json.message, /\/reload-plugins/);
  assert.ok(r.calls.some((c) => c.endsWith(UPDATE_CMD)));
});

test('upgrade --apply: failed update leaves the version unchanged and exits 1', () => {
  const r = runScript('upgrade.mjs', ['--apply', '--json'], {
    cfg: { claude: { 'plugin list --json': { code: 0, stdout: JSON.stringify(LIST_R2('0.1.0')) }, [UPDATE_CMD]: { code: 1, stderr: 'boom\n' } } },
    market: { version: '0.2.0', changelog: CHANGELOG() },
  });
  assert.equal(r.status, 1);
  assert.equal(r.json.code, 'UPDATE_FAILED');
  assert.match(r.json.message, /continua 0\.1\.0/);
});

test('upgrade --apply: command ok but version unchanged is reported as failure', () => {
  const r = runScript('upgrade.mjs', ['--apply', '--json'], {
    cfg: { claude: { 'plugin list --json': { code: 0, stdout: JSON.stringify(LIST_R2('0.1.0')) }, [UPDATE_CMD]: { code: 0 } } },
    market: { version: '0.2.0', changelog: CHANGELOG() },
  });
  assert.equal(r.status, 1);
  assert.equal(r.json.code, 'UPDATE_FAILED');
});

test('upgrade: plugin from the claude.ai account is never updated from here (AC-SRF-2)', () => {
  const r = runScript('upgrade.mjs', ['--apply', '--json'], { cfg: listCfg(LIST_R1('0.1.0')) });
  assert.equal(r.status, 0);
  assert.equal(r.json.code, 'MANAGED_BY_ACCOUNT');
  assert.equal(r.json.route, 'R1');
  assert.match(r.json.message, /conta do claude\.ai/);
  assert.match(r.json.message, /Check for updates/);
  noCall(r.calls, 'plugin update');
  noCall(r.calls, 'marketplace update');
});

test('upgrade: no access to the repository', () => {
  const r = runScript('upgrade.mjs', ['--check', '--json'], {
    cfg: { claude: { 'plugin list --json': { code: 0, stdout: JSON.stringify(LIST_R2('0.1.0')) }, [MKT_UPDATE]: { code: 1, stderr: 'fatal: could not read Username for https://github.com: terminal prompts disabled\n' } } },
  });
  assert.equal(r.status, 1);
  assert.equal(r.json.code, 'NO_ACCESS');
  assert.match(r.json.message, /gh auth login/);
  assert.match(r.json.message, /continua 0\.1\.0/);
});

test('upgrade: offline', () => {
  const r = runScript('upgrade.mjs', ['--check', '--json'], {
    cfg: { claude: { 'plugin list --json': { code: 0, stdout: JSON.stringify(LIST_R2('0.1.0')) }, [MKT_UPDATE]: { code: 1, stderr: 'fatal: unable to access: Could not resolve host: github.com\n' } } },
  });
  assert.equal(r.status, 1);
  assert.equal(r.json.code, 'OFFLINE');
});

test('upgrade: the three situations give three different messages (AC-CMD-5)', () => {
  const a = runScript('upgrade.mjs', ['--check', '--json'], { cfg: listCfg(LIST_R2('0.2.0')), market: { version: '0.2.0', changelog: CHANGELOG() } });
  const b = runScript('upgrade.mjs', ['--check', '--json'], { cfg: { claude: { 'plugin list --json': { code: 0, stdout: JSON.stringify(LIST_R2('0.1.0')) }, [MKT_UPDATE]: { code: 1, stderr: 'Repository not found\n' } } } });
  const c = runScript('upgrade.mjs', ['--check', '--json'], { cfg: { claude: { 'plugin list --json': { code: 0, stdout: JSON.stringify(LIST_R2('0.1.0')) }, [MKT_UPDATE]: { code: 1, stderr: 'Could not resolve host\n' } } } });
  assert.equal(new Set([a.json.message, b.json.message, c.json.message]).size, 3);
  assert.deepEqual([a.status, b.status, c.status], [0, 1, 1]);
});

test('upgrade: not installed, newer than stable, Claude CLI missing, usage error', () => {
  assert.equal(runScript('upgrade.mjs', ['--json'], { cfg: listCfg([]) }).json.code, 'NOT_INSTALLED');
  const newer = runScript('upgrade.mjs', ['--json'], { cfg: listCfg(LIST_R2('0.3.0')), market: { version: '0.2.0', changelog: CHANGELOG() } });
  assert.equal(newer.json.code, 'NEWER_THAN_STABLE');
  noCall(newer.calls, UPDATE_CMD);
  const none = runScript('upgrade.mjs', ['--json'], { withClaude: false });
  assert.equal(none.status, 1);
  assert.equal(none.json.code, 'CLAUDE_CLI_NOT_FOUND');
  const usage = runScript('upgrade.mjs', ['--bogus', '--json'], {});
  assert.equal(usage.status, 2);
  assert.equal(usage.json.code, 'USAGE');
});

// ---------- configure ----------

const HEALTHY_SETTINGS = {
  env: { CLAUDE_CODE_PLUGIN_PREFER_HTTPS: '1' },
  extraKnownMarketplaces: { 'isg-plugins': { source: { source: 'github', repo: 'org/isg-plugins' }, autoUpdate: true } },
  pluginConfigs: { 'isg-model-alignment@isg-plugins': { options: { user_name: 'Ana' } } },
};
const HEALTHY_CFG = (list = LIST_R2()) => ({
  claude: {
    'plugin list --json': { code: 0, stdout: JSON.stringify(list) },
    'plugin marketplace list --json': { code: 0, stdout: JSON.stringify([{ name: 'isg-plugins', source: 'github', ref: 'stable' }]) },
  },
  gh: { 'auth status': { code: 0, stdout: 'Logged in' } },
  git: {
    'config --get-all credential.helper': { code: 0, stdout: 'manager\n' },
    [`ls-remote --heads https://github.com/${REPO_SLUG}.git stable`]: { code: 0, stdout: 'abc123\trefs/heads/stable\n' },
  },
});
const byId = (json, id) => json.checks.find((c) => c.id === id);

test('configure: healthy machine passes, twice, and changes nothing (AC-CMD-1)', () => {
  const a = runScript('configure.mjs', ['--check', '--json'], { cfg: HEALTHY_CFG(), settings: HEALTHY_SETTINGS });
  assert.equal(a.status, 0);
  assert.equal(a.json.code, 'CHECKS_PASSED');
  assert.equal(a.json.checks.filter((c) => c.status === 'fail').length, 0);
  const file = path.join(a.dirs.configHome, 'settings.json');
  const before = sha(file);
  const b = runScript('configure.mjs', ['--check', '--json'], { cfg: HEALTHY_CFG(), settings: HEALTHY_SETTINGS });
  assert.deepEqual(b.json.checks.map((c) => [c.id, c.status]), a.json.checks.map((c) => [c.id, c.status]));
  assert.equal(sha(file), before);
  assert.equal(byId(a.json, 'C-02').status, 'ok');
  assert.equal(byId(a.json, 'C-03').status, 'ok');
  assert.equal(byId(a.json, 'C-07').status, 'ok');
});

test('configure: gh missing fails C-04 with the fix, and the other checks still run (AC-CMD-2)', () => {
  const r = runScript('configure.mjs', ['--check', '--json'], { cfg: HEALTHY_CFG(), settings: HEALTHY_SETTINGS, withGh: false });
  assert.equal(r.status, 1);
  assert.equal(byId(r.json, 'C-04').status, 'fail');
  assert.match(byId(r.json, 'C-04').fix, /gh auth login/);
  assert.equal(byId(r.json, 'C-08').status, 'ok');
  assert.ok(r.json.checks.length >= 12);
});

test('configure: gh logged out fails C-04 with gh auth login and setup-git', () => {
  const cfg = HEALTHY_CFG();
  cfg.gh['auth status'] = { code: 1, stderr: 'You are not logged in' };
  const r = runScript('configure.mjs', ['--check', '--json'], { cfg, settings: HEALTHY_SETTINGS });
  assert.equal(byId(r.json, 'C-04').status, 'fail');
  assert.match(byId(r.json, 'C-04').fix, /gh auth setup-git/);
});

test('configure: plugin from the account (R1) skips the git checks', () => {
  const r = runScript('configure.mjs', ['--check', '--json'], { cfg: HEALTHY_CFG(LIST_R1()), settings: {} });
  assert.equal(r.json.route, 'R1');
  for (const id of ['C-04', 'C-05', 'C-06', 'C-07', 'C-10']) assert.equal(byId(r.json, id).status, 'skip', id);
  assert.equal(byId(r.json, 'C-08').status, 'ok');
  assert.equal(r.status, 0);
});

test('configure: both routes at once is reported (C-12, P-33)', () => {
  const r = runScript('configure.mjs', ['--check', '--json'], { cfg: HEALTHY_CFG(LIST_BOTH()), settings: HEALTHY_SETTINGS });
  assert.equal(byId(r.json, 'C-12').status, 'fail');
  assert.match(byId(r.json, 'C-12').fix, /claude plugin disable/);
});

test('configure --check never changes anything and lists what it could change (AC-CMD-3)', () => {
  const settings = { extraKnownMarketplaces: { 'isg-plugins': { source: { source: 'github', repo: 'o/r' } } } };
  const r = runScript('configure.mjs', ['--check', '--json'], { cfg: HEALTHY_CFG(), settings });
  const file = path.join(r.dirs.configHome, 'settings.json');
  assert.deepEqual(JSON.parse(fs.readFileSync(file, 'utf8')), settings);
  assert.deepEqual(fs.readdirSync(r.dirs.configHome), ['settings.json'], 'no backup, no temp file');
  const ids = r.json.data.pendingChanges.map((c) => c.id).sort();
  assert.deepEqual(ids, ['autoUpdate', 'preferHttps']);
  for (const c of r.json.data.pendingChanges) for (const k of ['file', 'key', 'old', 'new', 'why']) assert.ok(k in c, `${c.id} has ${k}`);
});

test('configure --apply: changes only the two allowed keys, makes a backup, is idempotent', () => {
  const settings = { theme: 'dark', extraKnownMarketplaces: { 'isg-plugins': { source: { source: 'github', repo: 'o/r' } } } };
  const r = runScript('configure.mjs', ['--apply', '--json'], { cfg: HEALTHY_CFG(), settings });
  assert.equal(r.status, 0);
  assert.equal(r.json.code, 'APPLIED');
  const file = path.join(r.dirs.configHome, 'settings.json');
  const after = JSON.parse(fs.readFileSync(file, 'utf8'));
  assert.equal(after.theme, 'dark', 'unrelated keys untouched');
  assert.equal(after.extraKnownMarketplaces['isg-plugins'].autoUpdate, true);
  assert.equal(after.extraKnownMarketplaces['isg-plugins'].source.repo, 'o/r');
  assert.equal(after.env.CLAUDE_CODE_PLUGIN_PREFER_HTTPS, '1');
  const backups = fs.readdirSync(r.dirs.configHome).filter((f) => f.startsWith('settings.json.bak-'));
  assert.equal(backups.length, 1);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(r.dirs.configHome, backups[0]), 'utf8')), settings, 'backup is the original');
  assert.equal(fs.readFileSync(file, 'utf8').charCodeAt(0) === 0xfeff, false, 'no BOM');
  // second run on the result: nothing to do
  const again = runScript('configure.mjs', ['--apply', '--json'], { cfg: HEALTHY_CFG(), settings: after });
  assert.equal(again.json.code, 'NOTHING_TO_APPLY');
  assert.equal(fs.readdirSync(again.dirs.configHome).filter((f) => f.includes('.bak-')).length, 0);
});

test('configure --apply --only: applies just the requested change', () => {
  const settings = { extraKnownMarketplaces: { 'isg-plugins': { source: { source: 'github', repo: 'o/r' } } } };
  const r = runScript('configure.mjs', ['--apply', '--only', 'preferHttps', '--json'], { cfg: HEALTHY_CFG(), settings });
  const after = JSON.parse(fs.readFileSync(path.join(r.dirs.configHome, 'settings.json'), 'utf8'));
  assert.equal(after.env.CLAUDE_CODE_PLUGIN_PREFER_HTTPS, '1');
  assert.equal(after.extraKnownMarketplaces['isg-plugins'].autoUpdate, undefined);
});

test('configure --apply on the account route changes nothing', () => {
  const r = runScript('configure.mjs', ['--apply', '--json'], { cfg: HEALTHY_CFG(LIST_R1()), settings: { theme: 'dark' } });
  assert.equal(r.json.code, 'NOTHING_TO_APPLY');
  assert.deepEqual(fs.readdirSync(r.dirs.configHome), ['settings.json']);
});

test('configure --apply with a broken settings.json fails safely and leaves it untouched', () => {
  const r = runScript('configure.mjs', ['--apply', '--json'], { cfg: HEALTHY_CFG(), settingsRaw: '{ not json' });
  assert.equal(r.status, 1);
  assert.equal(r.json.code, 'APPLY_FAILED');
  assert.match(r.json.message, /nada foi alterado/);
  assert.equal(fs.readFileSync(path.join(r.dirs.configHome, 'settings.json'), 'utf8'), '{ not json');
  assert.deepEqual(fs.readdirSync(r.dirs.configHome), ['settings.json']);
});

test('configure --apply creates settings.json when it does not exist', () => {
  const r = runScript('configure.mjs', ['--apply', '--json'], { cfg: HEALTHY_CFG() });
  assert.equal(r.json.code, 'APPLIED');
  const after = JSON.parse(fs.readFileSync(path.join(r.dirs.configHome, 'settings.json'), 'utf8'));
  assert.equal(after.env.CLAUDE_CODE_PLUGIN_PREFER_HTTPS, '1');
});

test('configure C-14: Python and bundled pypdf (SPEC-003)', () => {
  const ok = runScript('configure.mjs', ['--check', '--json'], { cfg: HEALTHY_CFG(), settings: HEALTHY_SETTINGS });
  assert.equal(byId(ok.json, 'C-14').status, 'ok');
  assert.match(byId(ok.json, 'C-14').message, /pypdf 6\.21\.4/);

  // Python missing: only a warning (it is needed just to process PDFs), exit stays 0
  const none = runScript('configure.mjs', ['--check', '--json'], { cfg: HEALTHY_CFG(), settings: HEALTHY_SETTINGS, withPython: false });
  assert.equal(byId(none.json, 'C-14').status, 'warn');
  assert.match(byId(none.json, 'C-14').fix, /python\.org/);
  assert.equal(none.status, 0);

  // too old
  const old = HEALTHY_CFG();
  old.python = { '--version': { code: 0, stdout: 'Python 3.9.2\n' } };
  const r = runScript('configure.mjs', ['--check', '--json'], { cfg: old, settings: HEALTHY_SETTINGS });
  assert.equal(byId(r.json, 'C-14').status, 'warn');
  assert.match(byId(r.json, 'C-14').message, /antigo/);

  // bundled library does not load
  const bad = HEALTHY_CFG();
  bad.python = { '--version': { code: 0, stdout: 'Python 3.12.0\n' }, '-c': { code: 1, stderr: 'ModuleNotFoundError: pypdf' } };
  const f = runScript('configure.mjs', ['--check', '--json'], { cfg: bad, settings: HEALTHY_SETTINGS });
  assert.equal(byId(f.json, 'C-14').status, 'fail');
  assert.equal(f.status, 1);
});

test('configure: unknown flag is a usage error (exit 2)', () => {
  const r = runScript('configure.mjs', ['--nope', '--json'], {});
  assert.equal(r.status, 2);
  assert.equal(r.json.code, 'USAGE');
});

test('human output is PT-BR with accents (A9)', () => {
  const r = runScript('configure.mjs', ['--check'], { cfg: HEALTHY_CFG(), settings: HEALTHY_SETTINGS });
  assert.match(r.stdout, /Tudo certo/);
  assert.match(r.stdout, /\[OK\] C-02 Node\.js/);
  assert.match(r.stdout, /Acesso ao repositório/);
});
