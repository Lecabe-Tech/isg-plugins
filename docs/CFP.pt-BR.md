# Processamento de PDFs grandes (CFP)

> Guia para quem **usa** o plugin. Especificação: `specs/SPEC-003-chunked-file-processing.md`.

## O que é

PDFs de secretarias de educação podem ter mais de 150 páginas. Se o agente lesse o PDF direto, gastaria quase todos os tokens antes de começar a análise. O **CFP** resolve isso com um **programa** (não a IA):

1. extrai o texto **de todas as páginas**;
2. **não apaga nenhum texto** (cabeçalhos, rodapés e números de página vão para o marcador da própria página);
3. divide em **chunks** (trechos), cada um com as **páginas** que cobre;
4. gera um **índice** e um **relatório de qualidade**;
5. permite **buscar** nos trechos, também sem usar IA.

Só na hora da análise o agente lê os poucos trechos de que precisa, citando documento, chunk e página.

## Antes de usar

- Python 3.11 ou mais novo instalado (veja o guia de instalação, seção 3a). Confira com `/isg-model-alignment:configure` (item C-14).
- O PDF precisa estar **salvo no seu computador** (como o arquivo chega até você será tratado em outra etapa).
- Isto funciona no **Claude Code** (terminal ou aba Código do app Desktop). No chat do claude.ai e no Cowork sem terminal, o plugin explica que o processamento deve ser feito no Claude Code.

## Como usar

No Claude Code, diga ao agente algo como *"processe o PDF C:\Documentos\curriculo.pdf"* ou use o comando:

```text
/isg-model-alignment:cfp processar "C:\Documentos\curriculo.pdf" --uf SP --ano 2025
```

O agente vai **confirmar com você** a **UF** (sigla do estado), o **ano** e o **título** antes de processar. Ao terminar ele informa a **situação de qualidade**.

Outros comandos: `buscar "projeto de vida" --uf SP`, `listar`, `status <pasta>`, `pagina <pasta> 47` (mostra o texto bruto e o organizado de uma página, para você comparar com o PDF).

## Situação de qualidade

| Situação | Significa | O que fazer |
|---|---|---|
| **Aprovado** | Nenhuma página com aviso | Pode usar |
| **Aprovado com avisos** | Há páginas com tabela, colunas, imagem, etc. | Confira essas páginas no PDF; o agente usa esse conteúdo com confiança no máximo média |
| **Reprovado** | Uma verificação de fidelidade falhou, ou mais de 10 % das páginas sem texto, ou mais de 2 % de caracteres suspeitos | **Todo o texto é gerado**, mas não conclua nada sem conferir o PDF |

O arquivo `qualidade.md` da pasta do documento lista as verificações, as páginas com aviso, as hifenizações unidas (para você conferir) e **5 páginas sugeridas para comparar com o PDF**.

## Onde ficam os arquivos

Na **pasta de dados do plugin** (a mesma da memória local do agente), organizada por estado e ano:

- Windows: `%LOCALAPPDATA%\InstitutoSonhoGrande\isg-model-alignment\cfp\SP\2025\<documento>\`
- macOS: `~/Library/Application Support/InstitutoSonhoGrande/isg-model-alignment/cfp/…`
- Linux: `~/.local/share/InstitutoSonhoGrande/isg-model-alignment/cfp/…`

Você pode escolher outra pasta em `/plugin` → ISG Model Alignment → **Configure options** → "Pasta de dados". Essa pasta **não é apagada** ao atualizar ou desinstalar o plugin. Dentro de cada documento: `original.pdf` (cópia), `index.md`, `qualidade.md`, `chunks/001.md`…

Processar o **mesmo PDF** de novo não faz nada (o programa avisa que já foi processado). Uma **versão nova** do documento ganha uma pasta nova e a antiga fica marcada como substituída; nada é apagado.

## Limites conhecidos

- Imagens **não** são lidas: aparecem como `[Imagem não processada — página N]`.
- Tabelas ficam como texto em linhas e são marcadas com `[Início de tabela …]` e `[Fim de tabela]`: confira no PDF.
- PDFs escaneados (só imagem) não têm texto: a página aparece como "sem texto extraível" e o documento pode ficar **Reprovado**.
- PDFs protegidos por senha não são processados.
