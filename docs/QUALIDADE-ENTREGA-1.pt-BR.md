# Comece aqui — Qualidade, Entrega 1 (SPEC-017)

**Leitura para quem está entrando agora no projeto.** Última revisão: 16/11/2026. Este guia explica o trabalho real, as partes já construídas, a nova prioridade e como comprovar que terminamos. O plano normativo completo está em [SPEC-017](../specs/SPEC-017-jhon-quality-first-json-pipeline.md).

## Em uma frase

Queremos automatizar o **preenchimento analítico feito pelo Jhon**, sem eliminar a conferência humana: usar **quatro classes de documentos** para (A) avaliar as orientações pedagógicas e de gestão e (B) transcrever/classificar a matriz curricular **propedêutica de 9h**, cruzar informações coerentemente e devolver **JSON com provas e pendências**. Só depois vamos integrar com Thomaz/BI.

## 1. Quem faz o quê hoje (AS-IS)

1. O analista recebe/coleta as matrizes oficiais e os documentos das Secretarias; documentos podem vir de e-mail, WhatsApp, sites oficiais e arquivos diversos.
2. Escolhe dentro dos arquivos a matriz correta, vigente, **propedêutica 9h**. Um PDF pode ter diversas matrizes, inclusive técnicas.
3. Na planilha de template do cluster, preenche **componente original, classificação e aulas semanais da 1ª, 2ª e 3ª série**, além de UF/ano/tempo de aula. As fórmulas do próprio template geram resumos; não são dados a inventar.
4. Lê **vários documentos estaduais** e compara cada orientação do ICE, preenchendo **Sim/Não**, comentário, justificativa e referência.
5. A coordenação de Qualidade revisa. Depois o Thomaz transpõe/consolida os dados para outra planilha que calcula alinhamento e alimenta o painel.

Referências originais no Scripta: **NOTA-009**, **NOTA-016**, **NOTA-019**, **NOTA-029** e **NOTA-048** (esta última é parcialmente truncada; não extrapolar).

## 2. O que está pronto, o que não está

| Item | Estado verificado | Próximo trabalho |
|---|---|---|
| CFP | Extrai e indexa **PDF**, com controle de fidelidade; imagens podem exigir SIP | Aceitar entrada multiformato e garantir cobertura |
| SIP | Interpreta imagens e marca conteúdo derivado por IA | Verificar tabelas visuais/ilegíveis |
| EQV | Compara orientações por significado, usa códigos do template e citações | Cobrir todas orientações aplicáveis, múltiplos formatos, negativas somente com fontes suficientes |
| Componentes e resumos | Existem skills e schemas de base central, mas ainda não homologamos matriz completa de MG | Fechar seleção, transcrição, classificação, consolidação |
| JSON `SG_*` | Estrutura técnica e testes existem | **Não é a entrega final desta fase** |
| Notion, SharePoint, Thomaz, BI | Arquitetura e artefatos parciais; integração final não homologada | **Adiar até concluir a entrega JSON** |

**Atenção:** testes anteriores de MG/2026 cobriram parte das orientações e **não comprovam um ciclo completo**. Nenhum percentual global de automação do trabalho do Jhon foi validado.

### 2.1 Implementação da entrega 1 (marcos G0 a G5)

O motor da SPEC-017 está em `plugins/isg-model-alignment/scripts/quality/`. O analista usa a skill **`/isg-model-alignment:analisar`**, que conduz a esteira inteira:
1. entradas;
2. imagens;
3. matriz;
4. orientações;
5. cruzamento;
6. resultado e fila de revisão;
7. template preenchido (cópia do template do cluster com Sim ou Não por linha e a matriz da UF).

O comando `esteira` mostra a etapa atual. A skill `/isg-model-alignment:resultado-qualidade` é o manual técnico de cada etapa. O motor foi testado só com **dados sintéticos** (`test/quality/test_q17_*.py`).

