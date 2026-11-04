// Finds a usable Python (>= 3.11) and checks that the bundled pypdf can be imported (SPEC-003 REQ-CDP-02, check C-14).
// Candidates in order: python3, python, py -3 (the Windows launcher). The Microsoft Store "python" alias answers with an
// error, so a candidate only counts if `--version` succeeds and reports 3.11 or newer.

import { fileURLToPath } from 'node:url';
import { run } from './run.mjs';
import { compare, extract } from './semver.mjs';

export const MIN_PYTHON = '3.11.0';
const VENDOR_DIR = fileURLToPath(new URL('../cfp/vendor', import.meta.url));

const CANDIDATES = [
  ['python3', []],
  ['python', []],
  ['py', ['-3']],
];

/** Returns { found, name, prefix, version, tooOld, oldVersion }. */
export function findPython(env = process.env) {
  let oldVersion = null;
  for (const [name, prefix] of CANDIDATES) {
    const r = run(name, [...prefix, '--version'], { env, timeoutMs: 15_000 });
    if (r.notFound || !r.ok) continue;
    const version = extract(`${r.stdout} ${r.stderr}`);
    if (!version) continue;
    if (compare(version, MIN_PYTHON) === -1) {
      oldVersion = oldVersion ?? version;
      continue;
    }
    return { found: true, name, prefix, version };
  }
  return { found: false, tooOld: oldVersion !== null, oldVersion };
}

/** Imports the vendored pypdf with the given Python. Returns { ok, version }. */
export function checkPypdf(py, env = process.env) {
  const code = `import sys; sys.dont_write_bytecode = True; sys.path.insert(0, ${JSON.stringify(VENDOR_DIR)}); import pypdf; print(pypdf.__version__)`;
  const r = run(py.name, [...py.prefix, '-c', code], { env, timeoutMs: 30_000 });
  const version = r.ok ? extract(r.stdout) : null;
  return { ok: Boolean(version), version };
}
