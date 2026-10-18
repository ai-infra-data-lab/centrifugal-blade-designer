# 子午面の翼列距離

子午面の所属壁面を入口から順に数え、Impellerを0–1、Diffuserを1–2、RCを2–3のように表示する。左側の翼列一覧の並べ替えではなく、Hub/Shroudの線・円弧に設定した「所属翼列」が入口順を決める。RCのように半径が減る流路でも、壁面チェーンの進行方向を使う。

## 操作

- 子午面の線・円弧テーブルに「翼列距離 s 始→終」を表示する。
- LE/TEテーブルでは各Hub/Shroudの「翼列距離 s」をR/Zと併記する。たとえばDiffuserの1.2は、その所属壁面区間の入口から20%を意味する。
- 値のツールチップに翼列内位置と所属範囲を表示する。所属範囲外は赤字で示し、自動移動しない。
- 子午面グラフ下に番号と翼列名の対応を表示し、LE/TEハンドルのツールチップにもHub/Shroudのsを示す。グラフ自体は従来どおりR/Z座標で表示する。
- LE/TEの編集は既存のR/Z入力・適用またはハンドル操作を使う。sは読取り専用。
- 角度・厚さグラフは各翼のLE–TEを0–1とする従来の横軸を維持する。

## 換算契約

翼列番号をi、各壁面でその翼列が所有する区間の実距離を[a,b]、壁面全長をL、既存保存値をfとすると、`s = i + (f L - a) / (b - a)`。直線長と`radius × abs(sweep radians)`を積算し、Hub/Shroudそれぞれ独立に正規化する。したがって同じsは同じR/Zや同じmmを意味しない。

全翼列について、両壁面上に連続した所属区間が必要。所属不足、同じ翼列の区間分断、Hub/Shroudの入口順不一致、無効な壁面の場合は「未設定」と表示する。未所属の線・円弧にはsを割り当てず、隙間を隣の翼列へ含めない。LE/TEが所属範囲外なら換算値は範囲外として残す。この表示の不成立だけで既存プロジェクトを拒否しない。

現既定JSONのImpeller TEは所属区間を少し越えているため、Hub s≈1.01386503、Shroud s≈1.02059226を赤字で表示する。RCはLE s=2.1、TE s=2.9となる。既存R/Zや所属区間を自動補正しない。

計算はQtやファイル形式に依存しない`geometry/row_coordinates.py`が担当する。JSONの壁面全体0–1保存値、形状生成、既定値、CSV/TurboGrid/CAD出力へ新しい座標を渡さない。新しいフィールドは保存しない。

GUI変更は`gui/blade_edge_editor.py`（LE/TE距離列）、`gui/meridional_editor.py`（所属区間の始終）、`gui/context_meridional.py`（区間説明とハンドルのツールチップ）に限定する。機能一覧と責務は`FEATURES.md`、`docs/ARCHITECTURE.md`へ追記する。

## 検証

`tests/test_row_coordinates.py`は直線/円弧の解析長、各壁面の換算、整数境界、RC、未所属区間、異常入力を検査する。`tests/test_row_coordinates_gui.py`は既定JSONを明示読込みし、表示・所属変更・R/Z適用・Undo/Redo・名前変更・並べ替え・再読込み・未確定R/Z保持・角度/厚さ横軸・保存内容不変をQt offscreenで検査する。

2026-10-18: quick 63件、解析27件、GUI8件が成功。全回帰は同じproject `.venv`と`tools/run_tests.py`を使い、通常6群と実CAD1群に分割して1,486一意件成功（通常1,442・実CAD44）。既存1,451 IDを維持し、failure/error/skip/漏れ/重複/余分IDは0。ソース・テスト・設定・原本/既定JSONを含む固定297入力は実行中不変。Ruffの変更Python6ファイル検査、`git diff --check`も成功。

ローカル証跡は`artifacts/quality-row-coordinates/final-test-coverage.json`と同フォルダの収集ID、入力hash、各group log。各群のrun IDは順に`20261018T131009Z-91eb49dd`（116件）、`-d00be383`（147）、`-7866c9f6`（125）、`-02af8dc9`（211）、`-80eeaa5d`（153）、`-137343c8`（690）、`-48bce092`（実CAD44）。完全ログとJUnitは`artifacts/test-runs/<run ID>/`に保存する。既存テストの期待値は変更していない。

ネイティブ画面でのDPI/横スクロール/ツールチップの操作感は手動確認対象。ANSYSのImport/Mesh検証はこの表示機能の自動テストに含めない。
