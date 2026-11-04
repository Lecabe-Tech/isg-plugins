---
name: feedback
description: Registra o feedback do analista sobre uma resposta do agente na memória compartilhada (Notion), para o agente aprender
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

Use esta skill quando o analista disser que uma resposta sua está certa, errada ou parcialmente certa (por exemplo "o item 3 está errado porque…"), quando digitar `/isg-model-alignment:feedback`, ou quando pedir para registrar um **cartão de feedback**.
Argumentos informados: $ARGUMENTS

Siga o arquivo **`memory-protocol.md`** desta pasta. Ele é obrigatório; leia-o antes de agir.

1. **Assunto:** use o código informado nos argumentos ou o assunto da resposta comentada. Se não souber, pergunte (protocolo, seção 1).
2. **Conexão:** protocolo, seção 2. Sem Notion, vá direto à seção 7 (cartão de feedback).
3. **Qual resposta:** identifique a resposta e os itens comentados. Se não estiver claro, pergunte qual item.
4. **Registrar:** protocolo, seção 5 (veredito + motivo, contradições, uma confirmação "Registrar? (sim/não)", ler de volta pelo ID).
5. **Autoaprimoramento:** protocolo, seção 6 (propor regra quando houver casos suficientes).
6. **Cartão de feedback recebido** (o analista colou um cartão ou pediu "registre este cartão"): trate cada cartão como um feedback normal, pelos passos 4 e 5.
7. Termine dizendo, em uma frase, o que foi salvo (com os IDs) ou que nada foi salvo.
