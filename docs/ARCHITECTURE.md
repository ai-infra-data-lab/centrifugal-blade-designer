# アプリ構造（2026-10-08 調査）

対象は遠心圧縮機アプリ。親フォルダの家計簿は今回の対象外です。
Python package内は65ファイル、既存test_*.pyは54ファイルです。

| 場所 | 役割・依存 |
|---|---|
| main.py | argparseでdesign/optimizationとProjectを選び、QApplication・MainWindowを起動 |
| blade_designer/models/ | dataclass/Enum、入力・結果・Validation。数値配列はNumPy |
| blade_designer/geometry/ | PCHIP分布、子午面Line/Arc、G1接続、2D/3D断面、面積・曲率・スロート・全周投影。NumPy/SciPyとmodels |
| blade_designer/fileio/ | JSON保存・旧schema移行、CSV、TurboGrid固有形式。models/geometryに依存 |
| blade_designer/gui/ | PySide6 Widgets、PyQtGraph 2D、QPainterの3D wireframe、Undo。上記層を呼ぶ |
| blade_designer/optimization/ | パラメータ写像・制約・候補判定。models/geometryに依存。探索ソルバーを実行しない |
| tests/ | 解析解・幾何不変条件・旧座標fixture・Qt offscreen・入出力検証 |
| tools/ | GUI画像生成、開発用テスト実行。製品起動経路とは別 |
| docs/ / .vscode/ | 開発手順・調査結果・IDE設定 |

流れ: main → gui → models / geometry / fileio / optimization。
geometryからQtを呼ぶ構成ではありません。3Dはソフトウェアwireframeで、PyVista/VTK/OpenGLの依存はありません。

## 依存環境

Windows 11 build 26300、Python 3.12.14の既存.venvを確認。
直接依存: NumPy 2.5.3 / SciPy 1.18.1 / PySide6 6.11.2 / PyQtGraph 0.14.0 / pytest 9.1.1。
pip checkは成功。標準ライブラリはdataclasses、enum、json、csv、pathlib、copy等。
requirements.txtは既存の非固定指定を維持。requirements-windows-py312.lock.txtは現在の全依存の記録で、新規環境への再インストール結果ではありません。

## リソース・入出力

- パッケージ内の常設画像リソースは見つかりません。グラフ・wireframeは座標から描画。
- blade.json / blade.csv: ユーザーの作業データ。変更せずGit対象から除外。
- tests/fixtures/*.json / *.npz: 旧プロジェクト・既存実装座標の回帰資料。Git対象。
- artifacts/: 過去の画像・検証結果・zip・ANSYS形式資料・今回のログ。Git対象から除外。
- 読込: Project JSON schema 0.1/0.2/0.3、起動時--project。
- 書出: Project JSON（内部精度）、Diffuser segments/contour CSV（有効桁）、Impeller TurboGrid hub.curve/shroud.curve/profile.curve/BladeGen.inf。
- TurboGridで実際にImportする確認とCAD/CFD連携は今回実行していません。

既存の詳細仕様・変更報告はプロジェクト直下のV03_*.md、各EDITOR_REPORT.md等を維持しています。最新のユーザー要求を優先し、旧仕様から動作を勝手に戻さないでください。
