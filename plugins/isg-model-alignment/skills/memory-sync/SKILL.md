---
name: memory-sync
description: Força a sincronização da memória local com o Notion e mostra o que mudou (Claude Code)
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

Execute estas instruções somente porque o usuário digitou `/isg-model-alignment:memory-sync`.
Argumentos informados: $ARGUMENTS (um código de assunto, ou vazio para todos os assuntos ativos)

Siga o arquivo **`memory-protocol.md`** desta pasta (seções 0 a 3, 7 e 9).

1. **Onde você está:**
   - Se você **não** consegue gravar arquivos neste computador (chat do claude.ai, chat do app Desktop, Cowork), explique que aqui **não existe cópia local**: a memória é lida direto do Notion a cada pedido, então não há o que sincronizar. Pare.
2. **Conexão:** protocolo, seção 2. Sem Notion, diga quando foi a última sincronização (de `index.json`) e que a cópia continua sendo usada; pare.
3. Para cada assunto pedido (ou cada assunto **Ativo** em **Assuntos** ao qual você tem acesso):
   1. Guarde a lista atual de IDs e status de `${CLAUDE_PLUGIN_DATA}/memory/<CÓDIGO>/memoria.md` (se existir).
   2. Faça a **sincronização completa** do protocolo, seção 3 (ignore o marcador: leia as visões e reescreva os arquivos).
   3. Compare e mostre: **novas** entradas, entradas com **status alterado** (de → para) e entradas que **saíram** da memória legível.
4. Se houver cartões em `outbox/`, ofereça enviá-los (protocolo, seção 3, passo 3).
5. Termine com uma linha por assunto: *"EQV: 128 entradas, sincronizado agora."*
