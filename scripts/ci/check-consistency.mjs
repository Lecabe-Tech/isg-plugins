#!/usr/bin/env node
// VAL-04 (names and version) and, with --release, the release-only checks of REQ-REL-03 (d) (e).
//   node scripts/ci/check-consistency.mjs            every PR
//   node scripts/ci/check-consistency.mjs --release  also: org is not a placeholder, version has a CHANGELOG section
import path from 'node:path';
import { GITHUB_ORG, MARKETPLACE_NAME, MIN_CLAUDE_VERSION, ORG_IS_PLACEHOLDER, PLUGIN_NAME } from '../../plugins/isg-model-alignment/scripts/lib/constants.mjs';
import { findSection, validate as validateChangelog } from '../../plugins/isg-model-alignment/scripts/lib/changelog.mjs';
import { isValid } from '../../plugins/isg-model-alignment/scripts/lib/semver.mjs';
import { PLUGIN_DIR, ROOT, finish, readJson, readText, walk, rel } from './_common.mjs';

const release = process.argv.includes('--release');
const problems = [];

const market = readJson(path.join(ROOT, '.claude-plugin', 'marketplace.json'));
const plugin = readJson(path.join(PLUGIN_DIR, '.claude-plugin', 'plugin.json'));

if (market.name !== MARKETPLACE_NAME) problems.push(`marketplace.json name "${market.name}" != constants.mjs "${MARKETPLACE_NAME}"`);
if (plugin.name !== PLUGIN_NAME) problems.push(`plugin.json name "${plugin.name}" != constants.mjs "${PLUGIN_NAME}"`);
const entries = market.plugins ?? [];
if (entries.length !== 1) problems.push(`marketplace.json must list exactly 1 plugin in v1 (found ${entries.length})`);
const entry = entries.find((e) => e.name === PLUGIN_NAME);
if (!entry) problems.push(`marketplace.json has no entry named "${PLUGIN_NAME}" (REQ-REP-02)`);
else {
  if ('version' in entry) problems.push('marketplace.json entry must NOT have "version" (REQ-REL-01, P-02)');
  if (entry.source !== `./plugins/${PLUGIN_NAME}`) problems.push(`entry source must be "./plugins/${PLUGIN_NAME}" (found "${entry.source}")`);
}
if (!isValid(plugin.version)) problems.push(`plugin.json version "${plugin.version}" is not MAJOR.MINOR.PATCH (REQ-REL-01)`);

const changelogPath = path.join(PLUGIN_DIR, 'CHANGELOG.md');
let changelog = '';
try {
  changelog = readText(changelogPath);
} catch {
  problems.push(`${rel(changelogPath)} is missing (REQ-REL-05)`);
}
for (const e of validateChangelog(changelog)) problems.push(`CHANGELOG.md: ${e}`);

// Every text file must be UTF-8 without BOM and use LF (REQ-REP-06).
for (const file of walk(ROOT)) {
  const r = rel(file);
  if (r.startsWith('.git/') || r.includes('node_modules/') || !/\.(md|json|mjs|js|yml|yaml|sh|ps1|txt)$/.test(r) && r !== '.gitattributes' && r !== '.gitignore') continue;
  const buf = readText(file);
  if (buf.charCodeAt(0) === 0xfeff) problems.push(`${r}: has a BOM (REQ-REP-06)`);
  if (buf.includes('\r\n')) problems.push(`${r}: has CRLF line endings (REQ-REP-06)`);
}

// Workflows: the Claude Code version they install is MIN_CLAUDE_VERSION, and every action is pinned to a commit SHA (REQ-CST-04).
for (const name of ['validate.yml', 'release.yml']) {
  const file = path.join(ROOT, '.github', 'workflows', name);
  let text = '';
  try {
    text = readText(file);
  } catch {
    problems.push(`.github/workflows/${name} is missing`);
    continue;
  }
  const v = /CLAUDE_CODE_VERSION:\s*'([^']+)'/.exec(text);
  if (!v || v[1] !== MIN_CLAUDE_VERSION) problems.push(`.github/workflows/${name}: CLAUDE_CODE_VERSION (${v?.[1]}) must equal MIN_CLAUDE_VERSION (${MIN_CLAUDE_VERSION})`);
  for (const m of text.matchAll(/^\s*-?\s*uses:\s*(\S+)/gm)) {
    if (!/@[0-9a-f]{40}(\s|$)/.test(m[1] + ' ')) problems.push(`.github/workflows/${name}: action "${m[1]}" is not pinned to a commit SHA (REQ-CST-04)`);
  }
}

if (release) {
  if (ORG_IS_PLACEHOLDER) problems.push(`constants.mjs GITHUB_ORG is still "${GITHUB_ORG}": set the real organization before releasing (Q2)`);
  if (JSON.stringify(plugin).includes('<org>')) problems.push('plugin.json still contains "<org>"');
  if (isValid(plugin.version) && !findSection(changelog, plugin.version)) {
    problems.push(`CHANGELOG.md has no "## [${plugin.version}] - AAAA-MM-DD" section (REQ-REL-03 e)`);
  }
}

process.exitCode = finish('VAL-04', release ? 'Names, versions, changelog and release readiness' : 'Names, versions and changelog', problems);
