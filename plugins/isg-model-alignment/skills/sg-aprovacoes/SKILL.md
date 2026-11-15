---
name: sg-aprovacoes
description: Regras de extração, validação e preenchimento da aba SG_Aprovacoes no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 07 — SG_Aprovacoes

**Modo:** fluxo_externo. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `SG_Aprovacoes`.

## Fontes autorizadas
Novo requisito do MVP. A planilha do Thomaz e o template não contêm uma aba de aprovações equivalente. [ADR-002] define camada intermediária; autorização humana exigida no projeto.

## Colunas existentes no Excel
`AprovacaoID, CicloID, Decisao, Aprovador, DataHora, Comentarios, OrigemFluxo, Publicado`

## Regras específicas
- **PROIBIDO ao Claude criar, alterar ou simular aprovações.** Este é um registro de decisões humanas, escrito exclusivamente pela integração após receber um evento autêntico de revisão.
- Resposta da skill deve ser `{"aba":"SG_Aprovacoes","modo":"fluxo_externo","linhas":[],"pendencias":[{"campo":"Decisao","motivo":"Aguardando evento real do revisor"}],"fontes":[],"checagens":[]}`.
- Evento futuro da integração conterá `AprovacaoID` único, `CicloID` existente, `Decisao` (`Aprovado`/`Rejeitado`/conforme catálogo governado), `Aprovador` com identidade real, `DataHora` do sistema, `Comentarios` efetivos, `OrigemFluxo` identificável e `Publicado` coerente.
- A aprovação **não ocorre pelo simples fato** de Claude encontrar a orientação. Publicar só se todas as linhas do ciclo forem consistentes e um humano tiver aprovado o snapshot.
- Se pedirem para Claude 'aprovar', devolva uma solicitação de revisão, nunca um evento artificial.


## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"SG_Aprovacoes","modo":"fluxo_externo","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/9b44b89e-d84e-45cd-adb4-8ade7aa9a5ca/JE5fDl7YFlcKuo5c_4DuF3ZoEF-2FIQr)


> Fonte normativa: Scripta [GUIA-024]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.
