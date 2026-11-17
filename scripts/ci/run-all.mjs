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
  ['VAL-C09/C10 CFP vendored library and writes', [path.join(here, 'check-cfp.mjs')]],
  ['VAL-SEC-01 external addresses', [path.join(here, 'check-links.mjs')]],
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

// CFP and EQV tests (Python, SPEC-003 and SPEC-005). Needs Python 3.11+ (python3, python or py -3).
const pythons = [['python3', []], ['python', []], ['py', ['-3']]];
let ran = false;
for (const [cmd, pre] of pythons) {
  const probe = spawnSync(cmd, [...pre, '-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'], { encoding: 'utf8' });
  if (probe.status !== 0) continue;
  ran = true;
  const r = spawnSync(cmd, [...pre, '-m', 'unittest', 'test.cfp.test_cfp', 'test.eqv.test_eqv', 'test.quality.test_quality_payload', 'test.quality.test_quality_structured', 'test.quality.test_quality_templates', 'test.quality.test_q17_aprendizados', 'test.quality.test_q17_layout', 'test.quality.test_q17_result', 'test.quality.test_q17_crosscheck', 'test.quality.test_q17_orientations', 'test.quality.test_q17_matrix', 'test.quality.test_q17_extract', 'test.quality.test_q17_contracts'], { stdio: 'inherit', cwd: root, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  if (r.status !== 0) {
    failed++;
    console.error('>>> FAILED: Python tests (CFP, EQV, quality)');
  }
  break;
}
if (!ran) {
  failed++;
  console.error('>>> FAILED: no Python 3.11+ found to run the CFP tests (install Python 3.11 or newer)');
}
console.log(failed ? `\n${failed} check(s) failed.` : '\nAll local checks passed.');
process.exitCode = failed ? 1 : 0;