| Marco | O que existe | Ainda não comprovado |
|---|---|---|
| G0 | Manifesto das quatro classes e schema `resultado_qualidade.v1` versionados (`schemas/`), com exemplos em `examples/quality/` | Valores reais de homologação do ICE e das regras |
| G1 | Leitura de PDF, DOCX, XLSX, PNG/JPEG, TXT/CSV e HTML com hash e localização de cada unidade; pendência explícita para imagem, fórmula sem valor, formato antigo, arquivo ausente ou bloqueado | DOC/XLS antigos dependem de conversão |
| G2 | Seleção da matriz 9h, transcrição conferida célula a célula ou por citação, `0` × vazio × não verificado, classificação pela lista do template, totais só com a regra homologada | Paridade com uma matriz real conferida pelo analista |
| G3 | Reconciliação formal dos códigos ICE × template, Sim/Não/pendente com citação conferida, importação da EQV | Reconciliação 70 × 77 pela Qualidade; ciclo real completo |
| G4 | Cruzamento tipado (oferta, carga, norma × oferta, cobertura) sem alterar as frentes | Casos reais |
| G5 | JSON validado (schema + consistência), resumo PT-BR, hash de conteúdo reproduzível, relatório de paridade | Revisão da coordenação sobre um ciclo real; execução na aba Código do Desktop |

## 3. Entradas — formulário futuro e piloto técnico usam o mesmo contrato

| Campo lógico | O que entra | Regra |
|---|---|---|
| **1. Orientações estaduais** | Um ou vários documentos pedagógicos/gestão | Não necessariamente PDF; pode ser DOCX, Excel, imagem etc. |
| **2. Matriz estadual** | Arquivo da matriz vigente ou localização exata dentro do orientador | Tem de comprovar a oferta **propedêutica 9h** |
| **3. Template** | Planilha correta da UF/ano/cluster | É a **estrutura do preenchimento**, não evidência de oferta |
| **4. Referencial ICE** | Modelo e orientações homologados | É a **régua de classificação**; precisa de versão autorizada |

O Notion poderá receber os quatro documentos (ou conjuntos de arquivos); templates/ICE podem ter padrões cadastrados, mas **os arquivos/versões usados devem constar da solicitação**. Um arquivo físico pode servir a dois campos. Primeiro demonstramos o motor com arquivos locais ou URLs legitimamente acessíveis; o formulário e disparo automático ficam para depois.

**Acesso a fontes (decisão de 17/11/2026, depois do piloto de MG):** a análise roda **somente com os arquivos enviados, a pasta informada ou o link do SharePoint informado**. O link do SharePoint é lido da cópia que o OneDrive mantém no computador (biblioteca sincronizada ou atalho em "Meus arquivos") ou de uma cópia baixada pelo analista (`copia_local`). O plugin não pesquisa na web, não baixa documentos (outro endereço da internet no manifesto é recusado com `ORIGEM_NAO_PERMITIDA`) e não avalia se a matriz ou as orientações mudaram fora do que foi enviado: decidir o que vale é trabalho humano. Se faltar um documento, a frente fica pendente e o plugin pede o arquivo. Ver [aprendizados do piloto MG 2026](APRENDIZADOS-MG-2026.pt-BR.md).

**Tipos de documento:** PDF, DOCX, XLSX, imagens JPG/PNG e arquivos textuais, com adaptadores adequados. Documentos antigos DOC/XLS e tabelas que não puderem ser lidas geram pendência/conversão controlada. **Nunca converter erro de leitura em `Não`.**

## 4. Desenho de operação da entrega 1

```text
[Quatro entradas fornecidas pelo responsável]
                    |
                    v
[Inventário + leitura + hashes + páginas/abas/células]
                    |
           +--------+--------+
           |                 |
           v                 v
[Orientações]            [Matriz 9h]
  Pedagógicas/gestão      Componentes/séries
  Semântica/evidência     Classificação/carga
  Sim/Não/pendente        Consolidação homologada
           |                 |
           +--------+--------+
                    |
                    v
    [Validação cruzada tipada]
    contradições reais / ausências de prova
                    |
                    v
    [resultado_qualidade.v1.json]  (estado interno desde a 0.1.8)
    [Notion: bases "Resultados — …" + template preenchido na solicitação]
                    |
          PARAR A ENTREGA AQUI
```

### Exemplo de validação cruzada

- Matemática tem carga horária **positiva** na matriz, e outra fonte diz que o estado **não oferece Matemática** para o mesmo ano/modelo → **inconsistência a revisar**.
- Matemática tem carga horária positiva, mas falta uma **orientação pedagógica específica** sobre ela → **não é contradição automática**. São avaliações diferentes.
- ICE recomenda um componente, mas ele não consta da matriz → registrar diferença normativa × oferta real, sem inventar aulas.
- Documento diz 4/4/5, planilha histórica diz 4/4/4 → evidenciar diferenças, verificar ano/versão/oferta e encaminhar ao analista; nunca escolher silenciosamente.

