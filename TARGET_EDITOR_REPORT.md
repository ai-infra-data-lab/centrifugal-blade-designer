# 編集対象の独立化・インペラ投影表示 実装報告

2026-10-05。対象別の角度・厚さ編集と、インペラのXY以外の表示方向を追加しました。
最終検証は **258 passed、0 failure、0 warning**です。

## 操作方法

1. Toolbarの **Impeller / Diffuser** で表示と編集対象を選びます。
2. ImpellerではHub / Tip / 中間Spanを選択します。Blade AngleとThicknessはその断面の設定です。
3. **Projection: XY / XZ / YZ** でインペラの投影方向を切り替えます。CamberとLE/PS/TE/SSを実際のXYZ座標から表示し、軸名も切り替えます。
4. Diffuserでは専用のBlade Angle / Thickness / LE/TE設定を表示します。インペラのSection Selectorを隠し、従来2DのXY表示へ切り替えます。
5. Impellerへ戻ると、前に選んだ断面と投影方向を復元します。右のEditingラベルで対象を確認できます。
6. 対象・投影の変更でも現在のZoom/Panと3D Cameraを維持します。形状が表示範囲外ならFit Viewを使用します。

## データとGeometry

以前はDiffuserの角度・厚さ・端部設定がImpeller Hubと共有されていました。
BladeParameters.diffuser_profileを追加し、Impeller sectionsと独立して保存します。
別の対象の設定を変更しても他方の形状を変更しません。Hub/Tip/中間Spanの独立設定も維持します。

既存の2D Engineに渡す変換をdiffuser_design_parametersへ分離し、generate_diffuser APIを追加しました。
従来generate(parameters)とblade_angle/thickness/edgesのHub aliasは互換性のため維持しています。
独立したDiffuserにはgenerate_diffuser(parameters)を使用します。

GUIのDiffuser表示、Metrics、Curvature、Full Annulus、CSVは専用Diffuser設定を使用します。
Diffuserの最適化Baseline・候補も専用設定を使い、適用時にImpellerの断面を維持します。自動Optimization/CFD実行を追加したものではありません。
Impeller GeometryのPCHIP、壁面・Span計算、3D Preview、TurboGrid出力構文は変更していません。

## Save/LoadとUndo/Redo

schema 0.3にdiffuser_profileを追加しました。数値は既存どおりfull precisionです。
旧0.1/0.2/0.3は、従来共有していたHub値を独立Diffuserへコピーして初期化し、元ファイルを変更しません。
新しいProjectは両者の異なる角度・厚さ・LE/TE設定を保持して読み込みます。

Undo/Redo commandへ編集対象を記録しました。
別対象へ移ってからUndoしても、編集した対象・断面と値を復元します。
対象・Projectionだけの切替は設計編集として履歴に追加しません。表示範囲・Cameraも保持します。
対象とProjectionの選択は表示状態で、Project JSONへ永続化しません。

## 変更ファイル

既存9ファイルを変更しました。

- blade_designer/fileio/project_io.py
- blade_designer/geometry/designer.py
- blade_designer/gui/main_window.py
- blade_designer/gui/parameter_panel.py
- blade_designer/gui/undo_commands.py
- blade_designer/models/parameters.py
- README.md
- tests/test_gui.py
- tests/test_optimization_gui.py

新規4ファイルです。

- TARGET_EDITOR_REPORT.md
- tests/test_target_editor_gui.py
- tests/test_target_profiles.py
- tools/target_editor_smoke.py

変更前のソース: artifacts/before-target-editors.zip。
生成した画面画像・保存Project・Diffuser CSV・QA/Stage記録はartifacts/target-editorsにあります。

## 検証結果

| Stage | 全回帰テスト | 結果 |
|---|---|---|
| 1: 変更前Baseline | pytest -q -W error | 249 passed / 142.88 s |
| 2: 独立設定・対象Editor・投影 | pytest -q -W error | 258 passed / 224.08 s |
| 3: Projection欄整合・最終 | pytest -q -W error | **258 passed / 110.81 s** |

各Stage完了時に0 failure・0 warningを確認しました。
旧GUIの「インペラHub編集でDiffuserも変わる」期待は、今回の独立化仕様へ更新しました。
最適化候補もDiffuserを更新し、Impellerを保つことを検証しています。

追加テスト:

- Impeller / Diffuser角度・厚さの独立生成。
- Hub / Tip / Diffuserの切替と値の保持。
- XY / XZ / YZのCamberと全Segment座標が元のXYZ成分に一致。
- Diffuser時はXY固定、Impellerに戻ると以前のProjectionを復元。
- 両対象のSave/Load、旧Project初期化、無効Diffuser設定の保存拒否。
- 対象をまたぐUndo/RedoとView/Camera保持。
- Diffuserの最適化Baseline・候補適用でImpellerを保持。

tools/target_editor_smoke.py: **PASS**。
画像でXZ/YZ投影、対象ラベル、専用Diffuser EditorとXY欄を目視確認しました。
専用Project JSONと244点のDiffuser CSVを生成しました。
ユーザーの既存blade.json/blade.csvはSHA-256照合で不変でした。

## Manual確認と制限

Qt offscreenの自動操作と画像の目視確認を実施しました。人によるNative GUI操作・OSダイアログ操作は未実施です。
TurboGrid実機Importは従来どおり未検証です。今回の変更はExporterの構文へ影響しません。

手動確認:

1. Impeller Hubの角度・厚さを変え、Tipを別の値にする。
2. Diffuserへ切り替えてさらに別の角度・厚さを編集し、元のHub/Tip値が残ることを確認。
3. ImpellerでXY/XZ/YZを選び、軸名と形状を確認する。必要に応じFit Viewを押す。
4. 対象を往復し、投影選択・角度・厚さが保持されることを確認する。
5. Save/Openし両対象の値を確認する。Undo/Redoでも対象と値を確認する。

Diffuserは既存の単一2D radial profileです。Diffuserの新しい3D断面や任意方向投影を追加したものではありません。
インペラ全断面の立体形状は下部3D Previewで任意に回転して確認できます。
