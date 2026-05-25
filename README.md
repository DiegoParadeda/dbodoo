# dbodoo

CLI Python para workflows de banco de dados Odoo/Doodba.

O projeto ainda esta no bootstrap inicial. A ideia e transformar scripts locais de
backup e restore em uma ferramenta instalavel via `pip`/`pipx`, sempre operando a
partir do diretorio atual (`Path.cwd()`).

## Instalacao

Para instalar em modo isolado com `pipx`:

```bash
pipx install dbodoo
```

Durante o desenvolvimento local:

```bash
pipx install --editable .
```

Ou, usando `pip` em um virtualenv:

```bash
python -m pip install -e .
```

## Uso

```bash
dbodoo hello
```

Saida esperada:

```text
Hello from dbodoo!
Project path: /caminho/do/projeto/atual
```

Para selecionar um remote definido no `.remotes.json` do diretorio atual:

```bash
dbodoo choose
```

Exemplo de `.remotes.json`:

```json
{
  "prod": {
    "remote_address": "example.odoo.com",
    "dbname": "prod",
    "password": "admin"
  },
  "staging": {
    "remote_address": "staging.odoo.com",
    "dbname": "staging",
    "password": "admin"
  }
}
```

Se houver apenas um remote, ele sera selecionado automaticamente. O comando imprime
o nome final do remote selecionado:

```text
prod
```

## Roadmap

- `backup`: baixar backups remotos via `/web/database/backup`
- `restore`: restaurar localmente usando `click-odoo-restoredb`
- `sync`: sincronizar ambientes
- autodeteccao de projetos Doodba
- suporte SSH
- leitura de `.remotes.json` na raiz do projeto atual
