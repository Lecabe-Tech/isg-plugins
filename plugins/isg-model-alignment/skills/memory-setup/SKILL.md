---
name: memory-setup
description: Confere se a estrutura da memória do agente existe no Notion e, com sua confirmação, cria o que faltar
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

Execute estas instruções somente porque o usuário digitou `/isg-model-alignment:memory-setup`. Esta skill é para quem **administra** a memória (revisores ou responsáveis pelo Notion).
Argumentos informados: $ARGUMENTS (um código de assunto para criar ou conferir, por exemplo `EQV`; vazio = conferir tudo)
Pasta de dados configurada: `${user_config.data_folder}` (se estiver vazia ou aparecer literalmente assim, use a pasta padrão do protocolo, seção 3).

Siga o arquivo **`memory-protocol.md`** desta pasta (seções 0, 2 e 9) e use **`notion-schema.json`** desta pasta como a estrutura esperada.

1. **Conexão:** protocolo, seções 2 e 7. Sem Notion, explique como conectar e pare (montar a estrutura só é possível com a conexão).
2. **Conferir** (somente leitura) e mostrar uma checklist:
   - o espaço de equipe **ISG — Agente** existe e está acessível;
   - o banco **Assuntos** existe com todas as propriedades do esquema, com os nomes e tipos exatos;
   - para cada assunto pedido: a página do assunto, os bancos **"Memória — CÓDIGO"** e **"Registro — CÓDIGO"** com as propriedades do esquema, as visões **"Legível — CÓDIGO"** (filtro: Status em Ativo, Aprovado, Auto-aprovado, Em observação) e **"Em conflito — CÓDIGO"**, o formulário **"Enviar feedback — CÓDIGO"**, e a linha do assunto em **Assuntos** com **Base de memória** e **Base de registro** preenchidas;
   - qualquer diferença de nome ou tipo de propriedade (isso quebraria o agente).
3. **Criar o que falta** (só com confirmação):
   - Mostre exatamente o que será criado (banco, propriedades, visões, linha em Assuntos) e pergunte **"Criar agora? (sim/não)"**.
   - Com "sim", crie apenas o que falta. **Nunca** altere, renomeie ou apague bancos, propriedades ou entradas que já existem; se algo existe com nome ou tipo diferente, só **relate**.
   - Para o primeiro assunto use os valores de `firstSubject` do esquema (Código `EQV`). Para o assunto de correções de imagens (SIP) use os valores de `imageSubject` (Código `IMG`); nele as entradas são do tipo `Interpretação` e usam **Hash da imagem** e **Markdown corrigido**. Deixe **Revisores** vazio e peça ao administrador para preencher no Notion.
   - Leia de volta o que foi criado e confirme.
4. **O que só pode ser feito à mão no Notion** (diga isso no final, em uma lista curta):
   - preencher **Revisores** do assunto;
   - restringir o acesso da página do assunto às pessoas desse assunto;
   - criar as automações de e-mail e de prazo (guia `docs/notion/AUTOMATIONS.md` do repositório): e-mail aos revisores quando entrar uma entrada nova; todo dia, passar para **Auto-aprovado** as regras **Pendente** com **Prazo de revisão** vencido; e-mail quando algo ficar **Em conflito**.
