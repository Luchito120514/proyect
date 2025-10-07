# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import sqlite3
from sqlite3 import Connection

app = FastAPI(title="User CRUD + Demo Brute-Force Lab")

DB_PATH = "users.db" 

class UserCreate(BaseModel):
    username: str
    password: str 
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    is_active: bool

class LoginUser(BaseModel):
    username: str
    password: str

class PasswordChange(BaseModel):
    old_password: str
    new_password: str


def get_db() -> Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        email TEXT,
        is_active INTEGER NOT NULL DEFAULT 1
    )
    """)
    conn.commit()
    conn.close()


init_db()

def row_to_userout(row: sqlite3.Row) -> UserOut:
    return UserOut(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        is_active=bool(row["is_active"])
    )



@app.post("/users", response_model=UserOut, status_code=201)
def create_user(user: UserCreate):
    """
    Crear usuario. Recibe password en texto (requisito de la práctica).
    username debe ser único.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, email, is_active) VALUES (?, ?, ?, ?)",
            (user.username, user.password, user.email, int(user.is_active))
        )
        conn.commit()
        user_id = cur.lastrowid
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return row_to_userout(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="username ya existe")
    finally:
        conn.close()

@app.get("/users", response_model=List[UserOut])
def list_users(skip: int = 0, limit: int = 100):
    """
    Listar usuarios. Paginado simple con skip & limit.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY id LIMIT ? OFFSET ?", (limit, skip))
    rows = cur.fetchall()
    conn.close()
    return [row_to_userout(r) for r in rows]

@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return row_to_userout(row)

@app.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate):
    """
    Actualizar usuario: permitido username, email, is_active.
    NO se permite cambiar password por este endpoint (requisito).
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    new_username = data.username if data.username is not None else row["username"]
    new_email = data.email if data.email is not None else row["email"]
    new_is_active = int(data.is_active) if data.is_active is not None else row["is_active"]

    try:
        cur.execute(
            "UPDATE users SET username = ?, email = ?, is_active = ? WHERE id = ?",
            (new_username, new_email, new_is_active, user_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="username ya existe")

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    updated = cur.fetchone()
    conn.close()
    return row_to_userout(updated)

@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return

@app.post("/login")
def login(creds: LoginUser):
    """
    Autenticar usuario: devuelve mensaje simple "Login exitoso" / "Login fallido".
    NOTA: la contraseña se compara en texto plano (requisito pedagógico).
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (creds.username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"mensaje": "Login fallido"}
    if creds.password == row["password"]:
        if not bool(row["is_active"]):
            return {"mensaje": "Login fallido (usuario inactivo)"}
        return {"mensaje": "Login exitoso"}
    else:
        return {"mensaje": "Login fallido"}

@app.put("/users/{user_id}/password")
def change_password(user_id: int, payload: PasswordChange):
    """
    Cambiar la contraseña de un usuario.
    Requiere enviar la contraseña actual para autorizar el cambio.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if payload.old_password != row["password"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

    cur.execute("UPDATE users SET password = ? WHERE id = ?", (payload.new_password, user_id))
    conn.commit()
    conn.close()

    return {"mensaje": "Contraseña actualizada correctamente"}
