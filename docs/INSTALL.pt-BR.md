# Instalação do plugin ISG Model Alignment

> Guia para quem vai **usar** o plugin. Cada rota cabe em uma página.
> Antes de começar, leia a seção 1 para saber qual rota é a sua.

## 1. Antes de tudo

**O que você precisa (tudo gratuito):**

- Um plano do Claude **Pro, Max, Ultra, Team ou Enterprise**. O plano gratuito (Free) **não** é suportado.
- Uma **conta pessoal no GitHub** (https://github.com/signup). Dica: adicione e verifique também o seu e-mail institucional nessa conta, para sabermos quem é quem. **Não compartilhe contas.**
- **Ser convidado** para o repositório `<org>/isg-plugins` (peça a um dos responsáveis: **<nomes dos responsáveis>**) e **aceitar o convite** que chega por e-mail.

**Onde você vai usar?**

| Onde | Rota |
|---|---|
| Chat do claude.ai, chat do app Desktop, Cowork | **Rota A** (conta do claude.ai) |
| Claude Code (terminal, aba Código do app Desktop) | **Rota A** (recomendada) ou **Rota B** |
| Claude Code na web (claude.ai/code) | **Rota A** |

Use **uma rota só** por computador. Se instalar pelas duas, as versões podem divergir.

## 2. Rota A — pela sua conta do claude.ai (recomendada)

Uma única instalação vale para o chat, o Cowork e o Claude Code.

1. Abra o **claude.ai** (ou o app Desktop) e vá em **Customize > Plugins**.
   *(O nome dos botões pode estar em inglês ou português na sua tela. Se não achar, procure "Plugins" em "Personalizar".)*
2. Clique em **Add > Add marketplace**.
3. Digite `<org>/isg-plugins` e confirme.
4. Se pedir, **conecte sua conta do GitHub** e autorize o app **Claude**.
   Se aparecer "sem acesso", o convite ainda não foi aceito ou o app Claude ainda não tem acesso ao repositório: fale com os responsáveis.
5. Abra o marketplace **isg-plugins**, escolha **ISG Model Alignment** e clique em **Add**.
6. Ligue **"Sync automatically"** para receber as novas versões sozinho.
7. **Claude Code:** feche e abra de novo (logado com a **mesma conta do claude.ai**, não com chave de API). O plugin aparece como `isg-model-alignment@synced`.

**Conferir:** digite `/` em uma conversa e procure `isg-model-alignment`. No Claude Code, rode `/isg-model-alignment:configure`.

**Atualizar:** automático com "Sync automatically". Para forçar: **Customize > Plugins > Check for updates**; depois reinicie o Claude Code.

## 3. Rota B — pelo Claude Code, neste computador

Só para quem usa o Claude Code e não pode usar a Rota A (e para a equipe de manutenção).

**Uma vez só — instale:**

- **Claude Code** (versão 2.1.317 ou mais nova), **Git** (https://git-scm.com), **GitHub CLI** (https://cli.github.com) e **Node.js LTS** 20 ou mais (https://nodejs.org).

**Uma vez só — configure o acesso:**

```bash
gh auth login
gh auth setup-git
```

Em `gh auth login` escolha **GitHub.com** e **HTTPS**. Depois defina a variável de ambiente `CLAUDE_CODE_PLUGIN_PREFER_HTTPS` com o valor `1` (no Windows: Configurações > Variáveis de ambiente do usuário; ou deixe o `/isg-model-alignment:configure` fazer isso por você).

**Instalar (2 comandos):**

```bash
claude plugin marketplace add <org>/isg-plugins#stable
claude plugin install isg-model-alignment@isg-plugins
```

Abra o Claude Code e rode `/isg-model-alignment:configure`.

**Atualizar:** `/isg-model-alignment:upgrade` (mostra o que mudou e pede a sua confirmação). Depois reinicie o Claude Code ou rode `/reload-plugins`.

## 4. Rota C — organização Team/Enterprise (para quem administra)

Se o dono da sua organização no Claude bloqueou "adicionar marketplace", ele pode sincronizar este repositório em **Organization settings > Plugins & skills**.
**Atenção:** assim **todos os membros** dessa organização do Claude recebem o plugin, mesmo sem acesso ao GitHub. Use só se isso for aceitável. Veja `docs/RELEASING.md`.

## 5. Se você sair da equipe

Peça para remover o plugin da sua conta do claude.ai (Customize > Plugins). O acesso ao repositório é removido pelos responsáveis. Cópias já instaladas continuam funcionando na última versão, mas não recebem novas versões.

## 6. Problemas?

Veja `docs/TROUBLESHOOTING.pt-BR.md`.
