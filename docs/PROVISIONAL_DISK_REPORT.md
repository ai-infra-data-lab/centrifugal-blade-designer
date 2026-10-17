# 根元R入力と仮ディスク（2026-10-16）

対象はcentrifugal_blade_designerだけです。前回の未コミットCAD実装を保持し、stage・commit・pushは行っていません。今回の「仮の寸法を決めて作る」という指定に基づき、従来の寸法未設定状態から任意の仮ディスク作成へ対応しました。実機寸法の推定とは区別します。最終検証は全608件成功、失敗・error・skip・実行漏れは0件です。

## 変更

- `models/cad.py`: 仮状態と構造CAD用の前面距離を保持・検証。
- 新規`geometry/provisional_disk.py`: 実Hub根元R/Zの解析投影、TE外側10 mmの余裕、Shroudと逆側20 mmの裏面、内径通常20 mmのテンプレート。主翼・スプリッターを対象にし、元の設計値を変更しません。
- `gui/cad_editor.py` / `gui/main_window.py`: 根元R入力欄を明記、Enter/フォーカス確定、仮ディスク作成・表示、空の寸法の補完、手動値保護、Undo・保存。
- `gui/preview_3d.py`: ディスクだけのCAD表示で元の翼ワイヤーフレームを保持し、CAD翼・根元フィレットがないことを明示。
- `fileio/project_io.py`: 仮状態をJSON保存。非仮の既存データは任意キーを省略し互換を保持。
- `cad/client.py` / `cad/worker.py`: 仮前面とTurboGrid所属を分離、単体ディスクの閉solid・STEPを検証し、PROVISIONAL/NO_FILLETを記録。
- `fileio/turbogrid_cad_export.py`: Blade Blend手順の半径・有効状態を現在のsnapshotから出力。8 mm固定の説明を解消。
- 新規`tests/test_provisional_disk.py` / `tests/cad/test_provisional_disk_export.py`、更新`tests/test_cad_gui.py`: 入力・不変条件・JSON・Undo・所有範囲・R2.5実CAD・単体ディスク・出力手順を検証。
- README、FEATURES、CAD_EXPORT、ARCHITECTURE、本報告を更新。

## 実モデル

main.pyの既定JSON読込経路からImpellerを選び、Qt offscreenで「仮ディスクを作成・表示」を実行しました。

| 項目 | 仮寸法・結果 |
|---|---|
| 内径 | 20 mm |
| 外径 | 251.862833 mm |
| 裏面Z | 75 mm |
| 裏面オフセット | Hub Z上限から＋20 mm、Shroudと反対側 |
| ディスク体積 | 1,473,649.164582 mm³ |
| ディスク単体BREP/STEP再読込 | PASS |
| ディスクCAD＋元の翼ワイヤーフレーム表示 | offscreen確認 |
| 根元フィレット | 単体表示ではNOT_APPLICABLE |

生成物は`artifacts/provisional-disk-review/provisional_project.json`、`disk-preview.json`、`disk-preview.png`。検証済みSTEPは`artifacts/cad-runs/5d1e77f1757d4e16b1e928b4d754f62c/outputs/mechanical/provisional_disk_NO_FILLET.step`です。元JSON・アプリ既定JSONは変更しません。

最初の仮裏面を−Z側へ置く試作では翼を取り込んでRoot Edgeを識別できなかったため、TEのHub/Tip Z配置に従って反対側へ修正しました。修正後はディスク単体の生成に成功しています。一方、既定翼との結合後には根元候補15本中4本で4面共有が残り、R8は`ChFi3d_Builder:only 2 faces`で拒否されます。単純に候補を間引いても成立しないことを診断しました。半径を自動縮小したり、成功と偽装したりはしません。この結合位相の修復は今回未完了です。

任意R入力の実反映は独立した平面Hub・複数Spanの検証モデルでR2.5を生成し、STEP前後の根元半径を測定しています。仮ディスク体積も解析的な円環体積と照合します。TurboGrid所属が無効なときは構造CADの部分成功を残し、TurboGridは失敗として扱います。

## 検証

- 最初の関連試験: 14 passed / 1 failed。追加テストの配置誤りによるNameErrorで、配置を修正しました（20261016T093520Z-133d2c8c）。数値参照の変更はありません。
- GUI/保存/実CAD関連24件成功（20261016T093644Z-b6a970e9）。
- 裏面方向と実R/Z範囲の修正後、関連17件成功（20261016T094037Z-2dcd7ad5）。
- ディスク単体表示追加後、関連19件成功（20261016T094725Z-e69bb2da）。
- 最終CAD群33件成功、747.63秒（20261016T095020Z-95c3b48b）。既存R8・仮ディスク・R2.5・単体表示と出力保護を確認しました。
- 可変RのBlade Blend手順、無効状態、JSON・寸法規則、R2.5の実出力を追加10件で再確認し成功、163.66秒（20261016T095409Z-534becc3）。
- GUI・その他の全回帰574件成功、1062.67秒（20261016T095006Z-c81ecb14）。
- 最後に可変Rの出力手順を修正し、その処理を含む追加10件を新しいプロセスで再確認しました。上の3実行の617ケースには重複9件があり、一意のテストは608件です。全608収集IDとJUnitを照合し、実行漏れ・unexpected・failure/error・skipは0件でした。単一実行で608 passedという意味ではありません。照合記録は`artifacts/provisional-disk-review/final-test-coverage.json`です。
- 初回のテスト配置誤りは修正済みです。最終検証に環境エラーはありません。表示説明文の更新後もソースを固定し、最終照合時にPythonファイルの変化がないことを確認しました。

実ディスプレイでのF5・操作・DPI、ANSYS Import/Meshは未確認です。仮寸法の強度・性能を検証したものではありません。
