#!/usr/bin/env node
// Runs every local check in order (same ones as CI, except the `claude plugin validate`/install ones, which need the CLI).
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..', '..');
const steps = [
  ['VAL-04 consistency', [path.join(here, 'check-consistency.mjs')]],
  ['VAL-07 no root writes', [path.join(here, 'check-no-root-writes.mjs')]],
  ['VAL-11 language', [path.join(here, 'check-language.mjs')]],
  ['VAL-13 portable core', [path.join(here, 'check-portable.mjs')]],
  ['VAL-M02..M04 memory protocol', [path.join(here, 'check-memory.mjs')]],
  ['unit and script tests', ['--test', path.join(root, 'test', 'lib.test.mjs'), path.join(root, 'test', 'scripts.test.mjs')]],
  ['VAL-12 non-interactive', [path.join(here, 'check-non-interactive.mjs')]],
];
let failed = 0;
for (const [name, args] of steps) {
  const r = spawnSync(process.execPath, args, { stdio: 'inherit', cwd: root });
  if (r.status !== 0) {
    failed++;
    console.error(`>>> FAILED: ${name}`);
  }
}
console.log(failed ? `\n${failed} check(s) failed.` : '\nAll local checks passed.');
process.exitCode = failed ? 1 : 0;
