# 既存機能一覧

確認日: 2026-10-10。対象: Centrifugal Compressor Blade Designer v0.3。
v0.3.0最終版の保存先はアプリ専用の非公開GitHub `ai-infra-data-lab/centrifugal-blade-designer`。ソース・テスト・資料・デフォルト用JSONの167ファイルを対象とし、ユーザーJSON原本・仮想環境・キャッシュ・成果物・家計簿は除外します。実画面の未確認事項は維持します。
前回315件と指定デフォルト・翼枚数・起動Projectの追加3件を含む全回帰318件を再実行しました。
**動作確認済み（自動）はWindows .venv / Qt offscreenでの確認**です。実ディスプレイ・VS Codeボタン操作・TurboGrid実機まで確認した意味ではありません。

| 機能 | 実装状態 | 動作状態・根拠 |
|---|---|---|
| main.py起動、design / optimization、--project | 実装確認済み | 動作確認済み（自動）: test_simultaneous_editors、test_optimization_gui。変更前F5起動はユーザー確認済み。今回の変更後native操作は未確認 |
| 左の縦選択パネル・中央の翼形状・右Editor | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui、test_design_navigator_gui、test_gui、test_persistent_model_gui。中央は常に翼形状、子午面・角度・厚さのグラフは右側。対象切替でウィンドウサイズを維持し、初期サイズは画面内に収める |
| 中央上段2D・下段3Dの常時表示と高さ調整 | 実装確認済み | 動作確認済み（自動）: test_row_domain_gui。選択翼列に追従しカメラを保持。ImpellerはSpan付き3D、Diffuserは既存の平面輪郭をXYZのZ=0で表示 |
| 子午面の直線・円弧ごとの所属翼列、色・名前表示、翼列別TurboGrid壁面範囲 | 実装確認済み | 動作確認済み（自動）: test_row_domain、test_row_domain_gui。所属をUndo/JSON保存、順番変更・翼列削除に追従。両壁面の連続性と翼輪郭の包含を出力前に検証。全未割り当てなら旧出力を維持。Diffuser CSV輪郭は変更しない |
| 子午面はMeridionalのみ、翼列はBlade Angle / Thickness / LE/TE / Full Annulus | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui。選択翼列の形状を中央表示し、角度・厚さ・子午面は右側で編集。翼端ドラッグもUndo検証済み。最適化モードは専用タブを追加 |
| 上部Project / Edit / View / Exportの操作グループ | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui。Output Settings、Flow Area、Metrics、3D Preview、Diffuser CurvatureはViewから別ウィンドウで表示 |
| 子午面/翼列の選択、Impeller/Diffuser翼列の追加・削除・順序変更 | 実装確認済み | 動作確認済み（自動）: test_design_navigator_gui。独立編集、Undo/Redo、JSON往復、共有壁面、選択翼列CSV、別ウィンドウ最適化を検証。順序変更で翼端位置は変更しない。最少1翼列 |
| 追加ボタン後に名前・インペラ/静翼を指定するダイアログ | 実装確認済み | 動作確認済み（自動）: test_design_navigator_gui。名前の前後空白を除去し、空白名の確定を防止。キャンセルは設計・Undo履歴を変更せず、名前・種類はUndo/Redo・JSON往復で保持 |
| 任意のblade_rows/active_blade_row、全翼列の保存前検証 | 実装確認済み | 動作確認済み（自動）: test_blade_rows、test_project_io、既存migrationテスト。翼列管理未使用のJSONは追加フィールドなし |
| Impeller / Diffuserの独立した角度・厚さ・LE/TE | 実装確認済み | 動作確認済み（自動）: test_target_profiles、test_target_editor_gui |
| Hub/Tip角度・厚さを同じグラフで表示・表編集・Add/Delete/Drag | 実装確認済み | 動作確認済み（自動）: test_simultaneous_editors。重なるHub中心/Tip外輪もQt mouseイベントで検証 |
| 共通PCHIP、control pointを通り単調列のovershootを抑える | 実装確認済み | 動作確認済み（自動）: test_shared_pchip、test_distributions、test_thickness |
| 共通Impeller LE/TEタイプ・楕円比、Diffuser側は独立 | 実装確認済み | 動作確認済み（自動）: test_shared_edges_annulus_gui、test_edges |
| Hub/Shroud Line/Arc chain、G1接線、解析的長さ | 実装確認済み | 動作確認済み（自動）: test_meridional_line/arc/arc_arc/tangent/length |
| invalid geometry、負の半径、交差、非finiteの検出 | 実装確認済み | 動作確認済み（自動）: test_meridional_invalid、test_validation、test_checks |
| Flow Path、翼端位置、normalized meridional、既存Component Stationsデータの維持 | 実装確認済み | 動作確認済み（自動）: test_flow_path、test_component_stations、test_blade_edge_position。Component Stationsの編集表・子午面上部の値一覧は画面から撤去。Blade Edgesと保存データ・Flow Area計算は維持 |
| Hub/Tip・中間Span、追加/削除、線形Span対応 | 実装確認済み | 動作確認済み（自動）: test_blade_sections、test_preview_3d、test_blade_edge_span_interpolation |
| Copy Hub→Tip / Tip→Hubボタンの撤去 | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui、test_shared_edges_annulus_gui。既存の内部コピーAPIとUndoは保持 |
| 2D Camber/PS/SS/LE/TE、surface mapping | 実装確認済み | 動作確認済み（自動）: test_camber、test_surface、test_pitch、test_edges |
| XYZ/RTZ断面、XY/XZ/YZ projection | 実装確認済み | 動作確認済み（自動）: test_geometry_3d、test_target_editor_gui |
| Full Annulusの対象・選択断面・投影追従 | 実装確認済み | 動作確認済み（自動）: test_annulus、test_shared_edges_annulus_gui |
| 2D/3Dの独立した単翼・Full Annulus切り替え | 実装確認済み | 動作確認済み（自動）: test_persistent_model_gui。Full Annulusタブと上部Viewグループから操作。Impeller/静翼の翼枚数に追従し、設計値・カメラを保持。3D全周は描画用に各線最大151点を使用し、計算・出力は変更しない。表示チェックはJSONへ保存しない |
| 指定JSONをアプリ起動・Newのデフォルトに使用 | 実装確認済み | 動作確認済み（自動）: test_application_defaults_gui。blade_v03.jsonをアプリ内defaults/default_project.jsonへコピー。元ファイルを保持し、main.py/F5起動・Newへ適用。--projectは優先。F5実操作は未確認 |
| 右側上部で翼列ごとの翼枚数を編集 | 実装確認済み | 動作確認済み（自動）: test_application_defaults_gui。既存vane_count入力を移動。表示・Undo・JSON・出力の同じ設定を使用。子午面では非表示 |
| Diffuser Curvature（Viewから表示） | 実装確認済み | 動作確認済み（自動）: test_curvature、test_shared_edges_annulus_gui。Diffuser選択時の曲率を表示 |
| ソフトウェア3D wireframe、Hub/Shroud・Span線・表示選択 | 実装確認済み | 動作確認済み（自動）: test_preview_3d、test_spanwise_wireframe。native描画は未確認 |
| Zoom/Pan・Camera保持、明示的Fit View | 実装確認済み | 動作確認済み（自動）: test_undo_commands、test_target_editor_gui |
| Undo/Redo、numeric editing・dragの履歴 | 実装確認済み | 動作確認済み（自動）: test_undo_commands |
| Throat（LE上も許可）、曲率、Pitch/Solidity等 | 実装確認済み | 動作確認済み（自動）: test_throat、test_curvature、test_metrics、test_pitch |
| Gross Flow Area、area ratio、断面選択 | 実装確認済み | 動作確認済み（自動）: test_flow_area_axial/radial/general/gui |
| 内部計算解像度と出力LE/PS/TE/SS点数の分離 | 実装確認済み | 動作確認済み（自動）: test_geometry_resolution、test_resample |
| Project JSON保存/読込、0.1/0.2/旧0.3移行、精度維持 | 実装確認済み | 動作確認済み（自動）: test_project_io、test_project_migration、test_project_flow_path_migration。旧GUI読込で形状差はHub LE/TEへ統一 |
| Diffuser segments/closed contour CSV、有効桁1～15 | 実装確認済み | 動作確認済み（自動）: test_csv_export |
| TurboGrid 3 curve + BladeGen.inf、軸・単位・順序 | 実装確認済み | 動作確認済み（自動書出し）: test_turbogrid_export。実機Importは未確認 |
| Rotation CW/CCW、Reverse、座標反転 | 実装確認済み | 動作確認済み（自動）: test_rotation_direction |
| 別モード最適化、baseline・変数・制約・候補preview/apply | 実装確認済み | 動作確認済み（自動）: test_optimization_mapper/constraints/gui。探索実行・CFDは含まない |
| VS Code launch/tasks/Test Explorer設定 | 実装確認済み（設定作成） | JSON・対象ファイル・CLIテスト確認済み。変更前F5起動はユーザー確認済み。Testing画面のクリック実行は未確認 |
| Codex VS Code拡張のサインインと依頼実行 | 未確認 | 拡張導入状況は環境報告へ記載。本人の認証・対話は未実施 |
| WSL2 / Ubuntu 24.04実行 | 未確認 | 現在の環境では問題あり: distroなし、WSL2を使える構成ではない。Linux実行は未実施 |

