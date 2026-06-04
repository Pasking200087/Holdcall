"""
server.py — FastAPI-сервер базы контактов
Хранит baza.db и baza.key локально; клиенты подключаются по HTTPS.
"""
import os
import sqlite3
import threading
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# ─── CONFIG ──────────────────────────────────────────────────────────────────

DATA_DIR = os.environ.get("BAZA_DATA_DIR", "/opt/baza/data")
DB_PATH  = os.path.join(DATA_DIR, "baza.db")
KEY_PATH = os.path.join(DATA_DIR, "baza.key")
JWT_FILE = os.path.join(DATA_DIR, "jwt_secret.txt")
JWT_ALG  = "HS256"
JWT_DAYS = 30

STATUS_HIDDEN = {"irrelevant", "no_answer", "rude"}
CONTACT_PERSON = "person"

def _jwt_secret() -> str:
    p = Path(JWT_FILE)
    if p.exists():
        return p.read_text().strip()
    s = secrets.token_hex(32)
    p.write_text(s)
    return s

JWT_SECRET = _jwt_secret()

# ─── CRYPTO ──────────────────────────────────────────────────────────────────

_fernet: Optional[Fernet] = None

def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = Path(KEY_PATH).read_bytes().strip()
        _fernet = Fernet(key)
    return _fernet

def _enc(text: str) -> str:
    if not text:
        return ""
    return _get_fernet().encrypt(text.encode()).decode()

def _dec(text: str) -> str:
    if not text:
        return ""
    try:
        return _get_fernet().decrypt(text.encode()).decode()
    except Exception:
        return text  # уже открытый текст (legacy)

# ─── DATABASE ────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _decrypt_row(row) -> dict:
    d = dict(row)
    d["name"]    = _dec(d.get("name", ""))
    d["phone"]   = _dec(d.get("phone", ""))
    d["company"] = _dec(d.get("company", ""))
    return d

_CONTACTS_SQL = (
    "SELECT c.*, u.full_name as caller_name, u.username as caller_username "
    "FROM contacts c LEFT JOIN users u ON c.called_by = u.id "
    "{where} ORDER BY c.call_date DESC, c.id DESC"
)

def _contacts_where(status_filter, type_filter, hide_irrelevant, date_from, date_to):
    where = "WHERE c.is_deleted=0"
    params: list = []
    if status_filter:
        where += " AND c.status=?"
        params.append(status_filter)
    elif hide_irrelevant:
        ph = ",".join("?" * len(STATUS_HIDDEN))
        where += f" AND c.status NOT IN ({ph})"
        params.extend(STATUS_HIDDEN)
    if type_filter:
        where += " AND c.contact_type=?"
        params.append(type_filter)
    if date_from:
        where += " AND c.call_date >= ?"
        params.append(date_from)
    if date_to:
        where += " AND c.call_date <= ?"
        params.append(date_to + " 23:59:59")
    return where, params

# ─── APP & AUTH ───────────────────────────────────────────────────────────────

app = FastAPI(title="Baza API", docs_url=None, redoc_url=None)
_bearer = HTTPBearer()

