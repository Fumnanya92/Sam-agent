"""Launch the Sam glass orb."""
from orb.main import SamOrb
from PyQt6.QtWidgets import QApplication
import sys


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sam")
    orb = SamOrb()
    orb.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
