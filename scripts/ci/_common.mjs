// Shared helpers for the CI checks (not shipped to users: SPEC-001 4.1).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { PLUGIN_NAME } from '../../plugins/isg-model-alignment/scripts/lib/constants.mjs';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
export const PLUGIN_DIR = path.join(ROOT, 'plugins', PLUGIN_NAME);
export const SCRIPTS_DIR = path.join(PLUGIN_DIR, 'scripts');
export const SKILLS_DIR = path.join(PLUGIN_DIR, 'skills');

export const readText = (file) => fs.readFileSync(file, 'utf8');
export const readJson = (file) => JSON.parse(readText(file).replace(/^﻿/, ''));

export function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

export const rel = (p) => path.relative(ROOT, p).split(path.sep).join('/');

/** Collects problems, prints them, and exits with 1 when there are any. */
export function finish(checkId, title, problems) {
  if (problems.length === 0) {
    console.log(`[OK] ${checkId} ${title}`);
    return 0;
  }
  console.error(`[FALHOU] ${checkId} ${title}`);
  for (const p of problems) console.error(`  - ${p}`);
  return 1;
}

/** Splits a SKILL.md into { frontmatter: {key: value}, body }. */
export function parseSkill(text) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text.replace(/^﻿/, ''));
  if (!m) return { frontmatter: {}, body: text };
  const frontmatter = {};
  for (const line of m[1].split(/\r?\n/)) {
    const kv = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
    if (kv) frontmatter[kv[1]] = kv[2].trim();
  }
  return { frontmatter, body: m[2] };
}
