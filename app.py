"""Sistema simples de tarefas por setores.

Este arquivo concentra as rotas e as regras principais da aplicação. As funções
auxiliares ficam próximas do início para facilitar a leitura e a manutenção.
"""

import os
import sqlite3
from io import BytesIO
from datetime import datetime

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
)
DB = os.path.join(os.path.dirname(__file__), "tarefas.db")


# -----------------------------------------------------------------------------
# Banco de dados
# -----------------------------------------------------------------------------

def db():
    """Abre uma conexão SQLite com acesso às colunas pelo nome."""
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def now():
    """Retorna a data/hora atual em um formato curto e fácil de ler."""
    return datetime.now().isoformat(timespec="seconds")


def validate_password(password):
    """Exige uma senha minimamente resistente sem impor regras difíceis de usar."""
    if len(password) < 8:
        return "A senha deve ter pelo menos 8 caracteres."
    if not password.strip():
        return "A senha não pode ser composta apenas por espaços."
    return None


def init_db():
    """Cria as tabelas e prepara a compatibilidade com versões anteriores."""
    connection = db()
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS sectors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS user_sectors(
            user_id INTEGER,
            sector_id INTEGER,
            PRIMARY KEY(user_id, sector_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(sector_id) REFERENCES sectors(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS boards(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY(sector_id) REFERENCES sectors(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS columns(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            position INTEGER DEFAULT 0,
            FOREIGN KEY(board_id) REFERENCES boards(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            responsible_id INTEGER,
            priority TEXT DEFAULT 'Normal',
            due_date TEXT,
            notes TEXT DEFAULT '',
            created_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(column_id) REFERENCES columns(id) ON DELETE CASCADE,
            FOREIGN KEY(responsible_id) REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS task_assignees(
            task_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY(task_id, user_id),
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS checklist(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            task_id INTEGER,
            read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )

    # A versão anterior tinha apenas tasks.responsible_id. Copiamos esse
    # responsável para a nova tabela sem apagar a coluna antiga, mantendo
    # bancos já existentes funcionando normalmente.
    connection.execute(
        """
        INSERT OR IGNORE INTO task_assignees(task_id, user_id)
        SELECT id, responsible_id FROM tasks
        WHERE responsible_id IS NOT NULL
        """
    )

    if not connection.execute("SELECT id FROM users WHERE is_admin=1").fetchone():
        connection.execute(
            "INSERT INTO users(name, username, password, is_admin) VALUES(?,?,?,1)",
            ("Administrador", "admin", generate_password_hash("admin123")),
        )
    connection.commit()
    connection.close()


def get_assignee_ids(connection, task_id, fallback_id=None):
    """Busca os responsáveis de uma tarefa, usando o campo antigo como fallback."""
    rows = connection.execute(
        "SELECT user_id FROM task_assignees WHERE task_id=? ORDER BY user_id", (task_id,)
    ).fetchall()
    ids = [row["user_id"] for row in rows]
    return ids or ([fallback_id] if fallback_id else [])


def valid_assignee_ids(connection, raw_ids, sector_id):
    """Aceita somente usuários ativos que realmente pertencem ao setor."""
    ids = []
    for raw_id in raw_ids:
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if user_id not in ids:
            ids.append(user_id)

    if not ids:
        return []

    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"""
        SELECT u.id FROM users u
        JOIN user_sectors us ON us.user_id=u.id
        WHERE us.sector_id=? AND u.active=1 AND u.id IN ({placeholders})
        ORDER BY u.name
        """,
        [sector_id, *ids],
    ).fetchall()
    return [row["id"] for row in rows]


def save_assignees(connection, task_id, assignee_ids):
    """Substitui a lista de responsáveis e mantém o primeiro no campo antigo."""
    connection.execute("DELETE FROM task_assignees WHERE task_id=?", (task_id,))
    for user_id in assignee_ids:
        connection.execute(
            "INSERT INTO task_assignees(task_id, user_id) VALUES(?,?)", (task_id, user_id)
        )
    connection.execute(
        "UPDATE tasks SET responsible_id=? WHERE id=?",
        (assignee_ids[0] if assignee_ids else None, task_id),
    )


def notify_new_assignees(connection, task_id, title, assignee_ids, old_ids, actor_id, created_at):
    """Notifica apenas quem passou a receber a tarefa, evitando avisos repetidos."""
    for user_id in set(assignee_ids) - set(old_ids):
        if user_id != actor_id:
            connection.execute(
                "INSERT INTO notifications(user_id,text,task_id,created_at) VALUES(?,?,?,?)",
                (user_id, f"Você recebeu uma nova tarefa: {title}", task_id, created_at),
            )


# -----------------------------------------------------------------------------
# Usuário, acesso e contexto dos templates
# -----------------------------------------------------------------------------

def current_user():
    """Retorna o usuário logado ou None quando não há sessão."""
    if not session.get("user_id"):
        return None
    connection = db()
    person = connection.execute(
        "SELECT * FROM users WHERE id=? AND active=1", (session["user_id"],)
    ).fetchone()
    connection.close()
    if not person:
        session.clear()
    return person


def is_admin():
    person = current_user()
    return bool(person and person["is_admin"])


def can_access(sector_id):
    """Administradores acessam tudo; demais usuários usam seus setores."""
    person = current_user()
    if not person:
        return False
    if person["is_admin"]:
        return True
    connection = db()
    allowed = connection.execute(
        "SELECT 1 FROM user_sectors WHERE user_id=? AND sector_id=?",
        (person["id"], sector_id),
    ).fetchone()
    connection.close()
    return bool(allowed)


@app.context_processor
def template_context():
    person = current_user()
    unread = 0
    if person:
        connection = db()
        unread = connection.execute(
            "SELECT COUNT(*) AS total FROM notifications WHERE user_id=? AND read=0",
            (person["id"],),
        ).fetchone()["total"]
        connection.close()
    return dict(current_user=person, is_admin=is_admin(), unread=unread)


# -----------------------------------------------------------------------------
# Login e dashboard
# -----------------------------------------------------------------------------

@app.get("/")
def index():
    if not current_user():
        return redirect(url_for("login"))

    connection = db()
    person = current_user()
    if person["is_admin"]:
        sectors = connection.execute("SELECT * FROM sectors ORDER BY name").fetchall()
    else:
        sectors = connection.execute(
            """
            SELECT s.* FROM sectors s
            JOIN user_sectors us ON us.sector_id=s.id
            WHERE us.user_id=? ORDER BY s.name
            """,
            (person["id"],),
        ).fetchall()

    stats = []
    for sector in sectors:
        counts = connection.execute(
            """
            SELECT COUNT(*) AS total,
              SUM(CASE WHEN lower(col.name) LIKE '%feito%'
                    OR lower(col.name) LIKE '%conclu%'
                    OR lower(col.name) LIKE '%final%' THEN 1 ELSE 0 END) AS done
            FROM tasks t
            JOIN columns col ON col.id=t.column_id
            JOIN boards b ON b.id=col.board_id
            WHERE b.sector_id=?
            """,
            (sector["id"],),
        ).fetchone()
        total = counts["total"] or 0
        done = counts["done"] or 0
        stats.append((sector, total - done, done))

    overdue = connection.execute(
        """
        SELECT COUNT(*) AS total FROM tasks t
        JOIN columns col ON col.id=t.column_id
        WHERE t.due_date < date('now')
          AND lower(col.name) NOT LIKE '%feito%'
          AND lower(col.name) NOT LIKE '%conclu%'
          AND lower(col.name) NOT LIKE '%final%'
        """
    ).fetchone()["total"]
    today = connection.execute(
        "SELECT COUNT(*) AS total FROM tasks WHERE due_date=date('now')"
    ).fetchone()["total"]
    connection.close()
    return render_template("dashboard.html", stats=stats, overdue=overdue, today=today)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        connection = db()
        person = connection.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (username,)
        ).fetchone()
        connection.close()
        if person and check_password_hash(person["password"], password):
            session.clear()
            session["user_id"] = person["id"]
            return redirect(url_for("index"))
        flash("Usuário ou senha inválidos.")
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -----------------------------------------------------------------------------
# Setor e tarefas
# -----------------------------------------------------------------------------

@app.get("/sector/<int:sector_id>")
def sector(sector_id):
    if not can_access(sector_id):
        return redirect(url_for("index"))

    connection = db()
    sector_row = connection.execute(
        "SELECT * FROM sectors WHERE id=?", (sector_id,)
    ).fetchone()
    boards = connection.execute(
        "SELECT * FROM boards WHERE sector_id=? ORDER BY id", (sector_id,)
    ).fetchall()
    board_data = []
    for board in boards:
        columns = connection.execute(
            "SELECT * FROM columns WHERE board_id=? ORDER BY position,id", (board["id"],)
        ).fetchall()
        groups = []
        for column in columns:
            tasks = connection.execute(
                """
                SELECT t.*, u.name AS responsible,
                       COALESCE(group_concat(DISTINCT assigned.name), u.name) AS assignee_names
                FROM tasks t
                LEFT JOIN users u ON u.id=t.responsible_id
                LEFT JOIN task_assignees ta ON ta.task_id=t.id
                LEFT JOIN users assigned ON assigned.id=ta.user_id
                WHERE t.column_id=?
                GROUP BY t.id ORDER BY t.id DESC
                """,
                (column["id"],),
            ).fetchall()
            groups.append((column, tasks))
        board_data.append((board, groups))

    users = connection.execute(
        """
        SELECT u.* FROM users u
        JOIN user_sectors us ON us.user_id=u.id
        WHERE us.sector_id=? AND u.active=1 ORDER BY u.name
        """,
        (sector_id,),
    ).fetchall()
    connection.close()
    return render_template(
        "sector.html", sector=sector_row, boards=board_data, users=users, selected_assignee_ids=[]
    )


def task_form_values(connection, sector_id):
    """Lê e valida os campos comuns aos formulários de criar e editar."""
    assignee_ids = valid_assignee_ids(
        connection, request.form.getlist("responsible_ids"), sector_id
    )
    return {
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "priority": request.form.get("priority", "Normal"),
        "due_date": request.form.get("due_date") or None,
        "notes": request.form.get("notes", "").strip(),
        "assignee_ids": assignee_ids,
    }


@app.post("/task/create")
def create_task():
    person = current_user()
    if not person:
        return redirect(url_for("login"))

    sector_id = int(request.form["sector_id"])
    if not can_access(sector_id):
        return "Sem acesso", 403

    connection = db()
    column = connection.execute(
        """
        SELECT c.*, b.sector_id FROM columns c
        JOIN boards b ON b.id=c.board_id WHERE c.id=?
        """,
        (request.form["column_id"],),
    ).fetchone()
    if not column or column["sector_id"] != sector_id:
        connection.close()
        return "Inválido", 400

    values = task_form_values(connection, sector_id)
    if not values["title"]:
        connection.close()
        flash("Informe um título para a tarefa.")
        return redirect(url_for("sector", sector_id=sector_id))

    created_at = now()
    cursor = connection.execute(
        """
        INSERT INTO tasks(column_id,title,description,responsible_id,priority,due_date,notes,
                          created_by,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            column["id"], values["title"], values["description"],
            values["assignee_ids"][0] if values["assignee_ids"] else None,
            values["priority"], values["due_date"], values["notes"],
            person["id"], created_at, created_at,
        ),
    )
    task_id = cursor.lastrowid
    save_assignees(connection, task_id, values["assignee_ids"])

    for line in request.form.get("checklist", "").splitlines():
        if line.strip():
            connection.execute(
                "INSERT INTO checklist(task_id,text) VALUES(?,?)", (task_id, line.strip())
            )
    notify_new_assignees(
        connection, task_id, values["title"], values["assignee_ids"], [], person["id"], created_at
    )
    connection.execute(
        "INSERT INTO logs(user_id,action,created_at) VALUES(?,?,?)",
        (person["id"], f"Criou a tarefa: {values['title']}", created_at),
    )
    connection.commit()
    connection.close()
    return redirect(url_for("sector", sector_id=sector_id))


@app.route("/task/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    person = current_user()
    if not person:
        return redirect(url_for("login"))

    connection = db()
    task_row = connection.execute(
        """
        SELECT t.*, col.name AS column_name, col.position, b.id AS board_id,
               b.name AS board_name, b.sector_id
        FROM tasks t
        JOIN columns col ON col.id=t.column_id
        JOIN boards b ON b.id=col.board_id
        WHERE t.id=?
        """,
        (task_id,),
    ).fetchone()
    if not task_row or not can_access(task_row["sector_id"]):
        connection.close()
        return "Sem acesso", 403

    sector_id = task_row["sector_id"]
    if request.method == "GET":
        users = connection.execute(
            """
            SELECT u.* FROM users u
            JOIN user_sectors us ON us.user_id=u.id
            WHERE us.sector_id=? AND u.active=1 ORDER BY u.name
            """,
            (sector_id,),
        ).fetchall()
        assignee_ids = get_assignee_ids(connection, task_id, task_row["responsible_id"])
        connection.close()
        return render_template(
            "task_edit.html", task=task_row, users=users, selected_assignee_ids=assignee_ids
        )

    values = task_form_values(connection, sector_id)
    if not values["title"]:
        connection.close()
        flash("Informe um título para a tarefa.")
        return redirect(url_for("edit_task", task_id=task_id))

    old_ids = get_assignee_ids(connection, task_id, task_row["responsible_id"])
    updated_at = now()
    connection.execute(
        """
        UPDATE tasks SET title=?, description=?, responsible_id=?, priority=?, due_date=?,
                         notes=?, updated_at=? WHERE id=?
        """,
        (
            values["title"], values["description"],
            values["assignee_ids"][0] if values["assignee_ids"] else None,
            values["priority"], values["due_date"], values["notes"], updated_at, task_id,
        ),
    )
    save_assignees(connection, task_id, values["assignee_ids"])
    notify_new_assignees(
        connection, task_id, values["title"], values["assignee_ids"], old_ids,
        person["id"], updated_at,
    )
    connection.execute(
        "INSERT INTO logs(user_id,action,created_at) VALUES(?,?,?)",
        (person["id"], f"Editou a tarefa: {values['title']}", updated_at),
    )
    connection.commit()
    connection.close()
    return redirect(url_for("task", task_id=task_id))


@app.get("/task/<int:task_id>")
def task(task_id):
    person = current_user()
    if not person:
        return redirect(url_for("login"))

    connection = db()
    task_row = connection.execute(
        """
        SELECT t.*, col.name AS column_name, col.position, b.id AS board_id,
               b.name AS board_name, b.sector_id, u.name AS responsible,
               COALESCE(group_concat(DISTINCT assigned.name), u.name) AS assignee_names
        FROM tasks t
        JOIN columns col ON col.id=t.column_id
        JOIN boards b ON b.id=col.board_id
        LEFT JOIN users u ON u.id=t.responsible_id
        LEFT JOIN task_assignees ta ON ta.task_id=t.id
        LEFT JOIN users assigned ON assigned.id=ta.user_id
        WHERE t.id=? GROUP BY t.id
        """,
        (task_id,),
    ).fetchone()
    if not task_row or not can_access(task_row["sector_id"]):
        connection.close()
        return "Sem acesso", 403

    checks = connection.execute(
        "SELECT * FROM checklist WHERE task_id=? ORDER BY id", (task_id,)
    ).fetchall()
    assignees = connection.execute(
        """
        SELECT u.name FROM task_assignees ta
        JOIN users u ON u.id=ta.user_id WHERE ta.task_id=? ORDER BY u.name
        """,
        (task_id,),
    ).fetchall()
    if not assignees and task_row["responsible"]:
        assignees = [{"name": task_row["responsible"]}]
    previous = connection.execute(
        "SELECT * FROM columns WHERE board_id=? AND position<? ORDER BY position DESC LIMIT 1",
        (task_row["board_id"], task_row["position"]),
    ).fetchone()
    next_column = connection.execute(
        "SELECT * FROM columns WHERE board_id=? AND position>? ORDER BY position LIMIT 1",
        (task_row["board_id"], task_row["position"]),
    ).fetchone()
    connection.close()
    return render_template(
        "task.html", task=task_row, checks=checks, prev=previous,
        nxt=next_column, assignees=assignees,
    )


# -----------------------------------------------------------------------------
# Avançar, voltar, checklist e notificações
# -----------------------------------------------------------------------------

@app.post("/task/advance")
def advance():
    person = current_user()
    if not person:
        return jsonify(ok=False, message="Sua sessão expirou. Entre novamente."), 401
    return move_task(request.form["task_id"], forward=True, person=person)


@app.post("/task/back")
def back():
    person = current_user()
    if not person:
        return jsonify(ok=False, message="Sua sessão expirou. Entre novamente."), 401
    return move_task(request.form["task_id"], forward=False, person=person)


def move_task(task_id, forward, person):
    """Move uma tarefa uma etapa para frente ou para trás."""
    connection = db()
    task_row = connection.execute(
        """
        SELECT t.*, col.board_id, col.position, b.sector_id
        FROM tasks t JOIN columns col ON col.id=t.column_id
        JOIN boards b ON b.id=col.board_id WHERE t.id=?
        """,
        (task_id,),
    ).fetchone()
    if not task_row or not can_access(task_row["sector_id"]):
        connection.close()
        return jsonify(ok=False, message="Você não tem permissão para alterar esta tarefa."), 403

    comparison = ">" if forward else "<"
    ordering = "ASC" if forward else "DESC"
    edge_key = "done" if forward else "start"
    destination = connection.execute(
        f"SELECT * FROM columns WHERE board_id=? AND position{comparison}? ORDER BY position {ordering} LIMIT 1",
        (task_row["board_id"], task_row["position"]),
    ).fetchone()
    if not destination:
        connection.close()
        return jsonify(ok=False, **{edge_key: True})

    changed_at = now()
    connection.execute(
        "UPDATE tasks SET column_id=?, updated_at=? WHERE id=?",
        (destination["id"], changed_at, task_id),
    )
    action = "Avançou" if forward else "Voltou"
    connection.execute(
        "INSERT INTO logs(user_id,action,created_at) VALUES(?,?,?)",
        (person["id"], f"{action} a tarefa #{task_id} para {destination['name']}", changed_at),
    )
    connection.commit()
    connection.close()
    return jsonify(ok=True)


@app.post("/check/<int:check_id>")
def check(check_id):
    connection = db()
    row = connection.execute("SELECT * FROM checklist WHERE id=?", (check_id,)).fetchone()
    if not row:
        connection.close()
        return "Não encontrado", 404
    connection.execute("UPDATE checklist SET done=1-done WHERE id=?", (check_id,))
    connection.commit()
    connection.close()
    return redirect(request.referrer or url_for("index"))


@app.get("/notifications")
def notifications():
    if not current_user():
        return redirect(url_for("login"))
    person = current_user()
    connection = db()
    notes = connection.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100",
        (person["id"],),
    ).fetchall()
    connection.execute("UPDATE notifications SET read=1 WHERE user_id=?", (person["id"],))
    connection.commit()
    connection.close()
    return render_template("notifications.html", notes=notes)


# -----------------------------------------------------------------------------
# Administração
# -----------------------------------------------------------------------------

@app.get("/admin")
def panel():
    if not is_admin():
        return redirect(url_for("index"))
    connection = db()
    sectors = connection.execute("SELECT * FROM sectors ORDER BY name").fetchall()
    selected_sector = request.args.get("sector", "").strip()
    user_query = "SELECT DISTINCT u.* FROM users u"
    user_params = []
    if selected_sector.isdigit():
        user_query += " JOIN user_sectors filter_us ON filter_us.user_id=u.id AND filter_us.sector_id=?"
        user_params.append(int(selected_sector))
    user_query += " ORDER BY u.name"
    users = connection.execute(user_query, user_params).fetchall()
    access = {
        person["id"]: [row["sector_id"] for row in connection.execute(
            "SELECT sector_id FROM user_sectors WHERE user_id=?", (person["id"],)
        )]
        for person in users
    }
    logs = connection.execute(
        """
        SELECT l.*, u.name FROM logs l LEFT JOIN users u ON u.id=l.user_id
        ORDER BY l.id DESC LIMIT 30
        """
    ).fetchall()
    metrics = {
        "users": connection.execute("SELECT COUNT(*) AS total FROM users WHERE is_admin=0 AND active=1").fetchone()["total"],
        "sectors": connection.execute("SELECT COUNT(*) AS total FROM sectors").fetchone()["total"],
        "open_tasks": connection.execute(
            """SELECT COUNT(*) AS total FROM tasks t JOIN columns c ON c.id=t.column_id
               WHERE lower(c.name) NOT LIKE '%feito%' AND lower(c.name) NOT LIKE '%conclu%' AND lower(c.name) NOT LIKE '%final%'"""
        ).fetchone()["total"],
        "without_access": connection.execute(
            """SELECT COUNT(*) AS total FROM users u LEFT JOIN user_sectors us ON us.user_id=u.id
               WHERE u.is_admin=0 AND u.active=1 AND us.user_id IS NULL"""
        ).fetchone()["total"],
    }
    connection.close()
    return render_template("admin.html", sectors=sectors, users=users, access=access, logs=logs, metrics=metrics, selected_sector=selected_sector)


@app.get("/admin/report.pdf")
def admin_report():
    """Gera um relatório PDF do estado atual da administração."""
    if not is_admin():
        return "Não autorizado", 403
    connection = db()
    sectors = connection.execute("SELECT * FROM sectors ORDER BY name").fetchall()
    users = connection.execute("SELECT * FROM users WHERE is_admin=0 ORDER BY name").fetchall()
    access = {}
    for person in users:
        access[person["id"]] = connection.execute(
            """SELECT s.name FROM sectors s JOIN user_sectors us ON us.sector_id=s.id
               WHERE us.user_id=? ORDER BY s.name""", (person["id"],)
        ).fetchall()
    metrics = {
        "users": len(users),
        "sectors": len(sectors),
        "open_tasks": connection.execute(
            """SELECT COUNT(*) AS total FROM tasks t JOIN columns c ON c.id=t.column_id
               WHERE lower(c.name) NOT LIKE '%feito%' AND lower(c.name) NOT LIKE '%conclu%' AND lower(c.name) NOT LIKE '%final%'"""
        ).fetchone()["total"],
        "without_access": sum(1 for person in users if not access[person["id"]]),
    }
    logs = connection.execute(
        """SELECT l.*, u.name FROM logs l LEFT JOIN users u ON u.id=l.user_id
           ORDER BY l.id DESC LIMIT 20"""
    ).fetchall()
    connection.close()

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, leading=26, textColor=colors.HexColor("#3b2d25"), alignment=TA_CENTER, spaceAfter=5)
    subtitle_style = ParagraphStyle("ReportSubtitle", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#766b64"), alignment=TA_CENTER, spaceAfter=16)
    section_style = ParagraphStyle("ReportSection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=colors.HexColor("#b95113"), spaceBefore=13, spaceAfter=7)
    small_style = ParagraphStyle("ReportSmall", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#514741"))
    story = [Paragraph("Relatório administrativo", title_style), Paragraph(f"Sistema de tarefas · Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}", subtitle_style)]
    metric_data = [[Paragraph("Usuários ativos", small_style), Paragraph("Setores", small_style), Paragraph("Tarefas abertas", small_style), Paragraph("Sem acesso", small_style)], [str(metrics["users"]), str(metrics["sectors"]), str(metrics["open_tasks"]), str(metrics["without_access"])]]
    metric_table = Table(metric_data, colWidths=[43 * mm] * 4)
    metric_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fff1e5")), ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#b95113")), ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"), ("FONTSIZE", (0, 1), (-1, 1), 17), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#e8ddd5")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#e8ddd5")), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [metric_table, Paragraph("Usuários e acessos", section_style)]
    user_data = [["Nome", "Usuário", "Setores", "Status"]]
    for person in users:
        sector_names = ", ".join(row["name"] for row in access[person["id"]]) or "Sem acesso"
        user_data.append([person["name"], f"@{person['username']}", Paragraph(sector_names, small_style), "Ativo" if person["active"] else "Inativo"])
    if len(user_data) == 1:
        user_data.append(["Nenhum usuário comum cadastrado", "—", "—", "—"])
    users_table = Table(user_data, colWidths=[39 * mm, 32 * mm, 85 * mm, 22 * mm], repeatRows=1)
    users_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#47705b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#d8c6ba")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fffaf6")]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(users_table)
    story.append(Paragraph("Histórico recente", section_style))
    log_data = [["Data", "Responsável", "Ação"]]
    for log in logs:
        log_data.append([log["created_at"].replace("T", " "), log["name"] or "Sistema", Paragraph(log["action"], small_style)])
    if len(log_data) == 1:
        log_data.append(["—", "—", "Sem registros"])
    logs_table = Table(log_data, colWidths=[35 * mm, 40 * mm, 103 * mm], repeatRows=1)
    logs_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b95113")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#d8c6ba")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fffaf6")]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.append(logs_table)
    document.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="relatorio-administrativo.pdf")


@app.post("/admin/user/<int:user_id>/edit")
def edit_user(user_id):
    """Atualiza os dados básicos e os setores de um usuário comum."""
    actor = current_user()
    if not actor or not actor["is_admin"]:
        return "Não autorizado", 403
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip()
    if not name or not username:
        flash("Nome e usuário são obrigatórios.")
        return redirect(url_for("panel"))
    connection = db()
    target = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not target or target["is_admin"]:
        connection.close()
        flash("Apenas usuários comuns podem ser editados nesta tela.")
        return redirect(url_for("panel"))
    duplicate = connection.execute(
        "SELECT id FROM users WHERE username=? AND id<>?", (username, user_id)
    ).fetchone()
    if duplicate:
        connection.close()
        flash("Esse nome de usuário já está em uso.")
        return redirect(url_for("panel"))
    changed_at = now()
    connection.execute("UPDATE users SET name=?, username=? WHERE id=?", (name, username, user_id))
    connection.execute("DELETE FROM user_sectors WHERE user_id=?", (user_id,))
    for sector_id in request.form.getlist("sectors"):
        connection.execute("INSERT INTO user_sectors(user_id,sector_id) VALUES(?,?)", (user_id, int(sector_id)))
    connection.execute(
        "INSERT INTO logs(user_id,action,created_at) VALUES(?,?,?)",
        (actor["id"], f"Editou os dados de {name} (@{username})", changed_at),
    )
    connection.commit()
    connection.close()
    flash(f"Dados de {name} atualizados.")
    return redirect(url_for("panel"))


@app.post("/account/password")
def change_own_password():
    """Permite ao usuário trocar a própria senha conhecendo a atual."""
    person = current_user()
    if not person:
        return redirect(url_for("login"))
    current = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirmation = request.form.get("confirm_password", "")
    error = validate_password(new_password)
    if not check_password_hash(person["password"], current):
        error = "A senha atual está incorreta."
    elif new_password != confirmation:
        error = "A confirmação da nova senha não confere."
    elif new_password == current:
        error = "A nova senha deve ser diferente da atual."
    if error:
        flash(error)
        return redirect(url_for("panel") if person["is_admin"] else url_for("index"))
    changed_at = now()
    connection = db()
    connection.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(new_password), person["id"]))
    connection.execute("INSERT INTO logs(user_id,action,created_at) VALUES(?,?,?)", (person["id"], "Alterou a própria senha", changed_at))
    connection.commit()
    connection.close()
    flash("Sua senha foi alterada com sucesso.")
    return redirect(url_for("panel") if person["is_admin"] else url_for("index"))


@app.post("/admin/user/<int:user_id>/password")
def reset_user_password(user_id):
    """Redefine a senha sem jamais revelar a senha antiga ao administrador."""
    actor = current_user()
    if not actor or not actor["is_admin"]:
        return "Não autorizado", 403
    new_password = request.form.get("new_password", "")
    confirmation = request.form.get("confirm_password", "")
    error = validate_password(new_password)
    if new_password != confirmation:
        error = "A confirmação da nova senha não confere."
    connection = db()
    target = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not target:
        connection.close()
        flash("Usuário não encontrado.")
        return redirect(url_for("panel"))
    if error:
        connection.close()
        flash(error)
        return redirect(url_for("panel"))
    changed_at = now()
    connection.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(new_password), user_id))
    connection.execute("INSERT INTO logs(user_id,action,created_at) VALUES(?,?,?)", (actor["id"], f"Redefiniu a senha de {target['name']} (@{target['username']})", changed_at))
    connection.commit()
    connection.close()
    flash(f"Senha de {target['name']} redefinida. Entregue a nova senha com segurança ao usuário.")
    return redirect(url_for("panel"))


@app.post("/admin/user/<int:user_id>/delete")
def delete_user(user_id):
    """Exclui um usuário comum e remove seus vínculos sem apagar o histórico."""
    actor = current_user()
    if not actor or not actor["is_admin"]:
        return "Não autorizado", 403

    connection = db()
    target = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not target:
        connection.close()
        flash("Usuário não encontrado.")
        return redirect(url_for("panel"))
    if target["is_admin"]:
        connection.close()
        flash("Administradores não podem ser excluídos por esta tela.")
        return redirect(url_for("panel"))
    if target["id"] == actor["id"]:
        connection.close()
        flash("Você não pode excluir a própria conta enquanto está administrando o sistema.")
        return redirect(url_for("panel"))

    deleted_at = now()
    connection.execute("UPDATE tasks SET responsible_id=NULL WHERE responsible_id=?", (user_id,))
    connection.execute("DELETE FROM task_assignees WHERE user_id=?", (user_id,))
    connection.execute("DELETE FROM user_sectors WHERE user_id=?", (user_id,))
    connection.execute("DELETE FROM notifications WHERE user_id=?", (user_id,))
    connection.execute("DELETE FROM users WHERE id=?", (user_id,))
    connection.execute(
        "INSERT INTO logs(user_id,action,created_at) VALUES(?,?,?)",
        (actor["id"], f"Excluiu o usuário {target['name']} (@{target['username']})", deleted_at),
    )
    connection.commit()
    connection.close()
    flash(f"Usuário {target['name']} excluído. As tarefas dele foram mantidas.")
    return redirect(url_for("panel"))


@app.post("/admin/sector")
def add_sector():
    if not is_admin():
        return "Não autorizado", 403
    connection = db()
    try:
        sector_id = connection.execute(
            "INSERT INTO sectors(name,description) VALUES(?,?)",
            (request.form["name"].strip(), request.form.get("description", "")),
        ).lastrowid
        board_id = connection.execute(
            "INSERT INTO boards(sector_id,name) VALUES(?,?)", (sector_id, "Tarefas")
        ).lastrowid
        for position, name in enumerate(["A fazer", "Em andamento", "Feito"]):
            connection.execute(
                "INSERT INTO columns(board_id,name,position) VALUES(?,?,?)",
                (board_id, name, position),
            )
        connection.commit()
    except sqlite3.IntegrityError:
        flash("Esse setor já existe.")
    connection.close()
    return redirect(url_for("panel"))


@app.post("/admin/user")
def add_user():
    if not is_admin():
        return "Não autorizado", 403
    password_error = validate_password(request.form.get("password", ""))
    if password_error:
        flash(password_error)
        return redirect(url_for("panel"))
    connection = db()
    try:
        user_id = connection.execute(
            "INSERT INTO users(name,username,password) VALUES(?,?,?)",
            (request.form["name"], request.form["username"], generate_password_hash(request.form["password"])),
        ).lastrowid
        for sector_id in request.form.getlist("sectors"):
            connection.execute(
                "INSERT INTO user_sectors(user_id,sector_id) VALUES(?,?)",
                (user_id, int(sector_id)),
            )
        connection.commit()
    except sqlite3.IntegrityError:
        flash("Esse usuário já existe.")
    connection.close()
    return redirect(url_for("panel"))


@app.post("/admin/access")
def access():
    if not is_admin():
        return "Não autorizado", 403
    user_id = int(request.form["user_id"])
    connection = db()
    connection.execute("DELETE FROM user_sectors WHERE user_id=?", (user_id,))
    for sector_id in request.form.getlist("sectors"):
        connection.execute(
            "INSERT INTO user_sectors(user_id,sector_id) VALUES(?,?)",
            (user_id, int(sector_id)),
        )
    connection.commit()
    connection.close()
    return redirect(url_for("panel"))


if __name__ == "__main__":
    init_db()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
