import os
import sys

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .ui import theme
from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("RedBlack Laser")
    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "app.ico")))
    # Botões padrão do Qt (OK/Cancelar, Salvar/Descartar) em português.
    tr = QTranslator(app)
    if tr.load("qtbase_pt_BR", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)
    theme.apply(app)
    win = MainWindow()
    win.show()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:  # python -m redblack projeto.rbl ("Abrir com" do Windows)
        win.open_path(args[0])
    else:
        win.restaurar_sessao()  # continua o último projeto (ou recupera o que não foi salvo)
    if "--orcamento" in sys.argv and getattr(win, "plugin_orcamento", None):  # abre direto no orçamento
        win.plugin_orcamento["abrir"]()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
