import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime

from .database import (
    init_db, productos, agregar_producto, periodo_actual, abrir_periodo,
    cerrar_periodo, guardar_conteo, guardar_mov, resumen, historial_periodos,
    ultimos_movimientos,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Control de Stock y Pérdidas - Boliche")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.prods = []
        self._db_ready = False

        # Primero se dibuja la ventana. La base y los datos se cargan después.
        self.build_shell()
        self.update_idletasks()
        self.after(60, self._carga_inicial)

    # -------------------- ARRANQUE OPTIMIZADO --------------------
    def build_shell(self):
        header = ctk.CTkFrame(self, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(
            header, text="CONTROL DE STOCK Y PÉRDIDAS",
            font=ctk.CTkFont(size=26, weight="bold")
        ).pack(side="left", padx=22, pady=16)
        self.estado = ctk.CTkLabel(
            header, text="Iniciando...", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.estado.pack(side="right", padx=22)

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        self.ti = self.tabs.add("Dashboard")
        self.tp = self.tabs.add("Productos")
        self.ta = self.tabs.add("Apertura")
        self.tm = self.tabs.add("Movimientos")
        self.tc = self.tabs.add("Conteo final")
        self.tr = self.tabs.add("Resumen")
        self.th = self.tabs.add("Historial")

        self._build_dashboard()
        self._build_productos()
        self.ca, self.eic, self.cif = self.conteo_ui(self.ta, "Guardar stock inicial", self.guardar_inicial)
        self._build_movimientos()
        self.cc, self.efc, self.cff = self.conteo_ui(self.tc, "Guardar conteo final", self.guardar_final)
        self._build_resumen()
        self._build_historial()

    def _carga_inicial(self):
        try:
            self.estado.configure(text="Preparando base de datos...")
            self.update_idletasks()
            init_db()
            self._db_ready = True
            self.estado.configure(text="Cargando datos...")
            self.update_idletasks()
            self.refresh()
        except Exception as e:
            self.estado.configure(text="ERROR DE INICIO")
            messagebox.showerror("Error de inicio", f"No se pudo iniciar la aplicación:\n\n{e}")

    # -------------------- DASHBOARD --------------------
    def _build_dashboard(self):
        top = ctk.CTkFrame(self.ti)
        top.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(top, text="Nombre del período").pack(side="left", padx=(14, 8), pady=12)
        self.eperiodo = ctk.CTkEntry(top, width=310, placeholder_text="Ej.: Sábado 29/08/2026")
        self.eperiodo.pack(side="left", padx=8)
        ctk.CTkButton(top, text="Abrir período", command=self.nuevo_periodo, width=125).pack(side="left", padx=8)
        ctk.CTkButton(top, text="Cerrar período", command=self.fin_periodo, width=125, fg_color="#7f1d1d", hover_color="#991b1b").pack(side="left", padx=8)
        ctk.CTkButton(top, text="Actualizar", command=self.refresh, width=100).pack(side="right", padx=14)

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
            ctk.CTkLabel(frame, text=title, text_color=accent, font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=14, pady=(12, 2))
            lbl = ctk.CTkLabel(frame, text=value, font=ctk.CTkFont(size=24, weight="bold"))
            lbl.pack(anchor="w", padx=14, pady=(0, 12))
            self.card_vars[key] = lbl

        prog = ctk.CTkFrame(self.ti)
        prog.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(prog, text="Progreso del conteo final", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=14, pady=(12, 5))
        self.progress = ctk.CTkProgressBar(prog)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=14, pady=5)
        self.progress_label = ctk.CTkLabel(prog, text="Sin período activo")
        self.progress_label.pack(anchor="w", padx=14, pady=(2, 12))

        bottom = ctk.CTkFrame(self.ti, fg_color="transparent")
        bottom.pack(fill="both", expand=True, padx=16, pady=8)
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=1)
        bottom.grid_rowconfigure(0, weight=1)

        rank = ctk.CTkFrame(bottom)
        rank.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(rank, text="Mayores diferencias", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=14, pady=(12, 4))
        self.ranking_txt = ctk.CTkTextbox(rank, height=180)
        self.ranking_txt.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        quick = ctk.CTkFrame(bottom)
        quick.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(quick, text="Accesos rápidos", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=14, pady=(12, 8))
        for text, tab in [
            ("Realizar conteo final", "Conteo final"),
            ("Registrar movimiento", "Movimientos"),
            ("Cargar stock inicial", "Apertura"),
            ("Ver resumen", "Resumen"),
            ("Ver historial", "Historial"),
        ]:
            ctk.CTkButton(quick, text=text, command=lambda t=tab: self.tabs.set(t)).pack(fill="x", padx=14, pady=5)

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

    # -------------------- CONTEO --------------------
    def conteo_ui(self, parent, texto, cmd):
        f = ctk.CTkFrame(parent)
        f.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(f, text="Producto").grid(row=0, column=0, padx=10, pady=8)
        c = ctk.CTkComboBox(f, values=[""], width=320)
        c.grid(row=0, column=1, padx=10, pady=8)
        ctk.CTkLabel(f, text="Botellas cerradas").grid(row=1, column=0, padx=10, pady=8)
        e = ctk.CTkEntry(f, width=180)
        e.grid(row=1, column=1, padx=10, pady=8, sticky="w")
        ctk.CTkLabel(f, text="Botella abierta").grid(row=2, column=0, padx=10, pady=8)
        fr = ctk.CTkComboBox(f, values=["0", "0.25", "0.50", "0.75"], width=180)
        fr.set("0")
        fr.grid(row=2, column=1, padx=10, pady=8, sticky="w")
        ctk.CTkButton(f, text=texto, command=cmd).grid(row=3, column=0, columnspan=2, pady=15)
        ctk.CTkLabel(parent, text="Podés volver a cargar el mismo producto: se toma siempre el último conteo guardado.", text_color="#9ca3af").pack(anchor="w", padx=30, pady=4)
        return c, e, fr

    # -------------------- MOVIMIENTOS --------------------
    def _build_movimientos(self):
        mf = ctk.CTkFrame(self.tm)
        mf.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(mf, text="Producto").grid(row=0, column=0, padx=10, pady=8)
        self.cm = ctk.CTkComboBox(mf, values=[""], width=300)
        self.cm.grid(row=0, column=1, padx=10, pady=8)
        ctk.CTkLabel(mf, text="Tipo").grid(row=1, column=0, padx=10, pady=8)
        self.ct = ctk.CTkComboBox(mf, values=["INGRESO", "SALIDA", "MERMA"], width=220)
        self.ct.set("INGRESO")
        self.ct.grid(row=1, column=1, padx=10, pady=8, sticky="w")
        ctk.CTkLabel(mf, text="Cantidad equivalente").grid(row=2, column=0, padx=10, pady=8)
        self.ec = ctk.CTkEntry(mf, width=180)
        self.ec.grid(row=2, column=1, padx=10, pady=8, sticky="w")
        ctk.CTkLabel(mf, text="Motivo").grid(row=3, column=0, padx=10, pady=8)
        self.mot = ctk.CTkComboBox(mf, values=["", "Compra", "Rotura", "Derrame", "Cortesía", "Consumo autorizado", "Otro"], width=260)
        self.mot.grid(row=3, column=1, padx=10, pady=8)
        ctk.CTkLabel(mf, text="Observación").grid(row=4, column=0, padx=10, pady=8)
        self.obs = ctk.CTkEntry(mf, width=420)
        self.obs.grid(row=4, column=1, padx=10, pady=8)
        ctk.CTkButton(mf, text="Registrar movimiento", command=self.mov).grid(row=5, column=0, columnspan=2, pady=15)

        ctk.CTkLabel(self.tm, text="Últimos movimientos", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=24, pady=(4, 4))
        self.mov_txt = ctk.CTkTextbox(self.tm, height=220)
        self.mov_txt.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    # -------------------- RESUMEN --------------------
    def _build_resumen(self):
        rf = ctk.CTkFrame(self.tr)
        rf.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(rf, text="Actualizar", command=self.show_resumen).pack(side="left", padx=10, pady=10)
        ctk.CTkButton(rf, text="Exportar Excel", command=self.exportar).pack(side="left", padx=10, pady=10)
        self.txt = ctk.CTkTextbox(self.tr, font=ctk.CTkFont(size=14))
        self.txt.pack(fill="both", expand=True, padx=20, pady=10)

    # -------------------- HISTORIAL --------------------
    def _build_historial(self):
        bar = ctk.CTkFrame(self.th)
        bar.pack(fill="x", padx=20, pady=12)
        ctk.CTkButton(bar, text="Actualizar historial", command=self.refresh_historial).pack(side="left", padx=10, pady=10)
        self.hist_combo = ctk.CTkComboBox(bar, values=[""], width=420, command=lambda _=None: self.ver_periodo_historico())
        self.hist_combo.pack(side="left", padx=10)
        self.hist_txt = ctk.CTkTextbox(self.th)
        self.hist_txt.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self._hist_map = {}

    # -------------------- REFRESCO --------------------
    def refresh(self):
        if not self._db_ready:
            return
        self.prods = productos()
        names = [p["nombre"] for p in self.prods] or [""]
        for c in [self.ca, self.cc, self.cm]:
            current = c.get()
            c.configure(values=names)
            c.set(current if current in names else names[0])

        self.listap.delete("1.0", "end")
        self.listap.insert("end", "\n".join(
            f'{p["nombre"]:<30} | {p["categoria"]:<16} | {p["contenido_ml"]:.0f} ml | Costo ${p["costo"]:,.2f} | Venta ${p["precio_venta"]:,.2f}'
            for p in self.prods
        ) or "Sin productos.")

        p = periodo_actual()
        self.estado.configure(text=f'PERÍODO ACTIVO: {p["nombre"]}' if p else "NO HAY PERÍODO ABIERTO")
        self.show_resumen()
        self.refresh_historial()

    def prod(self, n):
        return next((p for p in self.prods if p["nombre"] == n), None)

    def periodo(self):
        p = periodo_actual()
        if not p:
            messagebox.showwarning("Sin período", "Primero abrí un período.")
        return p

    # -------------------- ACCIONES --------------------
    def nuevo_periodo(self):
        if periodo_actual():
            return messagebox.showwarning("Atención", "Ya existe un período abierto.")
        n = self.eperiodo.get().strip() or "Fin de semana " + datetime.now().strftime("%d/%m/%Y")
        abrir_periodo(n)
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
            texto += f"\n\nHay {pendientes} producto(s) pendiente(s) de conteo final."
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

    def guardar_inicial(self):
        self._guardar_conteo("INICIAL", self.ca, self.eic, self.cif)

    def guardar_final(self):
        self._guardar_conteo("FINAL", self.cc, self.efc, self.cff)

    def _guardar_conteo(self, tipo, cmb, ent, fr):
        p = self.periodo()
        if not p:
            return
        pr = self.prod(cmb.get())
        if not pr:
            return messagebox.showerror("Error", "Seleccioná un producto.")
        try:
            ce = float(ent.get().replace(",", "."))
            f = float(fr.get())
            if ce < 0 or f < 0:
                raise ValueError
        except Exception:
            return messagebox.showerror("Error", "Cantidad inválida.")
        guardar_conteo(p["id"], pr["id"], tipo, ce, f)
        ent.delete(0, "end")
        fr.set("0")
        self.show_resumen()
        ent.focus_set()

    def mov(self):
        p = self.periodo()
        if not p:
            return
        pr = self.prod(self.cm.get())
        if not pr:
            return messagebox.showerror("Error", "Seleccioná un producto.")
        try:
            cant = float(self.ec.get().replace(",", "."))
            if cant <= 0:
                raise ValueError
        except Exception:
            return messagebox.showerror("Error", "Ingresá una cantidad mayor que cero.")
        guardar_mov(p["id"], pr["id"], self.ct.get(), cant, self.mot.get(), self.obs.get().strip())
        self.ec.delete(0, "end")
        self.obs.delete(0, "end")
        self.show_resumen()
        self.ec.focus_set()

    # -------------------- RESUMEN + DASHBOARD --------------------
    def show_resumen(self):
        self.txt.delete("1.0", "end")
        self.mov_txt.delete("1.0", "end")
        p = periodo_actual()
        if not p:
            self.txt.insert("end", "No hay período abierto.")
            self.mov_txt.insert("end", "No hay período abierto.")
            self._actualizar_dashboard(None, [])
            return

        rows = resumen(p["id"])
        perdida = faltante = 0.0
        pendientes = 0
        self.txt.insert("end", f'CONTROL: {p["nombre"]}\nInicio: {p["fecha_inicio"]}\n\n')
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
                f'  Inicial {r["inicial"]:.2f} | +Ingresos {r["ingresos"]:.2f} | -Salidas {r["salidas"]:.2f} | -Mermas {r["mermas"]:.2f}\n'
                f'  Esperado {r["esperado"]:.2f} | Físico {fin} | Diferencia {dif} | {estado}\n'
            )
            if r["perdida"]:
                self.txt.insert("end", f'  Pérdida estimada: ${r["perdida"]:,.2f}\n')
            self.txt.insert("end", "\n")
        self.txt.insert("end", f'\nFALTANTE TOTAL: {faltante:.2f}\nPÉRDIDA ESTIMADA: ${perdida:,.2f}\nPENDIENTES DE CONTEO: {pendientes}\n')

        for m in ultimos_movimientos(p["id"], 20):
            self.mov_txt.insert("end", f'{m["fecha"]} | {m["producto"]} | {m["tipo"]} {m["cantidad"]:.2f} | {m["motivo"] or "Sin motivo"} | {m["observacion"]}\n')
        if not self.mov_txt.get("1.0", "end").strip():
            self.mov_txt.insert("end", "Todavía no hay movimientos en este período.")

        self._actualizar_dashboard(p, rows)

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
            "productos": str(total),
            "contados": f"{contados} / {total}",
            "diferencias": str(diferencias),
            "perdida": f"${perdida:,.2f}",
            "ingresos": f"{ingresos:.2f}",
            "salidas": f"{salidas:.2f}",
            "mermas": f"{mermas:.2f}",
            "pendientes": str(pendientes),
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

    # -------------------- HISTORIAL --------------------
    def refresh_historial(self):
        if not self._db_ready:
            return
        periodos = historial_periodos(80)
        self._hist_map = {}
        labels = []
        for p in periodos:
            label = f'#{p["id"]} | {p["nombre"]} | {p["estado"]} | {p["fecha_inicio"]}'
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
        for r in rows:
            estado = "PENDIENTE" if r["final"] is None else "DIFERENCIA" if (r["faltante"] or 0) > 0 else "OK"
            fin = "SIN CONTAR" if r["final"] is None else f'{r["final"]:.2f}'
            self.hist_txt.insert("end", f'{r["producto"]}: esperado {r["esperado"]:.2f} | físico {fin} | {estado} | pérdida ${r["perdida"] or 0:,.2f}\n')
        self.hist_txt.insert("end", f'\nPÉRDIDA TOTAL: ${sum((r["perdida"] or 0) for r in rows):,.2f}\n')

    def exportar(self):
        p = self.periodo()
        if not p:
            return
        d = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f'reporte_{p["nombre"].replace("/", "-").replace(" ", "_")}.xlsx',
        )
        if not d:
            return
        try:
            # Import diferido: no carga openpyxl durante el arranque.
            from .reports import exportar as exportar_excel
            exportar_excel(resumen(p["id"]), d, p["nombre"])
            messagebox.showinfo("Listo", "Excel generado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el Excel:\n\n{e}")
