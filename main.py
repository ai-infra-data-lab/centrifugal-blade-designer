import argparse
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from blade_designer.gui.main_window import MainWindow
from blade_designer.fileio.project_io import load_project


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description="Centrifugal Compressor Blade Designer")
    parser.add_argument("--mode", choices=("design", "optimization"), default="design")
    parser.add_argument("--project", help="Project JSON to open in this independent window")
    return parser.parse_args(argv)


def create_window(options):
    template = Path(__file__).resolve().parent / "blade_designer/defaults/default_project.json"
    window = MainWindow(mode=options.mode, default_parameters=load_project(template))
    if options.project:
        window.load_from_path(options.project)
    return window


def main() -> int:
    options = parse_arguments()
    app = QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    window = create_window(options)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
