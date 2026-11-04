#!/usr/bin/env node
// /isg-model-alignment:configure  (SPEC-001 REQ-CMD-01..06, 4.7)
//   node configure.mjs --check --json      read-only checklist (default)
//   node configure.mjs --apply --json      apply the offered changes (only after the user said "sim")
//   node configure.mjs --apply --only autoUpdate,preferHttps
// All messages for people are PT-BR; ids/codes/flags are English (REQ-LNG-02).

import { MARKETPLACE_NAME, MIN_CLAUDE_VERSION, MIN_NODE_MAJOR, PLUGIN_NAME, REPO_SLUG } from './lib/constants.mjs';
import { emit, parseArgs, unexpected, usageError } from './lib/io.mjs';
import { checkRepoAccess, listMarketplaces, listPlugins, marketplaceRef } from './lib/repo.mjs';
import { redact, resolveTool, runClaude, runGh, runGit } from './lib/run.mjs';
import { compare, extract } from './lib/semver.mjs';
import { detectRoute, detectSurface } from './lib/surface.mjs';
import { editSettings, pluginsRoot, readJsonFile, readSettings, settingsPath } from './lib/settings.mjs';
import path from 'node:path';

const COMMAND = 'configure';
const check = (id, title, status, message, fix) => ({ id, title, status, message, ...(fix ? { fix } : {}) });

/** Changes that this command may OFFER on R2 only (REQ-CMD-05). Nothing else is ever edited. */
function pendingChanges(settings) {
  const changes = [];
  const entry = settings?.extraKnownMarketplaces?.[MARKETPLACE_NAME];
  if (entry && entry.autoUpdate !== true) {
    changes.push({
      id: 'autoUpdate',
      file: settingsPath(),
      key: `extraKnownMarketplaces.${MARKETPLACE_NAME}.autoUpdate`,
      old: entry.autoUpdate ?? null,
      new: true,
      why: 'Atualização automática em segundo plano do marketplace.',
    });
  }
  if (settings?.env?.CLAUDE_CODE_PLUGIN_PREFER_HTTPS !== '1' && process.env.CLAUDE_CODE_PLUGIN_PREFER_HTTPS !== '1') {
    changes.push({
      id: 'preferHttps',
      file: settingsPath(),
      key: 'env.CLAUDE_CODE_PLUGIN_PREFER_HTTPS',
      old: settings?.env?.CLAUDE_CODE_PLUGIN_PREFER_HTTPS ?? null,
      new: '1',
      why: 'Usa HTTPS (e não SSH) para baixar o plugin; necessário em máquinas sem chave SSH do GitHub.',
    });
  }
  return changes;
}

