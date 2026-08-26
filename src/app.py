import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime

from .database import (
    init_db, productos, agregar_producto, periodo_actual, abrir_periodo,
    cerrar_periodo, guardar_conteo, guardar_mov, resumen, historial_periodos,
    ultimos_movimientos, encargados, agregar_encargado, sectores, agregar_sector,
    transferir_stock, resumen_sectores,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Control de Stock y Pérdidas - Boliche V4")
        self.geometry("1360x860")
        self.minsize(1180, 740)
        self.prods = []
        self.encs = []
        self.secs = []
        self._db_ready = False
        self._hist_map = {}

        self.build_shell()
        self.update_idletasks()
        self.after(60, self._carga_inicial)

    # -------------------- ARRANQUE --------------------
    def build_shell(self):
        header = ctk.CTkFrame(self, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(
            header, text="CONTROL DE STOCK Y PÉRDIDAS",
            font=ctk.CTkFont(size=25, weight="bold")
        ).pack(side="left", padx=22, pady=16)

        self.estado = ctk.CTkLabel(header, text="Iniciando...", font=ctk.CTkFont(size=13, weight="bold"))
        self.estado.pack(side="right", padx=18)
        self.enc_actual = ctk.CTkComboBox(header, values=[""], width=190)
        self.enc_actual.pack(side="right", padx=8)
        ctk.CTkLabel(header, text="Encargado actual:").pack(side="right", padx=(8, 2))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self.ti = self.tabs.add("Dashboard")
        self.tp = self.tabs.add("Productos")
        self.tcfg = self.tabs.add("Sectores y encargados")
        self.ta = self.tabs.add("Apertura")
        self.tm = self.tabs.add("Movimientos")
        self.tt = self.tabs.add("Transferencias")
        self.tc = self.tabs.add("Conteo final")
        self.tr = self.tabs.add("Resumen")
        self.th = self.tabs.add("Historial")

        self._build_dashboard()
        self._build_productos()
        self._build_config()
        self.ca, self.sa, self.eic, self.cif = self.conteo_ui(self.ta, "Guardar stock inicial", self.guardar_inicial)
        self._build_movimientos()
        self._build_transferencias()
        self.cc, self.sc, self.efc, self.cff = self.conteo_ui(self.tc, "Guardar conteo final", self.guardar_final)
        self._build_resumen()
        self._build_historial()

    def _carga_inicial(self):
        try:
            self.estado.configure(text="Preparando base...")
            self.update_idletasks()
            init_db()
            self._db_ready = True
            self.refresh()
        except Exception as e:
            self.estado.configure(text="ERROR DE INICIO")
            messagebox.showerror("Error de inicio", f"No se pudo iniciar la aplicación:\n\n{e}")

    # -------------------- DASHBOARD --------------------
    def _build_dashboard(self):
        top = ctk.CTkFrame(self.ti)
        top.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(top, text="Nombre del período").pack(side="left", padx=(14, 8), pady=12)
        self.eperiodo = ctk.CTkEntry(top, width=300, placeholder_text="Ej.: Sábado 29/08/2026")
        self.eperiodo.pack(side="left", padx=8)
        ctk.CTkButton(top, text="Abrir período", command=self.nuevo_periodo, width=120).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Cerrar período", command=self.fin_periodo, width=120,
                      fg_color="#7f1d1d", hover_color="#991b1b").pack(side="left", padx=8)
        ctk.CTkButton(top, text="Actualizar", command=self.refresh, width=95).pack(side="right", padx=14)

        self.cards_frame = ctk.CTkFrame(self.ti, fg_color="transparent")
        self.cards_frame.pack(fill="x", padx=16, pady=8)
        for i in range(4):
            self.cards_frame.grid_columnconfigure(i, weight=1)
        self.card_vars = {}
        cards = [
            ("productos", "PRODUCTOS", "0", "#2563eb"),
            ("contados", "CONTADOS", "0 / 0", "#16a34a"),
            ("diferencias", "CON DIFERENCIA", "0", "#dc2626"),
            ("perdida", "PÉRDIDA ESTIMADA", "$0,00", "#ea580c"),
            ("ingresos", "INGRESOS", "0,00", "#0284c7"),
            ("salidas", "SALIDAS", "0,00", "#7c3aed"),
            ("mermas", "MERMAS", "0,00", "#be123c"),
            ("pendientes", "PENDIENTES", "0", "#ca8a04"),
        ]
        for idx, (key, title, value, accent) in enumerate(cards):
            r, c = divmod(idx, 4)
            frame = ctk.CTkFrame(self.cards_frame, corner_radius=12, border_width=1, border_color=accent)
            frame.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
            ctk.CTkLabel(frame, text=title, text_color=accent,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=14, pady=(12, 2))
            lbl = ctk.CTkLabel(frame, text=value, font=ctk.CTkFont(size=23, weight="bold"))
            lbl.pack(anchor="w", padx=14, pady=(0, 12))
            self.card_vars[key] = lbl

        prog = ctk.CTkFrame(self.ti)
        prog.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(prog, text="Progreso del conteo final", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))
        self.progress = ctk.CTkProgressBar(prog)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=14, pady=4)
        self.progress_label = ctk.CTkLabel(prog, text="Sin período activo")
        self.progress_label.pack(anchor="w", padx=14, pady=(2, 10))

        sectorf = ctk.CTkFrame(self.ti)
        sectorf.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(sectorf, text="Control por sector", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(10, 4))
        self.sector_dash_txt = ctk.CTkTextbox(sectorf, height=105)
        self.sector_dash_txt.pack(fill="x", padx=12, pady=(2, 10))

        bottom = ctk.CTkFrame(self.ti, fg_color="transparent")
        bottom.pack(fill="both", expand=True, padx=16, pady=8)
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=1)
        bottom.grid_rowconfigure(0, weight=1)

        rank = ctk.CTkFrame(bottom)
        rank.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(rank, text="Mayores diferencias", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=14, pady=(12, 4))
        self.ranking_txt = ctk.CTkTextbox(rank, height=160)
        self.ranking_txt.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        quick = ctk.CTkFrame(bottom)
        quick.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(quick, text="Accesos rápidos", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=14, pady=(12, 8))
        for text, tab in [
            ("Realizar conteo final", "Conteo final"),
            ("Registrar movimiento", "Movimientos"),
            ("Transferir entre sectores", "Transferencias"),
            ("Sectores y encargados", "Sectores y encargados"),
            ("Ver resumen", "Resumen"),
        ]:
            ctk.CTkButton(quick, text=text, command=lambda t=tab: self.tabs.set(t)).pack(fill="x", padx=14, pady=4)

    # -------------------- PRODUCTOS --------------------
    def _build_productos(self):
        pf = ctk.CTkFrame(self.tp)
        pf.pack(fill="x", padx=20, pady=20)
        labs = ["Nombre", "Categoría", "Contenido ml", "Costo", "Precio venta"]
        defs = ["", "", "750", "0", "0"]
        self.pe = []
        for i, (lab, de) in enumerate(zip(labs, defs)):
            ctk.CTkLabel(pf, text=lab).grid(row=i, column=0, padx=10, pady=7, sticky="w")
            e = ctk.CTkEntry(pf, width=300)
            e.insert(0, de)
            e.grid(row=i, column=1, padx=10, pady=7)
            self.pe.append(e)
        ctk.CTkButton(pf, text="Agregar producto", command=self.add_prod).grid(row=5, column=0, columnspan=2, pady=15)
        self.listap = ctk.CTkTextbox(self.tp, height=280)
        self.listap.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    # -------------------- CONFIGURACIÓN --------------------
    def _build_config(self):
        cols = ctk.CTkFrame(self.tcfg, fg_color="transparent")
        cols.pack(fill="both", expand=True, padx=20, pady=20)
        cols.grid_columnconfigure((0, 1), weight=1)
        cols.grid_rowconfigure(0, weight=1)

        ef = ctk.CTkFrame(cols)
        ef.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(ef, text="Encargados", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        self.eenc = ctk.CTkEntry(ef, placeholder_text="Nombre del encargado")
        self.eenc.pack(fill="x", padx=16, pady=6)
        ctk.CTkButton(ef, text="Agregar encargado", command=self.add_encargado).pack(fill="x", padx=16, pady=6)
        self.enc_txt = ctk.CTkTextbox(ef)
        self.enc_txt.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        sf = ctk.CTkFrame(cols)
        sf.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(sf, text="Sectores", font=ctk.CTkFont(size=20, weight="bold")).pack(anchor="w", padx=16, pady=(16, 8))
        self.esec = ctk.CTkEntry(sf, placeholder_text="Ej.: Barra principal, VIP, Depósito")
        self.esec.pack(fill="x", padx=16, pady=6)
        ctk.CTkButton(sf, text="Agregar sector", command=self.add_sector).pack(fill="x", padx=16, pady=6)
        self.sec_txt = ctk.CTkTextbox(sf)
        self.sec_txt.pack(fill="both", expand=True, padx=16, pady=(8, 16))

    # -------------------- CONTEO --------------------
    def conteo_ui(self, parent, texto, cmd):
        f = ctk.CTkFrame(parent)
        f.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(f, text="Sector").grid(row=0, column=0, padx=10, pady=8)
        s = ctk.CTkComboBox(f, values=[""], width=300)
        s.grid(row=0, column=1, padx=10, pady=8)
        ctk.CTkLabel(f, text="Producto").grid(row=1, column=0, padx=10, pady=8)
        c = ctk.CTkComboBox(f, values=[""], width=320)
        c.grid(row=1, column=1, padx=10, pady=8)
        ctk.CTkLabel(f, text="Botellas cerradas").grid(row=2, column=0, padx=10, pady=8)
        e = ctk.CTkEntry(f, width=180)
        e.grid(row=2, column=1, padx=10, pady=8, sticky="w")
        ctk.CTkLabel(f, text="Botella abierta").grid(row=3, column=0, padx=10, pady=8)
        fr = ctk.CTkComboBox(f, values=["0", "0.25", "0.50", "0.75"], width=180)
        fr.set("0")
        fr.grid(row=3, column=1, padx=10, pady=8, sticky="w")
        ctk.CTkButton(f, text=texto, command=cmd).grid(row=4, column=0, columnspan=2, pady=15)
        ctk.CTkLabel(parent, text="Cada conteo queda registrado con sector, fecha y encargado.", text_color="#9ca3af").pack(anchor="w", padx=30, pady=4)
        return c, s, e, fr

    # -------------------- MOVIMIENTOS --------------------
    def _build_movimientos(self):
        mf = ctk.CTkFrame(self.tm)
        mf.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(mf, text="Sector").grid(row=0, column=0, padx=10, pady=8)
        self.sm = ctk.CTkComboBox(mf, values=[""], width=280)
        self.sm.grid(row=0, column=1, padx=10, pady=8)
        ctk.CTkLabel(mf, text="Producto").grid(row=1, column=0, padx=10, pady=8)
        self.cm = ctk.CTkComboBox(mf, values=[""], width=300)
        self.cm.grid(row=1, column=1, padx=10, pady=8)
        ctk.CTkLabel(mf, text="Tipo").grid(row=2, column=0, padx=10, pady=8)
        self.ct = ctk.CTkComboBox(mf, values=["INGRESO", "SALIDA", "MERMA"], width=220)
        self.ct.set("INGRESO")
        self.ct.grid(row=2, column=1, padx=10, pady=8, sticky="w")
        ctk.CTkLabel(mf, text="Cantidad equivalente").grid(row=3, column=0, padx=10, pady=8)
        self.ec = ctk.CTkEntry(mf, width=180)
        self.ec.grid(row=3, column=1, padx=10, pady=8, sticky="w")
        ctk.CTkLabel(mf, text="Motivo").grid(row=4, column=0, padx=10, pady=8)
        self.mot = ctk.CTkComboBox(mf, values=["", "Compra", "Rotura", "Derrame", "Cortesía", "Consumo autorizado", "Otro"], width=260)
        self.mot.grid(row=4, column=1, padx=10, pady=8)
        ctk.CTkLabel(mf, text="Observación").grid(row=5, column=0, padx=10, pady=8)
        self.obs = ctk.CTkEntry(mf, width=420)
        self.obs.grid(row=5, column=1, padx=10, pady=8)
        ctk.CTkButton(mf, text="Registrar movimiento", command=self.mov).grid(row=6, column=0, columnspan=2, pady=15)

        ctk.CTkLabel(self.tm, text="Últimos movimientos", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=24, pady=(4, 4))
        self.mov_txt = ctk.CTkTextbox(self.tm, height=220)
        self.mov_txt.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    # -------------------- TRANSFERENCIAS --------------------
    def _build_transferencias(self):
        f = ctk.CTkFrame(self.tt)
        f.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(f, text="Producto").grid(row=0, column=0, padx=10, pady=8)
        self.ctp = ctk.CTkComboBox(f, values=[""], width=300)
        self.ctp.grid(row=0, column=1, padx=10, pady=8)
        ctk.CTkLabel(f, text="Sector origen").grid(row=1, column=0, padx=10, pady=8)
        self.sto = ctk.CTkComboBox(f, values=[""], width=280)
        self.sto.grid(row=1, column=1, padx=10, pady=8)
        ctk.CTkLabel(f, text="Sector destino").grid(row=2, column=0, padx=10, pady=8)
        self.std = ctk.CTkComboBox(f, values=[""], width=280)
        self.std.grid(row=2, column=1, padx=10, pady=8)
        ctk.CTkLabel(f, text="Cantidad").grid(row=3, column=0, padx=10, pady=8)
        self.etc = ctk.CTkEntry(f, width=180)
        self.etc.grid(row=3, column=1, padx=10, pady=8, sticky="w")
        ctk.CTkLabel(f, text="Observación").grid(row=4, column=0, padx=10, pady=8)
        self.etobs = ctk.CTkEntry(f, width=420)
        self.etobs.grid(row=4, column=1, padx=10, pady=8)
        ctk.CTkButton(f, text="Transferir stock", command=self.transferir).grid(row=5, column=0, columnspan=2, pady=15)
        ctk.CTkLabel(self.tt, text="La transferencia descuenta del origen y suma al destino; el stock total del boliche no cambia.", text_color="#9ca3af").pack(anchor="w", padx=30)

    # -------------------- RESUMEN --------------------
    def _build_resumen(self):
        rf = ctk.CTkFrame(self.tr)
        rf.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(rf, text="Sector:").pack(side="left", padx=(10, 4), pady=10)
        self.res_sector = ctk.CTkComboBox(rf, values=["Todos los sectores"], width=230, command=lambda _=None: self.show_resumen())
        self.res_sector.set("Todos los sectores")
        self.res_sector.pack(side="left", padx=6)
        ctk.CTkButton(rf, text="Actualizar", command=self.show_resumen).pack(side="left", padx=10, pady=10)
        ctk.CTkButton(rf, text="Exportar Excel", command=self.exportar).pack(side="left", padx=10, pady=10)
        self.txt = ctk.CTkTextbox(self.tr, font=ctk.CTkFont(size=14))
        self.txt.pack(fill="both", expand=True, padx=20, pady=10)

    # -------------------- HISTORIAL --------------------
    def _build_historial(self):
        bar = ctk.CTkFrame(self.th)
        bar.pack(fill="x", padx=20, pady=12)
        ctk.CTkButton(bar, text="Actualizar historial", command=self.refresh_historial).pack(side="left", padx=10, pady=10)
        self.hist_combo = ctk.CTkComboBox(bar, values=[""], width=500, command=lambda _=None: self.ver_periodo_historico())
        self.hist_combo.pack(side="left", padx=10)
        self.hist_txt = ctk.CTkTextbox(self.th)
        self.hist_txt.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    # -------------------- HELPERS --------------------
    def prod(self, n):
        return next((p for p in self.prods if p["nombre"] == n), None)

    def sector(self, n):
        return next((s for s in self.secs if s["nombre"] == n), None)

    def encargado(self, n=None):
        nombre = n if n is not None else self.enc_actual.get()
        return next((e for e in self.encs if e["nombre"] == nombre), None)

    def periodo(self):
        p = periodo_actual()
        if not p:
            messagebox.showwarning("Sin período", "Primero abrí un período.")
        return p

    def _sector_resumen_id(self):
        n = self.res_sector.get()
        if n == "Todos los sectores":
            return None
        s = self.sector(n)
        return s["id"] if s else None

    # -------------------- REFRESCO --------------------
    def refresh(self):
        if not self._db_ready:
            return
        self.prods = productos()
        self.encs = encargados()
        self.secs = sectores()

        pnames = [p["nombre"] for p in self.prods] or [""]
        snames = [s["nombre"] for s in self.secs] or [""]
        enames = [e["nombre"] for e in self.encs] or [""]

        for c in [self.ca, self.cc, self.cm, self.ctp]:
            current = c.get()
            c.configure(values=pnames)
            c.set(current if current in pnames else pnames[0])
        for c in [self.sa, self.sc, self.sm, self.sto, self.std]:
            current = c.get()
            c.configure(values=snames)
            c.set(current if current in snames else snames[0])

        current_enc = self.enc_actual.get()
        self.enc_actual.configure(values=enames)
        if current_enc in enames:
            self.enc_actual.set(current_enc)
        else:
            preferred = next((x for x in enames if x != "Sin asignar"), enames[0])
            self.enc_actual.set(preferred)

        current_rs = self.res_sector.get()
        res_vals = ["Todos los sectores"] + snames
        self.res_sector.configure(values=res_vals)
        self.res_sector.set(current_rs if current_rs in res_vals else "Todos los sectores")

        self.listap.delete("1.0", "end")
        self.listap.insert("end", "\n".join(
            f'{p["nombre"]:<30} | {p["categoria"]:<16} | {p["contenido_ml"]:.0f} ml | Costo ${p["costo"]:,.2f} | Venta ${p["precio_venta"]:,.2f}'
            for p in self.prods
        ) or "Sin productos.")

        self.enc_txt.delete("1.0", "end")
        self.enc_txt.insert("end", "\n".join(f'• {e["nombre"]}' for e in self.encs) or "Sin encargados.")
        self.sec_txt.delete("1.0", "end")
        self.sec_txt.insert("end", "\n".join(f'• {s["nombre"]}' for s in self.secs) or "Sin sectores.")

        p = periodo_actual()
        self.estado.configure(text=f'PERÍODO: {p["nombre"]}' if p else "NO HAY PERÍODO ABIERTO")
        self.show_resumen()
        self.refresh_historial()

    # -------------------- ACCIONES CONFIG --------------------
    def add_encargado(self):
        try:
            agregar_encargado(self.eenc.get())
            self.eenc.delete(0, "end")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_sector(self):
        try:
            agregar_sector(self.esec.get())
            self.esec.delete(0, "end")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # -------------------- ACCIONES PERÍODO/PRODUCTO --------------------
    def nuevo_periodo(self):
        if periodo_actual():
            return messagebox.showwarning("Atención", "Ya existe un período abierto.")
        enc = self.encargado()
        n = self.eperiodo.get().strip() or "Fin de semana " + datetime.now().strftime("%d/%m/%Y")
        abrir_periodo(n, enc["id"] if enc else None)
        self.eperiodo.delete(0, "end")
        self.refresh()

    def fin_periodo(self):
        p = self.periodo()
        if not p:
            return
        rows = resumen(p["id"])
        pendientes = sum(1 for r in rows if r["final"] is None)
        texto = "¿Cerrar el período?"
        if pendientes:
            texto += f"\n\nHay {pendientes} producto(s) pendiente(s) de conteo final global."
        if messagebox.askyesno("Cerrar período", texto):
            cerrar_periodo(p["id"])
            self.refresh()

    def add_prod(self):
        v = [x.get().strip().replace(",", ".") for x in self.pe]
        if not v[0]:
            return messagebox.showerror("Error", "Ingresá un nombre.")
        try:
            agregar_producto(v[0], v[1], v[2], v[3], v[4])
        except Exception as e:
            return messagebox.showerror("Error", str(e))
        self.pe[0].delete(0, "end")
        self.pe[1].delete(0, "end")
        self.refresh()

    # -------------------- CONTEOS --------------------
    def guardar_inicial(self):
        self._guardar_conteo("INICIAL", self.ca, self.sa, self.eic, self.cif)

    def guardar_final(self):
        self._guardar_conteo("FINAL", self.cc, self.sc, self.efc, self.cff)

    def _guardar_conteo(self, tipo, cmb, seccmb, ent, fr):
        p = self.periodo()
        if not p:
            return
        pr = self.prod(cmb.get())
        sec = self.sector(seccmb.get())
        enc = self.encargado()
        if not pr:
            return messagebox.showerror("Error", "Seleccioná un producto.")
        if not sec:
            return messagebox.showerror("Error", "Seleccioná un sector.")
        if not enc:
            return messagebox.showerror("Error", "Seleccioná un encargado.")
        try:
            ce = float(ent.get().replace(",", "."))
            f = float(fr.get())
            if ce < 0 or f < 0:
                raise ValueError
        except Exception:
            return messagebox.showerror("Error", "Cantidad inválida.")
        guardar_conteo(p["id"], pr["id"], tipo, ce, f, sec["id"], enc["id"])
        ent.delete(0, "end")
        fr.set("0")
        self.show_resumen()
        ent.focus_set()

    # -------------------- MOVIMIENTOS / TRANSFERENCIAS --------------------
    def mov(self):
        p = self.periodo()
        if not p:
            return
        pr = self.prod(self.cm.get())
        sec = self.sector(self.sm.get())
        enc = self.encargado()
        if not pr or not sec or not enc:
            return messagebox.showerror("Error", "Seleccioná producto, sector y encargado.")
        try:
            cant = float(self.ec.get().replace(",", "."))
            if cant <= 0:
                raise ValueError
        except Exception:
            return messagebox.showerror("Error", "Ingresá una cantidad mayor que cero.")
        guardar_mov(p["id"], pr["id"], self.ct.get(), cant, self.mot.get(), self.obs.get().strip(), sec["id"], enc["id"])
        self.ec.delete(0, "end")
        self.obs.delete(0, "end")
        self.show_resumen()
        self.ec.focus_set()

    def transferir(self):
        p = self.periodo()
        if not p:
            return
        pr = self.prod(self.ctp.get())
        ori = self.sector(self.sto.get())
        des = self.sector(self.std.get())
        enc = self.encargado()
        if not pr or not ori or not des or not enc:
            return messagebox.showerror("Error", "Completá producto, origen, destino y encargado.")
        try:
            cant = float(self.etc.get().replace(",", "."))
            if cant <= 0:
                raise ValueError
            transferir_stock(p["id"], pr["id"], ori["id"], des["id"], cant, enc["id"], self.etobs.get().strip())
        except Exception as e:
            return messagebox.showerror("Error", str(e))
        self.etc.delete(0, "end")
        self.etobs.delete(0, "end")
        self.show_resumen()
        messagebox.showinfo("Transferencia", f'Se transfirieron {cant:.2f} de {pr["nombre"]}\n{ori["nombre"]} → {des["nombre"]}.')

    # -------------------- RESUMEN + DASHBOARD --------------------
    def show_resumen(self):
        if not self._db_ready:
            return
        self.txt.delete("1.0", "end")
        self.mov_txt.delete("1.0", "end")
        p = periodo_actual()
        if not p:
            self.txt.insert("end", "No hay período abierto.")
            self.mov_txt.insert("end", "No hay período abierto.")
            self._actualizar_dashboard(None, [])
            return

        sector_id = self._sector_resumen_id()
        sector_nombre = self.res_sector.get()
        rows = resumen(p["id"], sector_id)
        perdida = faltante = 0.0
        pendientes = 0
        self.txt.insert("end", f'CONTROL: {p["nombre"]}\nEncargado de apertura: {p["encargado"] or "Sin asignar"}\nVista: {sector_nombre}\n\n')
        for r in rows:
            if r["final"] is None:
                estado = "🟡 PENDIENTE"
                pendientes += 1
                fin = "SIN CONTAR"
                dif = "PENDIENTE"
            else:
                fin = f'{r["final"]:.2f}'
                dif = f'{r["diferencia"]:.2f}'
                if (r["faltante"] or 0) > 0:
                    estado = "🔴 DIFERENCIA"
                    faltante += r["faltante"]
                    perdida += r["perdida"] or 0
                elif (r["diferencia"] or 0) > 0:
                    estado = "🟡 SOBRANTE"
                else:
                    estado = "🟢 CONTROLADO"
            self.txt.insert(
                "end",
                f'{r["producto"]}\n'
                f'  Inicial {r["inicial"]:.2f} | +Ingresos {r["ingresos"]:.2f} | +Transf. {r["transferencias_in"]:.2f}\n'
                f'  -Salidas {r["salidas"]:.2f} | -Mermas {r["mermas"]:.2f} | -Transf. {r["transferencias_out"]:.2f}\n'
                f'  Esperado {r["esperado"]:.2f} | Físico {fin} | Diferencia {dif} | {estado}\n'
            )
            if r["perdida"]:
                self.txt.insert("end", f'  Pérdida estimada: ${r["perdida"]:,.2f}\n')
            self.txt.insert("end", "\n")
        self.txt.insert("end", f'\nFALTANTE TOTAL: {faltante:.2f}\nPÉRDIDA ESTIMADA: ${perdida:,.2f}\nPENDIENTES DE CONTEO: {pendientes}\n')

        for m in ultimos_movimientos(p["id"], 24):
            extra = ""
            if m["tipo"].startswith("TRANSFERENCIA") and m["sector_destino"]:
                extra = f' ↔ {m["sector_destino"]}'
            self.mov_txt.insert(
                "end",
                f'{m["fecha"]} | {m["sector"]}{extra} | {m["producto"]} | {m["tipo"]} {m["cantidad"]:.2f} | Enc.: {m["encargado"]} | {m["motivo"] or "Sin motivo"} | {m["observacion"]}\n'
            )
        if not self.mov_txt.get("1.0", "end").strip():
            self.mov_txt.insert("end", "Todavía no hay movimientos en este período.")

        # Dashboard siempre representa el total general.
        self._actualizar_dashboard(p, resumen(p["id"]))

    def _actualizar_dashboard(self, p, rows):
        total = len(rows)
        contados = sum(1 for r in rows if r["final"] is not None)
        pendientes = total - contados
        diferencias = sum(1 for r in rows if (r["faltante"] or 0) > 0)
        perdida = sum((r["perdida"] or 0) for r in rows)
        ingresos = sum(r["ingresos"] for r in rows)
        salidas = sum(r["salidas"] for r in rows)
        mermas = sum(r["mermas"] for r in rows)
        vals = {
            "productos": str(total), "contados": f"{contados} / {total}",
            "diferencias": str(diferencias), "perdida": f"${perdida:,.2f}",
            "ingresos": f"{ingresos:.2f}", "salidas": f"{salidas:.2f}",
            "mermas": f"{mermas:.2f}", "pendientes": str(pendientes),
        }
        for k, v in vals.items():
            self.card_vars[k].configure(text=v)
        ratio = (contados / total) if total else 0
        self.progress.set(ratio)
        self.progress_label.configure(text=(f"{contados} de {total} productos contados — {ratio*100:.0f}%" if p else "Sin período activo"))

        self.ranking_txt.delete("1.0", "end")
        ranking = sorted([r for r in rows if (r["faltante"] or 0) > 0], key=lambda x: x["perdida"] or 0, reverse=True)[:8]
        if not ranking:
            self.ranking_txt.insert("end", "Sin diferencias registradas.")
        else:
            for i, r in enumerate(ranking, 1):
                self.ranking_txt.insert("end", f'{i}. {r["producto"]}\n   Faltante: {r["faltante"]:.2f} | Pérdida: ${r["perdida"]:,.2f}\n\n')

        self.sector_dash_txt.delete("1.0", "end")
        if not p:
            self.sector_dash_txt.insert("end", "Sin período activo.")
            return
        secrows = resumen_sectores(p["id"])
        if not secrows:
            self.sector_dash_txt.insert("end", "Todavía no hay actividad por sector.")
        else:
            for s in secrows:
                estado = "OK" if s["pendientes"] == 0 and s["diferencias"] == 0 else ("DIFERENCIAS" if s["diferencias"] else "PENDIENTE")
                self.sector_dash_txt.insert("end", f'{s["sector"]:<22} | Contados {s["contados"]}/{s["productos"]} | Dif. {s["diferencias"]} | Pérdida ${s["perdida"]:,.2f} | {estado}\n')

    # -------------------- HISTORIAL --------------------
    def refresh_historial(self):
        if not self._db_ready:
            return
        periodos = historial_periodos(80)
        self._hist_map = {}
        labels = []
        for p in periodos:
            label = f'#{p["id"]} | {p["nombre"]} | {p["estado"]} | Enc.: {p["encargado"] or "Sin asignar"} | {p["fecha_inicio"]}'
            labels.append(label)
            self._hist_map[label] = p["id"]
        self.hist_combo.configure(values=labels or [""])
        if labels and self.hist_combo.get() not in labels:
            self.hist_combo.set(labels[0])
            self.ver_periodo_historico()
        elif not labels:
            self.hist_txt.delete("1.0", "end")
            self.hist_txt.insert("end", "No hay períodos registrados.")

    def ver_periodo_historico(self):
        label = self.hist_combo.get()
        pid = self._hist_map.get(label)
        if not pid:
            return
        rows = resumen(pid)
        self.hist_txt.delete("1.0", "end")
        self.hist_txt.insert("end", f"{label}\n\n")
        for s in resumen_sectores(pid):
            self.hist_txt.insert("end", f'SECTOR {s["sector"]}: contados {s["contados"]}/{s["productos"]} | diferencias {s["diferencias"]} | pérdida ${s["perdida"]:,.2f}\n')
        self.hist_txt.insert("end", "\nDETALLE GENERAL\n\n")
        for r in rows:
            estado = "PENDIENTE" if r["final"] is None else "DIFERENCIA" if (r["faltante"] or 0) > 0 else "OK"
            fin = "SIN CONTAR" if r["final"] is None else f'{r["final"]:.2f}'
            self.hist_txt.insert("end", f'{r["producto"]}: esperado {r["esperado"]:.2f} | físico {fin} | {estado} | pérdida ${r["perdida"] or 0:,.2f}\n')
        self.hist_txt.insert("end", f'\nPÉRDIDA TOTAL: ${sum((r["perdida"] or 0) for r in rows):,.2f}\n')

    # -------------------- EXPORTACIÓN --------------------
    def exportar(self):
        p = self.periodo()
        if not p:
            return
        sector_id = self._sector_resumen_id()
        sector_nombre = self.res_sector.get()
        d = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f'reporte_{p["nombre"].replace("/", "-").replace(" ", "_")}.xlsx',
        )
        if not d:
            return
        try:
            from .reports import exportar as exportar_excel
            exportar_excel(resumen(p["id"], sector_id), d, p["nombre"], sector_nombre, resumen_sectores(p["id"]))
            messagebox.showinfo("Listo", "Excel generado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el Excel:\n\n{e}")
