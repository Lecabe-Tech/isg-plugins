---
name: configure
description: Verifica se o ambiente está pronto para o plugin ISG Model Alignment e oferece ajustes seguros
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

Execute estas instruções somente porque o usuário digitou `/isg-model-alignment:configure`. Nunca as execute por conta própria.
Argumentos que o usuário informou: $ARGUMENTS
Se os argumentos contiverem `--check`, nunca altere nada: apenas mostre o resultado.

## 1. Descobrir o ambiente

- Se você **tem uma ferramenta para executar comandos de terminal** (Claude Code no terminal, na aba Código do app Desktop ou no Claude Code na web), siga a parte **2. Com terminal**.
- Se você **não tem** essa ferramenta (chat do claude.ai, chat do app Desktop ou Cowork), siga a parte **3. Sem terminal**.
- Em caso de dúvida, siga a parte 3. Nunca diga que executou ou verificou algo que você não executou.

## 2. Com terminal

1. Rode exatamente este comando (mantenha as aspas) e leia o resultado JSON:

   `node "${CLAUDE_PLUGIN_ROOT}/scripts/configure.mjs" --check --json`

   - Se aparecer "node: comando não encontrado" ou algo parecido, explique em PT-BR que o Node.js LTS (versão 20 ou mais) precisa estar instalado (https://nodejs.org) e pare.
2. Mostre ao usuário, em PT-BR, o campo `message` e a lista `checks` como uma checklist simples (feito / falhou / aviso / pulado). Para cada item que falhou ou deu aviso, mostre o campo `fix` ("Como resolver").
3. Se `data.pendingChanges` tiver itens e o usuário **não** pediu `--check`:
   - Mostre cada mudança com: arquivo (`file`), chave (`key`), valor antigo (`old`), valor novo (`new`) e o motivo (`why`).
   - Pergunte: **"Deseja aplicar estas mudanças? (sim/não)"**. Se o usuário quiser só algumas, pergunte quais.
   - Somente se a resposta for "sim", rode `node "${CLAUDE_PLUGIN_ROOT}/scripts/configure.mjs" --apply --json` (ou acrescente `--only autoUpdate` / `--only preferHttps` para aplicar só uma) e mostre o `message`.
   - Se a resposta for "não", não faça nada e diga que nada foi alterado.
4. Não rode nenhum outro comando que altere o sistema. Nunca mostre senhas, tokens ou o resultado de `gh auth token`.
5. Termine dizendo, em uma frase, o que o usuário deve fazer a seguir (por exemplo reiniciar o Claude Code).

## 3. Sem terminal

Você não consegue executar comandos aqui. **Não diga que verificou, executou ou alterou nada.** Explique em PT-BR, de forma curta e amigável, e peça que o usuário confira cada item por conta própria:

1. **GitHub conectado ao claude.ai:** em Customize > Plugins, o GitHub precisa estar conectado e o app "Claude" do GitHub precisa ter acesso ao repositório `isg-plugins`.
2. **Plugin presente e ativo:** em Customize > Plugins, o plugin **ISG Model Alignment** aparece na lista e está ativado ("Disable plugin" desligado).
3. **Atualização automática:** o marketplace `isg-plugins` está com **"Sync automatically"** ligado.
4. **Sem acesso?** Peça acesso a um dos responsáveis pela organização no GitHub e aceite o convite recebido por e-mail.
5. Para a checagem completa (versões, login do GitHub, etc.), use o Claude Code (terminal ou aba Código do app Desktop) e rode `/isg-model-alignment:configure`.

Termine perguntando se o usuário precisa de ajuda com algum desses itens.
