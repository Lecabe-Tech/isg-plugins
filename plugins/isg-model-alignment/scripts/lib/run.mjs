// Safe child-process wrapper (SPEC-001 4.8).
// - never reads stdin, never prompts, always has a timeout (REQ-CMD-13)
// - finds the Claude CLI without assuming it is on PATH (T0 finding F1, P-42)
// - redacts anything that looks like a credential before text can be shown (REQ-ACC-05)

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { DEFAULT_TIMEOUT_MS } from './constants.mjs';

const IS_WIN = process.platform === 'win32';

/** Finds an executable on PATH. On Windows, .cmd/.bat shims are accepted too (run through cmd.exe). */
export function which(cmd, env = process.env) {
  const dirs = String(env.PATH ?? env.Path ?? '').split(path.delimiter).filter(Boolean);
  const exts = IS_WIN ? ['.exe', '.com', '.cmd', '.bat'] : [''];
  for (const dir of dirs) {
    for (const ext of exts) {
      const candidate = path.join(dir, cmd + ext);
      try {
        if (fs.statSync(candidate).isFile()) return candidate;
      } catch {
        /* keep looking */
      }
    }
  }
  return null;
}

/**
 * Resolves a tool name ("claude", "gh", "git") to something spawnable.
 * Order for claude: test stub, CLAUDE_CODE_EXECPATH, PATH.
 * ISG_TEST_<NAME>_STUB is a TEST-ONLY hook: a .mjs file run with Node in place of the tool.
 */
export function resolveTool(name, env = process.env) {
  const stub = env[`ISG_TEST_${name.toUpperCase()}_STUB`];
  if (stub) return { cmd: process.execPath, prefix: [stub], via: 'stub' };
  if (name === 'claude') {
    const p = env.CLAUDE_CODE_EXECPATH;
    if (p && fs.existsSync(p)) return { cmd: p, prefix: [], via: 'CLAUDE_CODE_EXECPATH' };
  }
  const found = which(name, env);
  return found ? { cmd: found, prefix: [], via: 'PATH' } : null;
}

const SECRET_PATTERNS = [
  /gh[pousr]_[A-Za-z0-9]{20,}/g,
  /github_pat_[A-Za-z0-9_]{20,}/g,
  /sk-ant-[A-Za-z0-9_-]{10,}/g,
  /(Bearer|token)\s+[A-Za-z0-9._~+/=-]{16,}/gi,
  /(https?:\/\/)[^/\s:@]+:[^/\s@]+@/g,
];

/** Removes credential-looking text. Always use before showing stderr/stdout of another program. */
export function redact(text) {
  let out = String(text ?? '');
  for (const re of SECRET_PATTERNS) out = out.replace(re, (m, g1) => (typeof g1 === 'string' && g1.startsWith('http') ? `${g1}***@` : '***'));
  return out;
}

function quoteForCmd(arg) {
  if (arg === '') return '""';
  if (!/[\s"&|<>^%()]/.test(arg)) return arg;
  return `"${arg.replace(/"/g, '\\"')}"`;
}

/**
 * Runs a tool. Returns { ok, status, stdout, stderr, timedOut, notFound, via }.
 * Never throws. stdin is closed. Git/gh prompts are disabled.
 */
export function run(name, args, opts = {}) {
  const baseEnv = opts.env ?? process.env;
  const tool = resolveTool(name, baseEnv);
  if (!tool) return { ok: false, status: null, stdout: '', stderr: '', timedOut: false, notFound: true, via: null };

  const env = {
    ...baseEnv,
    GIT_TERMINAL_PROMPT: '0',
    GCM_INTERACTIVE: 'never',
    GIT_ASKPASS: '',
    SSH_ASKPASS: '',
    GH_PROMPT_DISABLED: '1',
    NO_COLOR: '1',
  };
  let timeout = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const testCap = Number(baseEnv.ISG_TEST_TIMEOUT_MS); // TEST-ONLY hook (VAL-12): shortens every timeout
  if (testCap > 0) timeout = Math.min(timeout, testCap);
  const base = { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout, windowsHide: true, env, cwd: opts.cwd, maxBuffer: 10 * 1024 * 1024 };

  let r;
  if (IS_WIN && /\.(cmd|bat)$/i.test(tool.cmd)) {
    const line = [tool.cmd, ...tool.prefix, ...args].map(quoteForCmd).join(' ');
    r = spawnSync(env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', `"${line}"`], { ...base, windowsVerbatimArguments: true });
  } else {
    r = spawnSync(tool.cmd, [...tool.prefix, ...args], base);
  }
  const timedOut = r.error?.code === 'ETIMEDOUT';
  return {
    ok: r.status === 0 && !r.error,
    status: r.status,
    stdout: r.stdout ?? '',
    stderr: r.stderr ?? (r.error ? String(r.error.message) : ''),
    timedOut,
    notFound: r.error?.code === 'ENOENT',
    via: tool.via,
  };
}

export const runClaude = (args, opts) => run('claude', args, opts);
export const runGit = (args, opts) => run('git', args, opts);
export const runGh = (args, opts) => run('gh', args, opts);

/** Parses JSON output safely. Returns null when the text is not valid JSON. */
export function parseJson(text) {
  try {
    return JSON.parse(String(text).replace(/^﻿/, ''));
  } catch {
    return null;
  }
}
