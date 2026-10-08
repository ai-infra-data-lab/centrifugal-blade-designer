# 同時編集・最適化モード分離 実装報告

日付: 2026-10-05。今回の要求範囲: 通常Editorの整理、Impeller/Diffuser別の分布編集、Hub/Tip同時編集、最適化の独立起動。

## 変更内容

- 通常Editorから **Diffuser Geometry / Optimization** タブを削除。
- ToolbarのImpeller/Diffuser選択で角度・厚さ・LE/TEの編集対象を切り替えます。データは各対象で独立。
- ImpellerではHub/Tipおよび追加した中間Spanの角度・厚さを一つのグラフへ表示。各断面の表・Add Point/Delete Pointと操作点から直接編集できます。
- Hubは水色の中心点、Tipはオレンジ色の外輪。値が一致しても中心と外輪でそれぞれをドラッグできます。どちらのドラッグも1回のUndoにまとめます。
- Section SelectorはBlade View / LE・TEの対象選択用と明記。角度・厚さの編集に切替は不要。
- Diffuserは単一分布の編集画面。R LE / R TEはDiffuser選択時のOutputへ移動。Output点数・有効桁数・Pressure Side Mappingは引き続き編集可能。
- 左Blade Viewの常時表示、XY/XZ/YZ、Zoom/Pan保持、3D Camera保持を維持。分布の更新も既存Graphic ItemのsetDataで行います。
- Geometry Engine、PCHIP、3D生成、TurboGrid/CSVフォーマット、Project schemaは今回変更していません。既存テストで回帰を確認。

## 独立した最適化モード

```powershell
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe main.py --mode optimization
.\.venv\Scripts\python.exe main.py --mode optimization --project blade.json
```

通常画面のModeメニューからも **Open Optimization Mode in Separate Window** を選択できます。この場合は現在の設計をコピーして起動します。候補の適用、Undo/Redo、保存は独立ウィンドウの設計に作用します。通常編集のプロジェクトを変更しません。最適化モードの名称を画面見出しにも表示。

## ファイル一覧

変更:

- `main.py`: モードとProjectのCLI引数。
- `blade_designer/gui/main_window.py`: 通常タブ整理、対象別設定配置、全断面更新、最適化起動と独立状態。
- `blade_designer/gui/control_point_editor.py`: 操作点の色・大きさ・塗りを指定可能にし、空配列も扱う。
- `blade_designer/gui/section_selector.py`: Blade View / LE・TE選択用の説明。
- `tests/test_gui.py`: 通常Editor構成の期待値を更新。
- `tests/test_optimization_gui.py`: 最適化起動モードで既存検証を実施。
- `tests/test_target_editor_gui.py`: 別ウィンドウ候補適用と通常設計の独立性を検証。
- `README.md`: 起動方法、同時編集操作、手動確認項目。

新規:

- `blade_designer/gui/profile_distribution_editor.py`: 共通グラフと断面別の操作点・入力表。
- `tests/test_simultaneous_editors.py`: 同時編集、同座標点の実マウスドラッグ、Undo、表示範囲、JSON、追加Span、対象別設定、モード分離、CLI。
- `tools/simultaneous_editor_smoke.py`: 画面生成と保存読込・独立性の検証。
- 本報告。画像・結果は `artifacts/simultaneous-editors/`。

変更前ソースは `artifacts/before-simultaneous-editors.zip` に保存。ユーザーの既存 `blade.json` / `blade.csv` はSHA-256が不変であることを確認。

## 検証

- 変更前全体: `pytest -q` → **258 passed in 112.71s**。
- 既存GUI関連: **56 passed in 107.43s**。
- 新規同時編集テスト: **8 passed in 21.62s**。実際のQtマウスイベントでHub中心点 / Tip外輪を両分布について検証。
- 全体1回目: `pytest -q -W error` → **266 passed in 143.76s**。
- 最終全体: `pytest -q -W error` → **266 passed in 171.24s (0:02:51)、0 failure / 0 warning**。
- `python main.py --help`: モード / Project引数を確認。
- `tools/simultaneous_editor_smoke.py`: PASS。Hub/Tip別入力、JSON往復、最適化候補の別ウィンドウ適用、通常設計不変、既存JSON/CSV不変。
- Qt offscreen画像を目視確認: Hub/Tip角度・厚さ、Diffuser角度・Output、Optimization Mode。不要な子Plotの表示を除去し、色・凡例・両入力表・対象設定を確認。

## 制限と次回へ残した項目

実デスクトップでの人による手動操作は未実施。今回のGUI操作はQt offscreenでの自動検証と生成画像の目視確認です。TurboGrid実機Importも今回未実施。既存のTurboGrid Export実装は維持し、回帰テストを実施しました。最適化は既存のDiffuser形状パラメータと候補検証を維持しており、最適化探索実行・CFD実行を追加する変更ではありません。中間Spanが多い場合の入力表は横スクロールになります。