## 検証上の問題と扱い

2026-10-10 指定デフォルト・翼枚数の最終コード: `tools/run_tests.py`で **318 passed / 0 failure / 0 error / 0 skipped**。記録: `artifacts/test-runs/20261010T135944Z-5663c711/pytest.xml`と`result.json`。関連21件も成功しました。指定JSONの起動・Newへの適用、設計の独立コピー、--project優先とNew復帰、翼列別の枚数・Undo/Redo・JSON再読込・2D/3D全周追従を検証しました。既存数値モデル・回帰参照は維持しています。実装失敗・環境エラーはありません。
元blade_v03.jsonとアプリ内コピーのSHA256は`CB05ADE89842434E5600BB01E6CA2AB95BED428E1628866E3AE94D7114834CBC`で一致し、元ファイルは変更していません。画像: `artifacts/defaults-blade-count-review/`。Qt offscreenで指定形状・右上入力・13枚全周表示を確認しました。実ディスプレイの手動操作・変更後F5は未確認です。
今回変更: main.py、gui/main_window.py、defaults/default_project.json、test_application_defaults_gui.py、FEATURES.md・README.md・docs/ARCHITECTURE.md。既存未コミット作業とユーザーファイルを保持し、stage/commit/pushは行っていません。以下は前回の検証記録です。

