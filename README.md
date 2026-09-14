# Sistema de tarefas por setores

Sistema web em Flask para organizar tarefas por setores, quadros e etapas. A aplicação possui autenticação individual, controle de acesso, administração de usuários, notificações, dashboard, histórico e exportação de relatório administrativo em PDF.

## Visão geral

O sistema foi desenvolvido para ser utilizado por equipes com diferentes níveis de familiaridade com tecnologia. Cada usuário acessa somente os setores autorizados. Administradores possuem acesso global e podem gerenciar usuários, setores e permissões.

O fluxo padrão de uma tarefa é:

```text
A fazer → Em andamento → Feito
```

Também é possível retornar uma tarefa para uma etapa anterior, editar seus dados, definir prazo, prioridade, observações, checklist e vários responsáveis.

## Principais recursos

| Área | Recursos disponíveis |
|---|---|
| Acesso | Login individual, sessão protegida, logout e senhas armazenadas com hash. |
| Tarefas | Criação, edição, descrição, prioridade, prazo, observações e checklist. |
| Fluxo | Avançar, voltar, iniciar, concluir e reabrir tarefas. |
| Responsáveis | Uma ou várias pessoas podem ser responsáveis pela mesma tarefa. |
| Setores | Setores com quadros e colunas próprias. |
| Permissões | Usuários podem receber acesso a setores específicos. |
| Notificações | Avisos internos quando uma tarefa é atribuída. |
| Administração | Dashboard de indicadores, edição de usuários, busca, filtro e histórico. |
| Relatórios | Exportação de relatório administrativo em PDF. |
| Interface | Layout responsivo para computador e celular. |
| Aparência | Modo claro e modo escuro persistente. |
| Ícones | Ícones SVG locais, sem emojis na interface. |

## Requisitos

- Python 3.10 ou superior.
- `pip` disponível no ambiente.
- Navegador moderno.
- Windows, Linux ou macOS.

As dependências estão listadas em [`requirements.txt`](requirements.txt). A biblioteca ReportLab é necessária para a geração do PDF.

## Instalação no Windows

Abra o Prompt de Comando ou PowerShell na pasta do projeto e execute:

```bat
py -m pip install -r requirements.txt
```

Depois, inicie a aplicação:

```bat
py app.py
```

Se o comando `py` não estiver disponível, use:

```bat
python -m pip install -r requirements.txt
python app.py
```

Acesse no navegador:

```text
http://127.0.0.1:5000
```

Para confirmar especificamente a instalação do ReportLab:

```bat
py -c "import reportlab; print('ReportLab instalado com sucesso')"
```

### Ambiente virtual recomendado

O uso de ambiente virtual evita conflitos com outros projetos Python:

```bat
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py app.py
```

No Linux ou macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 app.py
```

## Primeiro acesso

Na primeira execução, o banco SQLite é criado automaticamente e um administrador padrão é inserido:

| Campo | Valor inicial |
|---|---|
| Usuário | `admin` |
| Senha | `admin123` |

Altere essa senha imediatamente em **Administração → Minha senha**. Em ambiente real, também configure uma chave secreta própria.

## Uso da aplicação

### Dashboard

Após o login, o dashboard mostra um resumo das tarefas atrasadas, tarefas para hoje e setores disponíveis. Cada setor possui um cartão com a quantidade de tarefas pendentes e concluídas.

### Setores e tarefas

Ao abrir um setor, os quadros aparecem divididos por etapas. Para criar uma tarefa, use o botão de nova tarefa na coluna desejada. Uma tarefa pode conter:

- título;
- descrição;
- um ou mais responsáveis;
- prioridade;
- prazo;
- observações;
- checklist.

Os botões de movimentação alteram a etapa sem exigir que a tarefa seja editada manualmente.

### Notificações

Quando uma pessoa é adicionada como responsável por uma tarefa, ela recebe uma notificação interna. A quantidade de notificações não lidas aparece no ícone de notificações do cabeçalho.

## Administração

A tela de administração está disponível em `/admin` para usuários administradores.

### Dashboard administrativo

O painel apresenta quatro indicadores:

| Indicador | Descrição |
|---|---|
| Usuários ativos | Quantidade de usuários comuns ativos. |
| Setores | Quantidade de setores cadastrados. |
| Tarefas abertas | Tarefas que ainda não estão em uma etapa final. |
| Sem acesso | Usuários ativos que não possuem nenhum setor vinculado. |

### Usuários e acessos

A lista administrativa permite buscar por nome ou usuário e filtrar por setor. Cada pessoa apresenta um resumo dos setores vinculados.

O menu **Ações** permite:

- editar nome;
- editar nome de usuário;
- alterar os setores autorizados;
- redefinir a senha;
- excluir o usuário.

A exclusão exige que o administrador digite exatamente o nome da pessoa e confirme a operação. As tarefas são preservadas, mas o responsável removido deixa de ficar vinculado a elas. A operação também é registrada no histórico.

Administradores não podem ser excluídos por essa tela.

### Relatório PDF

O botão **Exportar relatório PDF** gera um arquivo chamado `relatorio-administrativo.pdf` contendo:

- data e hora da geração;
- indicadores administrativos;
- usuários e seus setores;
- status das contas;
- histórico administrativo recente.

A rota também pode ser acessada diretamente por:

```text
/admin/report.pdf
```

A rota exige uma sessão autenticada de administrador.

## Modo escuro

O modo escuro pode ser ativado pelo botão **Modo escuro** no cabeçalho. Na tela de login, o botão aparece no próprio cartão de acesso.

A preferência é salva no navegador usando `localStorage`. Na primeira visita, caso não exista uma preferência salva, o sistema acompanha a preferência de tema do sistema operacional.

No modo escuro:

- fundos e cartões recebem cores escuras;
- textos e bordas são ajustados para manter contraste;
- ícones SVG ficam brancos para facilitar a leitura;
- a logo e imagens de conteúdo não são alteradas pelo filtro dos ícones.

## Ícones e imagens

A interface não utiliza emojis. Os elementos visuais são SVGs locais armazenados em `static/icons/`. A coleção utilizada é o [Lucide Icons][1], uma biblioteca de ícones escaláveis e de código aberto.

Os ícones são usados em navegação, dashboard, setores, tarefas, prazos, responsáveis, prioridades, ações administrativas e notificações. Isso evita diferenças de aparência entre sistemas operacionais e navegadores.

## Estrutura do projeto

```text
sistema_tarefas_v3/
├── app.py                    # Rotas, regras de negócio e geração do PDF
├── tarefas.db                # Banco SQLite criado pela aplicação
├── requirements.txt          # Dependências Python
├── README.md                 # Esta documentação
├── GUIA-DO-ESTUDANTE.md      # Guia complementar da estrutura
├── templates/                # Páginas HTML Jinja
│   ├── admin.html
│   ├── dashboard.html
│   ├── login.html
│   ├── notifications.html
│   ├── sector.html
│   ├── task.html
│   └── task_edit.html
└── static/
    ├── style.css             # Tokens globais e modo escuro
    ├── admin.css             # Estilos da administração
    ├── dashboard.css         # Estilos do dashboard
    ├── sector.css            # Estilos dos setores
    ├── task.css              # Estilos das tarefas
    ├── login.css             # Estilos do login
    ├── notifications.css     # Estilos das notificações
    ├── app.js                # Interações, busca e tema
    ├── logo-sitio-agar.png   # Logo da aplicação
    └── icons/                # Ícones SVG locais
