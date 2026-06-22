import hashlib
import os
import sqlite3
from pathlib import Path

from core.paths import DB_PATH

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────
--  Пользователи
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT    NOT NULL UNIQUE,
    password_hash TEXT   NOT NULL,
    is_admin     INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
--  Статьи
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT,
    title       TEXT    NOT NULL,
    content     TEXT,
    summary     TEXT,                            -- NULL пока не суммаризирована
    source      TEXT,
    language    TEXT    DEFAULT 'ru',
    category    TEXT,
    embedding   BLOB,                            -- NULL пока не вычислен
    is_favorite INTEGER NOT NULL DEFAULT 0,
    file_path   TEXT    DEFAULT '',              -- путь к скачанному файлу
    authors     TEXT    DEFAULT '',              -- через запятую
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(url, user_id)                         -- один пользователь не сохраняет статью дважды
);

-- ─────────────────────────────────────────────
--  Теги
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    -- name всегда хранится в нижнем регистре — нормализуй через normalize_tag()
    name TEXT NOT NULL UNIQUE
);

-- ─────────────────────────────────────────────
--  Связь статей и тегов  (составной PK — без дублей)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id)     ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

-- ─────────────────────────────────────────────
--  Персоны
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS persons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);

-- ─────────────────────────────────────────────
--  Упоминания персон в статьях
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS person_mentions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL REFERENCES persons(id)  ON DELETE CASCADE,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    context    TEXT,                                     -- фрагмент текста с упоминанием
    UNIQUE(person_id, article_id, context)               -- нет дублирующих упоминаний
);

-- ─────────────────────────────────────────────
--  История поиска
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS search_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    query         TEXT    NOT NULL,
    results_count INTEGER NOT NULL DEFAULT 0,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    searched_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
--  Индексы для ускорения частых запросов
-- ─────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_articles_user_id    ON articles(user_id);
CREATE INDEX IF NOT EXISTS idx_articles_source     ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_category   ON articles(category);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);
CREATE INDEX IF NOT EXISTS idx_articles_favorite   ON articles(user_id, is_favorite);

CREATE INDEX IF NOT EXISTS idx_persons_user_id     ON persons(user_id);

CREATE INDEX IF NOT EXISTS idx_mentions_person     ON person_mentions(person_id);
CREATE INDEX IF NOT EXISTS idx_mentions_article    ON person_mentions(article_id);

CREATE INDEX IF NOT EXISTS idx_history_user_id     ON search_history(user_id);
CREATE INDEX IF NOT EXISTS idx_history_searched_at ON search_history(searched_at);

CREATE INDEX IF NOT EXISTS idx_article_tags_tag    ON article_tags(tag_id);

-- ─────────────────────────────────────────────
--  Настройки приложения (key-value)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

-- ─────────────────────────────────────────────
--  Записи созданных документов
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT    NOT NULL,
    fields_json   TEXT    NOT NULL DEFAULT '{}',
    output_path   TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_doc_records_user ON document_records(user_id);
CREATE INDEX IF NOT EXISTS idx_doc_records_tpl  ON document_records(template_name);

-- ─────────────────────────────────────────────
--  Списки значений для полей документов
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doc_field_lists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    list_name   TEXT    NOT NULL,
    item_value  TEXT    NOT NULL,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(list_name, item_value, user_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_field_lists_user ON doc_field_lists(user_id);
CREATE INDEX IF NOT EXISTS idx_doc_field_lists_name ON doc_field_lists(user_id, list_name);
"""


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Возвращает соединение с включёнными FK и WAL-журналом."""
    path = Path(db_path) if db_path else DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row          # доступ к колонкам по имени
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    """Создаёт все таблицы, индексы и дефолтного admin при первом запуске."""
    with get_connection(db_path) as conn:
        conn.executescript(_SCHEMA)
        # миграции для существующих БД
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE articles ADD COLUMN file_path TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE articles ADD COLUMN authors TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS app_settings "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')"
            )
        except Exception:
            pass
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS document_records ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "template_name TEXT NOT NULL, "
                "fields_json TEXT NOT NULL DEFAULT '{}', "
                "output_path TEXT, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE)"
            )
        except Exception:
            pass
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS doc_field_lists ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "list_name TEXT NOT NULL, "
                "item_value TEXT NOT NULL, "
                "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
                "sort_order INTEGER NOT NULL DEFAULT 0, "
                "UNIQUE(list_name, item_value, user_id))"
            )
        except Exception:
            pass
    ensure_default_admin(db_path)


# ─────────────────────────────────────────────
#  Пароли
# ─────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """SHA-256 с солью: 'hex_salt:hex_digest'."""
    salt = os.urandom(16).hex()
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}:{digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split(":", 1)
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == digest
    except ValueError:
        return False


# ─────────────────────────────────────────────
#  Пользователи
# ─────────────────────────────────────────────

def create_user(username: str, password: str | None = None,
                is_admin: bool = False,
                db_path: str | Path | None = None) -> int:
    """Создаёт пользователя. Если password=None — пароль не задан (нужно установить при первом входе)."""
    pw_hash = _hash_password(password) if password else ""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, is_admin) VALUES(?, ?, ?)",
            (username, pw_hash, int(is_admin)),
        )
        return cur.lastrowid


def authenticate_user(username: str, password: str,
                      db_path: str | Path | None = None) -> dict | None:
    """Возвращает dict пользователя или None при неверных данных.
    Если пароль не задан — dict содержит needs_password=True."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        return None
    if row["password_hash"] == "":
        return dict(row) | {"needs_password": True}
    if _verify_password(password, row["password_hash"]):
        return dict(row)
    return None


def reset_password(username: str, new_password: str,
                   db_path: str | Path | None = None) -> bool:
    """Сбрасывает пароль пользователя. Возвращает False если пользователь не найден."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash=? WHERE username=?",
            (_hash_password(new_password), username),
        )
        return cur.rowcount > 0


def get_all_users(db_path: str | Path | None = None) -> list[dict]:
    """Возвращает список всех пользователей (без password_hash)."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, username, is_admin, created_at FROM users ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_user(username: str, db_path: str | Path | None = None) -> bool:
    """Удаляет пользователя. Возвращает False если не найден."""
    with get_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM users WHERE username=?", (username,))
        return cur.rowcount > 0


def ensure_default_admin(db_path: str | Path | None = None) -> None:
    """При первом запуске создаёт учётную запись admin / admin с правами админа."""
    with get_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count == 0:
            conn.execute(
                "INSERT INTO users(username, password_hash, is_admin) VALUES(?, ?, 1)",
                ("admin", _hash_password("admin")),
            )
        else:
            # гарантируем что admin всегда имеет права админа
            conn.execute(
                "UPDATE users SET is_admin=1 WHERE username='admin'"
            )


# ─────────────────────────────────────────────
#  Теги
# ─────────────────────────────────────────────

def normalize_tag(name: str) -> str:
    """Приводит имя тега к нижнему регистру перед сохранением в БД.

    SQLite COLLATE NOCASE работает только для ASCII, поэтому нормализацию
    кириллицы делаем на стороне Python.
    """
    return name.strip().lower()


# ─────────────────────────────────────────────
#  История поиска
# ─────────────────────────────────────────────

def save_search_history(
    query:         str,
    results_count: int,
    user_id:       int,
    db_path:       "str | Path | None" = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO search_history (query, results_count, user_id) VALUES (?, ?, ?)",
            (query, results_count, user_id),
        )


def get_search_history(
    user_id:  int,
    limit:    int = 10,
    db_path:  "str | Path | None" = None,
) -> list[dict]:
    """Возвращает уникальные запросы пользователя, отсортированные по дате (новые первыми)."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT query, MAX(searched_at) AS searched_at
               FROM search_history
               WHERE user_id = ?
               GROUP BY query
               ORDER BY searched_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  Статьи
# ─────────────────────────────────────────────

def save_downloaded_article(
    title:     str,
    url:       str,
    source:    str,
    year:      str,
    file_path: str,
    user_id:   int,
    authors:   "list[str] | None" = None,
    db_path:   "str | Path | None" = None,
) -> int:
    """Сохраняет запись о скачанной статье. Если запись уже есть — обновляет поля.
    Возвращает id статьи в БД."""
    authors_str = ", ".join(authors) if authors else ""
    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM articles WHERE url = ? AND user_id = ?",
            (url, user_id),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE articles SET file_path = ?, authors = ? WHERE id = ?",
                (file_path, authors_str, existing["id"]),
            )
            return existing["id"]
        cur = conn.execute(
            """INSERT INTO articles (url, title, source, file_path, authors, user_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url, title, source, file_path, authors_str, user_id),
        )
        return cur.lastrowid


def get_user_articles(
    user_id: int,
    db_path: "str | Path | None" = None,
) -> list[dict]:
    """Все статьи пользователя, новые сверху."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT id, url, title, source, file_path, authors, created_at, is_favorite
               FROM articles
               WHERE user_id = ?
               ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_article(
    article_id: int,
    db_path: "str | Path | None" = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))


# ─────────────────────────────────────────────
#  Настройки приложения
# ─────────────────────────────────────────────

def get_setting(key: str, default: str = "",
                db_path: "str | Path | None" = None) -> str:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else default


