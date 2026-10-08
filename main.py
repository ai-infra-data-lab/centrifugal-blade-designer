import argparse
import sys
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description="Centrifugal Compressor Blade Designer")
    parser.add_argument("--mode", choices=("design", "optimization"), default="design")
    parser.add_argument("--project", help="Project JSON to open in this independent window")
    return parser.parse_args(argv)


def main() -> int:
    options = parse_arguments()
    app = QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    window = MainWindow(mode=options.mode)
    if options.project:
        window.load_from_path(options.project)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