## 5. Como saber se acabamos (não trabalhar em dez frentes)

| Marco | Demonstração exigida |
|---|---|
| **G0 Contrato** | Os quatro insumos têm identidade, formato, integridade e versão; JSON schema da entrega está definido |
| **G1 Extract** | Fontes em PDF/Word/Excel/imagem passam por leitores adequados e mantêm localização de cada valor |
| **G2 Matriz** | O plugin identifica corretamente a 9h propedêutica, preserva **todas as disciplinas e as aulas por série**, classifica com evidência; totais só com regras homologadas |
| **G3 Orientações** | Compara códigos pedagógicos **e** de gestão da versão aprovada, inclusive documentos complementares; pendências explícitas |
| **G4 Cruzamento** | Detecta contradições factuais sem confundir oferta com orientações normativas |
| **G5 JSON + revisão** | Gera resultado completo ou honestamente parcial, passa validação, registra fonte para cada conclusão e permite comparação com o preenchimento do Jhon |

A equipe deverá selecionar **uma matriz oficial e um conjunto completo de orientações do mesmo ciclo propedêutico 9h** e um **referencial ICE autorizado** para realizar o piloto. A diferença histórica **70 versus 77 orientações** ainda precisa de reconciliação pela Qualidade. A fórmula de **40 semanas** vista em planilhas históricas não é automaticamente uma regra homologada.

## 6. O que um desenvolvedor deve abrir primeiro

| Ordem | Local | Para quê |
|---|---|---|
| 1 | Este documento + [SPEC-017](../specs/SPEC-017-jhon-quality-first-json-pipeline.md) | Entender resultado e limites atuais |
| 2 | `specs/SPEC-001-...` | Superfícies e distribuição Claude; cuidado com Desktop/chat vs execução local |
| 3 | `specs/SPEC-003-...` e `SPEC-004-...` | Reaproveitar CFP e SIP |
| 4 | `specs/SPEC-005-...` e `skills/eqv/` | Reaproveitar regras de análise semântica |
| 5 | `specs/SPEC-006-...` + `scripts/quality/` | Entender validação existente **sem ficar preso ao `SG_*`** |
| 6 | Scripta **NOTA-016**, **NOTA-029**, **GUIA-032** | Ver campos do Jhon e critérios humanos de revisão |
| 7 | Scripta **ADR-001** e **ESP-012** | Acesso multiformato e proposta futura do formulário |
| 8 | PR #6 / SPEC-007 | Contexto de **paridade e integração downstream**; não é o objetivo desta entrega |

Rota de teste do mantenedor: `npm run check`. **Este PR é apenas documentação** e não implementa os marcos.

## 7. Regra de priorização

Enquanto não existir um ciclo 9h **avaliado, confrontado com preenchimento humano e devolvido em JSON com evidências**, não iniciar desenvolvimento de gravação da base intermediária, Power Query, aprovação no Excel, BI ou serviço de gatilho automático do Notion. Preservar o que já existe; a proibição é de **desviar o foco** agora.

**Próximo passo real:** obter as quatro entradas válidas do piloto, homologar a versão ICE e fechar os códigos de orientação aplicáveis. Depois concluir **Matriz (G2)** e **Orientações (G3)** como entregas demonstráveis, antes de juntar os resultados.

## 8. Análise independente, revisão enxuta e entrega no Notion (0.1.7)

