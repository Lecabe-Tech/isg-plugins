# Aprendizados do piloto CE 2026 (SPEC-017)

**Data:** 17/11/2026 · **Versão do plugin com as melhorias:** 0.1.3

Uma sessão do Claude Code recebeu os arquivos do Ceará e o pedido "vamos iniciar o processo de análise do estado do Ceará". A análise **não chegou ao resultado**. Este documento registra o porquê, a decisão tomada em cada ponto e o que mudou no plugin.

## O que aconteceu

1. **O fluxo do plugin não foi usado.** A skill `resultado-qualidade` só rodava com o comando digitado. A sessão improvisou:
   - leu a documentação do repositório de desenvolvimento;
   - tentou bibliotecas que não estão instaladas (openpyxl, pypdf, poppler);
   - rodou o programa da cópia de desenvolvimento, não do plugin instalado.
2. **O template era de outro cluster.** O Cluster 2 cobre MG, MS, MA e AL. A sessão percebeu isso só depois de abrir a planilha por fora.
3. **O referencial ICE não foi enviado.** A sessão escolheu por conta própria uma cópia de teste do piloto de MG, marcada "cópia de TESTE" e não aprovada.
4. **A matriz do CE vem em faixas.** A Formação Geral Básica traz "3 ou 4h/a", "4 ou 5h/a" e "1 ou 2h/a", e o plugin exigia um valor por série. As Diretrizes (p.88) dizem que as matrizes completas estão em outro documento da SEDUC, "Matrizes Curriculares para EEMTIs 2026", que não veio.
5. **Muitas imagens.** Havia 46 trechos em imagem nas Diretrizes, vários com a mesma figura repetida. Cada um precisava de uma leitura.
6. **A sessão parou para perguntar.** Ela perguntou qual template e qual ICE usar e, depois de transcrever a matriz, encerrou com "próximos passos". Não avaliou as orientações nem gerou o resultado.

## Decisões e mudanças

| Ponto | Decisão | O que mudou |
|---|---|---|
| Pedido em texto livre não chegava ao fluxo | A skill responde também ao pedido de análise de um estado | `resultado-qualidade` deixou de ser só por comando; a skill manda usar só o programa do plugin instalado |
| Parar no meio | A interação humana é na revisão do resultado | Roteiro "vá até o resultado": parar antes de começar só se faltar entrada; o resto vira pendência na fila de revisão |
| Template de outro cluster | Falhar logo, com a lista de UFs | `iniciar` recusa com `TEMPLATE_SEM_UF` em menos de um segundo, antes de ler os documentos |
| Referencial ICE | **Local fixo configurado**, igual para todos os estados | Manifesto com `referencial_ice: []` usa a pasta configurada (`quality_ice_reference`, também por link do SharePoint) com `manifesto_ice.json` aprovado; cópia de teste ou não aprovada é recusada; comando `ice-padrao` |
| Matriz em faixa | **Registrar a faixa e pedir o documento oficial** | Valor `{"faixa": [3, 4]}` com o trecho; pendência `VALOR_EM_FAIXA` com o documento citado; totais impressos conferidos contra a soma (`TOTAL_FONTE_NAO_CABE` quando não fecha) |
| Imagens repetidas | Ler uma vez | `imagens` marca `mesma_imagem_que`; a leitura registrada é copiada para as repetidas |
| `unidades --de/--ate` contam unidades, não páginas | Ler por página | `unidades --pagina N [--ate-pagina M]` |

## Conferido com os arquivos reais

- Template Cluster 2 para o CE: recusado com a lista "MG, MS, MA, AL".
- Cópia de teste como ICE padrão: recusada (`ICE_DE_TESTE`).
- Imagens: de 44 pendentes, 37 são diferentes. A leitura da faixa da p.6 foi copiada para quatro páginas.
- Matriz em faixa: 25 células ficaram em faixa, com o pedido do documento "Matrizes Curriculares para EEMTIs 2026".
- Totais: a conferência da 1ª série apontou que a soma lida da imagem da p.89 vai de 34 a 43h, e a fonte imprime 45h. A leitura de IA da outra sessão perdeu linhas; a p.88 cita Clubes Estudantis na 1ª série.

## Segunda rodada: esteira `analisar` (versão 0.1.4)

A análise do CE rodou de ponta a ponta em cerca de 6 minutos:
- 40 imagens diferentes, lidas por 5 subagentes;
- 99 orientações, avaliadas em 3 lotes paralelos;
- matriz de 45h com 34 componentes e 25 células em faixa; os 6 totais impressos fecham;
- resultado parcial com 103 itens na fila de revisão.

| Retorno do analista | Decisão | O que mudou (0.1.5) |
|---|---|---|
| "O número 11 não significa nada sem contexto: o template usa Sim ou Não por linha" | A entrega é o **template preenchido**, no formato em que o analista trabalha | Etapa 7 da esteira, `template-preencher`: cópia do template com Sim/Não/Pendente por linha, observação "Pág. X (documento): trecho", aba de matriz da UF e amarelo no que pede decisão. A sessão tinha montado isso por conta própria, editando o XML e instalando a biblioteca openpyxl; agora é do programa e só usa a biblioteca padrão |
| Alerta "oferta de 9h não comprovada" com a frase da p.88 | O título fora da tabela prova a oferta | Citação da seleção aceita em qualquer página do mesmo documento da matriz |
| Conflitos "exigido pelo ICE × sem aulas" em Eletivas, Projeto de Vida e Estudo Orientado, que estão na matriz | Valor lido de imagem mostra a oferta | O cruzamento conta o valor lido de imagem; só Práticas Experimentais segue como conflito real |

Observação dos analistas no template do CE: na Formação Geral Básica, "aqui foi considerado o máximo" da faixa, totalizando 24 horas-aula. O plugin mantém a faixa, como decidido. Se a Qualidade quiser adotar essa convenção, ela precisa ser registrada como regra.

## Ainda pendente

- A Qualidade configurar a pasta do referencial ICE oficial, com `manifesto_ice.json` aprovado (versão, `aprovado: true`, `aprovado_por`, `data`). A cópia de teste indica que o referencial vem da "Base do painel_v3.xlsx", no SharePoint PortalSG/Qualidade. Sem a planilha do ICE, os códigos das orientações ficam sem reconciliação.
- O documento "Matrizes Curriculares para EEMTIs 2026" (Coeti/SEDUC), para os valores exatos do CE.
- A duração da hora-aula do CE, que o documento não informa.