def _make_token(user: dict) -> str:
    payload = {
        "sub":       str(user["id"]),
        "username":  user["username"],
        "role":      user["role"],
        "full_name": user.get("full_name") or "",
        "exp":       datetime.utcnow() + timedelta(days=JWT_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def _get_payload(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    try:
        return jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Токен истёк, войдите заново")
    except Exception:
        raise HTTPException(401, "Неверный токен")

def _admin(p: dict = Depends(_get_payload)) -> dict:
    if p["role"] not in ("owner", "admin"):
        raise HTTPException(403, "Недостаточно прав")
    return p

def _owner(p: dict = Depends(_get_payload)) -> dict:
    if p["role"] != "owner":
        raise HTTPException(403, "Только для владельца")
    return p

# ─── MODELS ──────────────────────────────────────────────────────────────────

class LoginReq(BaseModel):
    username: str
    password: str

class ContactCreate(BaseModel):
    name: str = ""
    phone: str
    company: str = ""
    position: str = ""
    contact_type: str = "person"
    comment: str = ""

class ContactUpdate(BaseModel):
    name: str = ""
    phone: str
    company: str = ""
    position: str = ""
    contact_type: str = "person"
    comment: str = ""

class CallMark(BaseModel):
    status: str
    call_result: str = ""

class DeleteBulk(BaseModel):
    ids: list[int]

class ImportRow(BaseModel):
    name: str = ""
    phone: str
    company: str = ""
    position: str = ""
    contact_type: str = "person"
    comment: str = ""

class ImportReq(BaseModel):
    rows: list[ImportRow]

class UserCreate(BaseModel):
    username: str
    password_hash: str  # bcrypt-хэш, клиент хэширует сам
    role: str
    full_name: str = ""

class UserUpdate(BaseModel):
    full_name: str
    role: str
    active: int
    password_hash: Optional[str] = None

class PasswordChange(BaseModel):
    old_password: str   # открытый текст
    new_password: str   # открытый текст

class LogEntry(BaseModel):
    action: str
    details: str = ""

# ─── ROUTES: AUTH ────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/login")
def login(req: LoginReq):
    c = _conn()
    try:
        row = c.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (req.username,)
        ).fetchone()
    finally:
        c.close()
    if not row:
        raise HTTPException(401, "Неверный логин или пароль")
    if not bcrypt.checkpw(req.password.encode(), row["password"].encode()):
        raise HTTPException(401, "Неверный логин или пароль")
    token = _make_token(dict(row))
    return {"token": token, "role": row["role"],
            "full_name": row["full_name"] or "", "user_id": row["id"]}

@app.get("/auth/me")
def auth_me(p: dict = Depends(_get_payload)):
    """Проверить действительность токена и вернуть данные пользователя."""
    c = _conn()
    try:
        row = c.execute(
            "SELECT id, username, role, full_name, active FROM users WHERE id=?",
            (int(p["sub"]),)
        ).fetchone()
    finally:
        c.close()
    if not row or not row["active"]:
        raise HTTPException(401, "Пользователь деактивирован")
    return dict(row)

@app.post("/logout")
def logout(p: dict = Depends(_get_payload)):
    return {"ok": True}

# ─── ROUTES: CONTACTS ────────────────────────────────────────────────────────

@app.get("/contacts")
def get_contacts(
    status_filter: str = "",
    type_filter: str = "",
    hide_irrelevant: bool = False,
    date_from: str = "",
    date_to: str = "",
    p: dict = Depends(_get_payload),
):
    where, params = _contacts_where(status_filter, type_filter, hide_irrelevant, date_from, date_to)
    c = _conn()
    try:
        rows = c.execute(_CONTACTS_SQL.format(where=where), params).fetchall()
    finally:
        c.close()
    return [_decrypt_row(r) for r in rows]

@app.get("/contacts/count")
def get_contacts_count(p: dict = Depends(_get_payload)):
    c = _conn()
    try:
        rows = c.execute(
            "SELECT status, COUNT(*) as cnt FROM contacts WHERE is_deleted=0 GROUP BY status"
        ).fetchall()
    finally:
        c.close()
    return {r["status"]: r["cnt"] for r in rows}

@app.post("/contacts")
def create_contact(req: ContactCreate, p: dict = Depends(_get_payload)):
    user_id = int(p["sub"])
    c = _conn()
    try:
        cur = c.execute(
            "INSERT INTO contacts (name,phone,company,position,contact_type,comment,status,created_at,created_by)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (_enc(req.name), _enc(req.phone), _enc(req.company),
             req.position, req.contact_type, req.comment, "new", _now(), user_id)
        )
        c.commit()
        return {"id": cur.lastrowid}
    finally:
        c.close()

@app.put("/contacts/{cid}")
def update_contact(cid: int, req: ContactUpdate, p: dict = Depends(_admin)):
    c = _conn()
    try:
        c.execute(
            "UPDATE contacts SET name=?,phone=?,company=?,position=?,contact_type=?,comment=? WHERE id=?",
            (_enc(req.name), _enc(req.phone), _enc(req.company),
             req.position, req.contact_type, req.comment, cid)
        )
        c.commit()
    finally:
        c.close()
    return {"ok": True}

@app.post("/contacts/{cid}/call")
def mark_call(cid: int, req: CallMark, p: dict = Depends(_get_payload)):
    user_id = int(p["sub"])
    c = _conn()
    try:
        c.execute(
            "UPDATE contacts SET status=?,call_result=?,called_by=?,call_date=? WHERE id=?",
            (req.status, req.call_result, user_id, _now(), cid)
        )
        c.commit()
    finally:
        c.close()
    return {"ok": True}

@app.delete("/contacts")
def delete_contacts(req: DeleteBulk, p: dict = Depends(_admin)):
    c = _conn()
    try:
        ph = ",".join("?" * len(req.ids))
        c.execute(f"UPDATE contacts SET is_deleted=1 WHERE id IN ({ph})", req.ids)
        c.commit()
    finally:
        c.close()
    return {"ok": True}

@app.post("/contacts/import")
def import_contacts(req: ImportReq, p: dict = Depends(_admin)):
    user_id = int(p["sub"])
    c = _conn()
    count = 0
    try:
        for r in req.rows:
            if not r.phone.strip():
                continue
            c.execute(
                "INSERT INTO contacts (name,phone,company,position,contact_type,comment,status,created_at,created_by)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (_enc(r.name), _enc(r.phone), _enc(r.company),
                 r.position, r.contact_type, r.comment, "new", _now(), user_id)
            )
            count += 1
        c.commit()
    finally:
        c.close()
    return {"count": count}