| Tema | Regra |
|---|---|
| Fontes | Documentos do estado = evidência. Referencial ICE = critério. Template = estrutura (códigos, textos, classificações, layout, fórmulas). As respostas, observações e valores que já estão no template são **histórico**, nunca evidência: o `referencias.json` guarda só quantas respostas havia, e `buscar`/`unidades` recusam o template. A paridade continua opcional e só depois do resultado gravado. |
| Excel | `template-preencher` limpa todo o bloco da UF e do ano (inclusive colunas de observação ocultas) e escreve só o resultado novo. Campo sem resultado (hora-aula, vigência, orientação sem decisão) sai vazio e amarelo. Anos anteriores, outras UFs e fórmulas ficam. Sem o bloco UF/ano ou sem o layout da matriz, a cópia é gravada só para conferência e marcada `entrega_valida: false` (`ENTREGA_BLOQUEADA`). |
| Confiança | Limiar técnico de **70%** só no fluxo de Qualidade (`scripts/quality/quality_policy.py`); a EQV legada continua com 85%. Evidência só indireta, só de imagem ou página com aviso e "Não" com imagens pendentes ficam em revisão mesmo acima de 70%. Sem citação estadual válida, pendente. Na matriz, imagem, faixa e divergência nunca viram "verificado". |
| Reanálise | Uma segunda passagem por versão das entradas (`reanalise-planejar`, `reanalise-registrar`, `reanalise-matriz`, `reanalise-documento`, `reanalise-concluir`), registrada em `reanalise.json`. Os subagentes não veem a resposta anterior. Troca só por evidência melhor; resposta contrária fica em revisão; decisão do analista nunca é tocada. |
| Fila | `revisao-fila --agrupada`: tarefas por causa, ação e fonte, com os itens detalhados originais. A fila detalhada continua disponível para auditoria. |
| Notion | `publicar-*`: o programa confere a solicitação (page_id; sem ele, ID de negócio com correspondência única; **nunca** a mais recente), o XLSX (hash, resultado atual, entrega válida) e a página relida. O upload e a escrita são do conector autenticado. Anexos anteriores ficam; o status não regride; a linha de execução é criada ou atualizada sem tocar em "Validação humana". |

O que ainda não está comprovado: o upload integrado em uma solicitação de teste do Notion (depende de autorização) e a medição do esforço humano de revisão no piloto CE 2026.

## 9. Notion como única saída (0.1.8)

O resultado passa a ser entregue **só no Notion**:
- as bases "Resultados — Execuções", "Orientações", "Matriz (componentes)", "Matriz (elementos)" e "Fila de revisão", ligadas à solicitação;
- o template preenchido em "Template Preenchido".

O `resultado_qualidade.v1.json` e o `resumo.md` continuam na pasta da execução como **estado interno**: eles amarram o XLSX e cada linha ao mesmo hash de conteúdo, mas não são anexados nem linkados. O campo "Resultado JSON" deixa de ser preenchido.

| Tema | Regra |
|---|---|
| Comandos | `notion-iniciar` (confere a solicitação) → por base: `notion-linhas`, `notion-planejar` (criar / atualizar / manter, nunca apagar), gravação pelo conector, `notion-conferir` (releitura) → template (`publicar-*`) → `notion-entregar` (só então "Aguardando Validação"). Estado em `notion_saida.json`; retomada sem duplicar. |
| Chaves | `<UF>-<ano>-<execução>-<item>` (ex.: `CE-2026-QUA13r1-AC1`). Duas execuções do mesmo estado e ano não colidem. O ID da solicitação é obrigatório no `manifesto-montar`. |
| Campos humanos | Decisão humana, Classificação humana, Comentário analista, Validação humana (só "Aguardando" na criação), Status e Decisão registrada da fila: nunca gravados. Tarefa já fora de "Aberta" não é tocada. |
| Matriz | Faixa e componente ausente ficam vazios no Notion, nunca zero. Elementos só com a regra do template homologada; sem ela, o motivo vai para a linha da execução. |
| Fila | Uma linha por tarefa da fila agrupada. "Itens na fila" da execução = tarefas; o total de itens detalhados vai em "Observações". `revisao_humana.itens` passa a ser exatamente a fila detalhada (o QUA-13 tinha 105 contra 110). |
| Entradas | Os anexos da solicitação são baixados pelo conector e entram no manifesto com o link da solicitação como origem (`--origem`). |
| Regras do ICE | `configuracao_ice` (do `manifesto_ice.json` aprovado ou de `--config-ice`): códigos, carga mínima (`CARGA_ABAIXO_MINIMO`) e equivalências de componentes (`equivalencia_aprovada`). Os valores são da Qualidade. |
| Versão | `esteira` mostra a versão do plugin, e a linha da execução a registra em "Motor". |

A rotina na nuvem e o webhook do Notion estão em [notion/ROTINA.md](notion/ROTINA.md).

O que ainda não está comprovado: a gravação real nas bases e o upload numa solicitação de teste do Notion. Os testes usam um Notion simulado.
