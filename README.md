# Control Stock Boliche V3

Versión mejorada del sistema de control de stock y pérdidas.

## Mejoras incluidas
- Dashboard con indicadores del período activo.
- Progreso del conteo final.
- Indicadores de productos controlados, pendientes y con diferencias.
- Ranking de mayores pérdidas.
- Accesos rápidos desde el Dashboard.
- Historial de períodos anteriores.
- Vista de últimos movimientos.
- Advertencia al cerrar un período con conteos pendientes.
- Reporte Excel mejorado y más legible.
- Optimización de base de datos mediante índices y consultas agregadas.
- Arranque optimizado: la ventana aparece primero y la base se inicializa después.
- `openpyxl` se carga solo al exportar, no durante el inicio.
- Ruta de base de datos estable junto a la aplicación.
- Validaciones adicionales para cantidades y productos.

## Compilación
1. Subir todo al repositorio GitHub.
2. Ir a **Actions**.
3. Ejecutar **Compilar Control Stock Boliche V3**.
4. Descargar el artifact **ControlStockBoliche-Windows**.

> Importante: conservar la carpeta `data` al actualizar si contiene registros reales.