function runChecks() {
  const checks = [];
  const env = process.env;
  const { surface } = detectSurface(env);
  const settings = readSettings(env);

  // C-02 Node.js
  const nodeMajor = Number(process.versions.node.split('.')[0]);
  checks.push(
    nodeMajor >= MIN_NODE_MAJOR
      ? check('C-02', 'Node.js', 'ok', `Versão ${process.versions.node}.`)
      : check('C-02', 'Node.js', 'fail', `Versão ${process.versions.node}; é preciso ${MIN_NODE_MAJOR} ou mais.`, 'Instale o Node.js LTS em https://nodejs.org e abra uma nova sessão.'),
  );

  // C-03 Claude Code (CLI found + version)
  let claudeOk = false;
  const tool = resolveTool('claude', env);
  if (!tool) {
    checks.push(check('C-03', 'Claude Code', 'fail', 'Não encontrei o programa "claude" neste ambiente (CLAUDE_CLI_NOT_FOUND).', 'Atualize o Claude Code ou abra um terminal em que o comando "claude" funcione.'));
  } else {
    const v = runClaude(['--version']);
    const ver = extract(v.stdout);
    if (!ver) checks.push(check('C-03', 'Claude Code', 'warn', 'Não consegui ler a versão do Claude Code.', 'Execute "claude --version" e confira se aparece algo como 2.1.317.'));
    else if (compare(ver, MIN_CLAUDE_VERSION) === -1) checks.push(check('C-03', 'Claude Code', 'fail', `Versão ${ver}; é preciso ${MIN_CLAUDE_VERSION} ou mais.`, 'Atualize o Claude Code.'));
    else {
      claudeOk = true;
      checks.push(check('C-03', 'Claude Code', 'ok', `Versão ${ver}.`));
    }
  }

  // Plugin list → route
  let route = { route: 'NONE', synced: null, market: null, entry: null };
  if (claudeOk || tool) {
    const l = listPlugins();
    if (l.ok) route = detectRoute(l.list, surface);
  }
  const r = route.route;

  // C-01 surface and route (informational)
  checks.unshift(check('C-01', 'Ambiente', 'ok', `Superfície ${surface}, rota ${r === 'NONE' ? 'não identificada' : r}.`));

  const isR2 = r === 'R2' || r === 'R4' || r === 'R1+R2';
  const isSynced = r === 'R1' || r === 'R1+R2';

  // C-04 / C-05 / C-06 / C-07 / C-10 / C-11: only for routes that use git on this machine (R2, R4)
  const gitRoute = isR2;
  const skipRoute = (id, title) => check(id, title, 'skip', 'Não se aplica a esta rota (plugin vindo da conta do claude.ai).');

  if (r === 'R2') {
    const gh = runGh(['auth', 'status']);
    if (gh.notFound) checks.push(check('C-04', 'Login no GitHub (gh)', 'fail', 'O programa "gh" (GitHub CLI) não está instalado.', 'Instale o GitHub CLI (https://cli.github.com), depois rode "gh auth login" e "gh auth setup-git".'));
    else if (!gh.ok) checks.push(check('C-04', 'Login no GitHub (gh)', 'fail', 'Você não está logado no GitHub.', 'Rode "gh auth login" (GitHub.com, HTTPS) e depois "gh auth setup-git".'));
    else checks.push(check('C-04', 'Login no GitHub (gh)', 'ok', 'Logado no GitHub.'));
  } else if (r === 'R4') checks.push(check('C-04', 'Login no GitHub (gh)', 'skip', 'Na nuvem o acesso ao GitHub é feito pelo proxy da sessão.'));
  else checks.push(skipRoute('C-04', 'Login no GitHub (gh)'));

  if (r === 'R2') {
    const h = runGit(['config', '--get-all', 'credential.helper']);
    const h2 = runGit(['config', '--get-all', 'credential.https://github.com.helper']);
    const has = (h.ok && h.stdout.trim()) || (h2.ok && h2.stdout.trim());
    checks.push(has ? check('C-05', 'Credencial do Git', 'ok', 'Há um gerenciador de credenciais configurado.') : check('C-05', 'Credencial do Git', 'fail', 'Nenhum gerenciador de credenciais do Git configurado; as atualizações em segundo plano vão falhar.', 'Rode "gh auth setup-git".'));
  } else checks.push(skipRoute('C-05', 'Credencial do Git'));

  if (gitRoute) {
    const a = checkRepoAccess();
    if (a.status === 'ok') checks.push(check('C-06', 'Acesso ao repositório', 'ok', `Consigo ler ${REPO_SLUG} sem pedir senha.`));
    else if (a.status === 'skip') checks.push(check('C-06', 'Acesso ao repositório', 'skip', 'O nome da organização ainda não foi definido neste plugin (versão de desenvolvimento).'));
    else {
      const why = { NO_ACCESS: 'Sem acesso ao repositório.', OFFLINE: 'Sem conexão com o GitHub.', GIT_NOT_FOUND: 'O programa "git" não está instalado.', NO_STABLE_BRANCH: 'O repositório não tem a branch "stable".', UNKNOWN: 'Não consegui ler o repositório.' }[a.reason] ?? 'Falha ao ler o repositório.';
      const fix = { NO_ACCESS: 'Peça acesso a um dos responsáveis da organização no GitHub e aceite o convite recebido por e-mail.', OFFLINE: 'Verifique a internet e tente de novo.', GIT_NOT_FOUND: 'Instale o Git (https://git-scm.com).', NO_STABLE_BRANCH: 'Avise a equipe responsável pelo plugin.', UNKNOWN: 'Rode "gh auth status" e confira o login.' }[a.reason];
      checks.push(check('C-06', 'Acesso ao repositório', 'fail', why, fix));
    }
  } else checks.push(skipRoute('C-06', 'Acesso ao repositório'));

  if (gitRoute) {
    const m = listMarketplaces();
    const entry = m.list.find((e) => e.name === MARKETPLACE_NAME);
    if (!entry) checks.push(check('C-07', 'Marketplace na branch stable', 'fail', `O marketplace ${MARKETPLACE_NAME} não está registrado.`, `Rode "claude plugin marketplace add ${REPO_SLUG}#stable".`));
    else {
      const ref = marketplaceRef(entry);
      if (ref === 'stable') checks.push(check('C-07', 'Marketplace na branch stable', 'ok', 'Registrado e seguindo a branch stable.'));
      else if (ref === null) checks.push(check('C-07', 'Marketplace na branch stable', 'warn', 'Registrado, mas não consegui confirmar a branch.', `Se necessário, remova e adicione de novo: "claude plugin marketplace add ${REPO_SLUG}#stable".`));
      else checks.push(check('C-07', 'Marketplace na branch stable', 'fail', `Registrado seguindo "${ref}" em vez de stable.`, `Remova e adicione de novo: "claude plugin marketplace add ${REPO_SLUG}#stable".`));
    }
  } else checks.push(skipRoute('C-07', 'Marketplace na branch stable'));

  // C-08 plugin installed and enabled
  if (!route.entry) checks.push(check('C-08', 'Plugin instalado', 'fail', 'O plugin não aparece na lista de plugins instalados.', 'Siga o guia de instalação (docs/INSTALL.pt-BR.md).'));
  else if (route.entry.enabled === false) checks.push(check('C-08', 'Plugin instalado', 'fail', 'O plugin está instalado, mas desativado.', `Rode "claude plugin enable ${route.entry.id}".`));
  else checks.push(check('C-08', 'Plugin instalado', 'ok', `${route.entry.id} versão ${route.entry.version ?? '?'} ativo.`));

  // C-09 optional user_name
  const pcfg = settings?.pluginConfigs;
  const userName = route.entry ? pcfg?.[route.entry.id]?.options?.user_name : undefined;
  checks.push(userName ? check('C-09', 'Seu nome (opcional)', 'ok', 'Definido.') : check('C-09', 'Seu nome (opcional)', 'warn', 'Não definido; o plugin vai perguntar quando precisar.', 'Rode /plugin, abra ISG Model Alignment e escolha "Configure options".'));

  // C-10 HTTPS preference
  if (r === 'R2') {
    const on = env.CLAUDE_CODE_PLUGIN_PREFER_HTTPS === '1' || settings?.env?.CLAUDE_CODE_PLUGIN_PREFER_HTTPS === '1';
    checks.push(on ? check('C-10', 'Preferir HTTPS', 'ok', 'Ativado.') : check('C-10', 'Preferir HTTPS', 'warn', 'Desativado; sem chave SSH do GitHub, instalar e atualizar dentro da sessão pode falhar.', 'Posso ativar para você (mostro a mudança antes e peço confirmação).'));
  } else checks.push(skipRoute('C-10', 'Preferir HTTPS'));

  // C-11 auto-update
  if (r === 'R2') {
    const known = readJsonFile(path.join(pluginsRoot(env), 'known_marketplaces.json'));
    const on = settings?.extraKnownMarketplaces?.[MARKETPLACE_NAME]?.autoUpdate === true || known?.[MARKETPLACE_NAME]?.autoUpdate === true;
    checks.push(on ? check('C-11', 'Atualização automática', 'ok', 'Ligada.') : check('C-11', 'Atualização automática', 'warn', 'Desligada; use /isg-model-alignment:upgrade para atualizar.', 'Posso ligar para você (mostro a mudança antes e peço confirmação), ou em /plugin > Marketplaces > Enable auto-update.'));
  } else if (r === 'R1' || r === 'R1+R2') {
    checks.push(check('C-11', 'Atualização automática', 'skip', 'Plugin vindo da conta do claude.ai: mantenha "Sync automatically" ligado em Customize > Plugins.'));
  } else checks.push(skipRoute('C-11', 'Atualização automática'));

  // C-12 one route only
  if (r === 'R1+R2') checks.push(check('C-12', 'Uma rota só', 'fail', 'O plugin está instalado pela conta do claude.ai (@synced) e também por este computador (@isg-plugins); as versões podem divergir.', `Desative uma das cópias, por exemplo: "claude plugin disable ${PLUGIN_NAME}@synced".`));
  else checks.push(check('C-12', 'Uma rota só', r === 'NONE' ? 'skip' : 'ok', r === 'NONE' ? 'Sem plugin para comparar.' : 'Apenas uma cópia ativa.'));

  checks.sort((a, b) => a.id.localeCompare(b.id));
  return { checks, surface, route: r, changes: r === 'R2' ? pendingChanges(settings) : [] };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.unknown.length) return usageError(COMMAND, args.json, `Opção desconhecida: ${args.unknown[0]}. Use --check, --apply, --only e --json.`);

  const { checks, surface, route, changes } = runChecks();
  const failed = checks.filter((c) => c.status === 'fail');
  const warned = checks.filter((c) => c.status === 'warn');
  const base = { command: COMMAND, mode: args.mode, surface, route, checks };

  if (args.mode === 'check') {
    const msg = failed.length
      ? `${failed.length} verificação(ões) falharam. Veja como resolver abaixo.`
      : warned.length
        ? 'Tudo certo, com alguns avisos.'
        : 'Tudo certo: o ambiente está pronto.';
    return emit({ ...base, ok: failed.length === 0, code: failed.length ? 'CHECKS_FAILED' : 'CHECKS_PASSED', message: msg, data: { pendingChanges: changes } }, { json: args.json });
  }

  // --apply
  if (route !== 'R2') {
    return emit({ ...base, ok: true, code: 'NOTHING_TO_APPLY', message: 'Nada para alterar nesta rota: os ajustes automáticos só existem para quem instalou pelo Claude Code neste computador (rota R2).', data: { pendingChanges: [] } }, { json: args.json });
  }
  const wanted = args.only ? changes.filter((c) => args.only.includes(c.id)) : changes;
  if (wanted.length === 0) {
    return emit({ ...base, ok: true, code: 'NOTHING_TO_APPLY', message: 'Nada para alterar: tudo já está como esperado.', data: { pendingChanges: [] } }, { json: args.json });
  }
  try {
    const res = editSettings((draft) => {
      for (const c of wanted) {
        if (c.id === 'autoUpdate' && draft.extraKnownMarketplaces?.[MARKETPLACE_NAME]) draft.extraKnownMarketplaces[MARKETPLACE_NAME].autoUpdate = true;
        if (c.id === 'preferHttps') {
          draft.env = { ...(draft.env ?? {}), CLAUDE_CODE_PLUGIN_PREFER_HTTPS: '1' };
        }
      }
    });
    return emit(
      { ...base, ok: true, code: 'APPLIED', message: res.changed ? `Pronto. Alterei ${wanted.length} configuração(ões). Reinicie o Claude Code para valer. Cópia de segurança: ${res.backup ?? '(arquivo novo)'}.` : 'Nada precisou mudar.', data: { applied: wanted.map((c) => c.id), file: res.file, backup: res.backup } },
      { json: args.json },
    );
  } catch (err) {
    return emit({ ...base, ok: false, code: 'APPLY_FAILED', message: redact(String(err.message)), data: {} }, { json: args.json });
  }
}

try {
  process.exitCode = main();
} catch (err) {
  process.exitCode = unexpected(COMMAND, process.argv.includes('--json'), err);
}
