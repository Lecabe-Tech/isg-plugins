#!/usr/bin/env node
// SPEC-002 E9 / 4.7: copies the single-source files of plugins/isg-model-alignment/shared/ into the skills that need them.
// Skills cannot reliably read files outside their own folder on every surface (chat, Cowork), so each gets a copy.
//   node scripts/ci/sync-protocol.mjs          write the copies
//   node scripts/ci/sync-protocol.mjs --check  only report differences (exit 1 if any) — used by check-memory.mjs
import fs from 'node:fs';
import path from 'node:path';
import { MEMORY_SKILLS, SCHEMA_SKILLS } from '../../plugins/isg-model-alignment/scripts/lib/constants.mjs';
import { PLUGIN_DIR, SKILLS_DIR, rel } from './_common.mjs';

const SHARED = path.join(PLUGIN_DIR, 'shared');
const plan = [
  ...MEMORY_SKILLS.map((s) => ['memory-protocol.md', s]),
  ...SCHEMA_SKILLS.map((s) => ['notion-schema.json', s]),
];

export function differences() {
  const out = [];
  for (const [file, skill] of plan) {
    const src = path.join(SHARED, file);
    const dst = path.join(SKILLS_DIR, skill, file);
    if (!fs.existsSync(path.join(SKILLS_DIR, skill, 'SKILL.md'))) out.push({ dst, problem: `skill "${skill}" has no SKILL.md` });
    else if (!fs.existsSync(dst)) out.push({ src, dst, problem: 'missing copy' });
    else if (!fs.readFileSync(src).equals(fs.readFileSync(dst))) out.push({ src, dst, problem: 'copy differs from shared/' + file });
  }
  return out;
}

if (process.argv[1] && path.basename(process.argv[1]) === 'sync-protocol.mjs') {
  const check = process.argv.includes('--check');
  const diffs = differences();
  if (check) {
    for (const d of diffs) console.error(`  - ${rel(d.dst)}: ${d.problem}`);
    process.exitCode = diffs.length ? 1 : 0;
  } else {
    let n = 0;
    for (const d of diffs) {
      if (!d.src) {
        console.error(`  - ${rel(d.dst)}: ${d.problem}`);
        process.exitCode = 1;
        continue;
      }
      fs.copyFileSync(d.src, d.dst);
      n++;
      console.log(`copied ${rel(d.src)} -> ${rel(d.dst)}`);
    }
    console.log(n ? `${n} file(s) updated.` : 'All copies are up to date.');
  }
}
