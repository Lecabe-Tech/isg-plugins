// Parser for CHANGELOG.md in the format of SPEC-001 section 4.6 (PT-BR, Keep a Changelog).
// Both upgrade.mjs and the CI check depend on this exact format.

import { compare, isValid } from './semver.mjs';

export const ALLOWED_SUBSECTIONS = [
  'Quebra de compatibilidade',
  'Adicionado',
  'Alterado',
  'Corrigido',
  'Removido',
  'Segurança',
];
export const BREAKING_HEADING = 'Quebra de compatibilidade';

const VERSION_HEADING = /^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})\s*$/;

/** Splits the text into version sections, newest first as written in the file. */
export function parse(text) {
  const lines = String(text ?? '').replace(/\r\n/g, '\n').split('\n');
  const sections = [];
  let current = null;
  let sub = null;
  for (const line of lines) {
    const v = VERSION_HEADING.exec(line);
    if (v) {
      current = { version: v[1], date: v[2], subsections: [], lines: [line] };
      sections.push(current);
      sub = null;
      continue;
    }
    if (!current) continue;
    current.lines.push(line);
    const s = /^### (.+?)\s*$/.exec(line);
    if (s) {
      sub = { heading: s[1], lines: [] };
      current.subsections.push(sub);
    } else if (sub) {
      sub.lines.push(line);
    }
  }
  return sections.map((s) => ({
    version: s.version,
    date: s.date,
    subsections: s.subsections,
    text: s.lines.join('\n').trimEnd(),
    breaking: s.subsections.some((x) => x.heading === BREAKING_HEADING && x.lines.join('').trim() !== ''),
  }));
}

/** Returns a list of format errors (empty when the file is valid). */
export function validate(text) {
  const errors = [];
  const raw = String(text ?? '');
  if (raw.charCodeAt(0) === 0xfeff) errors.push('O arquivo tem BOM; use UTF-8 sem BOM.');
  if (!/^# Changelog\s*$/m.test(raw)) errors.push('Falta o título "# Changelog".');
  if (/\[Unreleased\]/i.test(raw)) errors.push('Não use a seção [Unreleased] (SPEC-001 4.6).');
  const sections = parse(raw);
  if (sections.length === 0) errors.push('Nenhuma seção "## [X.Y.Z] - AAAA-MM-DD" encontrada.');
  const seen = new Set();
  for (let i = 0; i < sections.length; i++) {
    const s = sections[i];
    if (!isValid(s.version)) errors.push(`Versão inválida no título: [${s.version}].`);
    if (seen.has(s.version)) errors.push(`Versão repetida: ${s.version}.`);
    seen.add(s.version);
    if (i > 0 && compare(sections[i - 1].version, s.version) !== 1) {
      errors.push(`As versões devem estar da mais nova para a mais antiga (${sections[i - 1].version} antes de ${s.version}).`);
    }
    for (const sub of s.subsections) {
      if (!ALLOWED_SUBSECTIONS.includes(sub.heading)) {
        errors.push(`Subtítulo não permitido em ${s.version}: "${sub.heading}".`);
      }
      if (sub.lines.join('').trim() === '') errors.push(`Subtítulo vazio em ${s.version}: "${sub.heading}" (omita se não houver itens).`);
    }
  }
  return errors;
}

export function findSection(text, version) {
  return parse(text).find((s) => s.version === version) ?? null;
}

/** Sections with installed < version <= latest, newest first. */
export function sectionsBetween(text, installed, latest) {
  return parse(text).filter((s) => compare(s.version, installed) === 1 && compare(s.version, latest) !== 1);
}

/** Sections that contain a "Quebra de compatibilidade" subsection, as a single PT-BR text. */
export function breakingText(sections) {
  const parts = [];
  for (const s of sections) {
    const b = s.subsections.find((x) => x.heading === BREAKING_HEADING);
    if (b && b.lines.join('').trim() !== '') parts.push(`Versão ${s.version}:\n${b.lines.join('\n').trim()}`);
  }
  return parts.join('\n\n');
}
