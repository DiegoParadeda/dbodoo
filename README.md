# dbodoo

CLI Python para workflows de banco de dados Odoo/Doodba.

Automatiza backup remoto, restore local via Docker Compose e gerenciamento de
múltiplos ambientes, sempre operando a partir do diretório atual (`Path.cwd()`).

## Instalação

Modo isolado com `pipx` (recomendado):

```bash
pipx install dbodoo
```

Desenvolvimento local:

```bash
pipx install --editable .
# ou
pip install -e .
```

## Fluxo rápido

```bash
cd ~/projects/meu-projeto-doodba

# 1. Baixar backup do servidor remoto
dbodoo remote -b

# 2. Restaurar o ZIP baixado no banco local
dbodoo remote -r

# 3. Ou fazer os dois de uma vez
dbodoo remote -b -r
```

Se não existir `.remotes.json`, o wizard de configuração inicia
automaticamente no primeiro comando.

---

## Comandos

### `dbodoo init`

Cria ou atualiza o `.remotes.json` com wizard interativo.

```bash
dbodoo init
```

O wizard pergunta:

1. **Modo** — determina quais campos são necessários:
   - **Backup + Restore** — baixa o ZIP e restaura localmente (URL + senha + dbname)
   - **Backup only** — só baixa o ZIP (URL + senha + dbname)
   - **Restore only** — só restaura um ZIP já existente (apenas dbname)
2. Remote name (modos backup), database name, URL e senha

Se `.remotes.json` já existir, o wizard oferece adicionar um novo remote ou
sobrescrever o arquivo. Use `--force` para sobrescrever sem perguntar.

**Sem prompts (CI / scripts):**

```bash
# Backup + Restore
dbodoo init --name prod --dbname prod \
            --remote-address https://cliente.odoo.com/ \
            --password admin

# Restore-only (sem URL nem senha)
dbodoo init --name prod --dbname prod
```

---

### `dbodoo remote -b`

Baixa um ZIP de backup do servidor Odoo remoto.

```bash
dbodoo remote -b
```

- Conecta em `https://<remote_address>/web/database/backup`
- Exibe barra de progresso Rich durante o download
- Salva em `../<dbname>.zip` (um nível acima da raiz do projeto)
- Erros diferenciados: timeout, falha de conexão, senha incorreta (Odoo
  retorna HTML em vez do ZIP), HTTP 4xx/5xx

---

### `dbodoo remote -r`

Restaura o último ZIP baixado no banco de dados local via Docker Compose.

```bash
dbodoo remote -r

# Restaurar em banco diferente de 'devel' (padrão)
dbodoo remote -r --destination-db homolog
```

- Espera o ZIP em `../<dbname>.zip` — rode `-b` antes se não existir
- Detecta Docker Compose v2 (`docker compose`) com fallback para v1 (`docker-compose`)
- Executa `click-odoo-restoredb` dentro do serviço `odoo` via bind-mount read-only
- Se o banco de destino já existir, pergunta se quer reexecutar com `--force`
  (dropa e recria o banco) — nunca força automaticamente
- Emite aviso se o diretório não parecer um projeto Doodba (markers ausentes),
  mas não bloqueia

---

### `dbodoo remote -b -r`

Baixa o backup e restaura em uma única etapa.

```bash
dbodoo remote -b -r

# Com banco de destino explícito
dbodoo remote -b -r --destination-db homolog
```

Se o download falhar, o restore não é tentado.

---

### `dbodoo choose`

Seleciona e imprime o nome de um remote (útil em scripts).

```bash
dbodoo choose
```

Com um único remote configurado, seleção é automática.

---

## Estrutura do `.remotes.json`

O arquivo fica na raiz do projeto (ao lado do `docker-compose.yml`).

**Backup + Restore / Backup only:**

```json
{
  "prod": {
    "remote_address": "cliente.odoo.com",
    "dbname": "prod",
    "password": "senhamestre"
  },
  "staging": {
    "remote_address": "staging.cliente.odoo.com",
    "dbname": "staging",
    "password": "senhamestre"
  }
}
```

**Restore only** (sem conexão remota):

```json
{
  "prod": {
    "dbname": "prod"
  }
}
```

URLs são normalizadas ao salvar: `https://cliente.odoo.com:8069/` → `cliente.odoo.com:8069`.

---

## Detecção de projeto

O dbodoo localiza a raiz do projeto subindo o diretório a partir do `cwd`,
procurando por:

1. `.remotes.json`
2. Marcadores Doodba: `common.yaml`, `docker-compose.yml`, `odoo/custom/src`

A configuração é sempre local ao projeto — não existe arquivo global.

---

## Troubleshooting

### ZIP não encontrado ao restaurar

```text
Error: Backup ZIP not found at /home/.../projeto.zip.
Run dbodoo remote -b first to download it.
```

Execute `dbodoo remote -b` antes do restore.

---

### Senha incorreta no backup remoto

```text
Error: Authentication failed for 'cliente.odoo.com'. The server returned
an HTML page instead of a ZIP. Check the master password.
```

Verifique a senha em `.remotes.json` ou rode `dbodoo init` para atualizar.

---

### Banco de destino já existe

```text
Error: Destination database already exists: devel
⚠  click-odoo-restoredb exited with code 1.
? Rerun with --force? (drops and recreates the 'devel' database) (y/N)
```

Responda `y` para dropar e recriar o banco, ou `n` para cancelar sem alterar nada.

---

### Docker Compose não encontrado

```text
Error: Docker Compose not found. Install Docker with the Compose plugin (v2)
or 'docker-compose' (v1).
```

Instale o [Docker Desktop](https://docs.docker.com/get-docker/) ou o plugin
Compose: `apt install docker-compose-plugin`.

---

### Diretório não parece projeto Doodba

```text
Warning: This directory does not look like a Doodba project
(missing: common.yaml, docker-compose.yml, odoo/custom/src).
The Docker restore may not work as expected.
```

O restore continua, mas pode falhar se o serviço `odoo` não existir no
`docker-compose.yml`. Rode a partir da raiz do projeto Doodba.

---

### `.remotes.json` não encontrado

O comando `remote` inicia o wizard de configuração automaticamente. Para criar
o arquivo manualmente:

```bash
dbodoo init
```
