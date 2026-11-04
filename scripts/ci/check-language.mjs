#!/usr/bin/env node
// VAL-11 (REQ-LNG-01, P-24): every user-facing text is PT-BR and every skill carries the fixed PT-BR instruction.
import path from 'node:path';
import { ROOT, PLUGIN_DIR, SKILLS_DIR, finish, parseSkill, readJson, readText, rel, walk } from './_common.mjs';

export const FIRST_LINE = 'Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.';

const PT_WORDS = /\b(de|do|da|dos|das|para|com|que|um|uma|no|na|nos|nas|em|e|ou|o|a|os|as|seu|sua|ao|pelo|pela|não|está|são)\b/i;
const EN_WORDS = /\b(the|and|with|for|your|this|that|use|used|when|from|helper|plugin for)\b/i;

/** Rough PT-BR test: has at least one Portuguese function word, and is not obviously English. */
export function looksPortuguese(text) {
  const t = String(text ?? '').trim();
  if (!t) return false;
  if (/[áàâãéêíóôõúç]/i.test(t)) return true;
  if (PT_WORDS.test(t)) return !(EN_WORDS.test(t) && !/\b(de|do|da|para|com|que|não)\b/i.test(t));
  return false;
}

const problems = [];
const need = (where, text) => {
  if (!looksPortuguese(text)) problems.push(`${where}: text is empty or does not look like PT-BR: "${String(text ?? '').slice(0, 80)}"`);
};

const plugin = readJson(path.join(PLUGIN_DIR, '.claude-plugin', 'plugin.json'));
need('plugin.json description', plugin.description);
for (const [key, cfg] of Object.entries(plugin.userConfig ?? {})) {
  need(`plugin.json userConfig.${key}.title`, cfg.title);
  need(`plugin.json userConfig.${key}.description`, cfg.description);
}
const market = readJson(path.join(ROOT, '.claude-plugin', 'marketplace.json'));
need('marketplace.json description', market.description);
for (const e of market.plugins ?? []) need(`marketplace.json plugins[${e.name}].description`, e.description);

const skillFiles = walk(SKILLS_DIR).filter((f) => path.basename(f) === 'SKILL.md');
if (skillFiles.length === 0) problems.push('no SKILL.md found');
for (const file of skillFiles) {
  const { frontmatter, body } = parseSkill(readText(file));
  const firstLine = body.split('\n').find((l) => l.trim() !== '') ?? '';
  if (firstLine.trim() !== FIRST_LINE) problems.push(`${rel(file)}: first line of the body must be exactly: ${FIRST_LINE}`);
  need(`${rel(file)} description`, frontmatter.description);
}
// Messages in scripts must not be English by accident: the most common slip is "Error:" / "Failed".
for (const file of walk(path.join(PLUGIN_DIR, 'scripts')).filter((f) => f.endsWith('.mjs'))) {
  readText(file).split('\n').forEach((line, i) => {
    if (/(message|fix):\s*['"`](Error|Failed|Could not|Unable|Cannot|Invalid)\b/.test(line)) problems.push(`${rel(file)}:${i + 1}: English user-facing message`);
  });
}
if (process.argv[1] && path.basename(process.argv[1]) === 'check-language.mjs') {
  process.exitCode = finish('VAL-11', 'PT-BR language rules', problems);
}
