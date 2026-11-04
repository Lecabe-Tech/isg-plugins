#!/usr/bin/env node
// /isg-model-alignment:upgrade  (SPEC-001 REQ-CMD-07..11, 4.10, 4.11)
//   node upgrade.mjs --check --json     report installed vs latest and the changelog between them (default)
//   node upgrade.mjs --apply --json     update (only after the user said "sim")
// Uses ONLY the official CLI to change anything: `claude plugin marketplace update`, `claude plugin update`.
// Never edits caches, installed_plugins.json or known_marketplaces.json (P-16).

import { MARKETPLACE_NAME, PLUGIN_ID, PLUGIN_NAME, STABLE_BRANCH } from './lib/constants.mjs';
import { breakingText, sectionsBetween } from './lib/changelog.mjs';
import { emit, parseArgs, unexpected, usageError } from './lib/io.mjs';
import { checkRepoAccess, classifyFailure, listPlugins, marketplaceInstallLocation, readLatestFromCheckout, readLatestViaGh } from './lib/repo.mjs';
import { redact, runClaude } from './lib/run.mjs';
import { compare } from './lib/semver.mjs';
import { detectRoute, detectSurface } from './lib/surface.mjs';

const COMMAND = 'upgrade';
const RELOAD = 'Para aplicar, reinicie o Claude Code ou rode /reload-plugins.';

function result(base, over) {
  return { command: COMMAND, ...base, ...over };
}

function changelogInfo(changelog, installed, latest) {
  const sections = sectionsBetween(changelog, installed, latest);
  return {
    changelog: sections.map((s) => s.text).join('\n\n'),
    breaking: sections.some((s) => s.breaking),
    breakingText: breakingText(sections),
  };
}

