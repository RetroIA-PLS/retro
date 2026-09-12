"""Gestor de base de datos compatible con SQLite local y Turso (LibSQL Hrana)."""

from __future__ import annotations

import os
import sqlite3
import json
import random
from pathlib import Path
from typing import Any, Iterable, Optional
from datetime import datetime, timezone, timedelta

from config import DB_PATH, EXPORTS_DIR
from models import Actividad, Criterio, Frase, Nivel, Recurso, Retroalimentacion, Rubrica
from utils import now_slug

try:
    import libsql
    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False


# ==========================================
# FUNCIONES BLINDADAS PARA CREAR OBJETOS
# ==========================================
def safe_actividad(id_val, nombre, proposito, instrucciones, grupo, orden):
    try:
        obj = Actividad(id=id_val, nombre=nombre, proposito=proposito, instrucciones=instrucciones)
        obj.grupo = grupo
        obj.orden = orden
        return obj
    except Exception:
        pass
    # Inyección forzada si falla el orden normal
    obj = Actividad.__new__(Actividad)
    obj.id = id_val
    obj.nombre = nombre
    obj.proposito = proposito
    obj.instrucciones = instrucciones
    obj.grupo = grupo
    obj.orden = orden
    obj.recursos = []
    obj.rubrica = None
    obj.frase = None
    return obj

def safe_rubrica(id_val, nombre, contenido):
    try:
        return Rubrica(id=id_val, nombre=nombre, contenido=contenido, criterios=[])
    except Exception:
        pass
    obj = Rubrica.__new__(Rubrica)
    obj.id = id_val
    obj.nombre = nombre
    obj.contenido = contenido
    obj.criterios = []
    return obj

def safe_frase(id_val, texto, autor):
    try:
        return Frase(id=id_val, texto=texto, autor=autor)
    except Exception:
        pass
    obj = Frase.__new__(Frase)
    obj.id = id_val
    obj.texto = texto
    obj.autor = autor
    return obj

def safe_recurso(id_val, tipo, titulo, url, descripcion):
    try:
        return Recurso(id=id_val, tipo=tipo, titulo=titulo, url=url, descripcion=descripcion)
    except Exception:
        pass
    obj = Recurso.__new__(Recurso)
    obj.id = id_val
    obj.tipo = tipo
    obj.titulo = titulo
    obj.url = url
    obj.descripcion = descripcion
    return obj


class CustomRow(dict):
    """Fila personalizada que permite acceso por clave o por atributo."""
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Fila no tiene la columna '{name}'")


class LibSQLCursorWrapper:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> LibSQLCursorWrapper:
        self._cursor.execute(sql, params)
        return self

    def fetchone(self) -> Optional[CustomRow]:
        row = self._cursor.fetchone()
        if row is None:
            return None
        if hasattr(self._cursor, "description") and self._cursor.description:
            cols = [col[0] for col in self._cursor.description]
            return CustomRow(zip(cols, row))
        return row

    def fetchall(self) -> list[CustomRow]:
        rows = self._cursor.fetchall()
        if not rows:
            return []
        if hasattr(self._cursor, "description") and self._cursor.description:
            cols = [col[0] for col in self._cursor.description]
            return [CustomRow(zip(cols, r)) for r in rows]
        return rows

    @property
    def lastrowid(self) -> Any:
        return getattr(self._cursor, "lastrowid", None)


class LibSQLConnectionWrapper:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def cursor(self) -> LibSQLCursorWrapper:
        return LibSQLCursorWrapper(self._conn.cursor())

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> LibSQLCursorWrapper:
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self) -> None:
        if hasattr(self._conn, "commit"):
            try:
                self._conn.commit()
            except Exception:
                pass

    def rollback(self) -> None:
        if hasattr(self._conn, "rollback"):
            try:
                self._conn.rollback()
            except Exception:
                pass

    def close(self) -> None:
        if hasattr(self._conn, "close"):
            try:
                self._conn.close()
            except Exception:
                pass

    def __enter__(self) -> LibSQLConnectionWrapper:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()


