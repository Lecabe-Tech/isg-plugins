# Solução de problemas

Rode primeiro `/isg-model-alignment:configure`: ele aponta o que está errado e como resolver.

## "Sem acesso" ao adicionar o marketplace ou ao atualizar

- Você precisa ser **convidado** para o repositório e **aceitar o convite** (e-mail do GitHub). Peça a um dos responsáveis: **<nomes>**.
- Rota B: rode `gh auth login` e `gh auth setup-git` (GitHub.com, HTTPS) e tente de novo.
- Rota A: no claude.ai, confirme que o GitHub está conectado e que o app **Claude** tem acesso ao repositório `isg-plugins`.

## O plugin não atualiza

Responda nesta ordem:

1. **Qual rota?** (A = conta do claude.ai; B = Claude Code neste computador.)
2. Foi publicada uma versão nova? Veja a página **Releases** do repositório. Mudanças só chegam quando há um *release*.
3. **Rota A:** "Sync automatically" está ligado? Tente **Check for updates**. Depois reinicie o Claude Code.
4. **Rota B:** rode `gh auth status`. A atualização automática está ligada? (`/isg-model-alignment:configure`). Rode `/isg-model-alignment:upgrade` e depois `/reload-plugins`.

## O comando mostra duas versões diferentes / aparece `@synced` e `@isg-plugins`

O plugin está instalado pelas duas rotas. Mantenha uma só: `claude plugin disable isg-model-alignment@synced` (ou desinstale a cópia que não quer).

## "node: comando não encontrado"

Instale o **Node.js LTS** (versão 20 ou mais) em https://nodejs.org e abra uma nova sessão. Só `/isg-model-alignment:configure` e `/isg-model-alignment:upgrade` precisam do Node.

## "claude: comando não encontrado" (CLAUDE_CLI_NOT_FOUND)

Use o terminal do próprio Claude Code, ou instale/atualize o Claude Code. No app Desktop o programa nem sempre está no PATH; o plugin tenta achá-lo sozinho.

## No chat do claude.ai, do app Desktop ou no Cowork

Não há terminal. Os comandos `configure` e `upgrade` mostram o passo a passo para você fazer manualmente. Para checagens completas use o Claude Code.

## O plugin não aparece no Claude Code na web

Precisa de um plano que inclua o Claude Code na web e do plugin instalado pela **Rota A**. Pode levar uma nova sessão para aparecer. Se não aparecer, avise os responsáveis.

## O plugin não aparece no Claude Code depois de instalar pela Rota A

O Claude Code precisa estar logado com a **conta do claude.ai** (não chave de API). Reinicie-o ou rode `/reload-plugins`.

## Textos com acentos aparecem estranhos (Windows)

Use o Windows Terminal ou o terminal do Claude Code (UTF-8). Avise os responsáveis com uma captura de tela.

## Ainda não resolveu?

Fale com os responsáveis: **<nomes>**. Informe: a rota (A ou B), o sistema (Windows/macOS/Linux), a versão (`claude plugin list`) e a mensagem que apareceu.
