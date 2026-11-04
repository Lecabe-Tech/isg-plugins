---
name: upgrade
description: Mostra a versão instalada do plugin ISG Model Alignment, a mais recente e o que mudou, e atualiza com confirmação
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

Execute estas instruções somente porque o usuário digitou `/isg-model-alignment:upgrade`. Nunca as execute por conta própria.
Argumentos que o usuário informou: $ARGUMENTS
Se os argumentos contiverem `--check`, nunca atualize nada: apenas informe se há atualização.

## 1. Descobrir o ambiente

- Se você **tem uma ferramenta para executar comandos de terminal** (Claude Code no terminal, na aba Código do app Desktop ou no Claude Code na web), siga a parte **2. Com terminal**.
- Se você **não tem** essa ferramenta (chat do claude.ai, chat do app Desktop ou Cowork), siga a parte **3. Sem terminal**.
- Em caso de dúvida, siga a parte 3. Nunca diga que executou ou verificou algo que você não executou.

## 2. Com terminal

1. Rode exatamente este comando (mantenha as aspas) e leia o resultado JSON:

   `node "${CLAUDE_PLUGIN_ROOT}/scripts/upgrade.mjs" --check --json`

   - Se aparecer "node: comando não encontrado" ou algo parecido, explique em PT-BR que o Node.js LTS (versão 20 ou mais) precisa estar instalado (https://nodejs.org) e pare.
2. Mostre ao usuário o campo `message`. Use o campo `code` para decidir o que fazer:
   - `UP_TO_DATE`: diga que já está na versão mais recente e pare.
   - `UPDATE_AVAILABLE`: mostre a versão instalada, a mais recente e o que mudou (`data.changelog`).
     - Se `data.breaking` for verdadeiro, mostre **primeiro** `data.breakingText` e peça confirmação explícita: **"Esta atualização tem mudanças que quebram a compatibilidade. Deseja continuar? (sim/não)"**.
     - Caso contrário pergunte: **"Deseja atualizar agora? (sim/não)"**.
     - Se o usuário pediu `--check`, não pergunte nada e pare.
     - Somente se a resposta for "sim", rode `node "${CLAUDE_PLUGIN_ROOT}/scripts/upgrade.mjs" --apply --json`, mostre o `message` e lembre o usuário de reiniciar o Claude Code ou rodar `/reload-plugins`.
   - `MANAGED_BY_ACCOUNT`: o plugin vem da conta do claude.ai. **Não rode nenhum comando de atualização.** Explique o que o `message` diz e mostre `data.changelog` se existir.
   - `NEWER_THAN_STABLE`: explique que a versão instalada é mais nova que a publicada e que nada será alterado.
   - `NO_ACCESS`, `OFFLINE`, `UPDATE_FAILED`, `NOT_INSTALLED`, `CLAUDE_CLI_NOT_FOUND`: explique o problema com as palavras do `message` e diga que a versão instalada não mudou.
3. Use somente o script acima. Não edite arquivos de plugins nem de configuração por conta própria. Nunca mostre senhas ou tokens.

## 3. Sem terminal

Você não consegue executar comandos aqui. **Não diga que verificou, executou ou atualizou nada e não afirme qual é a versão instalada se você não consegue ver.** Explique em PT-BR:

1. Neste ambiente o plugin vem da sua conta do claude.ai, então a atualização acontece lá.
2. Abra **Customize > Plugins**, escolha o marketplace `isg-plugins` e use **"Check for updates"** (ou deixe **"Sync automatically"** ligado).
3. A versão aparece na página do plugin **ISG Model Alignment**. O histórico de mudanças está no arquivo `CHANGELOG.md` do plugin.
4. Se você também usa o Claude Code, reinicie-o depois da atualização (ou rode `/reload-plugins`) e use `/isg-model-alignment:upgrade` lá para ver a versão exata e o que mudou.