class DatabaseManager:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.turso_url = os.getenv("TURSO_DATABASE_URL", "").strip()
        self.turso_token = os.getenv("TURSO_AUTH_TOKEN", "").strip()

    def connect(self) -> Any:
        if HAS_LIBSQL and self.turso_url and self.turso_token:
            conn = libsql.connect(self.turso_url, auth_token=self.turso_token)
            return LibSQLConnectionWrapper(conn)
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()
        self._add_missing_columns()
        self._init_default_directrices()
        self._init_default_models()

    def _create_tables(self) -> None:
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS actividades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    proposito TEXT NOT NULL,
                    instrucciones TEXT NOT NULL,
                    grupo TEXT DEFAULT 'M11C1G78-050',
                    orden INTEGER DEFAULT 0,
                    rubrica_id INTEGER,
                    frase_id INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rubricas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    contenido TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS criterios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actividad_id INTEGER NOT NULL,
                    nombre TEXT NOT NULL,
                    orden INTEGER DEFAULT 0,
                    FOREIGN KEY(actividad_id) REFERENCES actividades(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS niveles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    criterio_id INTEGER NOT NULL,
                    nombre TEXT NOT NULL,
                    puntaje REAL NOT NULL,
                    descripcion TEXT NOT NULL,
                    FOREIGN KEY(criterio_id) REFERENCES criterios(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recursos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actividad_id INTEGER,
                    tipo TEXT NOT NULL,
                    titulo TEXT NOT NULL,
                    url TEXT NOT NULL,
                    descripcion TEXT NOT NULL,
                    FOREIGN KEY(actividad_id) REFERENCES actividades(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS directrices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT UNIQUE NOT NULL,
                    contenido TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS frases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    texto TEXT NOT NULL,
                    autor TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS historial (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actividad_id INTEGER,
                    estudiante TEXT NOT NULL,
                    actividad_nombre TEXT NOT NULL,
                    fecha TEXT NOT NULL,
                    calificacion REAL NOT NULL,
                    modelo_usado TEXT NOT NULL,
                    retroalimentacion TEXT NOT NULL,
                    criterios_evaluados TEXT,
                    observaciones TEXT,
                    prompt_usado TEXT,
                    temperatura REAL,
                    FOREIGN KEY(actividad_id) REFERENCES actividades(id) ON DELETE SET NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    nivel TEXT NOT NULL,
                    mensaje TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS modelos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    api_id TEXT NOT NULL UNIQUE,
                    categoria TEXT NOT NULL
                )
            """)

    def _add_missing_columns(self, conn: Any = None) -> None:
        if conn is not None:
            alterations = [
                "ALTER TABLE actividades ADD COLUMN grupo TEXT DEFAULT 'M11C1G78-050'",
                "ALTER TABLE actividades ADD COLUMN orden INTEGER DEFAULT 0",
                "ALTER TABLE actividades ADD COLUMN proposito TEXT DEFAULT ''",
                "ALTER TABLE actividades ADD COLUMN instrucciones TEXT DEFAULT ''",
                "ALTER TABLE actividades ADD COLUMN rubrica_id INTEGER",
                "ALTER TABLE actividades ADD COLUMN frase_id INTEGER",
                "ALTER TABLE criterios ADD COLUMN orden INTEGER DEFAULT 0",
                "ALTER TABLE recursos ADD COLUMN actividad_id INTEGER",
                "ALTER TABLE historial ADD COLUMN actividad_nombre TEXT DEFAULT 'General'",
                "ALTER TABLE historial ADD COLUMN criterios_evaluados TEXT",
                "ALTER TABLE historial ADD COLUMN observaciones TEXT",
                "ALTER TABLE historial ADD COLUMN prompt_usado TEXT",
                "ALTER TABLE historial ADD COLUMN temperatura REAL",
                "ALTER TABLE historial ADD COLUMN modelo_usado TEXT DEFAULT 'IA'"
            ]
            for alt in alterations:
                try:
                    conn.execute(alt)
                except Exception:
                    pass
        else:
            with self.connect() as connection:
                self._add_missing_columns(connection)

    def _init_default_directrices(self) -> None:
        defaults = {
            "asesor_nombre": "Tu Nombre Completo",
            "asesor_rol": "Asesor virtual",
            "asesor_id": "00000000",
            "grupo": "M00C0G00-000",
            "prompt_sistema": "Eres un {asesor_rol} empático y profesional llamado {asesor_nombre}. Debes redactar una retroalimentación ÚNICA y PERSONALIZADA. Tienes PROHIBIDO repetir estructuras sintácticas entre un estudiante y otro.",
            "reglas_formato": "ESTÁ ESTRICTAMENTE PROHIBIDO usar subtítulos Markdown (Ejemplo: NO escribas \"## Áreas de Oportunidad\"). Todo debe fluir como una carta natural, separada únicamente por saltos de párrafo.",
            "saludo": "Inicia con 'Apreciable, [Nombre]'. Resalta fortalezas de forma personalizada evitando muletillas.",
            "fortalezas": "Destaca los puntos fuertes del estudiante de forma motivadora y clara.",
            "criterios": "Menciona los criterios en orden numérico estricto indicando el nivel obtenido en minúsculas y negritas.",
            "areas_oportunidad": "Redacta áreas de oportunidad en prosa fluida y natural sin subtítulos Markdown.",
            "sugerencias": "Brinda consejos prácticos y amigables para mejorar en futuras entregas.",
            "recursos_apoyo": "Si existen recursos registrados, compártelos en párrafos independientes.",
            "despedida": "Para finalizar con tu retroalimentación nuevamente te felicito y agradezco tu entrega. Me despido con una frase motivadora.",
            "firma": "Cordialmente."
        }
        for name, content in defaults.items():
            try:
                with self.connect() as conn:
                    conn.execute("INSERT OR IGNORE INTO directrices(nombre, contenido) VALUES (?, ?)", (name, content))
            except Exception:
                pass

    def _init_default_models(self) -> None:
        defaults = [
            ("⚡ Claude Haiku 4.5", "anthropic/claude-haiku-4.5", "De pago"),
            ("🚀 Cohere-gratis", "cohere/north-mini-code:free", "Gratis"),
            ("🟢 GPT Luna", "openai/gpt-5.6-luna", "De pago"),
            ("🟣 GPT Luna Pro", "openai/gpt-5.6-luna-pro", "De pago")
        ]
        try:
            with self.connect() as conn:
                cur = conn.execute("SELECT COUNT(*) as c FROM modelos")
                row = cur.fetchone()
                if row and row["c"] == 0:
                    for n, a, c in defaults:
                        conn.execute("INSERT INTO modelos (nombre, api_id, categoria) VALUES (?, ?, ?)", (n, a, c))
        except Exception:
            pass

    # ==========================================
    # GESTIÓN DE MODELOS DE IA
    # ==========================================
    def get_modelos(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.execute("SELECT * FROM modelos ORDER BY categoria, nombre")
            return [dict(r) for r in cur.fetchall()]

    def create_modelo(self, nombre: str, api_id: str, categoria: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO modelos (nombre, api_id, categoria) VALUES (?, ?, ?)",
                (nombre, api_id, categoria)
            )

    def delete_modelo(self, modelo_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM modelos WHERE id = ?", (modelo_id,))

    # ==========================================
    # GESTIÓN DE ACTIVIDADES Y RÚBRICAS
    # ==========================================
    def create_rubric(self, rubrica: Any) -> int:
        with self.connect() as conn:
            nombre = getattr(rubrica, "nombre", "Rúbrica")
            contenido = getattr(rubrica, "contenido", "")
            cur = conn.execute("INSERT INTO rubricas (nombre, contenido) VALUES (?, ?)", (nombre, contenido))
            return cur.lastrowid or 0

    def list_rubrics(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.execute("SELECT id, nombre FROM rubricas ORDER BY id DESC")
            return [dict(r) for r in cur.fetchall()]

    def get_rubric(self, rubric_id: int) -> Optional[Any]:
        with self.connect() as conn:
            cur = conn.execute("SELECT * FROM rubricas WHERE id = ?", (rubric_id,))
            row = cur.fetchone()
            if row:
                return safe_rubrica(row["id"], row["nombre"], row["contenido"])
            return None

    def update_rubric(self, rubric_id: int, rubrica: Any) -> None:
        with self.connect() as conn:
            nombre = getattr(rubrica, "nombre", "Rúbrica")
            contenido = getattr(rubrica, "contenido", "")
            conn.execute("UPDATE rubricas SET nombre = ?, contenido = ? WHERE id = ?", (nombre, contenido, rubric_id))

    def delete_rubric(self, rubric_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM rubricas WHERE id = ?", (rubric_id,))

    def list_activities(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.execute("SELECT * FROM actividades ORDER BY orden ASC, id ASC")
            return [dict(r) for r in cur.fetchall()]

    def get_activity(self, actividad_id: int) -> Optional[Any]:
        with self.connect() as conn:
            cur = conn.execute("SELECT * FROM actividades WHERE id = ?", (actividad_id,))
            row = cur.fetchone()
            if not row:
                return None
            
            grupo = row.get("grupo") or "M11C1G78-050"
            orden = row.get("orden") or 0
            
            # Usar función blindada
            act = safe_actividad(row["id"], row["nombre"], row["proposito"], row["instrucciones"], grupo, orden)
            
            if row.get("rubrica_id"):
                rub = self.get_rubric(row["rubrica_id"])
                if rub: act.rubrica = rub
            
            if row.get("frase_id"):
                cur_f = conn.execute("SELECT * FROM frases WHERE id = ?", (row["frase_id"],))
                row_f = cur_f.fetchone()
                if row_f: 
                    act.frase = safe_frase(row_f["id"], row_f["texto"], row_f["autor"])

            cur_rec = conn.execute("SELECT * FROM recursos WHERE actividad_id = ?", (actividad_id,))
            for rec_row in cur_rec.fetchall():
                recurso = safe_recurso(rec_row["id"], rec_row["tipo"], rec_row["titulo"], rec_row["url"], rec_row["descripcion"])
                
                if hasattr(act, "add_recurso"):
                    act.add_recurso(recurso)
                elif hasattr(act, "recursos"):
                    act.recursos.append(recurso)

            return act

    def create_activity(self, act: Any, r_id: Optional[int], f_id: Optional[int], rec_ids: list[int]) -> int:
        with self.connect() as conn:
            nombre = getattr(act, "nombre", "Nueva Actividad")
            proposito = getattr(act, "proposito", "")
            instrucciones = getattr(act, "instrucciones", "")
            grupo = getattr(act, "grupo", "M11C1G78-050")
            orden = getattr(act, "orden", 0)
            
            cur = conn.execute(
                "INSERT INTO actividades (nombre, proposito, instrucciones, grupo, orden, rubrica_id, frase_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (nombre, proposito, instrucciones, grupo, orden, r_id, f_id)
            )
            act_id = cur.lastrowid
            for rec_id in rec_ids:
                conn.execute("UPDATE recursos SET actividad_id = ? WHERE id = ?", (act_id, rec_id))
            return act_id or 0

    def update_activity(self, act_id: int, nombre: str, proposito: str, instrucciones: str, grupo: str, orden: int, r_id: Optional[int], f_id: Optional[int], rec_ids: list[int]) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE actividades SET nombre=?, proposito=?, instrucciones=?, grupo=?, orden=?, rubrica_id=?, frase_id=? WHERE id=?",
                (nombre, proposito, instrucciones, grupo, orden, r_id, f_id, act_id)
            )
            conn.execute("UPDATE recursos SET actividad_id = NULL WHERE actividad_id = ?", (act_id,))
            for rec_id in rec_ids:
                conn.execute("UPDATE recursos SET actividad_id = ? WHERE id = ?", (act_id, rec_id))

    def delete_activity(self, actividad_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM actividades WHERE id = ?", (actividad_id,))

    # ==========================================
    # GESTIÓN DE RECURSOS
    # ==========================================
    def create_recurso(self, recurso: Any) -> int:
        with self.connect() as conn:
            tipo = getattr(recurso, "tipo", "Enlace")
            titulo = getattr(recurso, "titulo", "Recurso")
            url = getattr(recurso, "url", "")
            descripcion = getattr(recurso, "descripcion", "")
            cur = conn.execute(
                "INSERT INTO recursos (tipo, titulo, url, descripcion) VALUES (?, ?, ?, ?)",
                (tipo, titulo, url, descripcion)
            )
            return cur.lastrowid or 0

    def list_recursos_globales(self) -> list[Any]:
        with self.connect() as conn:
            cur = conn.execute("SELECT * FROM recursos ORDER BY id DESC")
            return [safe_recurso(r["id"], r["tipo"], r["titulo"], r["url"], r["descripcion"]) for r in cur.fetchall()]

    def update_recurso(self, recurso_id: int, recurso: Any) -> None:
        with self.connect() as conn:
            tipo = getattr(recurso, "tipo", "Enlace")
            titulo = getattr(recurso, "titulo", "Recurso")
            url = getattr(recurso, "url", "")
            descripcion = getattr(recurso, "descripcion", "")
            conn.execute(
                "UPDATE recursos SET tipo = ?, titulo = ?, url = ?, descripcion = ? WHERE id = ?",
                (tipo, titulo, url, descripcion, recurso_id)
            )

    def delete_recurso(self, recurso_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM recursos WHERE id = ?", (recurso_id,))

    # ==========================================
    # DIRECTRICES PEDAGÓGICAS
    # ==========================================
    def get_all_directrices(self) -> dict[str, str]:
        with self.connect() as conn:
            cur = conn.execute("SELECT nombre, contenido FROM directrices")
            return {r["nombre"]: r["contenido"] for r in cur.fetchall()}

    def update_directriz(self, nombre: str, contenido: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO directrices (nombre, contenido) VALUES (?, ?) ON CONFLICT(nombre) DO UPDATE SET contenido = excluded.contenido",
                (nombre, contenido)
            )

    # ==========================================
    # FRASES MOTIVACIONALES
    # ==========================================
    def list_frases(self) -> list[Any]:
        with self.connect() as conn:
            cur = conn.execute("SELECT * FROM frases ORDER BY id DESC")
            return [safe_frase(r["id"], r["texto"], r["autor"]) for r in cur.fetchall()]

    def create_frase(self, texto: str, autor: str) -> int:
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO frases (texto, autor) VALUES (?, ?)", (texto, autor))
            return cur.lastrowid or 0

    def update_frase(self, frase_id: int, texto: str, autor: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE frases SET texto = ?, autor = ? WHERE id = ?", (texto, autor, frase_id))

    def delete_frase(self, frase_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM frases WHERE id = ?", (frase_id,))

    # ==========================================
    # HISTORIAL DE EVALUACIONES
    # ==========================================
    def create_history(self, item: Any, actividad_id: Optional[int] = None) -> int:
        with self.connect() as conn:
            criterios_dict = getattr(item, "criterios_evaluados", None) or getattr(item, "criterios", {})
            crit_json = json.dumps(criterios_dict, ensure_ascii=False)
            
            fecha_val = getattr(item, "fecha", None)
            if not fecha_val:
                fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                fecha_str = fecha_val if isinstance(fecha_val, str) else fecha_val.strftime("%Y-%m-%d %H:%M:%S")
            
            actividad_nombre = getattr(item, "actividad_nombre", None) or getattr(item, "actividad", "General")
            modelo_usado = getattr(item, "modelo_usado", None) or getattr(item, "modelo", "IA")
            texto_generado = getattr(item, "texto_generado", None) or getattr(item, "retroalimentacion", None) or getattr(item, "texto", "")
            prompt_usado = getattr(item, "prompt_usado", None) or getattr(item, "prompt", "")
            temperatura = getattr(item, "temperatura", 0.3)
            observaciones = getattr(item, "observaciones", "")
            calificacion = getattr(item, "calificacion", 0.0)
            estudiante = getattr(item, "estudiante", "Estudiante")

            cur = conn.execute("""
                INSERT INTO historial (
                    actividad_id, estudiante, actividad_nombre, fecha, calificacion,
                    modelo_usado, retroalimentacion, criterios_evaluados, observaciones,
                    prompt_usado, temperatura
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                actividad_id, estudiante, actividad_nombre, fecha_str,
                calificacion, modelo_usado, texto_generado, crit_json,
                observaciones, prompt_usado, temperatura
            ))
            return cur.lastrowid or 0

    def list_history(
        self,
        estudiante: str = "",
        actividad_id: int | None = None,
        limit: int = 500,
        fecha_inicio: str | None = None,
        fecha_fin: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM historial WHERE 1=1"
        params: list[Any] = []

        if actividad_id:
            sql += " AND actividad_id = ?"
            params.append(actividad_id)
        if estudiante:
            sql += " AND estudiante LIKE ?"
            params.append(f"%{estudiante}%")
        if fecha_inicio:
            sql += " AND date(fecha) >= date(?)"
            params.append(fecha_inicio)
        if fecha_fin:
            sql += " AND date(fecha) <= date(?)"
            params.append(fecha_fin)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            return [dict(r) for r in cur.fetchall()]

    # ==========================================
    # LOGS (BITÁCORA DE BOT PARA STREAMLIT)
    # ==========================================
    def add_log(self, nivel: str, mensaje: str) -> None:
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS bot_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, nivel TEXT, mensaje TEXT)")
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO bot_logs (fecha, nivel, mensaje) VALUES (?, ?, ?)", (fecha, nivel, mensaje))

    def get_logs(self, limit: int = 100) -> list[dict]:
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS bot_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, nivel TEXT, mensaje TEXT)")
            cur = conn.execute("SELECT * FROM bot_logs ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def clear_logs(self) -> None:
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS bot_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, nivel TEXT, mensaje TEXT)")
            conn.execute("DELETE FROM bot_logs")

    # ==========================================
    # UTILIDADES DE RESPALDO Y EXPORTACIÓN
    # ==========================================
    def export_all_json(self) -> dict[str, Any]:
        with self.connect() as conn:
            tables = ["actividades", "criterios", "niveles", "recursos", "directrices", "frases", "historial", "rubricas", "bot_logs", "modelos"]
            data = {}
            for t in tables:
                try:
                    cur = conn.execute(f"SELECT * FROM {t}")
                    data[t] = [dict(r) for r in cur.fetchall()]
                except Exception:
                    data[t] = []
            return data

    def backup(self) -> Path:
        data = self.export_all_json()
        filepath = EXPORTS_DIR / f"backup_{now_slug()}.json"
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath
