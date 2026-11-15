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

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/fd1c52d3-925c-46b0-86a9-145996546939/K7t1CjvY7o4u7oVYtDFc-Qd2F3zLHnCi)


> Fonte normativa: Scripta [GUIA-028]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.
