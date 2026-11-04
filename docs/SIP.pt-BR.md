# Leitura de imagens (SIP)

> Guia para quem **usa** o plugin. Especificação: `specs/SPEC-004-smart-image-processor.md`.

## O que é

O **SIP** (Smart Image Processor) é a skill que **olha uma imagem e devolve o que ela mostra e significa, em Markdown**. Serve para qualquer imagem que o Claude consiga ver e, junto do CFP, para as **figuras dos PDFs**: gráficos, tabelas em imagem, infográficos, capas.

O CFP só guardava um marcador (`[Imagem não processada — página 47 — id p047-02]`). Agora ele também **extrai cada imagem para um arquivo** (sem IA), e o SIP interpreta essas imagens quando é preciso.

## Regras que não mudam

- Os **trechos originais (`chunks/`) nunca são alterados**. As interpretações ficam numa **cópia separada**, `chunks_com_imagens/`, dentro de blocos marcados **"interpretação por IA — conferir no PDF"**.
- A transcrição do texto da imagem é **literal**; o que não dá para ler vira `[ilegível]`. **Números nunca são inventados**; valores lidos pela forma de uma barra ou linha são marcados *(aproximado)*.
- O Claude pode errar, principalmente em imagens pequenas, borradas ou giradas. **Confira no PDF** antes de decidir com base em uma interpretação.
- O texto que aparece dentro de uma imagem é tratado como dado, **nunca como ordem**. Pessoas não são identificadas pelo rosto.

## Como usar

| Quero… | Faça |
|---|---|
| Interpretar **uma imagem** (qualquer superfície com visão) | Anexe a imagem e peça *"interprete esta imagem"*, ou use `/isg-model-alignment:sip <caminho da imagem>` |
| Ler as figuras **durante uma análise** (padrão) | Não precisa fazer nada: ao usar um trecho com figuras, o agente interpreta **só as figuras daquele trecho** |
| Interpretar **o documento inteiro** | `/isg-model-alignment:sip documento <pasta>`: mostra a quantidade e a estimativa de tokens e **só começa depois do seu "sim"** |
| Ver o que falta | `/isg-model-alignment:sip pendentes <pasta>` |
| Gerar a cópia com as interpretações | `/isg-model-alignment:sip integrar <pasta>` |
| Corrigir uma interpretação | `/isg-model-alignment:sip corrigir <pasta> <id>`: pede **um** "sim" e guarda a correção na memória compartilhada |

Com terminal (Claude Code), tudo funciona. No chat e no Cowork sem terminal só dá para interpretar uma imagem anexada; o plugin diz isso e não finge salvar nada.

## Quanto custa

Cada imagem usa de **cerca de 1 mil a 6 mil tokens** do seu plano (a imagem mais a resposta). Por isso o padrão é **sob demanda**. Nos documentos de teste: MG ≈ 11 imagens (20 a 22 mil tokens); CE ≈ 59 imagens (118 a 151 mil tokens). A estimativa é **aproximada**. A execução do documento inteiro grava **depois de cada imagem** e pode ser **interrompida e retomada**. Imagens repetidas e as já interpretadas (cache pelo hash da imagem) **não gastam IA de novo**.

## O que há na pasta do documento

```text
imagens/               arquivos das imagens, index.json e as interpretações (pNNN-NN.md)
chunks/                texto original (intocado)
chunks_com_imagens/    cópia com as interpretações em blocos "por IA"
cobertura.md           quantas imagens estão interpretadas/pendentes e "Conteúdo completo: sim/não"
```

**"Conteúdo completo: sim"** só aparece quando não há imagem pendente, imagem não extraível, página com **possível gráfico vetorial** (desenhado com linhas, sem arquivo de imagem; o plugin só avisa) nem documento Reprovado no CFP.

## Limites desta versão

- Gráficos **vetoriais** são apenas **detectados e avisados**; não são lidos.
- Imagens em formatos que o programa não extrai (por exemplo CCITT, JBIG2, JPX) ficam listadas como **não extraíveis**.
- Ícones pequenos (menos de 2 % da página ou menos de 200 px no lado menor) não são interpretados por padrão.
- Documentos processados com a versão anterior do CFP precisam ser processados de novo (`processar ... --force`) para ganhar os ids das imagens.
