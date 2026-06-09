def main() -> None:
    from PySide6.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Prep")
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())