/** R1 / R3: the plugin comes from the claude.ai account. We never run `claude plugin update` here. */
function accountRoute(base, args, installed) {
  const latest = readLatestViaGh();
  const how = 'No claude.ai ou no app Desktop, abra Customize > Plugins, escolha o marketplace e use "Check for updates" (ou deixe "Sync automatically" ligado). Depois reinicie o Claude Code.';
  if (!latest.ok) {
    return result(base, {
      ok: true,
      code: 'MANAGED_BY_ACCOUNT',
      message: `Este plugin vem da sua conta do claude.ai (versão instalada: ${installed}). Não consegui consultar a versão mais recente (${latest.reason}); para isso é preciso estar logado no GitHub com "gh auth login". ${how}`,
      data: { installed, latest: null, updateAvailable: null, reason: latest.reason },
    });
  }
  const cmp = compare(latest.version, installed);
  const info = changelogInfo(latest.changelog, installed, latest.version);
  const head =
    cmp === 1
      ? `Há uma versão nova publicada: ${latest.version} (instalada: ${installed}).`
      : `Você está na versão mais recente publicada (${installed}).`;
  return result(base, {
    ok: true,
    code: 'MANAGED_BY_ACCOUNT',
    message: `${head} Este plugin vem da sua conta do claude.ai, então a atualização acontece por lá. ${how}`,
    data: { installed, latest: latest.version, updateAvailable: cmp === 1, ...info },
    extraText: cmp === 1 && info.changelog ? `O que mudou:\n${info.changelog}` : undefined,
  });
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.unknown.length) return usageError(COMMAND, args.json, `Opção desconhecida: ${args.unknown[0]}. Use --check, --apply e --json.`);

  const { surface } = detectSurface();
  const base = { mode: args.mode, surface, route: null };
  const out = (r) => emit(r, { json: args.json });

  // 1. What is installed?
  const l = listPlugins();
  if (l.notFound) return out(result(base, { ok: false, code: 'CLAUDE_CLI_NOT_FOUND', message: 'Não encontrei o programa "claude" neste ambiente. Atualize o Claude Code ou abra um terminal em que o comando "claude" funcione.' }));
  if (!l.ok) return out(result(base, { ok: false, code: 'LIST_FAILED', message: `Não consegui listar os plugins instalados (${l.error}).` }));
  const route = detectRoute(l.list, surface);
  base.route = route.route;
  if (!route.entry) {
    return out(result(base, { ok: false, code: 'NOT_INSTALLED', message: `O plugin ${PLUGIN_NAME} não está instalado. Siga o guia de instalação (docs/INSTALL.pt-BR.md).` }));
  }

  // 2. Account route (R1/R3): explain, never update from here (REQ-CMD-08, AC-SRF-2)
  if (route.route === 'R1') return out(accountRoute(base, args, route.synced.version ?? '?'));

  const installed = route.market?.version ?? route.entry.version ?? '?';
  const scope = route.market?.scope ?? 'user';
  const bothNote = route.route === 'R1+R2' ? ' Atenção: o plugin também está instalado pela conta do claude.ai (@synced); use uma rota só (rode /isg-model-alignment:configure).' : '';

  // 3. Refresh the catalog (always; needed to know the latest version, even with --check)
  const refresh = runClaude(['plugin', 'marketplace', 'update', MARKETPLACE_NAME], { timeoutMs: 90_000 });
  if (!refresh.ok) {
    const text = `${refresh.stderr}\n${refresh.stdout}`;
    let kind = classifyFailure(text, refresh.timedOut);
    if (kind === 'UNKNOWN') {
      const a = checkRepoAccess();
      if (a.status === 'fail' && (a.reason === 'NO_ACCESS' || a.reason === 'OFFLINE')) kind = a.reason;
    }
    const detail = redact(text).trim().split('\n').find(Boolean) ?? '';
    if (kind === 'OFFLINE') return out(result(base, { ok: false, code: 'OFFLINE', message: `Sem conexão com o GitHub. Verifique a internet e tente de novo. A versão instalada continua ${installed}.`, data: { installed } }));
    if (kind === 'NO_ACCESS') return out(result(base, { ok: false, code: 'NO_ACCESS', message: `Sem acesso ao repositório. Rode "gh auth login" e "gh auth setup-git" e, se continuar, peça acesso a um dos responsáveis no GitHub. A versão instalada continua ${installed}.`, data: { installed } }));
    return out(result(base, { ok: false, code: 'UPDATE_FAILED', message: `Não consegui atualizar a lista de versões${detail ? ` (${detail})` : ''}. A versão instalada continua ${installed}.`, data: { installed } }));
  }

  // 4. Latest version from the local marketplace checkout (read-only)
  const location = marketplaceInstallLocation();
  const latest = location ? readLatestFromCheckout(location) : null;
  if (!latest) {
    return out(result(base, { ok: false, code: 'UPDATE_FAILED', message: `Atualizei a lista de versões, mas não consegui ler a versão mais recente do marketplace ${MARKETPLACE_NAME}. A versão instalada continua ${installed}.`, data: { installed } }));
  }

  const cmp = compare(latest.version, installed);
  if (cmp === null) return out(result(base, { ok: false, code: 'UPDATE_FAILED', message: `Versão inválida (instalada: ${installed}, mais recente: ${latest.version}).`, data: { installed, latest: latest.version } }));
  if (cmp === 0) return out(result(base, { ok: true, code: 'UP_TO_DATE', message: `Você já está na versão mais recente (${installed}).${bothNote}`, data: { installed, latest: latest.version } }));
  if (cmp === -1) {
    return out(result(base, { ok: true, code: 'NEWER_THAN_STABLE', message: `A versão instalada (${installed}) é mais nova que a da branch ${STABLE_BRANCH} (${latest.version}). Nada será alterado.`, data: { installed, latest: latest.version } }));
  }

  const info = changelogInfo(latest.changelog, installed, latest.version);
  if (args.mode === 'check') {
    const brk = info.breaking ? ' ATENÇÃO: esta atualização tem mudanças que quebram a compatibilidade.' : '';
    return out(
      result(base, {
        ok: true,
        code: 'UPDATE_AVAILABLE',
        message: `Há uma nova versão disponível: ${latest.version} (você tem ${installed}).${brk}${bothNote}`,
        data: { installed, latest: latest.version, scope, ...info },
        extraText: [info.breaking ? `Quebra de compatibilidade:\n${info.breakingText}` : '', info.changelog ? `O que mudou:\n${info.changelog}` : ''].filter(Boolean).join('\n\n') || undefined,
      }),
    );
  }

  // 5. --apply: update with the official CLI, then confirm
  const up = runClaude(['plugin', 'update', PLUGIN_ID, '--scope', scope], { timeoutMs: 120_000 });
  if (!up.ok) {
    const detail = redact(`${up.stderr}\n${up.stdout}`).trim().split('\n').find(Boolean) ?? '';
    return out(result(base, { ok: false, code: 'UPDATE_FAILED', message: `A atualização falhou${detail ? ` (${detail})` : ''}. A versão instalada continua ${installed}. Tente de novo mais tarde.`, data: { installed, latest: latest.version } }));
  }
  const after = listPlugins();
  const now = after.ok ? detectRoute(after.list, surface).market?.version : null;
  if (now === latest.version) {
    return out(result(base, { ok: true, code: 'UPDATED', message: `Atualizado: ${installed} → ${now}. ${RELOAD}`, data: { installed, latest: latest.version, now, scope, ...info } }));
  }
  if (now === installed) {
    return out(result(base, { ok: false, code: 'UPDATE_FAILED', message: `O comando terminou, mas a versão instalada continua ${installed}. Rode "claude plugin list" para conferir e tente de novo.`, data: { installed, latest: latest.version, now } }));
  }
  return out(result(base, { ok: true, code: 'UPDATED_UNVERIFIED', message: `O comando de atualização terminou, mas não consegui confirmar a nova versão. ${RELOAD} Depois confira com "claude plugin list".`, data: { installed, latest: latest.version, now: now ?? null } }));
}

try {
  process.exitCode = main();
} catch (err) {
  process.exitCode = unexpected(COMMAND, process.argv.includes('--json'), err);
}
