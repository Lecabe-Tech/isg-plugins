# Changelog

Todas as mudanças relevantes deste plugin são registradas aqui.

## [0.1.4] - 2026-11-17

### Adicionado
- **`/isg-model-alignment:analisar`**: a esteira completa da análise de Qualidade de um estado em um só pedido. O analista anexa os arquivos (ou informa a pasta ou o link do SharePoint) e pede "analisar <estado> <ano>"; o Claude prepara as entradas, lê as imagens, transcreve a matriz, avalia as orientações em lotes paralelos, cruza as frentes e entrega o resultado com a fila de revisão. Só para antes de começar se faltar entrada. Se for interrompida, continua de onde parou.
- Comando `esteira`: mostra as seis etapas da análise (feita, em andamento ou pendente) e o próximo passo.
- Comando `manifesto-montar`: monta o manifesto a partir dos arquivos enviados (documentos do estado, template e, se houver, ICE).

### Alterado
- `/isg-model-alignment:resultado-qualidade` volta a ser só por comando e passa a ser o manual técnico usado pela `analisar`.

## [0.1.3] - 2026-11-17

### Alterado
- Análise de Qualidade (`resultado-qualidade`): começa também quando o analista **pede a análise de um estado** em texto livre, sem digitar o comando, e segue um roteiro **até o resultado**. Ela só para antes de começar se faltar entrada (documento do estado, template da UF ou referencial ICE); faixas, classificações duvidosas, conflitos e homologações viram pendências na fila de revisão, sem interromper a análise.
- Referencial ICE em **local fixo**: deixe `referencial_ice` vazio no manifesto para usar o referencial configurado no plugin (pasta ou link do SharePoint, com `manifesto_ice.json` aprovado). O plugin nunca escolhe um referencial por conta própria; cópia de teste ou não aprovada é recusada. A homologação vem do `manifesto_ice.json` quando ele tem a data. Novo comando `ice-padrao`.
- Template de outro cluster: a análise para logo no início e diz quais UFs o template enviado cobre, em vez de ler tudo para depois falhar.

### Adicionado
- Matriz com **valores em faixa** (por exemplo "3 ou 4h/a"): a faixa é registrada como está, sem escolher um valor, e fica pendente com o pedido do documento oficial que a fonte cita. Os **totais impressos na fonte** são conferidos contra a soma dos componentes; um total que não fecha aponta linha faltando na transcrição.
- Imagens repetidas: a mesma figura em várias páginas é lida uma vez só, e a leitura é copiada para as repetidas.
- `unidades --pagina N`: lê pelas páginas do PDF, com as imagens delas.

## [0.1.2] - 2026-11-17

### Alterado
- Análise de Qualidade (`/isg-model-alignment:resultado-qualidade`) com **entradas fechadas**: roda só com os arquivos enviados, a pasta informada (a pasta entra com todos os arquivos dentro dela) ou o **link do SharePoint** informado. O link é lido da cópia que o OneDrive mantém no computador (biblioteca sincronizada ou atalho em "Meus arquivos") ou de uma cópia baixada pelo analista; o comando `sharepoint` mostra se a cópia existe. Outros endereços da internet são recusados e o plugin não pesquisa nem baixa documentos; se faltar um documento, a frente fica pendente e o plugin pede o arquivo.
- Tabelas de matriz em PDF: o programa remonta linhas e colunas pela posição do texto (também em páginas deitadas) e confere em que **série** está cada número. Série declarada que não bate com a tabela fica não verificada; tabela ilegível fica marcada para o analista. Novo comando `tabela-pdf` mostra a grade reconstruída. O resultado passa para a versão de conteúdo 1.1 (novo método de evidência `celula_layout_conferida`); resultados 1.0 continuam válidos.
- Imagens: os trechos em imagem saem exportados para a pasta da execução, ligados ao trecho, para a leitura de imagem ser feita na figura exata (comando `imagens`). Avisos internos da biblioteca de PDF não aparecem mais na tela.

### Adicionado
- **Fila de revisão** no resumo e no comando `revisao-fila`: as decisões do analista em ordem de importância, cada uma com o que decidir e onde está a evidência.
- Avaliação das orientações **em lotes**, que podem ser feitos em paralelo: `orientacoes-lotes` prepara o texto dos documentos, os lotes de orientações e as instruções, sem nada do preenchimento dos analistas; `orientacoes-conferir` confere um lote antes de registrar.

## [0.1.1] - 2026-11-16

### Adicionado
- Análise de Qualidade da entrega 1 (`/isg-model-alignment:resultado-qualidade`, SPEC-017), só para o Ensino Médio Integral propedêutico de 9h: a partir das quatro entradas (orientações estaduais, matriz estadual, template do cluster e referencial ICE), em PDF, Word, Excel, imagem, texto ou HTML, transcreve e classifica a matriz curricular e avalia as orientações pedagógicas e de gestão. Cada valor e cada citação são conferidos por um programa na página, célula ou parágrafo citado. Depois cruza as duas frentes e gera `resultado_qualidade.v1.json`, validado, com um resumo em português para o analista e a coordenação conferirem. Falta de prova vira pendência, nunca "Não"; totais só com a regra do template aprovada pela Qualidade; nada é gravado no Excel, no SharePoint, na base central ou no painel.

### Alterado
- Processo de Qualidade roda igual no Claude Code em terminal e na aba Código do app Desktop: a saída estruturada não depende mais de abrir outra sessão com `claude -p`. Novo comando `modelo-resposta` gera o esqueleto de cada aba; o Claude preenche e valida com `validar-resposta` até passar. A garantia continua: `agrupar`, `validar` e `preparar` revalidam tudo e o lote registra a impressão digital (SHA-256) do schema de cada aba, recusando lotes validados contra outra versão do contrato.

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
