---
name: contrato-th
description: Regras de extração, validação e preenchimento da aba CONTRATO_TH no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 11 — CONTRATO_TH

**Modo:** somente_leitura. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `CONTRATO_TH`.

## Fontes autorizadas
Aba CONTRATO_TH do Excel central e as abas de entrada base_matrizes, base_orientações, base_orientações_gestão e controle_mapeamento do painel do Thomaz; [GUIA-016].

## Colunas existentes no Excel
`Aba de documentação: Saída Excel existente, Origem canônica, Regra de seleção, Formato, Observação.`

## Regras específicas
- **Não escrever nesta aba** nem atualizar diretamente o Excel do Thomaz. Seu papel é validar se a saída proposta é compatível com o contrato.
- `base_matrizes` recebe SG_ResumoMatriz e SG_Ciclos; `base_orientações` recebe SG_Avaliacoes pedagógicas pivotadas (70 códigos); `base_orientações_gestão` recebe SG_Avaliacoes gestão pivotadas (29 códigos).
- `controle_mapeamento` requer flags de mapeamento explícitos que **ainda não estão completos em SG_Ciclos**; não fabricar. `base_infos_gerais` fica fora do MVP.
- Todo consumo exige ciclo e linhas `Aprovado + Publicado=Sim`, não basta preenchimento inicial. Distinguir 7h e 9h para evitar colisão da chave legada UF+Ano.
- Responder `modo="somente_leitura"`, `linhas=[]`, e lista de eventuais incompatibilidades, sem alteração de layout.

## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"CONTRATO_TH","modo":"somente_leitura","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

> Fonte normativa: Scripta [GUIA-028]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.

## Structured Output — contrato versionado (obrigatório)

**Contrato canônico:** `scripts/quality/schemas/CONTRATO_TH.schema.json`. A skill **não deve** retornar Markdown livre, tabelas, JSON parcialmente preenchido ou campos adicionais quando estiver preparando dados para a integração.

O objeto JSON contém exatamente `aba`, `modo`, `linhas`, `pendencias`, `fontes` e `checagens`. `aba="CONTRATO_TH"` e `modo="somente_leitura"`. **Todas as colunas da planilha são obrigatórias no JSON de cada linha**; campos sem informação comprovada recebem `null` somente quando seu schema autoriza. Nunca criar colunas extras nem transformar texto livre em número. `Publicado="Não"` e status pendente são valores fixos da geração pelo Claude.

**Esta aba não aceita linhas propostas pelo Claude.** A resposta sempre deve ter `linhas: []`; devolver somente `pendencias`, `fontes` e `checagens`, sem editar o workbook.

Para obter o schema utilizado no Claude Code em modo não interativo:
```text
python <raiz-do-plugin>/scripts/quality/quality_payload.py esquema --aba CONTRATO_TH
```
O orquestrador usa `claude -p --output-format json --json-schema "<schema JSON>"` para obter `structured_output`. **Uma conversa interativa com a skill não impõe constrained decoding automaticamente**: o JSON ainda deve ser rejeitado se falhar na validação local. Extrair **somente** `structured_output` do envelope CLI; nunca aceitar `result` em Markdown como substituto.

Depois de gerar, executar `quality_payload.py validar-resposta "<arquivo-da-resposta>.json" --json`. Se houver erro, corrigir a extração e executar novamente; **não importar para o SharePoint**. O JSON válido comprova forma e tipos, **não prova a equivalência pedagógica ao ICE**.
