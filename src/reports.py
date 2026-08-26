def exportar(rows, destino, nombre):
    # Import diferido: openpyxl solo se carga cuando el usuario exporta.
    # Esto reduce notablemente el tiempo de arranque del EXE.
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Control"

    ws.append(["CONTROL DE STOCK Y PÉRDIDAS"])
    ws.append([nombre])
    ws.append([])
    headers = [
        "Producto", "Categoría", "Inicial", "Ingresos", "Salidas", "Mermas",
        "Esperado", "Físico", "Diferencia", "Faltante", "Costo", "Pérdida", "Estado"
    ]
    ws.append(headers)

    dark = "1F2937"
    light = "E5E7EB"
    red = "FEE2E2"
    yellow = "FEF3C7"
    green = "DCFCE7"
    thin = Side(style="thin", color="D1D5DB")

    ws["A1"].font = Font(bold=True, size=18, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=dark)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
    ws["A2"].font = Font(bold=True, size=12)
    ws["A2"].alignment = Alignment(horizontal="center")

    for c in ws[4]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=dark)
        c.alignment = Alignment(horizontal="center")
        c.border = Border(bottom=thin)

    for r in rows:
        if r["final"] is None:
            estado = "PENDIENTE"
        elif (r["faltante"] or 0) > 0:
            estado = "DIFERENCIA"
        elif (r["diferencia"] or 0) > 0:
            estado = "SOBRANTE"
        else:
            estado = "CONTROLADO"
        ws.append([
            r["producto"], r["categoria"], r["inicial"], r["ingresos"], r["salidas"],
            r["mermas"], r["esperado"], "SIN CONTAR" if r["final"] is None else r["final"],
            "" if r["diferencia"] is None else r["diferencia"],
            "" if r["faltante"] is None else r["faltante"], r["costo"],
            "" if r["perdida"] is None else r["perdida"], estado
        ])
        fill = green if estado == "CONTROLADO" else yellow if estado in ("PENDIENTE", "SOBRANTE") else red
        ws.cell(ws.max_row, 13).fill = PatternFill("solid", fgColor=fill)

    ws.append([])
    ws.append(["PÉRDIDA TOTAL", sum((r["perdida"] or 0) for r in rows)])
    ws.append(["PENDIENTES", sum(1 for r in rows if r["final"] is None)])
    ws.append(["PRODUCTOS CON DIFERENCIA", sum(1 for r in rows if (r["faltante"] or 0) > 0)])

    for row in ws.iter_rows(min_row=5):
        for cell in row:
            cell.border = Border(bottom=thin)

    for col in range(1, len(headers) + 1):
        max_len = 0
        for cell in ws[get_column_letter(col)]:
            max_len = max(max_len, len(str(cell.value or "")))
        ws.column_dimensions[get_column_letter(col)].width = min(max(max_len + 2, 11), 35)

    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:M{max(4, ws.max_row - 4)}"
    wb.save(destino)
