---
name: memory
description: Consulta o que a memória compartilhada do agente sabe sobre um termo, além de pendências e conflitos (somente leitura)
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

Execute estas instruções somente porque o usuário digitou `/isg-model-alignment:memory`. Esta skill **só lê**: nunca grava nada.
Argumentos informados: $ARGUMENTS
Pasta de dados configurada: `${user_config.data_folder}` (se estiver vazia ou aparecer literalmente assim, use a pasta padrão do protocolo, seção 3).

Siga o arquivo **`memory-protocol.md`** desta pasta (seções 0 a 4, 7 e 9). **Sem conexão com o Notion:** seção 7 (mostre a cópia local, se houver, com a data; senão diga que não há memória disponível agora).

1. **Assunto:** protocolo, seção 1 (código nos argumentos ou pergunte).
2. **Conexão e memória:** protocolo, seções 2 e 3. Diga de onde veio a informação: Notion agora, cópia local sincronizada em <data e hora>, ou "sem memória".
3. Conforme o pedido do analista:
   - **Um termo** (por exemplo `EQV "Projeto de Vida"`): liste as entradas cujo **Termo externo**, **Componente ISG** ou **Enunciado** combinam, com **ID**, **Tipo**, **Status**, escopo (**UF / Órgão**, **Documento**, **Ano**), **Enunciado** e o motivo. Diga em uma frase o que a memória concluiria para esse termo e com qual confiança.
   - **"pendentes":** regras com **Status** `Pendente`, com **Prazo de revisão** e **Revisores**; marque as que já passaram do prazo ("conta como Auto-aprovado").
   - **"conflitos":** pares **Em conflito**, com os dois lados e quem registrou cada um.
   - **"resumo":** quantas entradas por **Tipo** e **Status**, e quando foi a última sincronização.
4. Não analise documentos nem registre feedback aqui. Se o analista quiser corrigir algo, sugira `/isg-model-alignment:feedback`.
