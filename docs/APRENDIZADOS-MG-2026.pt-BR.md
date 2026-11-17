# Aprendizados do piloto MG 2026 (SPEC-017)

**Data do piloto:** 16/11/2026 · **Decisões registradas:** 17/11/2026 · **Versão do plugin com as melhorias:** 0.1.2

O piloto rodou a análise de Qualidade de Minas Gerais 2026 (Ensino Médio Integral propedêutico de 9h) de ponta a ponta, sem usar resultados preenchidos. O resultado validado saiu **parcial**:
- os documentos foram lidos por completo;
- a matriz oficial teve 22 componentes transcritos;
- 96 das 99 orientações foram decididas;
- ficaram pendentes as decisões humanas: confirmar a matriz, homologar o ICE e a regra de consolidação, e resolver os conflitos.

Na comparação feita depois com o preenchimento dos analistas, 85 de 96 orientações coincidiram. As 11 divergências estavam todas marcadas para revisão. Este documento registra o que dificultou o processo, a decisão tomada em cada ponto e o que mudou no plugin.

## 1. Entradas

| Dificuldade no piloto | Decisão | O que mudou |
|---|---|---|
| A matriz oficial não estava nos arquivos enviados; ela foi buscada na web | O plugin roda **só com os arquivos enviados ou com a pasta informada** | Endereço da internet no manifesto é recusado (`ORIGEM_NAO_PERMITIDA`); o código de download saiu; uma pasta informada entra com todos os arquivos dentro dela |
| Parte dos arquivos chegou como link do SharePoint | Link do SharePoint é **local informado**: vale como entrada, porque o SharePoint estará conectado | O link entra no manifesto e fica como origem; o programa lê a cópia que o OneDrive mantém no computador (biblioteca sincronizada ou atalho), sem acessar a rede. O comando `sharepoint` mostra se a cópia existe. Sem cópia, o conector identifica o arquivo e o analista sincroniza a biblioteca ou baixa o arquivo (`copia_local`). O texto do conector não é evidência, porque não tem página nem célula para conferir |
| A busca na web indicou errado uma resolução como alteração da matriz | O plugin **não avalia se a matriz ou as orientações mudaram fora do que foi enviado**. O alinhamento ao modelo é decidido por pessoas | A skill proíbe pesquisa e conhecimento externo; documento faltante vira pendência e pedido ao analista |
| O ICE de 2024 usa itens PADI e o template 2026 usa outros códigos | Tabela de correspondência é decisão da Qualidade | Sem mudança de código: a reconciliação formal continua exigindo códigos iguais ou mapeamento aprovado |

## 2. Ambiente

| Dificuldade | Decisão | O que mudou |
|---|---|---|
| Download bloqueado pelo certificado da rede corporativa | Correto que tenha falhado: os arquivos serão enviados | Não há mais download no plugin |
| Sem renderizador de páginas (poppler), as imagens foram abertas por fora | Contornar sem dependência nova | `iniciar` exporta a figura de cada trecho em imagem para `imagens/` e liga o arquivo ao trecho; o comando `imagens` lista o que falta ler. Imagem desenhada no conteúdo da página (inline) não é exportável: o motivo aparece e o analista envia um print |
| Avisos de fonte da biblioteca de PDF poluíram a saída | Silenciar | Avisos do pypdf não aparecem mais |

## 3. Limites do plugin

### 3.1 Tabelas em PDF perdiam a coluna (série)

No Anexo XVIII, cada componente de aprofundamento tinha um único "3" no texto extraído, sem a série. A posição de cada fragmento de texto resolve o problema:

1. **Direção de leitura:** segue a rotação da página. Uma página deitada guarda as linhas no eixo x e as colunas no y.
2. **Linhas:** cada fragmento numérico define uma linha; os rótulos próximos se juntam a ela, inclusive os quebrados em duas linhas.
3. **Colunas:** os pontos de início dos fragmentos numéricos formam as âncoras de coluna.
4. **Tamanho do grupo de cada série:** vem da linha mais completa. Por exemplo, 9 números em 3 séries dão grupos de 3 (A/S, A/A, H/A).
5. **Layout que não fecha:** com colunas demais, grupos que não se dividem ou linha ambígua, nada é confirmado e a célula fica marcada como "coluna não conferida".

No registro da matriz, cada número citado de PDF passa por essa conferência:
- se bate, a evidência vira `celula_layout_conferida`;
- se a série declarada não bate, a célula fica não verificada;
- `tabela-pdf` mostra a grade reconstruída antes da transcrição.

Nas páginas reais do Anexo XVIII, a reconstrução acertou as séries dos seis componentes de aprofundamento e os valores 2/2/1 de Sociologia e Filosofia, sem ajuda.

### 3.2 Seleção sempre "para revisão"

A interação humana é na análise das saídas, não em cada passo. Por isso o plugin entrega sempre os dados que ajudam a decidir. A **fila de revisão** no `resumo.md` e no comando `revisao-fila` ordena as decisões nesta sequência:
1. conflitos graves;
2. decisões da Qualidade;
3. orientações pendentes;
4. componentes e seleção marcados para revisão;
5. orientações de baixa confiança.

Cada item diz o que decidir, onde está a evidência e por quê.

### 3.3 Volume das orientações

O trabalho em lotes paralelos virou padrão:
- `orientacoes-lotes` grava o texto dos documentos estaduais por unidade, os lotes de orientações do ICE e as instruções, sem nada do preenchimento dos analistas;
- cada lote pode ir para um subagente;
- `orientacoes-conferir` aplica as regras sem registrar, até zero problemas.

### 3.4 Zona de julgamento

Confiança, justificativa, citações e prova de ausência já seguem no JSON como evidência para análise. Elas também vão alimentar o futuro painel dos usuários, depois da base centralizada.

## 4. Release

O fluxo fica como está: PR para `main` e o workflow **release** disparado na `main`, que publica a tag e move a `stable`. O seletor do "Run workflow" abre na `stable` e precisa ser trocado para `main`. Nenhuma PR da `main` para a `stable`.

## 5. Ainda pendente

- Homologação do ICE 2026 e decisão sobre os códigos PADI de 2024.
- Homologação da regra de consolidação do template (impressão digital `1d5535d0…` para o Cluster 2).
- Confirmação da matriz de MG pelo analista e decisão sobre Estudos Orientados (4/4/4 na Resolução 5.212/2025 × 4/4/5 no documento orientador).
- Teste na aba Código do app Desktop.