```

## Banco de dados

O sistema usa SQLite e cria as tabelas automaticamente na primeira execução. As principais tabelas são:

| Tabela | Finalidade |
|---|---|
| `users` | Usuários, senhas com hash, status e perfil de administrador. |
| `sectors` | Setores disponíveis. |
| `user_sectors` | Relação entre usuários e setores. |
| `boards` | Quadros de cada setor. |
| `columns` | Etapas dos quadros. |
| `tasks` | Tarefas e seus dados principais. |
| `task_assignees` | Relação entre tarefas e vários responsáveis. |
| `checklist` | Itens de checklist das tarefas. |
| `notifications` | Notificações internas. |
| `logs` | Histórico de ações administrativas e movimentações. |

A aplicação ativa `PRAGMA foreign_keys=ON` para manter os relacionamentos consistentes.

## Configuração de produção

Defina uma chave secreta forte por variável de ambiente:

Windows PowerShell:

```powershell
$env:SECRET_KEY="uma-chave-longa-e-aleatoria"
py app.py
```

Windows Prompt de Comando:

```bat
set SECRET_KEY=uma-chave-longa-e-aleatoria
py app.py
```

Linux ou macOS:

```bash
export SECRET_KEY="uma-chave-longa-e-aleatoria"
python3 app.py
```

Para HTTPS, configure também:

```text
COOKIE_SECURE=1
```

O modo debug fica desligado por padrão. Use `FLASK_DEBUG=1` somente em desenvolvimento local.

## Backup

Para fazer um backup básico, pare a aplicação e copie o arquivo:

```text
tarefas.db
```

Exemplo no Windows:

```bat
copy tarefas.db tarefas-backup.db
```

Exemplo no Linux ou macOS:

```bash
cp tarefas.db tarefas-backup.db
```

Em produção, mantenha cópias em local separado e teste periodicamente a restauração.

## Testes e validações

A validação manual recomendada inclui:

1. Entrar com o usuário administrador.
2. Criar um setor.
3. Criar um usuário comum.
4. Atribuir o usuário ao setor.
5. Criar e movimentar uma tarefa.
6. Confirmar o recebimento da notificação.
7. Testar a busca e o filtro administrativo.
8. Editar o usuário.
9. Alterar uma senha.
10. Exportar o relatório PDF.
11. Alternar entre modo claro e modo escuro.
12. Confirmar a leitura dos ícones em ambos os temas.

## Solução de problemas

### `ModuleNotFoundError: No module named 'reportlab'`

Instale as dependências usando o mesmo interpretador utilizado para iniciar o sistema:

```bat
py -m pip install -r requirements.txt
```

Se estiver usando um ambiente virtual, ative-o antes da instalação:

```bat
.venv\Scripts\activate
py -m pip install -r requirements.txt
```

Confirme com:

```bat
py -c "import reportlab; print(reportlab.__version__)"
```

### A aplicação abre, mas o CSS não aparece

Confirme que a pasta `static` está no mesmo nível de `app.py` e que o sistema está sendo iniciado a partir da pasta do projeto.

### O banco não aparece

O arquivo `tarefas.db` é criado quando `app.py` é executado. Verifique se o usuário do sistema possui permissão de escrita na pasta do projeto.

### O relatório não é baixado

Confirme que o usuário conectado é administrador e que o pacote ReportLab está instalado no ambiente Python em uso.

## Licenças

Os ícones Lucide são distribuídos sob a licença ISC. Consulte a licença oficial para detalhes sobre uso e redistribuição.[1]

O ReportLab é utilizado como dependência para a geração do arquivo PDF.[2]

## Referências

[1]: https://lucide.dev/license "Licença oficial do Lucide Icons"
[2]: https://docs.reportlab.com/ "Documentação oficial do ReportLab"
