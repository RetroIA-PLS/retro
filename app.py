"""Punto de entrada de la aplicación."""

from database import DatabaseManager
from ui import RetroalimentacionApp


def main() -> None:
    """Inicializa dependencias y ejecuta la interfaz."""
    db = DatabaseManager()
    db.initialize()
    RetroalimentacionApp(db).run()


if __name__ == "__main__":
    main()
