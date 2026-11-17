# ISG Model Alignment

Plugin do Instituto Sonho Grande para apoiar processos de qualidade com o Claude.

## Comandos

| Comando | O que faz |
|---|---|
| `/isg-model-alignment:configure` | Verifica se o ambiente está pronto e oferece ajustes seguros (sempre pedindo confirmação). |
| `/isg-model-alignment:upgrade` | Mostra a versão instalada, a mais recente e as mudanças entre elas, e atualiza com a sua confirmação. |

Use `--check` depois do comando para apenas consultar, sem alterar nada.

### Analisar um estado

| Comando | O que faz |
|---|---|
| `/isg-model-alignment:analisar` | Esteira completa da análise de Qualidade de um estado (propedêutico 9h): anexe os documentos do estado e o template do cluster e peça, por exemplo, "analisar Ceará 2026". O Claude executa todas as etapas e entrega o resultado com a fila de revisão. Funciona no Claude Code (terminal ou aba Código do app Desktop). |

As etapas da esteira:
1. Entradas
2. Imagens
3. Matriz
4. Orientações
5. Cruzamento
6. Resultado e fila de revisão

O referencial ICE vem da pasta configurada em "Pasta de referenciais ICE" (com `manifesto_ice.json` aprovado), a menos que seja enviado junto.

## Onde funciona

Claude Code (terminal, aba Código do app Desktop e Claude Code na web), chat do claude.ai, chat do app Desktop e Cowork.
No chat e no Cowork não há terminal: os comandos mostram o passo a passo para você fazer manualmente.

## Instalação e atualização

Veja o guia de instalação do repositório (`docs/INSTALL.pt-BR.md`).
Histórico de versões: `CHANGELOG.md`.

## Qualidade — análise estadual e base central (SPEC-006)

O comando `/isg-model-alignment:qualidade` coordena CFP → SIP → EQV → classificação curricular → geração de propostas de registros para `SG_*`. As 11 skills por aba fazem parte do plugin; somente cinco tabelas recebem propostas de dados. **Não executa aprovação ou publicação.**

A análise de alinhamento **exige um referencial ICE externo aprovado**, além dos documentos estaduais. Configure:

| Variável | Conteúdo |
|---|---|
| `ISG_QUALITY_BASE` | Caminho absoluto do XLSX central **ou URL HTTPS direta do arquivo no SharePoint** (identifica destino, não grava) |
| `ISG_QUALITY_STATE_DOCS` | Pasta local/sincronizada com arquivos `UF/Ano/` (ex.: `MG/2026/`) |
| `ISG_QUALITY_ICE_REFERENCE` | Pasta local/sincronizada com `manifesto_ice.json` e workbooks ICE homologados por modelo 7h/9h |

Alternativas no `userConfig`: `quality_base`, `quality_state_docs`, `quality_ice_reference`. Variáveis de ambiente têm precedência. **Para as duas pastas de entrada, um link SharePoint sozinho não funciona:** use arquivos locais/sincronizados ou desenvolva conexão autenticada.

Antes de comparar, execute o preflight:
```bash
python plugins/isg-model-alignment/scripts/quality/quality_payload.py fontes --uf MG --ano 2026 --modelo 9h --json
```
Esse comando verifica arquivo, aba, versão, modelo e hash opcional, mas não substitui a validação do gabarito por Qualidade. Um manifesto com aprovação declarada não autentica aprovação humana. Se faltar a matriz adequada ou os critérios, o Claude não pode concluir classificação.

O pipeline prepara JSON/CSV; **não possui cliente SharePoint para gravar**. O `office-script-import.ts` é um exemplo de importação que exige integração Microsoft externa e testes antes de produção.

Guia detalhado: `docs/QUALITY-PIPELINE.pt-BR.md`. Exemplo de manifesto: `examples/quality/manifesto_ice.example.json`. Para MG, a `eqv` também precisa do catálogo de orientações em template compatível com MG/2026; o template Cluster 4 não tem essa coluna.

### Templates pré-cadastrados por estado

Defina `ISG_QUALITY_TEMPLATES_DIR` ou `quality_templates_dir` para uma pasta local/sincronizada com `MG/Template-MG.xlsx` ou `MG/2026/Template-MG-2026.xlsx`. O plugin seleciona um template compatível com as abas de orientações `1.1` e `1.2` e colunas da UF e do ano. Evita reenviar o mesmo Excel a cada ciclo; **não substitui matriz estadual nem referencial ICE**.

Exemplo de início em Claude Code: `/isg-model-alignment:qualidade iniciar --ano 2026 --orientacao "C:\\Qualidade\\Estados\\MG\\2026\\Orientacoes.pdf"`. A UF é deduzida **somente do caminho UF/Ano** dentro da pasta de documentos já configurada; fora dessa pasta, informar `--uf MG`. O resolvedor `quality_payload.py resolver --ano ... --orientacao ...` localiza o template, mas não confirma a matriz curricular vigente; o Claude precisa lê-la antes de preencher componentes e horas.
