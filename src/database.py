import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def _app_data_dir() -> Path:
    """Ubicación estable de la base, independiente del directorio de ejecución."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[1]
    data = base / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data


DB = _app_data_dir() / "control_stock.db"


def get_conn():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    return c


def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS productos(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nombre TEXT UNIQUE NOT NULL,
          categoria TEXT DEFAULT '',
          contenido_ml REAL DEFAULT 750,
          costo REAL DEFAULT 0,
          precio_venta REAL DEFAULT 0,
          activo INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS periodos(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nombre TEXT NOT NULL,
          fecha_inicio TEXT NOT NULL,
          fecha_fin TEXT,
          estado TEXT DEFAULT 'ABIERTO'
        );
        CREATE TABLE IF NOT EXISTS movimientos(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          periodo_id INTEGER NOT NULL,
          producto_id INTEGER NOT NULL,
          fecha TEXT NOT NULL,
          tipo TEXT NOT NULL,
          cantidad REAL NOT NULL,
          motivo TEXT DEFAULT '',
          observacion TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS conteos(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          periodo_id INTEGER NOT NULL,
          producto_id INTEGER NOT NULL,
          fecha TEXT NOT NULL,
          tipo TEXT NOT NULL,
          cerradas REAL DEFAULT 0,
          fraccion REAL DEFAULT 0,
          total REAL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_mov_periodo_prod ON movimientos(periodo_id, producto_id);
        CREATE INDEX IF NOT EXISTS idx_conteos_periodo_prod_tipo ON conteos(periodo_id, producto_id, tipo, id);
        CREATE INDEX IF NOT EXISTS idx_periodos_estado ON periodos(estado, id);
        """)


def productos():
    with get_conn() as c:
        return c.execute("SELECT * FROM productos WHERE activo=1 ORDER BY nombre COLLATE NOCASE").fetchall()


def agregar_producto(nombre, categoria, ml, costo, precio):
    with get_conn() as c:
        c.execute(
            """INSERT INTO productos(nombre,categoria,contenido_ml,costo,precio_venta)
               VALUES(?,?,?,?,?)""",
            (nombre.strip(), categoria.strip(), float(ml), float(costo), float(precio)),
        )


def periodo_actual():
    with get_conn() as c:
        return c.execute("SELECT * FROM periodos WHERE estado='ABIERTO' ORDER BY id DESC LIMIT 1").fetchone()


def abrir_periodo(nombre):
    with get_conn() as c:
        c.execute(
            "INSERT INTO periodos(nombre,fecha_inicio) VALUES(?,?)",
            (nombre.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def cerrar_periodo(pid):
    with get_conn() as c:
        c.execute(
            "UPDATE periodos SET estado='CERRADO', fecha_fin=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pid),
        )


def guardar_conteo(pid, prod, tipo, cerradas, fraccion):
    total = float(cerradas) + float(fraccion)
    with get_conn() as c:
        c.execute(
            """INSERT INTO conteos(periodo_id,producto_id,fecha,tipo,cerradas,fraccion,total)
               VALUES(?,?,?,?,?,?,?)""",
            (
                pid,
                prod,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                tipo,
                float(cerradas),
                float(fraccion),
                total,
            ),
        )


def guardar_mov(pid, prod, tipo, cant, motivo, obs):
    with get_conn() as c:
        c.execute(
            """INSERT INTO movimientos(periodo_id,producto_id,fecha,tipo,cantidad,motivo,observacion)
               VALUES(?,?,?,?,?,?,?)""",
            (
                pid,
                prod,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                tipo,
                float(cant),
                motivo,
                obs,
            ),
        )


def resumen(pid):
    """Resumen agregado en una sola consulta (evita consultas repetidas por producto)."""
    sql = """
    WITH ultimo_ini AS (
        SELECT c.producto_id, c.total
        FROM conteos c
        JOIN (
            SELECT producto_id, MAX(id) AS max_id
            FROM conteos
            WHERE periodo_id=? AND tipo='INICIAL'
            GROUP BY producto_id
        ) x ON x.max_id=c.id
    ),
    ultimo_fin AS (
        SELECT c.producto_id, c.total
        FROM conteos c
        JOIN (
            SELECT producto_id, MAX(id) AS max_id
            FROM conteos
            WHERE periodo_id=? AND tipo='FINAL'
            GROUP BY producto_id
        ) x ON x.max_id=c.id
    ),
    mov AS (
        SELECT producto_id,
               SUM(CASE WHEN tipo='INGRESO' THEN cantidad ELSE 0 END) ingresos,
               SUM(CASE WHEN tipo='SALIDA' THEN cantidad ELSE 0 END) salidas,
               SUM(CASE WHEN tipo='MERMA' THEN cantidad ELSE 0 END) mermas
        FROM movimientos
        WHERE periodo_id=?
        GROUP BY producto_id
    )
    SELECT p.id, p.nombre AS producto, p.categoria, p.costo,
           COALESCE(i.total,0) inicial,
           COALESCE(m.ingresos,0) ingresos,
           COALESCE(m.salidas,0) salidas,
           COALESCE(m.mermas,0) mermas,
           f.total final
    FROM productos p
    LEFT JOIN ultimo_ini i ON i.producto_id=p.id
    LEFT JOIN ultimo_fin f ON f.producto_id=p.id
    LEFT JOIN mov m ON m.producto_id=p.id
    WHERE p.activo=1
    ORDER BY p.nombre COLLATE NOCASE
    """
    with get_conn() as c:
        rows = c.execute(sql, (pid, pid, pid)).fetchall()

    out = []
    for r in rows:
        inicial = float(r["inicial"] or 0)
        ingresos = float(r["ingresos"] or 0)
        salidas = float(r["salidas"] or 0)
        mermas = float(r["mermas"] or 0)
        final = None if r["final"] is None else float(r["final"])
        esperado = inicial + ingresos - salidas - mermas
        diferencia = None if final is None else final - esperado
        faltante = None if diferencia is None else max(0.0, -diferencia)
        costo = float(r["costo"] or 0)
        perdida = None if faltante is None else faltante * costo
        out.append(
            dict(
                id=r["id"],
                producto=r["producto"],
                categoria=r["categoria"],
                inicial=inicial,
                ingresos=ingresos,
                salidas=salidas,
                mermas=mermas,
                esperado=esperado,
                final=final,
                diferencia=diferencia,
                faltante=faltante,
                perdida=perdida,
                costo=costo,
            )
        )
    return out


def historial_periodos(limite=50):
    with get_conn() as c:
        return c.execute(
            """SELECT id,nombre,fecha_inicio,fecha_fin,estado
               FROM periodos ORDER BY id DESC LIMIT ?""",
            (int(limite),),
        ).fetchall()


def ultimos_movimientos(pid, limite=15):
    with get_conn() as c:
        return c.execute(
            """SELECT m.fecha,p.nombre producto,m.tipo,m.cantidad,m.motivo,m.observacion
               FROM movimientos m
               JOIN productos p ON p.id=m.producto_id
               WHERE m.periodo_id=?
               ORDER BY m.id DESC LIMIT ?""",
            (pid, int(limite)),
        ).fetchall()
