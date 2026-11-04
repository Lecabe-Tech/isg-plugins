// Argument parsing and output for the scripts (SPEC-001 4.8).
//   --check  read-only (default)      --apply  make the change (only after the user said "sim")
//   --json   one JSON object on stdout; otherwise human text (PT-BR)
// Exit codes: 0 ok / nothing to do, 1 expected failure, 2 wrong usage, 3 unexpected error.

export const EXIT = { OK: 0, FAIL: 1, USAGE: 2, UNEXPECTED: 3 };

export function parseArgs(argv, extra = {}) {
  const out = { mode: 'check', json: false, help: false, only: null, unknown: [], ...extra };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--check') out.mode = 'check';
    else if (a === '--apply') out.mode = 'apply';
    else if (a === '--json') out.json = true;
    else if (a === '--help' || a === '-h') out.help = true;
    else if (a === '--only') out.only = String(argv[++i] ?? '').split(',').filter(Boolean);
    else if (a.startsWith('--only=')) out.only = a.slice(7).split(',').filter(Boolean);
    else out.unknown.push(a);
  }
  return out;
}

const LABEL = { ok: '[OK]', fail: '[FALHOU]', warn: '[AVISO]', skip: '[PULADO]' };

export function renderChecks(checks) {
  return checks
    .map((c) => {
      const lines = [`${LABEL[c.status] ?? '[?]'} ${c.id} ${c.title}: ${c.message}`];
      if (c.fix && (c.status === 'fail' || c.status === 'warn')) lines.push(`        Como resolver: ${c.fix}`);
      return lines.join('\n');
    })
    .join('\n');
}

/** Prints the result and returns the exit code to use. */
export function emit(result, { json }) {
  const full = {
    ok: result.ok,
    command: result.command,
    mode: result.mode,
    surface: result.surface ?? null,
    route: result.route ?? null,
    code: result.code,
    message: result.message,
    data: result.data ?? {},
    checks: result.checks ?? [],
  };
  if (json) {
    process.stdout.write(`${JSON.stringify(full)}\n`);
  } else {
    const parts = [full.message];
    if (full.checks.length) parts.push('', renderChecks(full.checks));
    if (result.extraText) parts.push('', result.extraText);
    process.stdout.write(`${parts.join('\n')}\n`);
  }
  return result.exit ?? (result.ok ? EXIT.OK : EXIT.FAIL);
}

export function usageError(command, json, text) {
  const code = emit({ ok: false, command, mode: 'check', code: 'USAGE', message: text, exit: EXIT.USAGE }, { json });
  return code;
}

export function unexpected(command, json, err) {
  const msg = `Erro inesperado: ${String(err?.message ?? err).split('\n')[0]}. Tente de novo; se continuar, avise a equipe responsável pelo plugin.`;
  return emit({ ok: false, command, mode: 'check', code: 'UNEXPECTED_ERROR', message: msg, exit: EXIT.UNEXPECTED }, { json });
}
