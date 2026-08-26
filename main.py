import sys
import traceback


def main():
    try:
        # Import único del módulo visual. openpyxl ya no se importa al iniciar.
        from src.app import App
        app = App()
        app.mainloop()
    except Exception:
        err = traceback.format_exc()
        # Si se ejecuta desde consola, deja el error visible.
        print("\n=== ERROR DE LA APLICACIÓN ===\n" + err, flush=True)
        try:
            from tkinter import messagebox
            messagebox.showerror("Control Stock Boliche - Error", err)
        except Exception:
            pass
        if not getattr(sys, "frozen", False):
            input("\nPresioná ENTER para cerrar...")
        raise


if __name__ == "__main__":
    main()
