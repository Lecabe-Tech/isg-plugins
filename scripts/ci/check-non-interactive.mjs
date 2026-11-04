#!/usr/bin/env node
// VAL-12 (REQ-CMD-13, AC-CMD-6): every script mode finishes on its own with stdin closed.
// `claude`, `gh` and `git` are replaced by test stubs; one scenario makes a tool hang to prove timeouts work.
import { LIST_R1, LIST_R2, CHANGELOG, listCfg, runScript } from '../../test/_harness.mjs';
import { finish } from './_common.mjs';

const problems = [];
const LIMIT_MS = 60_000;
const modes = [
  ['configure.mjs', ['--check', '--json']],
  ['configure.mjs', ['--check']],
  ['configure.mjs', ['--apply', '--json']],
  ['upgrade.mjs', ['--check', '--json']],
  ['upgrade.mjs', ['--apply', '--json']],
  ['upgrade.mjs', []],
];
const scenarios = [
  { name: 'gh logged out', cfg: { ...listCfg(LIST_R2('0.1.0')), gh: { 'auth status': { code: 1, stderr: 'not logged in' } } }, market: { version: '0.2.0', changelog: CHANGELOG() } },
  { name: 'synced route', cfg: listCfg(LIST_R1('0.1.0')) },
  { name: 'nothing installed', cfg: listCfg([]) },
  { name: 'no claude, no gh, no git', cfg: {}, withClaude: false, withGh: false, withGit: false },
  { name: 'tools hang', cfg: { claude: { 'plugin list --json': { code: 0, stdout: '[]', sleepMs: 120_000 } }, gh: { 'auth status': { sleepMs: 120_000 } } }, env: { ISG_TEST_TIMEOUT_MS: '1500' } },
];

for (const sc of scenarios) {
  for (const [script, args] of modes) {
    const r = runScript(script, args, { ...sc, timeoutMs: LIMIT_MS });
    const label = `${script} ${args.join(' ')} [${sc.name}]`;
    if (r.timedOut || r.ms >= LIMIT_MS) problems.push(`${label}: did not finish within ${LIMIT_MS / 1000}s (it may be waiting for input)`);
    else if (r.status === null) problems.push(`${label}: killed by a signal`);
    else if (r.status === 3) problems.push(`${label}: unexpected error exit (3): ${r.stdout.trim().slice(0, 160)}`);
    else if (args.includes('--json') && !r.json) problems.push(`${label}: --json did not print one JSON object`);
  }
}
process.exitCode = finish('VAL-12', 'Scripts are non-interactive and always finish', problems);
