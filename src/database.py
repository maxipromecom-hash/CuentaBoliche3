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


def _columnas(c, tabla):
    return {r["name"] for r in c.execute(f"PRAGMA table_info({tabla})").fetchall()}


def _agregar_columna_si_falta(c, tabla, columna, definicion):
    if columna not in _columnas(c, tabla):
        c.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")


def init_db():
    """Crea/migra la base sin borrar datos de versiones anteriores."""
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
        CREATE TABLE IF NOT EXISTS encargados(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nombre TEXT UNIQUE NOT NULL,
          activo INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS sectores(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nombre TEXT UNIQUE NOT NULL,
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
        """)

        # Migración V4: agrega responsable y sector sin destruir registros existentes.
        _agregar_columna_si_falta(c, "periodos", "encargado_id", "INTEGER")
        _agregar_columna_si_falta(c, "movimientos", "sector_id", "INTEGER")
        _agregar_columna_si_falta(c, "movimientos", "encargado_id", "INTEGER")
        _agregar_columna_si_falta(c, "movimientos", "sector_destino_id", "INTEGER")
        _agregar_columna_si_falta(c, "conteos", "sector_id", "INTEGER")
        _agregar_columna_si_falta(c, "conteos", "encargado_id", "INTEGER")

        # Valores de compatibilidad para registros previos.
        c.execute("INSERT OR IGNORE INTO sectores(nombre,activo) VALUES('General',1)")
        c.execute("INSERT OR IGNORE INTO encargados(nombre,activo) VALUES('Sin asignar',1)")
        sector_general = c.execute("SELECT id FROM sectores WHERE nombre='General'").fetchone()["id"]
        sin_asignar = c.execute("SELECT id FROM encargados WHERE nombre='Sin asignar'").fetchone()["id"]
        c.execute("UPDATE conteos SET sector_id=? WHERE sector_id IS NULL", (sector_general,))
        c.execute("UPDATE conteos SET encargado_id=? WHERE encargado_id IS NULL", (sin_asignar,))
        c.execute("UPDATE movimientos SET sector_id=? WHERE sector_id IS NULL", (sector_general,))
        c.execute("UPDATE movimientos SET encargado_id=? WHERE encargado_id IS NULL", (sin_asignar,))
        c.execute("UPDATE periodos SET encargado_id=? WHERE encargado_id IS NULL", (sin_asignar,))

        c.executescript("""
        CREATE INDEX IF NOT EXISTS idx_mov_periodo_prod ON movimientos(periodo_id, producto_id);
        CREATE INDEX IF NOT EXISTS idx_mov_periodo_sector ON movimientos(periodo_id, sector_id, producto_id);
        CREATE INDEX IF NOT EXISTS idx_mov_encargado ON movimientos(encargado_id, id);
        CREATE INDEX IF NOT EXISTS idx_conteos_periodo_prod_tipo ON conteos(periodo_id, producto_id, tipo, id);
        CREATE INDEX IF NOT EXISTS idx_conteos_periodo_sector ON conteos(periodo_id, sector_id, producto_id, tipo, id);
        CREATE INDEX IF NOT EXISTS idx_conteos_encargado ON conteos(encargado_id, id);
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


def encargados():
    with get_conn() as c:
        return c.execute("SELECT * FROM encargados WHERE activo=1 ORDER BY nombre COLLATE NOCASE").fetchall()


def agregar_encargado(nombre):
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("Ingresá el nombre del encargado.")
    with get_conn() as c:
        c.execute("INSERT INTO encargados(nombre) VALUES(?)", (nombre,))


def sectores():
    with get_conn() as c:
        return c.execute("SELECT * FROM sectores WHERE activo=1 ORDER BY nombre COLLATE NOCASE").fetchall()


def agregar_sector(nombre):
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("Ingresá el nombre del sector.")
    with get_conn() as c:
        c.execute("INSERT INTO sectores(nombre) VALUES(?)", (nombre,))


def periodo_actual():
    with get_conn() as c:
        return c.execute(
            """SELECT pe.*, e.nombre encargado
               FROM periodos pe LEFT JOIN encargados e ON e.id=pe.encargado_id
               WHERE pe.estado='ABIERTO' ORDER BY pe.id DESC LIMIT 1"""
        ).fetchone()


def abrir_periodo(nombre, encargado_id=None):
    with get_conn() as c:
        c.execute(
            "INSERT INTO periodos(nombre,fecha_inicio,encargado_id) VALUES(?,?,?)",
            (nombre.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), encargado_id),
        )


def cerrar_periodo(pid):
    with get_conn() as c:
        c.execute(
            "UPDATE periodos SET estado='CERRADO', fecha_fin=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pid),
        )


def guardar_conteo(pid, prod, tipo, cerradas, fraccion, sector_id, encargado_id):
    total = float(cerradas) + float(fraccion)
    with get_conn() as c:
        c.execute(
            """INSERT INTO conteos(periodo_id,producto_id,fecha,tipo,cerradas,fraccion,total,sector_id,encargado_id)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                pid, prod, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tipo,
                float(cerradas), float(fraccion), total, sector_id, encargado_id,
            ),
        )


def guardar_mov(pid, prod, tipo, cant, motivo, obs, sector_id, encargado_id, sector_destino_id=None):
    with get_conn() as c:
        c.execute(
            """INSERT INTO movimientos(
                   periodo_id,producto_id,fecha,tipo,cantidad,motivo,observacion,
                   sector_id,encargado_id,sector_destino_id
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                pid, prod, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tipo,
                float(cant), motivo, obs, sector_id, encargado_id, sector_destino_id,
            ),
        )


def transferir_stock(pid, prod, origen_id, destino_id, cant, encargado_id, obs=""):
    if origen_id == destino_id:
        raise ValueError("El sector de origen y destino deben ser diferentes.")
    cant = float(cant)
    if cant <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        c.execute(
            """INSERT INTO movimientos(
                   periodo_id,producto_id,fecha,tipo,cantidad,motivo,observacion,
                   sector_id,encargado_id,sector_destino_id
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (pid, prod, fecha, "TRANSFERENCIA_SALIDA", cant, "Transferencia", obs,
             origen_id, encargado_id, destino_id),
        )
        c.execute(
            """INSERT INTO movimientos(
                   periodo_id,producto_id,fecha,tipo,cantidad,motivo,observacion,
                   sector_id,encargado_id,sector_destino_id
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (pid, prod, fecha, "TRANSFERENCIA_INGRESO", cant, "Transferencia", obs,
             destino_id, encargado_id, origen_id),
        )


def resumen(pid, sector_id=None):
    """Resumen por producto. Si sector_id es None suma todos los sectores."""
    filtro_c = "" if sector_id is None else " AND c.sector_id=? "
    filtro_m = "" if sector_id is None else " AND sector_id=? "
    filtro_u_c = "" if sector_id is None else " AND sector_id=? "
    filtro_u_m = "" if sector_id is None else " AND sector_id=? "

    # La lista de parámetros sigue el orden exacto de los CTE.
    params = [pid]
    if sector_id is not None: params.append(sector_id)       # ini_rank
    params.append(pid)
    if sector_id is not None: params.append(sector_id)       # fin_rank
    params.append(pid)
    if sector_id is not None: params.append(sector_id)       # usados conteos
    params.append(pid)
    if sector_id is not None: params.append(sector_id)       # usados movimientos
    params.append(pid)
    if sector_id is not None: params.append(sector_id)       # mov

    sql = f"""
    WITH ini_rank AS (
        SELECT c.producto_id,c.sector_id,c.total,
               ROW_NUMBER() OVER(PARTITION BY c.producto_id,c.sector_id ORDER BY c.id DESC) rn
        FROM conteos c WHERE c.periodo_id=? AND c.tipo='INICIAL' {filtro_c}
    ),
    ini AS (
        SELECT producto_id,SUM(total) total,COUNT(*) hay_ini
        FROM ini_rank WHERE rn=1 GROUP BY producto_id
    ),
    fin_rank AS (
        SELECT c.producto_id,c.sector_id,c.total,
               ROW_NUMBER() OVER(PARTITION BY c.producto_id,c.sector_id ORDER BY c.id DESC) rn
        FROM conteos c WHERE c.periodo_id=? AND c.tipo='FINAL' {filtro_c}
    ),
    fin_raw AS (
        SELECT producto_id,SUM(total) total,COUNT(*) sectores_contados
        FROM fin_rank WHERE rn=1 GROUP BY producto_id
    ),
    usados AS (
        SELECT producto_id,sector_id FROM conteos
        WHERE periodo_id=? {filtro_u_c}
        UNION
        SELECT producto_id,sector_id FROM movimientos
        WHERE periodo_id=? {filtro_u_m}
    ),
    usados_count AS (
        SELECT producto_id,COUNT(DISTINCT sector_id) sectores_usados
        FROM usados GROUP BY producto_id
    ),
    fin AS (
        SELECT f.producto_id,
               CASE WHEN f.sectores_contados >= COALESCE(u.sectores_usados,0)
                    THEN f.total ELSE NULL END total,
               f.sectores_contados
        FROM fin_raw f LEFT JOIN usados_count u ON u.producto_id=f.producto_id
    ),
    mov AS (
        SELECT producto_id,
               SUM(CASE WHEN tipo='INGRESO' THEN cantidad ELSE 0 END) ingresos,
               SUM(CASE WHEN tipo='SALIDA' THEN cantidad ELSE 0 END) salidas,
               SUM(CASE WHEN tipo='MERMA' THEN cantidad ELSE 0 END) mermas,
               SUM(CASE WHEN tipo='TRANSFERENCIA_INGRESO' THEN cantidad ELSE 0 END) transferencias_in,
               SUM(CASE WHEN tipo='TRANSFERENCIA_SALIDA' THEN cantidad ELSE 0 END) transferencias_out,
               COUNT(*) hay_mov
        FROM movimientos
        WHERE periodo_id=? {filtro_m}
        GROUP BY producto_id
    )
    SELECT p.id,p.nombre AS producto,p.categoria,p.costo,
           COALESCE(i.total,0) inicial,
           COALESCE(m.ingresos,0) ingresos,
           COALESCE(m.salidas,0) salidas,
           COALESCE(m.mermas,0) mermas,
           COALESCE(m.transferencias_in,0) transferencias_in,
           COALESCE(m.transferencias_out,0) transferencias_out,
           f.total final,
           CASE WHEN COALESCE(i.hay_ini,0)>0 OR COALESCE(m.hay_mov,0)>0 OR COALESCE(f.sectores_contados,0)>0
                THEN 1 ELSE 0 END actividad
    FROM productos p
    LEFT JOIN ini i ON i.producto_id=p.id
    LEFT JOIN fin f ON f.producto_id=p.id
    LEFT JOIN mov m ON m.producto_id=p.id
    WHERE p.activo=1
    ORDER BY p.nombre COLLATE NOCASE
    """
    with get_conn() as c:
        rows = c.execute(sql, params).fetchall()

    out = []
    for r in rows:
        inicial = float(r["inicial"] or 0)
        ingresos = float(r["ingresos"] or 0)
        salidas = float(r["salidas"] or 0)
        mermas = float(r["mermas"] or 0)
        tin = float(r["transferencias_in"] or 0)
        tout = float(r["transferencias_out"] or 0)
        final = None if r["final"] is None else float(r["final"])
        esperado = inicial + ingresos + tin - salidas - mermas - tout
        diferencia = None if final is None else final - esperado
        faltante = None if diferencia is None else max(0.0, -diferencia)
        costo = float(r["costo"] or 0)
        perdida = None if faltante is None else faltante * costo
        out.append(dict(
            id=r["id"], producto=r["producto"], categoria=r["categoria"],
            inicial=inicial, ingresos=ingresos, salidas=salidas, mermas=mermas,
            transferencias_in=tin, transferencias_out=tout, esperado=esperado,
            final=final, diferencia=diferencia, faltante=faltante, perdida=perdida,
            costo=costo, actividad=bool(r["actividad"]),
        ))
    return out

def resumen_sectores(pid):
    out = []
    for s in sectores():
        rows = resumen(pid, s["id"])
        # Un sector se considera "usado" si tuvo conteo o movimiento en el período.
        with get_conn() as c:
            usado = c.execute(
                """SELECT EXISTS(SELECT 1 FROM conteos WHERE periodo_id=? AND sector_id=?)
                           OR EXISTS(SELECT 1 FROM movimientos WHERE periodo_id=? AND sector_id=?) AS x""",
                (pid, s["id"], pid, s["id"]),
            ).fetchone()["x"]
        if not usado:
            continue
        rows = [r for r in rows if r.get("actividad")]
        total = len(rows)
        contados = sum(1 for r in rows if r["final"] is not None)
        pendientes = total - contados
        diferencias = sum(1 for r in rows if (r["faltante"] or 0) > 0)
        perdida = sum((r["perdida"] or 0) for r in rows)
        out.append(dict(
            sector_id=s["id"], sector=s["nombre"], productos=total, contados=contados,
            pendientes=pendientes, diferencias=diferencias, perdida=perdida,
        ))
    return out


def historial_periodos(limite=50):
    with get_conn() as c:
        return c.execute(
            """SELECT pe.id,pe.nombre,pe.fecha_inicio,pe.fecha_fin,pe.estado,e.nombre encargado
               FROM periodos pe LEFT JOIN encargados e ON e.id=pe.encargado_id
               ORDER BY pe.id DESC LIMIT ?""",
            (int(limite),),
        ).fetchall()


def ultimos_movimientos(pid, limite=15, sector_id=None):
    filtro = "" if sector_id is None else " AND m.sector_id=? "
    params = [pid]
    if sector_id is not None:
        params.append(sector_id)
    params.append(int(limite))
    with get_conn() as c:
        return c.execute(
            f"""SELECT m.fecha,p.nombre producto,m.tipo,m.cantidad,m.motivo,m.observacion,
                       s.nombre sector,e.nombre encargado,sd.nombre sector_destino
                FROM movimientos m
                JOIN productos p ON p.id=m.producto_id
                LEFT JOIN sectores s ON s.id=m.sector_id
                LEFT JOIN sectores sd ON sd.id=m.sector_destino_id
                LEFT JOIN encargados e ON e.id=m.encargado_id
                WHERE m.periodo_id=? {filtro}
                ORDER BY m.id DESC LIMIT ?""",
            params,
        ).fetchall()


def ultimo_conteo_por_sector(pid, producto_id, sector_id, tipo):
    with get_conn() as c:
        return c.execute(
            """SELECT c.*,e.nombre encargado FROM conteos c
               LEFT JOIN encargados e ON e.id=c.encargado_id
               WHERE c.periodo_id=? AND c.producto_id=? AND c.sector_id=? AND c.tipo=?
               ORDER BY c.id DESC LIMIT 1""",
            (pid, producto_id, sector_id, tipo),
        ).fetchone()

