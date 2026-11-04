# Changelog

Todas as mudanças relevantes deste plugin são registradas aqui.

## [0.1.0] - 2026-11-04

### Adicionado
- Comando `/isg-model-alignment:configure`: verifica o ambiente e oferece ajustes seguros.
- Comando `/isg-model-alignment:upgrade`: mostra a versão instalada, a mais recente e as mudanças entre elas, e atualiza com confirmação.
- Funciona no Claude Code (terminal, aba Código do app Desktop e Claude Code na web), no chat do claude.ai e do app Desktop e no Cowork.
- Conexão com o Notion já incluída no plugin: basta autenticar a sua conta do Notion uma vez.
- Processamento de PDFs grandes (`/isg-model-alignment:cfp`): um programa em Python (com a biblioteca pypdf já incluída) extrai o texto, divide em chunks com as páginas de cada trecho, gera índice e relatório de qualidade e permite buscar sem gastar tokens da IA. Nenhum texto é removido; tudo é guardado por UF e ano na pasta de dados do plugin, que continua no computador depois de atualizações. Exige Python 3.11 ou mais novo.
- `/isg-model-alignment:configure` agora também confere o Python e a biblioteca de PDFs (item C-14).
- Leitura de imagens (`/isg-model-alignment:sip`, SIP): transforma qualquer imagem (figura, gráfico, tabela em imagem) em Markdown em PT-BR, com transcrição literal, conteúdo estruturado, confiança e dúvidas. O CFP agora também **extrai as imagens** dos PDFs (sem IA) e a cópia `chunks_com_imagens/` recebe as interpretações, sem alterar os trechos originais. O uso é sob demanda; o documento inteiro só roda com estimativa e confirmação. Correções dos analistas vão para a memória compartilhada (assunto `IMG`) pelo hash da imagem.
- Memória compartilhada do agente no Notion: `/isg-model-alignment:feedback` (registrar correções), `/isg-model-alignment:memory` (consultar), `/isg-model-alignment:memory-sync` (sincronizar a cópia local), `/isg-model-alignment:memory-setup` (montar a estrutura no Notion) e `/isg-model-alignment:memory-audit` (auditar).