def save_setting(key: str, value: str,
                 db_path: "str | Path | None" = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_user_setting(user_id: int, key: str, default: str = "",
                     db_path: "str | Path | None" = None) -> str:
    return get_setting(f"user_{user_id}_{key}", default, db_path)


def save_user_setting(user_id: int, key: str, value: str,
                      db_path: "str | Path | None" = None) -> None:
    save_setting(f"user_{user_id}_{key}", value, db_path)


# ─────────────────────────────────────────────
#  Эмбеддинги
# ─────────────────────────────────────────────

def save_embedding(
    article_id: int,
    embedding:  list,
    db_path:    "str | Path | None" = None,
) -> bool:
    import numpy as np
    blob = np.array(embedding, dtype=np.float32).tobytes()
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "UPDATE articles SET embedding = ? WHERE id = ?",
            (blob, article_id),
        )
        return cur.rowcount > 0


def get_articles_with_embeddings(
    user_id: "int | None" = None,
    db_path: "str | Path | None" = None,
) -> list[dict]:
    import numpy as np
    sql = "SELECT id, title, summary, embedding FROM articles WHERE embedding IS NOT NULL"
    params: list = []
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["embedding"] = np.frombuffer(d["embedding"], dtype=np.float32).tolist()
        result.append(d)
    return result


def search_similar_articles(
    query_embedding: list,
    top_k:           int = 5,
    user_id:         "int | None" = None,
    db_path:         "str | Path | None" = None,
) -> list[dict]:
    import numpy as np
    q  = np.array(query_embedding, dtype=np.float32)
    qn = np.linalg.norm(q)

    sql = "SELECT id, title, summary, url, embedding FROM articles WHERE embedding IS NOT NULL"
    params: list = []
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    scored = []
    for r in rows:
        v  = np.frombuffer(r["embedding"], dtype=np.float32)
        vn = np.linalg.norm(v)
        score = float(np.dot(q, v) / (qn * vn)) if (qn > 0 and vn > 0) else 0.0
        scored.append({
            "id":      r["id"],
            "title":   r["title"],
            "summary": r["summary"],
            "url":     r["url"],
            "score":   score,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ─────────────────────────────────────────────
#  Записи документов
# ─────────────────────────────────────────────

def save_document_record(
    template_name: str,
    fields:        dict,
    output_path:   "str | None",
    user_id:       int,
    db_path:       "str | Path | None" = None,
) -> int:
    import json as _json
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO document_records (template_name, fields_json, output_path, user_id)"
            " VALUES (?, ?, ?, ?)",
            (template_name, _json.dumps(fields, ensure_ascii=False), output_path, user_id),
        )
        return cur.lastrowid


def get_document_records(
    user_id:  int,
    db_path:  "str | Path | None" = None,
) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, template_name, fields_json, output_path, created_at"
            " FROM document_records WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_document_record(
    record_id: int,
    db_path:   "str | Path | None" = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM document_records WHERE id = ?", (record_id,))


# ─────────────────────────────────────────────
#  Списки значений для полей документов
# ─────────────────────────────────────────────

def get_doc_list_names(
    user_id: int,
    db_path: "str | Path | None" = None,
) -> list:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT list_name FROM doc_field_lists WHERE user_id = ? ORDER BY list_name",
            (user_id,),
        ).fetchall()
    return [r["list_name"] for r in rows]


def get_doc_list_items(
    list_name: str,
    user_id:   int,
    db_path:   "str | Path | None" = None,
) -> list:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT item_value FROM doc_field_lists"
            " WHERE list_name = ? AND user_id = ? ORDER BY sort_order, item_value",
            (list_name, user_id),
        ).fetchall()
    return [r["item_value"] for r in rows]


def add_doc_list_item(
    list_name:  str,
    item_value: str,
    user_id:    int,
    db_path:    "str | Path | None" = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO doc_field_lists (list_name, item_value, user_id)"
            " VALUES (?, ?, ?)",
            (list_name, item_value, user_id),
        )


def delete_doc_list_item(
    list_name:  str,
    item_value: str,
    user_id:    int,
    db_path:    "str | Path | None" = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "DELETE FROM doc_field_lists WHERE list_name = ? AND item_value = ? AND user_id = ?",
            (list_name, item_value, user_id),
        )


def delete_doc_list(
    list_name: str,
    user_id:   int,
    db_path:   "str | Path | None" = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "DELETE FROM doc_field_lists WHERE list_name = ? AND user_id = ?",
            (list_name, user_id),
        )


def rename_doc_list(
    old_name: str,
    new_name: str,
    user_id:  int,
    db_path:  "str | Path | None" = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE doc_field_lists SET list_name = ? WHERE list_name = ? AND user_id = ?",
            (new_name, old_name, user_id),
        )