@app.post("/contacts/fix-bitrix")
def fix_bitrix(p: dict = Depends(_owner)):
    LABELS = {"юр. лицо", "физ. лицо"}
    c = _conn()
    fixed = 0
    try:
        rows = c.execute(
            "SELECT id, company, position FROM contacts WHERE is_deleted=0"
        ).fetchall()
        for row in rows:
            if _dec(row["company"]).strip().lower() not in LABELS:
                continue
            new_co = row["position"] or ""
            c.execute(
                "UPDATE contacts SET company=?, position='' WHERE id=?",
                (_enc(new_co), row["id"])
            )
            fixed += 1
        if fixed:
            c.commit()
    finally:
        c.close()
    return {"count": fixed}

# ─── ROUTES: USERS ───────────────────────────────────────────────────────────

@app.get("/users")
def get_users(p: dict = Depends(_owner)):
    c = _conn()
    try:
        rows = c.execute("SELECT * FROM users ORDER BY role, username").fetchall()
    finally:
        c.close()
    return [dict(r) for r in rows]

@app.post("/users")
def create_user(req: UserCreate, p: dict = Depends(_owner)):
    c = _conn()
    try:
        cur = c.execute(
            "INSERT INTO users (username,password,role,full_name,active,created_at) VALUES (?,?,?,?,1,?)",
            (req.username, req.password_hash, req.role, req.full_name, _now())
        )
        c.commit()
        return {"id": cur.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Пользователь уже существует")
    finally:
        c.close()

@app.put("/users/{uid}")
def update_user(uid: int, req: UserUpdate, p: dict = Depends(_owner)):
    c = _conn()
    try:
        if req.password_hash:
            c.execute(
                "UPDATE users SET full_name=?,role=?,active=?,password=? WHERE id=?",
                (req.full_name, req.role, req.active, req.password_hash, uid)
            )
        else:
            c.execute(
                "UPDATE users SET full_name=?,role=?,active=? WHERE id=?",
                (req.full_name, req.role, req.active, uid)
            )
        c.commit()
    finally:
        c.close()
    return {"ok": True}

@app.delete("/users/{uid}")
def delete_user(uid: int, p: dict = Depends(_owner)):
    c = _conn()
    try:
        c.execute("UPDATE users SET active=0 WHERE id=?", (uid,))
        c.commit()
    finally:
        c.close()
    return {"ok": True}

@app.put("/users/{uid}/password")
def change_password(uid: int, req: PasswordChange, p: dict = Depends(_get_payload)):
    if int(p["sub"]) != uid:
        raise HTTPException(403, "Нельзя менять чужой пароль")
    c = _conn()
    try:
        row = c.execute("SELECT password FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(404, "Пользователь не найден")
        if not bcrypt.checkpw(req.old_password.encode(), row["password"].encode()):
            raise HTTPException(400, "Неверный текущий пароль")
        if len(req.new_password) < 4:
            raise HTTPException(400, "Новый пароль должен быть не менее 4 символов")
        new_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode()
        c.execute("UPDATE users SET password=? WHERE id=?", (new_hash, uid))
        c.commit()
    finally:
        c.close()
    return {"ok": True}

# ─── ROUTES: AUDIT & LOG ─────────────────────────────────────────────────────

@app.get("/audit")
def get_audit(limit: int = 500, p: dict = Depends(_owner)):
    c = _conn()
    try:
        rows = c.execute(
            "SELECT a.ts, u.username, u.full_name, a.action, a.details "
            "FROM audit_log a LEFT JOIN users u ON a.user_id=u.id "
            "ORDER BY a.ts DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        c.close()
    return [dict(r) for r in rows]

@app.post("/log")
def log_action(entry: LogEntry, p: dict = Depends(_get_payload)):
    user_id = int(p["sub"])
    ts = _now()
    def _write():
        try:
            c = _conn()
            try:
                c.execute(
                    "INSERT INTO audit_log (user_id,action,details,ts) VALUES (?,?,?,?)",
                    (user_id, entry.action, entry.details, ts)
                )
                c.commit()
            finally:
                c.close()
        except Exception:
            pass
    threading.Thread(target=_write, daemon=True).start()
    return {"ok": True}

# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    ssl_dir = os.environ.get("BAZA_SSL_DIR", "/opt/baza/ssl")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8443,
        ssl_keyfile=os.path.join(ssl_dir, "key.pem"),
        ssl_certfile=os.path.join(ssl_dir, "cert.pem"),
    )
