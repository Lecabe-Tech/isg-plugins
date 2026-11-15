# ISG Model Alignment

Plugin do Instituto Sonho Grande para apoiar processos de qualidade com o Claude.

## Comandos

| Comando | O que faz |
|---|---|
| `/isg-model-alignment:configure` | Verifica se o ambiente está pronto e oferece ajustes seguros (sempre pedindo confirmação). |
| `/isg-model-alignment:upgrade` | Mostra a versão instalada, a mais recente e as mudanças entre elas, e atualiza com a sua confirmação. |

Use `--check` depois do comando para apenas consultar, sem alterar nada.

## Onde funciona

Claude Code (terminal, aba Código do app Desktop e Claude Code na web), chat do claude.ai, chat do app Desktop e Cowork.
No chat e no Cowork não há terminal: os comandos mostram o passo a passo para você fazer manualmente.

## Instalação e atualização

Veja o guia de instalação do repositório (`docs/INSTALL.pt-BR.md`).
Histórico de versões: `CHANGELOG.md`.

## Qualidade — base central de dados (proposta em revisão)

O comando `/isg-model-alignment:qualidade` coordena a análise de PDFs estaduais com CFP, SIP e EQV, a interpretação das matrizes e a geração de propostas para o Excel central. Há uma skill para cada aba. Veja `docs/QUALITY-PIPELINE.pt-BR.md` no repositório.

Configure opcionalmente `ISG_QUALITY_BASE` com o caminho absoluto do XLSX ou com a URL HTTPS do arquivo no SharePoint; alternativamente use o campo `quality_base` das preferências do plugin. **Configurar a variável não grava dados no SharePoint.** O plugin prepara lotes JSON/CSV e fornece um Office Script para integração Microsoft, que deverá ser instalada, autenticada e testada pelo Instituto.
