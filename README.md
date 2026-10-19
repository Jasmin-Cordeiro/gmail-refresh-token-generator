# Gmail Refresh Token Generator

Script de linha de comando que gera o **`refresh_token` OAuth2 do Gmail** para as aplicações que acessam caixas de e-mail via OAuth2 (PagueContas e Mutuus).

Você faz login no browser com a conta desejada, autoriza o acesso e o script imprime o `refresh_token` no terminal. Nada é gravado em disco.

---

## Sumário

- [Para que serve](#para-que-serve)
- [Como funciona](#como-funciona)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [Gerando token para outra conta ou ambiente](#gerando-token-para-outra-conta-ou-ambiente)
- [Depois de gerar o token](#depois-de-gerar-o-token)
- [Problemas comuns](#problemas-comuns)
- [Segurança](#segurança)
- [Estrutura do repositório](#estrutura-do-repositório)

---

## Para que serve

Aplicações que leem ou modificam uma caixa do Gmail não guardam a senha da conta. Elas guardam um **refresh token**, uma credencial de longa duração que permite pedir *access tokens* novos ao Google sem interação humana.

Esse refresh token só pode ser obtido uma vez, passando por um login interativo no browser. Este script automatiza esse passo.

Use quando:
- for configurar uma nova caixa de e-mail em um ambiente (homologação, produção);
- o refresh token atual foi revogado, expirou ou foi perdido;
- as credenciais do app OAuth mudaram.

## Como funciona

Fluxo **Authorization Code com PKCE**:

1. O script lê o `config.json` e monta a URL de autorização do Google (`access_type=offline` e `prompt=consent`, que obrigam o Google a devolver um refresh token).
2. Abre essa URL no seu browser padrão (ou só imprime, com `--no-browser`).
3. Sobe um servidor temporário em `localhost` (porta do `redirect_uri`) e aguarda o Google redirecionar de volta com o `code`.
4. Confere o parâmetro `state` para garantir que o callback é legítimo.
5. Troca o `code` por tokens no endpoint do Google e imprime o `refresh_token`.

O servidor local só vive até o callback chegar (timeout de 180 s).

## Pré-requisitos

- **Python 3.9+** (`python3 --version`)
- **Credenciais do app OAuth** (`client_id` e `client_secret`). Ficam no cofre do time: *SquadColeta → Email → faturas.homologacao@paguecontas.asaas.com*
- No Google Cloud Console, o cliente OAuth deve ser do tipo **Web application** e ter este **URI de redirecionamento autorizado**:
  ```
  http://localhost:8080/oauth2callback
  ```
- **Porta 8080 livre** na sua máquina
- Acesso à conta Gmail para a qual o token será gerado

## Instalação

```bash
git clone <url-do-repositorio>
cd gmail-refresh-token-generator

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

A única dependência é o `google-auth-oauthlib`.

## Configuração

```bash
cp config.example.json config.json
```

Edite o `config.json`:

```json
{
  "client_id": "SEU_CLIENT_ID_AQUI",
  "client_secret": "SEU_CLIENT_SECRET_AQUI",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "redirect_uri": "http://localhost:8080/oauth2callback",
  "scopes": "https://www.googleapis.com/auth/gmail.modify"
}
```

| Campo | Descrição |
|---|---|
| `client_id` / `client_secret` | Credenciais do app OAuth (obrigatórios; pegue no cofre) |
| `redirect_uri` | Deve ser **exatamente** igual ao cadastrado no Google Cloud |
| `scopes` | Permissões pedidas, separadas por espaço. `gmail.modify` permite ler e alterar mensagens |
| `auth_uri` / `token_uri` | Endpoints do Google. Opcionais; os valores acima são o padrão |

> O `config.json` está no `.gitignore` e **nunca** deve ser commitado.

## Uso

```bash
python gerar_token.py
```

1. O browser abre na tela de login do Google.
2. Entre com a conta cujo token você quer gerar.
3. Aceite as permissões solicitadas.
4. A página mostra "Autenticado! Pode fechar esta janela."
5. No terminal aparece:
   ```
   refresh_token:
   1//0g...
   ```

### Opções

| Opção | Efeito |
|---|---|
| `--no-browser` | Não abre o browser; imprime a URL para você colar onde quiser (ex.: janela anônima) |
| `--config ARQUIVO` | Usa outro arquivo de configuração (padrão: `config.json`) |

## Gerando token para outra conta ou ambiente

**Outra conta Gmail:** o browser pode reaproveitar uma sessão já logada e autorizar a conta errada. Use `--no-browser` e cole a URL em uma **janela anônima**:

```bash
python gerar_token.py --no-browser
```

**Outro ambiente** (ex.: homologação e produção com apps OAuth diferentes): crie um config por ambiente e aponte para ele.

```bash
python gerar_token.py --config config.prod.json
```

Todo arquivo `config*.json` (exceto o `config.example.json`) já é ignorado pelo git.

## Depois de gerar o token

1. Copie o `refresh_token` do terminal.
2. Guarde-o no cofre de segredos da aplicação (Azure Key Vault, no fluxo atual do time) no ambiente correspondente.
3. Limpe o terminal e não guarde o valor em arquivos, chats ou tickets.

Gerar um token novo para a mesma conta e o mesmo app **não invalida automaticamente o anterior**, mas o Google limita a quantidade de refresh tokens ativos por par conta/app (os mais antigos deixam de valer). Atualize todos os ambientes que usam essa conta.

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `redirect_uri_mismatch` na tela do Google | O `redirect_uri` não está cadastrado no cliente OAuth | Cadastre `http://localhost:8080/oauth2callback` no Google Cloud (Credenciais → seu cliente OAuth) |
| `Não foi possível abrir a porta 8080` | Outro processo usa a porta | Feche o processo (`lsof -i :8080` no macOS/Linux, `netstat -ano` no Windows) e rode de novo. O script não encerra processos sozinho |
| "O Google não retornou refresh_token" | A conta já tinha autorizado o app e o Google não reemitiu | Revogue o acesso em <https://myaccount.google.com/permissions> e rode de novo |
| `invalid_client` ou `unauthorized_client` | `client_id`/`client_secret` errados ou de outro app | Reconfira os valores no cofre |
| `access_denied` | Conta não é usuária de teste do app, ou você recusou as permissões | Adicione a conta como usuário de teste na tela de consentimento, ou aceite as permissões |
| Timeout de 180 s | O login não foi concluído a tempo | Rode de novo |
| Token parou de funcionar depois de ~7 dias | App OAuth em modo **Testing** | Veja a seção abaixo |

### Expiração em 7 dias

Se a tela de consentimento OAuth estiver em **Testing** no Google Cloud, o Google invalida o refresh token após **7 dias**. Para um token duradouro, mude o status de publicação para **In production** (ou **Internal**, se o app e as contas pertencerem ao mesmo Google Workspace). Essa alteração é feita no Google Cloud Console, não neste código.

## Segurança

- O `refresh_token` e o `client_secret` equivalem a senhas: quem os tem acessa a caixa de e-mail com as permissões do escopo.
- O `config.json` e qualquer `token*.json` ou `client_secret*.json` estão no `.gitignore`. Mesmo assim, confira o `git status` antes de cada commit.
- O callback usa `http://localhost`. O script habilita `OAUTHLIB_INSECURE_TRANSPORT` apenas quando o `redirect_uri` é `localhost` ou `127.0.0.1`, porque a biblioteca exige https por padrão. O tráfego não sai da sua máquina.
- Peça apenas os escopos necessários. `gmail.modify` não permite excluir mensagens permanentemente; se a aplicação só lê, considere `gmail.readonly`.
- Se um token vazar, revogue em <https://myaccount.google.com/permissions> e gere outro.

## Estrutura do repositório

| Arquivo | Descrição | Vai pro git? |
|---|---|---|
| `gerar_token.py` | Script principal | Sim |
| `requirements.txt` | Dependências Python | Sim |
| `config.example.json` | Modelo de configuração, sem credenciais | Sim |
| `.gitignore` | Protege credenciais e ambiente local | Sim |
| `config.json` | Suas credenciais (criado por você) | **Não** |
| `.venv/` | Ambiente virtual local | **Não** |