2026-10-10 中央の翼形状維持・右側の分布編集・独立2D/3D全周表示の最終コード: `tools/run_tests.py`で **315 passed / 0 failure / 0 error / 0 skipped**。記録: `artifacts/test-runs/20261010T133854Z-8931f52f/pytest.xml`と`result.json`。関連8件も成功しました。タブ・子午面選択時の中央形状維持、右グラフの点クリック・ドラッグ・Undo、Impeller/静翼のZ軸回転と翼枚数追従、設計値・カメラ保持を検証しています。
途中の関連試験は狭い右グラフでマウス移動がドラッグ開始距離に届かず、クリック処理の不足により2 failed / 56 passedでした。クリック処理を追加し、ドラッグ試験はQtのピクセル開始距離を超える移動に合わせました。数値参照は変更していません。これは実装・操作試験の問題であり環境エラーではありません。
画像: `artifacts/persistent-model-review/`。Qt offscreenで中央上下の翼形状・右角度グラフ・子午面・全周を確認。実ディスプレイ、DPI/native操作は未確認です。今回変更: `gui/main_window.py`・`preview_3d.py`・`control_point_editor.py`、`test_persistent_model_gui.py`・`test_gui.py`・`test_target_layout_gui.py`・`test_undo_commands.py`、`tools/shared_edges_annulus_smoke.py`、FEATURES.md・README.md・docs/ARCHITECTURE.md。起動・Newの設計デフォルト値はユーザー指示により変更していません。既存未コミット作業を保持し、stage/commit/pushは行っていません。以下は前回の検証記録です。

2026-10-10 子午面所属・上下モデル表示の最終コード: `tools/run_tests.py`で **311 passed / 0 failure / 0 error / 0 skipped**。記録: `artifacts/test-runs/20261010T131706Z-6611b0fa/pytest.xml`と`result.json`。関連テスト54件と、3D Fit View/既存操作4件も成功しました。解析的な直線・円弧の区間長、所属JSON往復・Undo・削除復元、壁面出力端点・点数、輪郭座標の不変性、不正範囲時の既存ファイル保護を検証しています。
途中の関連試験は静翼3D表示の参照名誤りで1 failed / 25 passedでした。参照名修正後は26 passed、最終コードは上記の全回帰311件成功です。これは実装上の不具合であり環境エラーではありません。
画面画像: `artifacts/row-domain-review/`。初期760×720で上下表示を確認し、拡大画面で所属列・色・名前と選択静翼を確認しました。3D Fit Viewでは上下の描画領域内にモデル全体が入ることも自動検証済み。画像確認プロセスだけMeiryoを明示読み込みしています。実ディスプレイでの操作、DPI/nativeテーマ、TurboGrid実機Importは未確認です。
今回の変更ファイル: GUIの`main_window.py`・`meridional_editor.py`・`preview_3d.py`、モデルの`meridional.py`・`blade_rows.py`、範囲計算の`geometry/row_domain.py`、保存・出力の`project_io.py`・`turbogrid_export.py`、`test_row_domain.py`・`test_row_domain_gui.py`・`test_target_layout_gui.py`、この文書・README.md・docs/ARCHITECTURE.md。既存の未コミット作業を保持し、stage/commit/pushは行っていません。以下は前回の検証記録です。

