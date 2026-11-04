# Montar a memória do agente no Notion

> Para quem administra a memória (revisores e responsáveis pelo Notion). Base: SPEC-002, seções 4.1 a 4.4.
> A estrutura exata (nomes e tipos) está em `plugins/isg-model-alignment/shared/notion-schema.json`. **Os nomes são contratos:** se você renomear uma propriedade no Notion, o agente deixa de encontrá-la.
> **Teste primeiro em uma cópia** ("ISG — Agente (TESTE)") e só depois monte a versão real.

## Caminho rápido (recomendado)

1. Conecte o Notion no Claude (guia de instalação, seção "Conectar o Notion").
2. No Claude Code ou no chat, rode `/isg-model-alignment:memory-setup EQV`.
3. Leia a checklist, confira o que será criado e responda **sim**.
4. Faça à mão o que o comando listar no final (passos 4 a 6 abaixo).

## Caminho manual (o mesmo resultado)

### 1. Espaço de equipe
Crie o espaço de equipe **ISG — Agente** e compartilhe com os analistas e revisores (todos precisam ser **membros** do espaço de trabalho; convidados não conseguem usar o agente).

### 2. Banco "Assuntos"
Crie o banco **Assuntos** com as propriedades (nome exato → tipo):

| Propriedade | Tipo |
|---|---|
| Nome | Título |
| Código | Texto |
| Descrição | Texto |
| Campos-chave | Texto |
| Revisores | Pessoa |
| Prazo de revisão (dias úteis) | Número (padrão 2) |
| Casos para ativar regra | Número (padrão 2) |
| Erros para retirar regra | Número (padrão 3) |
| Confiança mínima para decidir | Seleção: alta, média, baixa |
| Ativo | Caixa de seleção |
| Base de memória | URL |
| Base de registro | URL |
| Última alteração da memória | Rollup (ver passo 3) |
| Versão da memória | Número |

### 3. Página do assunto (uma por assunto)
Dentro de **ISG — Agente**, crie a página **EQV — Equivalência de componentes** e, dentro dela:

**Banco "Memória — EQV"**

| Propriedade | Tipo |
|---|---|
| Título | Título |
| ID | ID único, prefixo `EQV` |
| Assunto | Relação → Assuntos (com propriedade de volta em Assuntos) |
| Tipo | Seleção: Fato, Rejeição, Regra |
| Status | Status: Rascunho, Pendente, Ativo, Aprovado, Auto-aprovado, Em observação, Em conflito, Rejeitado, Retirado, Substituído |
| UF / Órgão | Texto |
| Documento | Texto |
| Ano | Número |
| Escopo geral | Caixa de seleção |
| Termo externo | Texto |
| Componente ISG | Texto |
| Enunciado | Texto |
| Evidência | Texto |
| Justificativa | Texto |
| Confiança | Seleção: alta, média, baixa |
| Casos de suporte | Relação → o próprio banco |
| Relacionado | Relação → o próprio banco |
| Substitui | Relação → o próprio banco |
| Erros | Número |
| Revisores | Pessoa |
| Prazo de revisão | Data |
| Decidido por | Pessoa |
| Decisão em | Data |
| Motivo da decisão | Texto |
| Criado por | Criado por |
| Criado em | Data de criação |

Visões salvas: **Legível — EQV** (filtro: Status é Ativo, Aprovado, Auto-aprovado ou Em observação), **Em conflito — EQV** (Status é Em conflito), **Pendentes** (Status é Pendente, ordenado por Prazo de revisão), **Perto de ser retiradas** (Tipo é Regra e Erros ≥ 2).

**Banco "Registro — EQV"**

| Propriedade | Tipo |
|---|---|
| Título | Título |
| Tipo de evento | Seleção: Feedback, Mudança de status, Cartão importado, Auditoria |
| Assunto | Relação → Assuntos |
| Analista | Criado por |
| Superfície | Seleção: Chat, Cowork, Claude Code, Claude Code na web |
| Pergunta / trecho da resposta | Texto |
| Veredito | Seleção: Correto, Incorreto, Parcial |
| Motivo | Texto |
| Memórias usadas | Relação → Memória — EQV |
| Entradas criadas ou alteradas | Relação → Memória — EQV |
| De / Para (status) | Texto |

Formulário **Enviar feedback — EQV** (formulário do banco Registro) com os campos do cartão de feedback.

Página **Painel — EQV** (opcional): gráficos de feedback por semana, % marcado como correto, regras aprovadas × auto-aprovadas.

Em **Assuntos**, crie a linha **Equivalência de componentes**: Código `EQV`, Campos-chave "UF / Órgão, Documento, Ano, Termo externo, Componente ISG", **Ativo** marcado, **Base de memória** e **Base de registro** com os links dos dois bancos. Na propriedade **Última alteração da memória**, faça um rollup da relação com "Memória — EQV", propriedade *Última edição*, cálculo *Data mais recente*.

### 4. Revisores
Preencha **Revisores** na linha do assunto (uma ou mais pessoas). É para eles que vão os e-mails.

### 5. Acesso por assunto
Restrinja a página **EQV — Equivalência de componentes** às pessoas desse assunto (analistas e revisores). Cada assunto tem o seu próprio acesso.

### 6. Automações
Siga `AUTOMATIONS.md` (nesta pasta).

## Novo assunto
Duplique a página de um assunto (ou o **Modelo de assunto**), troque o código no nome dos bancos e das visões e no prefixo do **ID**, crie a linha em **Assuntos**, ajuste o acesso e recrie as automações para os bancos novos. Depois peça à equipe de manutenção para incluir a skill do assunto no plugin.
