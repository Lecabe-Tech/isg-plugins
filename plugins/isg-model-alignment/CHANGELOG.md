# Changelog

Todas as mudanças relevantes deste plugin são registradas aqui.

## [0.1.1] - 2026-11-16

### Corrigido
- Processo de Qualidade: avaliações (`SG_Avaliacoes`) sem documento confirmado (`DocumentoID` vazio) eram recusadas, embora o formato permita. Agora são aceitas; em `SG_Documentos` o identificador continua obrigatório.
- Processo de Qualidade: o pacote preparado (`preparar`) perdia a lista de fontes (arquivo e página) reunida pelo `agrupar`. Agora ela é mantida em `lote-validado.json`.
- Processo de Qualidade: os schemas de saída estruturada declaravam um padrão (JSON Schema 2020-12) que o Claude Code recusa no `claude -p --json-schema`. Agora declaram o padrão aceito, sem mudar nenhuma regra.
- Processo de Qualidade: `fontes`, `resolver` e `template` aceitavam qualquer par de letras como UF. Agora só as 27 siglas oficiais.
- Segurança: as skills de Qualidade tinham links para anexos em um servidor externo não auditado. Os links foram removidos e uma checagem impede novos endereços fora da lista permitida.

## [0.1.0] - 2026-11-16

### Adicionado
- Comando `/isg-model-alignment:configure`: verifica o ambiente e oferece ajustes seguros.
- Comando `/isg-model-alignment:upgrade`: mostra a versão instalada, a mais recente e as mudanças entre elas, e atualiza com confirmação.
- Funciona no Claude Code (terminal, aba Código do app Desktop e Claude Code na web), no chat do claude.ai e do app Desktop e no Cowork.
- Conexão com o Notion já incluída no plugin: basta autenticar a sua conta do Notion uma vez.
- Processamento de PDFs grandes (`/isg-model-alignment:cfp`): um programa em Python (com a biblioteca pypdf já incluída) extrai o texto, divide em chunks com as páginas de cada trecho, gera índice e relatório de qualidade e permite buscar sem gastar tokens da IA. Nenhum texto é removido; tudo é guardado por UF e ano na pasta de dados do plugin, que continua no computador depois de atualizações. Exige Python 3.11 ou mais novo.
- `/isg-model-alignment:configure` agora também confere o Python e a biblioteca de PDFs (item C-14).
- Leitura de imagens (`/isg-model-alignment:sip`, SIP): transforma qualquer imagem (figura, gráfico, tabela em imagem) em Markdown em PT-BR, com transcrição literal, conteúdo estruturado, confiança e dúvidas. O CFP agora também **extrai as imagens** dos PDFs (sem IA) e a cópia `chunks_com_imagens/` recebe as interpretações, sem alterar os trechos originais. O uso é sob demanda; o documento inteiro só roda com estimativa e confirmação. Correções dos analistas vão para a memória compartilhada (assunto `IMG`) pelo hash da imagem.
- Comparação com o modelo do Instituto (`/isg-model-alignment:eqv`): para um estado e um ano, compara cada orientação das abas 1.1 e 1.2 da planilha dos analistas com os documentos do estado, por significado. Propõe **Sim** ou **Não** (sempre um dos dois) com comentário no estilo dos analistas (página e citação), explicação, confiança em % e a marca **Revisar**. Um programa **confere cada citação** nas páginas dos documentos e decide o valor final. O resultado sai em arquivos separados (.xlsx e .csv); a planilha original nunca é alterada.
- Memória compartilhada do agente no Notion: `/isg-model-alignment:feedback` (registrar correções), `/isg-model-alignment:memory` (consultar), `/isg-model-alignment:memory-sync` (sincronizar a cópia local), `/isg-model-alignment:memory-setup` (montar a estrutura no Notion) e `/isg-model-alignment:memory-audit` (auditar).
- Processo de Qualidade (`/isg-model-alignment:qualidade`): coordena CFP, SIP e EQV, a análise da matriz curricular contra o referencial ICE e a montagem das cinco abas `SG_*` da base central, com uma skill por aba e saída validada por schema. O resultado é um pacote JSON e CSV **ainda não gravado**: a importação no Excel central e a aprovação continuam com a equipe de Qualidade.
- Pastas configuráveis para os documentos estaduais (`UF/Ano`), os templates de cada estado e o referencial ICE (com `manifesto_ice.json`). O comando `resolver` permite começar só com o ano e o documento orientador do ciclo.