2026-10-10 Station欄撤去・配置復元後の最終GUIコード: `tools/run_tests.py`で **299 passed / 0 failure / 0 error / 0 skipped**。記録: `artifacts/test-runs/20261010T004406Z-07cb8951/pytest.xml`と`result.json`。関連テストも46 passed。通常値と異なる既存Station値の保存・再読込、翼端編集、Station表の非表示、中央形状/右Editorの配置を検証しました。
画面画像: `artifacts/station-removal-review/meridional.png`。Station操作欄と上部数値一覧がなく、Blade Edgesが残ることをQt offscreenで確認しました。実ディスプレイでの手動操作は未確認です。以下は前回の検証記録です。

2026-10-10最終GUIコード: `tools/run_tests.py`で **298 passed / 0 failure / 0 error / 0 skipped**。記録: `artifacts/test-runs/20261010T001829Z-c16449e5/pytest.xml`と`result.json`。追加・保存・Undo・既存ドラッグ編集を含む関連テストも49 passedでした。
画面画像: `artifacts/add-dialog-review/`。左の対象一覧・中央Editor・右形状表示、名前/インペラ/静翼の追加画面をQt offscreenで確認しました。実ディスプレイでの操作は未確認です。以下は前回の検証記録です。

2026-10-09最終GUIコード: `tools/run_tests.py`で **296 passed / 0 failure / 0 error**。警告はエラーとして実行し、warning summaryもありません。
記録: `artifacts/test-runs/20261009T133658Z-1dafb893/pytest.xml`と`result.json`。変更後の角度・厚さ・翼端のドラッグ関連3件も個別に通過しました。
画面構成を更新した `tools/shared_edges_annulus_smoke.py`、`tools/v03_smoke.py`、`tools/v03_additional_smoke.py` はすべてPASS。JSON往復・CSV/TurboGrid書出し・回転/Undo・カメラ保持を確認し、既存座標との差は最大約1.15e-12 mm、ユーザーJSON/CSVは変更なしでした。
自動描画画像: `artifacts/target-layout-review/`。800×800のoffscreen画面で初期サイズ760×720を維持したまま子午面/翼列の切替を確認。この環境のQt offscreenはシステムフォントの自動列挙が0件だったため、画像確認プロセスだけ既存Meiryoを明示読込しました。アプリ本体のフォント設定は変更していません。
前回の翼列管理追加時は292 passed（`artifacts/test-runs/20261009T130429Z-18cd4fc1/`）、関連GUIは19 passedでした。
今回の変更後の実画面操作、OS標準ファイルダイアログ、TurboGrid実機Importは未確認です。手順はREADME.mdの「左側の編集対象・複数翼列」を参照してください。

通常のpytest -q -W errorは、sandbox内TEMPの作成失敗（47 setup errors）と過去のcacheへのアクセス拒否で終了しました。
テストコード・比較値は変更せず、tools/run_tests.pyでプロジェクト内の専用TEMPを使いcacheproviderを無効化した再実行は **277 passed / 0 failure / 0 error / 0 warning**。
キャッシュを使わないため--last-failed等のcache依存機能はこの設定では使いません。

解析解で比較する試験と、過去実装の座標を保つ試験を区別してください。NPZの一致を実機の正しさの保証にしないでください。説明はdocs/DEVELOPMENT.mdの「数値の基準」を参照。

未実装・今回対象外: Splitter、tip clearance、専用lean/sweep/rake、optimization探索、CFX実行、自動meshing、STEP/IGES・Solid CAD。
詳細の手動確認手順はdocs/DEVELOPMENT.mdにあります。
