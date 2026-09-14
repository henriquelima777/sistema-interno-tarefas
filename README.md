# Sistema de tarefas

Sistema simples de tarefas por setores, feito para ser usado por qualquer funcionário, independentemente do nível de familiaridade com tecnologia.

## Fluxo principal

```text
A FAZER → INICIAR → EM ANDAMENTO → CONCLUIR → FEITO
                         ↑                         ↓
                         └──────── REABRIR ───────┘
```

Também é possível voltar uma etapa, abrir o detalhe da tarefa e editar seus dados.

## Recursos

O sistema possui login individual, administrador, setores, controle de acesso por setor, quadros e etapas, tarefas com título, descrição, prazo, prioridade e checklist, notificações internas, dashboard, histórico básico, edição de tarefas e vários responsáveis para a mesma tarefa. A interface funciona em computador e celular.

## Primeiro acesso

Usuário: `admin`  
Senha: `admin123`

Altere a senha e a chave secreta antes de usar o sistema em produção. Senhas são armazenadas com hash: não podem ser visualizadas, apenas trocadas ou redefinidas.

## Executar

```bash
pip install -r requirements.txt
python app.py
```

Acesse `http://127.0.0.1:5000`. O banco `tarefas.db` é criado automaticamente na primeira execução. Para produção, configure `SECRET_KEY` e, se estiver usando HTTPS, `COOKIE_SECURE=1`. O debug fica desligado por padrão; habilite somente localmente com `FLASK_DEBUG=1`.

## Documentação para estudantes

Consulte [`GUIA-DO-ESTUDANTE.md`](GUIA-DO-ESTUDANTE.md) para entender a estrutura dos arquivos, as tabelas, as rotas de edição e o relacionamento entre tarefas e vários responsáveis.

## Observação sobre atualização do banco

A tabela `task_assignees` é criada automaticamente. A inicialização também copia para ela os responsáveis existentes no campo antigo `tasks.responsible_id`, para que bancos criados em versões anteriores continuem funcionando.
