// Minimal SemVer helpers (MAJOR.MINOR.PATCH only; pre-release tags are not used by this project).

const RE = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;

export function isValid(version) {
  return typeof version === 'string' && RE.test(version);
}

export function parse(version) {
  const m = typeof version === 'string' ? RE.exec(version.trim()) : null;
  if (!m) return null;
  return { major: Number(m[1]), minor: Number(m[2]), patch: Number(m[3]) };
}

/** Returns -1, 0 or 1. Returns null when either value is not a valid version. */
export function compare(a, b) {
  const pa = parse(a);
  const pb = parse(b);
  if (!pa || !pb) return null;
  for (const key of ['major', 'minor', 'patch']) {
    if (pa[key] !== pb[key]) return pa[key] < pb[key] ? -1 : 1;
  }
  return 0;
}

/** Extracts the first X.Y.Z found in a text such as "2.1.317 (Claude Code)". */
export function extract(text) {
  const m = /(\d+)\.(\d+)\.(\d+)/.exec(String(text ?? ''));
  return m ? `${m[1]}.${m[2]}.${m[3]}` : null;
}
