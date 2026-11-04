// Locations of Claude Code files and the ONLY place where a settings file is edited (REQ-CMD-04, 05).
// This plugin never writes under the plugins root or ${CLAUDE_PLUGIN_ROOT} (P-08, VAL-07).

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { parseJson } from './run.mjs';

export function configHome(env = process.env) {
  return env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
}

export function settingsPath(env = process.env) {
  return path.join(configHome(env), 'settings.json');
}

/** Folder with known_marketplaces.json, installed_plugins.json and cache/ (read-only for us). */
export function pluginsRoot(env = process.env) {
  return env.CLAUDE_CODE_PLUGIN_CACHE_DIR || path.join(configHome(env), 'plugins');
}

/** Reads a JSON file. Returns null when missing or invalid. */
export function readJsonFile(file) {
  try {
    return parseJson(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

export function readSettings(env = process.env) {
  return readJsonFile(settingsPath(env)) ?? {};
}

function clone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Applies `mutate(draft)` to the user settings and writes the file ONLY if something changed.
 * Always makes a backup first: settings.json.bak-<timestamp>. UTF-8 without BOM, atomic rename.
 * Returns { changed, file, backup }.
 */
export function editSettings(mutate, env = process.env) {
  const file = settingsPath(env);
  let before = {};
  let existed = false;
  if (fs.existsSync(file)) {
    existed = true;
    const parsed = readJsonFile(file);
    if (parsed === null) throw new Error('settings.json não pôde ser lido (JSON inválido); nada foi alterado.');
    before = parsed;
  }
  const draft = clone(before);
  mutate(draft);
  if (JSON.stringify(draft) === JSON.stringify(before)) return { changed: false, file, backup: null };

  let backup = null;
  if (existed) {
    const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+$/, '');
    backup = `${file}.bak-${stamp}`;
    fs.copyFileSync(file, backup);
  } else {
    fs.mkdirSync(path.dirname(file), { recursive: true });
  }
  const tmp = `${file}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, `${JSON.stringify(draft, null, 2)}\n`, { encoding: 'utf8' });
  fs.renameSync(tmp, file);
  return { changed: true, file, backup };
}
