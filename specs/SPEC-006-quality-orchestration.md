# SPEC-006 — Orquestração Claude de Qualidade e base central

**Estado:** implementação inicial para revisão em PR (2026-11-15); requisitos 9 e 10 e decisão de 2026-11-16 acrescentados.

## Requisitos
1. `/isg-model-alignment:qualidade` coordena CFP, SIP, EQV e classificação subjetiva de matrizes.
2. Cinco tabelas recebem propostas Claude: SG_Documentos, SG_Ciclos, SG_Componentes, SG_ResumoMatriz e SG_Avaliacoes. As demais são somente leitura, governança ou decisão humana.
3. `ISG_QUALITY_BASE` aponta para caminho absoluto local/UNC ou URL HTTPS do arquivo Excel central; `quality_base` em userConfig é alternativa. Nenhuma credencial/token no repositório.
4. A análise é evidenciável por documento/página/trecho; `Revisar` em EQV bloqueia publicação.
5. JSON gerado é validado: nomes de tabela/colunas, IDs, flags, referência de ciclo e identidade UF/ano/modelo.
6. Gerador de staging CSV/JSON não modifica o Excel central.
7. Office Script de importação pendente anexa somente linhas não publicadas, com verificação de duplicação; precisa de integração autenticada no tenant. Nenhuma gravação SharePoint está implementada diretamente no plugin.
8. A liberação ao Thomaz é posterior à revisão humana.
9. **Mesmo comportamento em qualquer Claude Code com terminal** (CLI e aba Código do app Desktop). Nenhuma skill depende de recurso exclusivo de um ambiente, como abrir outra sessão com `claude -p` (exige login próprio do CLI). Verificado pela VAL-13.
10. **Garantia da saída estruturada pelo código, não pelo ambiente.** Cada aba parte do esqueleto `modelo-resposta`, é validada com `validar-resposta` até passar e é revalidada por `agrupar`, `validar` e `preparar`. O lote registra em `contratos` o SHA-256 do schema de cada aba, e `validar`/`preparar` recusam um lote validado contra outra versão do contrato. `claude -p --json-schema` fica como atalho opcional de automação.

## Decisões
- **2026-11-16 — saída estruturada sem dependência do CLI.** O teste de MG 2026 mostrou que `claude -p --json-schema` não roda no app Desktop sem login separado do CLI e que o schema em draft 2020-12 era recusado. Decisão do Instituto: o plugin deve rodar igual no CLI e no Desktop, mantendo a garantia de saída estruturada. A garantia passa a ser o portão de validação no código (requisitos 9 e 10), igual nos dois ambientes; a geração com schema imposto continua possível como atalho, nunca como requisito.

## Aceite
- [x] Skill orquestradora e skills por aba no plugin.
- [x] Contrato JSON, validação e staging.
- [x] Variável de ambiente e preferência de configuração.
- [x] Modelo de Office Script para importar no Excel.
- [ ] Office Script configurado/testado em cópia da base real no SharePoint.
- [ ] Teste end-to-end CE/2026 com PDFs e template e paridade com Thomaz.
- [ ] Fluxo de revisão e publicação de snapshot aprovado homologado.
