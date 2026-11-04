// Detects the surface (S1..S3) and the install route (R1..R4) when a shell exists (SPEC-001 4.11).
// On chat and Cowork there is no shell, so these scripts never run there.
//
// Assumption A13 (cloud detection through CLAUDE_CODE_REMOTE) is NOT yet confirmed: see T0 results G9.
// Until then a cloud session may be reported as S1; configure/upgrade still work (they only use `claude plugin list`).

import { PLUGIN_ID, PLUGIN_NAME, SYNCED_ID } from './constants.mjs';

export function detectSurface(env = process.env) {
  const remote = String(env.CLAUDE_CODE_REMOTE ?? '').toLowerCase();
  if (remote === '1' || remote === 'true') {
    return { surface: 'S3', evidence: 'CLAUDE_CODE_REMOTE', confirmed: false };
  }
  if (env.CLAUDE_CODE_ENTRYPOINT === 'claude-desktop') {
    return { surface: 'S2', evidence: 'CLAUDE_CODE_ENTRYPOINT=claude-desktop', confirmed: true };
  }
  return { surface: 'S1', evidence: 'default (terminal or IDE)', confirmed: false };
}

/**
 * Looks at the output of `claude plugin list --json` and decides the route.
 *   R1  = synced from the claude.ai account (also what R3 org sync looks like)
 *   R2  = installed from the marketplace on this machine
 *   R4  = like R2 but inside a cloud session (setup script)
 *   R1+R2 = both present (P-33, check C-12)
 *   NONE = not installed
 */
export function detectRoute(list, surface = 'S1') {
  const entries = Array.isArray(list) ? list.filter((e) => typeof e?.id === 'string' && e.id.split('@')[0] === PLUGIN_NAME) : [];
  const synced = entries.find((e) => e.id === SYNCED_ID) ?? null;
  const market = entries.find((e) => e.id === PLUGIN_ID) ?? null;
  const other = entries.filter((e) => e !== synced && e !== market);
  let route = 'NONE';
  if (synced && market) route = 'R1+R2';
  else if (synced) route = 'R1';
  else if (market) route = surface === 'S3' ? 'R4' : 'R2';
  else if (other.length) route = 'OTHER';
  return { route, synced, market, other, entry: market ?? synced ?? other[0] ?? null };
}
