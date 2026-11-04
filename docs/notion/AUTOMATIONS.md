# Automações do Notion para a memória do agente

> Base: SPEC-002, seção 4.8. Crie estas automações **para cada assunto** (elas agem nos bancos daquele assunto).
> Automações **não ficam no git**: depois de criar ou mudar qualquer uma, atualize a tabela "Registro de quem criou" no fim desta página.
> Importante: **uma automação não dispara outra** no Notion. Por isso a aprovação é só uma mudança de **Status**, e o próprio agente aplica as regras de prazo e de erros quando lê a memória. As automações servem para **avisar por e-mail** e **manter o banco arrumado**.

## AUT-1 — Avisar os revisores quando entrar uma entrada nova
- **Banco:** Memória — EQV
- **Gatilho:** Página adicionada
- **Ação:** Enviar e-mail (Send mail to) para a propriedade **Revisores** da página
- **Assunto do e-mail:** `[ISG — Agente] Nova entrada {Tipo}: {Título}`
- **Corpo:** tipo, status, enunciado, justificativa, prazo de revisão e link da página. Texto sugerido:
  - Fato/Rejeição: "Para conhecimento: um analista registrou esta correção. Se estiver errada, mude o Status para Rejeitado e escreva o motivo."
  - Regra: "O agente propôs esta regra. Aprove (Aprovado) ou rejeite (Rejeitado) até {Prazo de revisão}. Sem resposta até lá, ela passa a valer (Auto-aprovado)."

## AUT-2 — Aprovação automática quando o prazo vence
- **Banco:** Memória — EQV
- **Gatilho:** Todo dia, 07:00 (horário de Brasília)
- **Ação:** Editar páginas em **Memória — EQV** onde **Status** é `Pendente` **e** **Prazo de revisão** é antes de hoje:
  - **Status** → `Auto-aprovado`
  - **Decisão em** → hoje
  - **Motivo da decisão** → `Prazo vencido`
- **Nunca** inclua `Em conflito` neste filtro.
- Se o rollup **Última alteração da memória** não atualizar com esta automação (a testar no M-T0), acrescente aqui: somar 1 em **Versão da memória** na linha do assunto em **Assuntos**.

## AUT-3 — Rebaixar regras com erros (opcional)
- **Banco:** Memória — EQV
- **Gatilho:** Propriedade **Erros** editada
- **Ação:** se **Erros** ≥ **Erros para retirar regra** (3) → **Status** `Retirado`; senão, se **Erros** ≥ 1 → **Status** `Em observação`.
- Opcional: o agente já aplica essa regra ao ler.

## AUT-4 — Avisar sobre conflitos
- **Banco:** Memória — EQV
- **Gatilho:** Propriedade **Status** editada para `Em conflito`
- **Ação:** Enviar e-mail aos **Revisores**: "Dois analistas discordam sobre {Título}. Abra as duas entradas (propriedade Relacionado), mantenha a correta e marque a outra como Substituído."

## AUT-5 — Resumo diário (alternativa ao AUT-1)
- Use se AUT-1 não disparar para páginas criadas pelo agente (a testar no M-T0), ou se os revisores preferirem um e-mail por dia.
- **Gatilho:** Todo dia, 08:00. **Ação:** e-mail aos revisores com as entradas criadas no dia anterior (visão **Pendentes**).

## AUT-6 — Marcador de mudança (só se necessário)
- Use apenas se o rollup **Última alteração da memória** em **Assuntos** não mudar quando uma entrada muda (a testar no M-T0).
- **Banco:** Memória — EQV. **Gatilho:** **Status** ou **Erros** editados. **Ação:** em **Assuntos**, linha do assunto: somar 1 em **Versão da memória**.

## Quem envia os e-mails
A ação "Enviar e-mail" usa a conta de e-mail conectada por **quem criou** a automação, e só essa pessoa consegue editá-la. Se essa pessoa sair do Instituto, os e-mails param. Registre abaixo e inclua no processo de desligamento.

## Registro de quem criou

| Automação | Assunto | Criada por | E-mail que envia | Data | Observação |
|---|---|---|---|---|---|
| | | | | | |
