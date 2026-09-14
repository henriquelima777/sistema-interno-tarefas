# Guia do estudante

Este projeto é um sistema pequeno de tarefas feito com **Flask**, **SQLite**, HTML, CSS e JavaScript. A ideia é manter cada parte visível e fácil de testar, sem separar o projeto em muitas camadas difíceis de acompanhar.

## Como executar

No terminal, entre na pasta `sistema_tarefas_v3` e execute:

```bash
pip install -r requirements.txt
python app.py
```

Depois, abra `http://127.0.0.1:5000`. No primeiro acesso, o sistema cria o banco `tarefas.db` e o usuário administrativo padrão `admin`, com senha `admin123`.

## Onde alterar cada parte

| Arquivo | Responsabilidade |
|---|---|
| `app.py` | Banco de dados, regras de acesso, rotas e gravação das tarefas. |
| `templates/base.html` | Cabeçalho, navegação e estrutura comum das páginas. |
| `templates/dashboard.html` | Dashboard com contadores e setores. |
| `templates/sector.html` | Quadro por etapas e formulário de nova tarefa. |
| `templates/task.html` | Visualização de uma tarefa, checklist e movimentação. |
| `templates/task_edit.html` | Formulário de edição de uma tarefa. |
| `templates/admin.html` | Cadastro de setores, usuários e acessos. |
| `static/style.css` | Aparência, espaçamento e responsividade. |
| `static/app.js` | Ações de avançar e voltar sem criar formulários extras. |

## Fluxo de uma tarefa

Uma tarefa é criada em uma coluna, normalmente `A fazer`. Os botões de ação usam as rotas `/task/advance` e `/task/back` para alterar apenas a etapa. A edição usa `GET /task/<id>/edit` para mostrar o formulário e `POST /task/<id>/edit` para salvar os campos.

A tabela `tasks` guarda os dados principais da tarefa. A tabela `checklist` guarda os itens do checklist. A nova tabela `task_assignees` faz a ligação entre tarefas e usuários:

```text
tasks 1 ---- vários task_assignees vários ---- 1 users
```

A coluna antiga `tasks.responsible_id` foi mantida por compatibilidade. Ela guarda o primeiro responsável, enquanto `task_assignees` guarda a lista completa. Na inicialização, tarefas antigas são copiadas automaticamente para a nova tabela.

## Como funciona a seleção de responsáveis

O formulário envia vários campos com o mesmo nome:

```html
<input type="checkbox" name="responsible_ids" value="3">
<input type="checkbox" name="responsible_ids" value="5">
```

No Flask, todos eles são lidos com:

```python
request.form.getlist("responsible_ids")
```

A função `valid_assignee_ids` confirma se as pessoas estão ativas e pertencem ao setor da tarefa. Isso evita gravar usuários de outros setores. Quando uma nova pessoa é incluída na tarefa, `notify_new_assignees` cria uma notificação para ela.

## Um caminho simples para fazer uma alteração

Comece pela tela que será modificada. Depois localize a rota correspondente em `app.py`, altere o template HTML e, por último, ajuste o CSS. Ao criar uma nova regra, prefira uma função pequena com nome claro, como `save_assignees` ou `move_task`, em vez de colocar toda a lógica dentro da rota.

Após cada alteração, execute:

```bash
python -m py_compile app.py
python app.py
```

Em seguida, teste manualmente no navegador. Para mudanças no banco, altere `init_db` com cuidado e mantenha compatibilidade com bancos já existentes sempre que possível.

## Convenções usadas no código

As funções e variáveis usam nomes em inglês por serem nomes comuns no código, enquanto os textos exibidos ao usuário estão em português. As consultas SQL usam parâmetros `?`, e não concatenação de strings, para evitar problemas com valores digitados pelo usuário. As conexões são fechadas após cada operação e as transações são confirmadas com `commit()` somente quando os dados estão prontos para serem salvos.

O objetivo desta organização não é criar um sistema complexo, mas deixar claro **onde cada comportamento acontece**. Uma boa próxima prática é alterar uma coisa pequena por vez, testar o fluxo relacionado e só depois iniciar a próxima melhoria.
