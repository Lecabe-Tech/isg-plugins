#!/usr/bin/env node
// SPEC-002 VAL-M02..M04 (VAL-M05, the .mcp.json rule, lives in check-portable.mjs).
//   VAL-M02 every memory skill points to its protocol copy and keeps the PT-BR first line (VAL-11 checks the sentence)
//   VAL-M03 copies are identical to plugins/isg-model-alignment/shared/ (run sync-protocol.mjs to fix)
//   VAL-M04 the protocol names every Notion property and status of notion-schema.json exactly
import fs from 'node:fs';
import path from 'node:path';
import { MEMORY_SKILLS } from '../../plugins/isg-model-alignment/scripts/lib/constants.mjs';
import { PLUGIN_DIR, SKILLS_DIR, finish, readJson, readText } from './_common.mjs';
import { differences } from './sync-protocol.mjs';

const problems = [];
const shared = path.join(PLUGIN_DIR, 'shared');

let schema = null;
try {
  schema = readJson(path.join(shared, 'notion-schema.json'));
} catch (e) {
  problems.push(`shared/notion-schema.json is not valid JSON: ${e.message}`);
}
const protocol = fs.existsSync(path.join(shared, 'memory-protocol.md')) ? readText(path.join(shared, 'memory-protocol.md')) : '';
if (!protocol) problems.push('shared/memory-protocol.md is missing');

// VAL-M02
for (const skill of MEMORY_SKILLS) {
  const file = path.join(SKILLS_DIR, skill, 'SKILL.md');
  if (!fs.existsSync(file)) {
    problems.push(`skills/${skill}/SKILL.md is missing (listed in MEMORY_SKILLS)`);
    continue;
  }
  if (!readText(file).includes('memory-protocol.md')) problems.push(`skills/${skill}/SKILL.md does not tell Claude to follow memory-protocol.md`);
}

// VAL-M03
for (const d of differences()) problems.push(`${path.relative(PLUGIN_DIR, d.dst).split(path.sep).join('/')}: ${d.problem} (run: node scripts/ci/sync-protocol.mjs)`);

// REQ-DEG-04: the offline instructions must stay complete (situations A-D, messages, how to keep working, feedback, recovery, never).
for (const heading of ['## 7. Sem conexão com o Notion', '### 7.1', '### 7.2', '### 7.3', '### 7.4', '### 7.5', '### 7.6', '### 7.7']) {
  if (protocol && !protocol.includes(heading)) problems.push(`memory-protocol.md is missing "${heading}" (offline instructions, REQ-DEG-04)`);
}
for (const skill of MEMORY_SKILLS) {
  const file = path.join(SKILLS_DIR, skill, 'SKILL.md');
  if (fs.existsSync(file) && !/seç(ão|ões)[^.\n]*\b7\b/.test(readText(file))) problems.push(`skills/${skill}/SKILL.md does not point to protocol section 7 (working without Notion, REQ-DEG-04)`);
}

// VAL-M04
if (schema && protocol) {
  const names = new Set();
  for (const part of ['subjects', 'memory', 'log']) for (const p of schema[part]?.properties ?? []) names.add(p.name);
  for (const s of schema.statuses?.all ?? []) names.add(s);
  names.add(schema.teamspace);
  names.add(schema.subjects?.database);
  for (const n of names) if (n && !protocol.includes(n)) problems.push(`memory-protocol.md never names "${n}" (from notion-schema.json)`);
  for (const s of schema.statuses?.readable ?? []) if (!schema.statuses.all.includes(s)) problems.push(`readable status "${s}" is not in statuses.all`);
  const d = schema.defaults ?? {};
  for (const [k, v] of [['reviewDeadlineBusinessDays', 2], ['ruleActivationCases', 2], ['ruleRetirementErrors', 3], ['offlineWarningDays', 7]]) {
    if (d[k] !== v) problems.push(`notion-schema.json defaults.${k} = ${d[k]}, SPEC-002 4.6 says ${v}`);
  }
}

process.exitCode = finish('VAL-M02..M04', 'Memory protocol, copies and Notion schema', problems);
