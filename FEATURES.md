# 既存機能一覧

確認日: 2026-10-12。対象: Centrifugal Compressor Blade Designer v0.3。
v0.3.0最終版の保存先はアプリ専用の非公開GitHub `ai-infra-data-lab/centrifugal-blade-designer`。ソース・テスト・資料・デフォルト用JSONの167ファイルを対象とし、ユーザーJSON原本・仮想環境・キャッシュ・成果物・家計簿は除外します。実画面の未確認事項は維持します。
公開済みv0.3.0は全回帰318件成功。中央3Dの全翼列/所属壁面表示までのローカルコードは全回帰450件が成功しました。その後の「全翼列に独立したLE/TE欄を追加する」修正は、再開後の拡張関連108件と最終全回帰457件が成功しました。Git status・差分チェックも実行できています。今回の最終コードの検証結果は457件成功です。
**動作確認済み（自動）はWindows .venv / Qt offscreenでの確認**です。実ディスプレイ・VS Codeボタン操作・TurboGrid実機まで確認した意味ではありません。

| 機能 | 実装状態 | 動作状態・根拠 |
|---|---|---|
| 翼列ごとに独立したLE/TE欄・子午面の線とドラッグ点を追加 | 実装確認済み | 拡張関連108件成功: test_all_row_edges_gui、test_design_navigator_gui、test_row_edge_selection_gui、test_edge_rz_gui、test_undo_commands、test_contextual_3d_gui。表は4×翼列数、LE/TE線は2×翼列数。RCの追加・独立R/Z編集・ドラッグ・名前変更/順番/削除/Undo/JSONを確認。再開後のGit status/差分チェックと最終全回帰457件は成功 |
| main.py起動、design / optimization、--project | 実装確認済み | 動作確認済み（自動）: test_simultaneous_editors、test_optimization_gui。変更前F5起動はユーザー確認済み。今回の変更後native操作は未確認 |
| 左の縦選択パネル・中央の選択対象形状・右Editor | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui、test_design_navigator_gui、test_gui、test_persistent_model_gui。中央上段は子午面選択時に子午面、翼列選択時に翼形状。角度・厚さのグラフと数値・所属編集は右側。対象切替でウィンドウサイズを維持し、初期サイズは画面内に収める |
| 中央3Dは子午面で全翼列、翼列で所属Hub/Shroudと選択翼 | 実装確認済み | 動作確認済み（自動）: test_contextual_3d_gui。全翼列合成・独立した全周枚数・所属壁面の端点と欠落/離れた区間・選択切替・入力変更/Undo/JSON・カメラ保持・無効翼列の理由表示を対象 |
| 中央上段2D・下段3Dの常時表示と高さ調整 | 実装確認済み | 動作確認済み（自動）: test_row_domain_gui。選択翼列に追従しカメラを保持。Impeller・Diffuserとも子午面上の断面とSpanwise接続を3D表示 |
| 子午面の直線・円弧ごとの所属翼列、色・名前表示、翼列別TurboGrid壁面範囲 | 実装確認済み | 動作確認済み（自動）: test_row_domain、test_row_domain_gui。所属をUndo/JSON保存、順番変更・翼列削除に追従。両壁面の連続性と翼輪郭の包含を出力前に検証。全未割り当てなら旧出力を維持。Diffuser CSV輪郭は変更しない |
| 子午面はMeridionalのみ、翼列はBlade Angle / Thickness / LE/TE / Full Annulus | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui。選択対象を中央表示し、角度・厚さ・子午面の数値は右側で編集。中央子午面の翼端ドラッグもUndo検証済み。最適化モードは専用タブを追加 |
| 上部Project / Edit / View / Exportの操作グループ | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui。Output Settings、Flow Area、Metrics、3D Preview、Diffuser CurvatureはViewから別ウィンドウで表示 |
| 子午面/翼列の選択、Impeller/Diffuser翼列の追加・削除・順序変更 | 実装確認済み | 動作確認済み（自動）: test_design_navigator_gui。独立編集、Undo/Redo、JSON往復、共有壁面、選択翼列CSV、別ウィンドウ最適化を検証。順序変更で翼端位置は変更しない。最少1翼列 |
| 追加ボタン後に名前・インペラ/静翼を指定するダイアログ | 実装確認済み | 動作確認済み（自動）: test_design_navigator_gui。名前の前後空白を除去し、空白名の確定を防止。キャンセルは設計・Undo履歴を変更せず、名前・種類はUndo/Redo・JSON往復で保持 |
| 登録後の翼列名変更・子午面Blade EdgesのRow名同期 | 実装確認済み | 動作確認済み（自動）: test_design_navigator_gui。名前変更ダイアログ、空白/キャンセル/同名、Undo/Redo・JSON、同種類複数翼列の名前切替、ID・形状・区間所属の維持を確認。実画面は未確認 |
| 任意のblade_rows/active_blade_row、全翼列の保存前検証 | 実装確認済み | 動作確認済み（自動）: test_blade_rows、test_project_io、既存migrationテスト。翼列管理未使用のJSONは追加フィールドなし |
| Impeller / Diffuserの独立した角度・厚さ・LE/TE | 実装確認済み | 動作確認済み（自動）: test_target_profiles、test_target_editor_gui |
| Hub/Tip角度・厚さを同じグラフで表示・表編集・Add/Delete/Drag | 実装確認済み | 動作確認済み（自動）: test_simultaneous_editors。重なるHub中心/Tip外輪もQt mouseイベントで検証 |
| 分布編集の共有グラフを直接利用し、不要な一時Widgetを撤去 | 実装確認済み | 動作確認済み（自動）: test_editor_resources_gui。Hub/Tip・中間Span・Diffuserへ再構築してもグラフは1つ。旧描画項目の除去、再構築後の点編集、単独Editorの表編集・追加・削除を検証 |
| 共通PCHIP、control pointを通り単調列のovershootを抑える | 実装確認済み | 動作確認済み（自動）: test_shared_pchip、test_distributions、test_thickness |
| 共通Impeller LE/TEタイプ・楕円比、Diffuser側は独立 | 実装確認済み | 動作確認済み（自動）: test_shared_edges_annulus_gui、test_edges |
| Hub/Shroud Line/Arc chain、G1接線、解析的長さ | 実装確認済み | 動作確認済み（自動）: test_meridional_line/arc/arc_arc/tangent/length |
| 追加済み子午面区間のLine / Arc切替 | 実装確認済み | 動作確認済み（自動）: test_row_domain_gui。Type選択欄、経路長と所属翼列の維持、種類別入力欄、Hub/Shroud両側の双方向切替、1 UndoとJSON往復。実画面は未確認 |
| invalid geometry、負の半径、交差、非finiteの検出 | 実装確認済み | 動作確認済み（自動）: test_meridional_invalid、test_validation、test_checks |
| Flow Path、翼端位置、normalized meridional、既存Component Stationsデータの維持 | 実装確認済み | 動作確認済み（自動）: test_flow_path、test_component_stations、test_blade_edge_position。Component Stationsの編集表・子午面上部の値一覧は画面から撤去。Blade Edgesと保存データ・Flow Area計算は維持 |
| 子午面LE/TEをHub・ShroudのR/Z [mm]で指定 | 実装確認済み | 動作確認済み（自動）: test_edge_rz_gui。IMP/DIFの全8端点、対応壁面の最近点への投影、適用前の保留・無変更時の精度維持、壁面/ドラッグ後の表示更新、一括Undo、旧JSON形式での往復。正規化入力は画面から撤去し内部互換APIのみ保持 |
| 子午面の直線・円弧追加時にLE/TEのR/Zを維持 | 実装確認済み | 動作確認済み（自動）: test_edge_rz_gui。Hub/Shroud両側、直線/円弧、連続追加、未適用入力、非選択翼列、1 UndoとJSON保存・翼列切替を確認。既存区間の削除・移動は維持 |
| 子午面の数値入力をフォーカス移動・Enter時に確定 | 実装確認済み | 動作確認済み（自動）: test_edge_rz_gui。長さ・半径・Sweep・開始Z/R/角度の入力途中はモデルと再計算信号を保持。確定時1更新、変更なしの再フォーカスでは更新なし、1 Undoを検証 |
| 子午面の寸法・開始条件・種類変更を優先しLE/TE位置を調整 | 実装確認済み | 動作確認済み（自動）: test_edge_rz_gui。旧端点が新壁面上に残れば保持し、外れる場合は対応壁面の最近点へ投影。全翼列・未適用入力・Undo/Redo・JSONを対象。壁面自体が無効な編集は拒否し、投影後の無効な翼は既存の形状・保存検証で検出 |
| DiffuserをHub/Shroud子午面上の断面とSpanwise線で3D化 | 実装確認済み | 動作確認済み（自動）: test_diffuser_3d。Hub/Tipの2断面配置、角度積分、LE/PS/TE/SS接続、静翼Cutoff、回転方向、独立分布・翼端、Undo/JSON、既存2D座標維持。Span別の独立分布編集は追加しない |
| Hub/Tip・中間Span、追加/削除、線形Span対応 | 実装確認済み | 動作確認済み（自動）: test_blade_sections、test_preview_3d、test_blade_edge_span_interpolation |
| Copy Hub→Tip / Tip→Hubボタンの撤去 | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui、test_shared_edges_annulus_gui。既存の内部コピーAPIとUndoは保持 |
| 2D Camber/PS/SS/LE/TE、surface mapping | 実装確認済み | 動作確認済み（自動）: test_camber、test_surface、test_pitch、test_edges |
| XYZ/RTZ断面、XY/XZ/YZ projection | 実装確認済み | 動作確認済み（自動）: test_geometry_3d、test_target_editor_gui |
| インペラTE CutoffをHub TEの外径Dの円筒面で切断 | 実装確認済み | 関連自動テスト成功: test_cylindrical_cutoff。全SpanでR=D/2、PS/SSとの接続、正負角度・回転・PS mapping、端部の延長、JSON往復・TurboGrid座標を検証。到達不能なSpanは拒否。円形・楕円TEと静翼のCutoffは維持 |
| Full Annulusの対象・選択断面・投影追従 | 実装確認済み | 動作確認済み（自動）: test_annulus、test_shared_edges_annulus_gui |
| 2D/3Dの独立した単翼・Full Annulus切り替え | 実装確認済み | 動作確認済み（自動）: test_persistent_model_gui。Full Annulusタブと上部Viewグループから操作。Impeller/静翼の翼枚数に追従し、設計値・カメラを保持。3D全周は描画用に各線最大151点を使用し、計算・出力は変更しない。表示チェックはJSONへ保存しない |
| 指定JSONをアプリ起動・Newのデフォルトに使用 | 実装確認済み | 動作確認済み（自動）: test_application_defaults_gui。blade_v03.jsonをアプリ内defaults/default_project.jsonへコピー。元ファイルを保持し、main.py/F5起動・Newへ適用。--projectは優先。F5実操作は未確認 |
| 右側上部で翼列ごとの翼枚数を編集 | 実装確認済み | 動作確認済み（自動）: test_application_defaults_gui。既存vane_count入力を移動。表示・Undo・JSON・出力の同じ設定を使用。子午面では非表示 |
| Diffuser Curvature（Viewから表示） | 実装確認済み | 動作確認済み（自動）: test_curvature、test_shared_edges_annulus_gui。Diffuser選択時の曲率を表示 |
| ソフトウェア3D、Hub/Shroud回転面・翼/Span線・表示選択 | 実装確認済み | 動作確認済み（自動）: test_revolved_surface、test_preview_3d、test_spanwise_wireframe。Z軸回り360度の半透明壁面、チェックによる非表示、全周翼への切替時の壁面維持、面全体のFit View。native描画は未確認 |
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

2026-10-12 再開後の検証: 同じ承認手順で検証コマンドを実行できました。拡張関連108 passed（artifacts/test-runs/20261012T103159Z-ed8397bf）。Git status・diff --check・cached statを確認し、stageはありません。最終全回帰457 passed / 0 failure / 0 error / 0 skipped（artifacts/test-runs/20261012T103211Z-03c1e786）。数値fixture・原本JSON・保存/出力形式を維持し、実画面操作は未確認です。stage/commit/pushは未実施。下記の429による未実行記録は過去の停止時点の記録です。

2026-10-12 翼列数に対応するLE/TE表とドラッグ点（codex/edge-groups-per-blade-row）: Impeller/Diffuserの2組固定を撤去し、各翼列IDにHub LE・Shroud LE・Hub TE・Shroud TEの4行と、子午面上のLE/TE線・ドラッグ点を設けました。RC追加では既存Diffuserの欄・名前・値を維持し、新しい独立した欄を追加します。追加時の初期値は従来どおり同種類の翼列設定をコピーし、その後は独立して編集します。名前変更・順番変更・削除・Undoで表と線が追従します。旧impeller_edges/diffuser_edgesの入力APIは選択中/最初の同種類翼列への互換参照として維持し、画面の管理・保存は全翼列IDで行います。JSON schema・数値計算・CSV/TurboGrid形式は変更していません。
変更: gui/blade_edge_editor.py・blade_edge_handles.py・context_meridional.py・meridional_editor.py・main_window.py、tests/test_all_row_edges_gui.py・test_design_navigator_gui.py・test_edge_rz_gui.py、FEATURES.md・README.md・docs/ARCHITECTURE.md。
初回関連試験は60 passed / 4 failed（artifacts/test-runs/20261012T021247Z-c731b5ef）。3件は「追加翼列の名前が既存の同種類欄を置き換える」という旧表示の期待だったため、独立した追加欄を確認する期待へ変更しました。残り1件は内部snapshotへ直接値を入れる試験だったため、全翼列を管理するGUIの正規化入力へ同じ0.999を入れる形に変更し、短縮後の端点1と保存拒否の期待は維持しました。数値fixtureは変更していません。
修正後の関連24件成功（artifacts/test-runs/20261012T021843Z-cdc0989e）。RC追加で12行・LE/TE 6本、元Diffuserの値の維持、非選択RCのR/Z編集・ドラッグ精度・1 Undo・JSON往復、名前変更/順序/削除/復元、全翼列の区間追加時位置維持を確認しました。指定blade_v03.jsonも原本を変更せず読み、RC追加後の3組とDiffuser値不変をoffscreen確認しました。
当時の拡張関連テスト・全回帰コマンドは利用上限で自動承認レビューが完了せず未実行。継続指示後の再試行も「exceeded retry limit / 429 Too Many Requests」で拒否され、実行されていません。安全性の判定による拒否ではなく承認レビューの実行制限であり、確認を回避する実行は行っていません。最終Git status/diff確認も未実行です。先に実行したgit diff --checkは成功しましたが、最終コード全体の確認済みとは扱いません。説明資料は更新済み。既存の未コミット変更・原本JSONを保持し、実画面操作は未確認、stage/commit/pushは未実施です。

2026-10-12 中央3Dの対象別表示（codex/contextual-3d-rows）: 子午面は全翼列と共通壁面、選択翼列はその翼と所属Hub/Shroud区間を表示。全未割当の旧Projectは全壁面、部分割当の未所属壁面は非表示、離れた区間は別々の面です。全周表示は翼列別の枚数を使います。無効な翼列は全翼列表示から除外して名前・理由を表示し、他の形状・2D編集を維持します。変更: geometry/row_domain.py・gui/main_window.py・preview_3d.py、tests/test_contextual_3d_gui.py、FEATURES.md・README.md・docs/ARCHITECTURE.md。初回関連試験は32 passed / 1 failed（artifacts/test-runs/20261012T013353Z-cebc6c33）。翼列復元中の旧形状で表示cacheを作ったためDiffuser切替に反映されず、復元中の更新を止め、再計算時にcacheを無効化するよう修正。追加試験28件は成功し、入力変更直後の全周切替を追加検証しています。指定blade_v03.jsonでも子午面の2翼列・488 Spanwise線と、Diffuser選択時の所属回転面をoffscreen確認。診断用コマンドの初回stdoutはcp932で中点文字を出せず失敗し、UTF-8指定で再確認しました。形状計算の失敗ではありません。修正後の関連60件成功（artifacts/test-runs/20261012T013921Z-601fd17b）。最終全回帰450 passed / 0 failure / 0 error / 0 skipped（artifacts/test-runs/20261012T013935Z-41c9df27）。自動描画画像 artifacts/contextual-3d-review/all-rows.png・diffuser.pngを確認し、全翼列と選択Diffuserの所属壁面表示を確認。画像生成プロセスだけMeiryoを明示読込し、アプリのフォント設定は変更していません。元JSON・数値fixture・出力形式は変更せず、実画面操作は未確認、stage/commit/pushは未実施です。

2026-10-11 Diffuser 2断面・選択時LE/TE保持（codex/preserve-row-edge-selection）: 中間Span生成を撤去し、Hub/Shroudの2断面をSpanwiseで直接接続。blade_v03.jsonの読み込み直後とDiffuser選択後を確認し、トップレベルDIF値とDiffuser内の古いsnapshotが異なることを確認しました。起動・読込では表示値を対応する所有翼列へ引き継ぎ、その後はIMP/DIFの各欄を選択中/最初の同種類翼列へ同期します。他の同種類翼列の独立値は維持。指定JSONで切替前後の両LE/TE不変、Ready・2断面、原本SHA256不変をoffscreen確認。変更: models/blade_rows.py・gui/main_window.py・geometry/geometry_3d.py、tests/test_row_edge_selection_gui.py・test_diffuser_3d.py・test_application_defaults_gui.py、FEATURES.md・README.md・docs/ARCHITECTURE.md。初回関連試験は31 passed / 2 failed（artifacts/test-runs/20261011T142339Z-4d05f4b7）。旧デフォルト内の古い控えも読込補正の対象となるため、起動/New試験の期待値をその補正後へ更新し、既定の数値と原本・数値fixtureは変更していません。修正後の関連88件成功（artifacts/test-runs/20261011T142641Z-c2743877）。最終全回帰441 passed / 0 failure / 0 error / 0 skipped（artifacts/test-runs/20261011T142706Z-7e47c661）。環境エラーはありません。Git差分を確認し、既存の未コミット作業を保持。実画面操作は未確認、stage/commit/pushは未実施です。

2026-10-11 Diffuserの子午面3D（codex/diffuser-meridional-3d、初期3断面版の記録。現在は上記の2断面版へ変更済み）: DIFのHub/Shroud LE/TEと子午面を使い、共通分布のHub・中間Span・Tip断面を生成し、対応点をSpanwise線で接続します。中央下段とViewの3D Preview、全周表示へ適用します。既存2D/CSV・JSON・Impeller計算を維持。変更: geometry/geometry_3d.py・designer.py、gui/main_window.py・preview_3d.py、tests/test_diffuser_3d.py・test_row_domain_gui.py・test_persistent_model_gui.py・test_revolved_surface.py、README.md・FEATURES.md・docs/ARCHITECTURE.md。初回の新規試験は8 passed / 1 failed。JSON読込時の既存Fit View動作とカメラ保持の期待が矛盾していたため、編集・Undo/Redoの時点でカメラ保持を確認するよう修正しました。関連試験では旧Z=0 APIを呼ぶ回転面テストを新3D APIへ更新しています。解析的な円錐壁面・翼角度・端点接続と旧2D座標の不変性を検証し、数値fixtureは変更していません。関連試験の旧API呼出しは54 passed / 1 failedから修正後58 passed。初回全回帰は旧API更新中に中断しました。次の全回帰（434 passed / 1 failed、artifacts/test-runs/20261011T135702Z-112f89f0）で、厚い2D翼が狭い子午面範囲では3Dとして無効になると2D更新まで止める不具合を検出し、3Dエラーを独立して扱うよう修正しました。無効な3Dは前回形状と理由表示、有効な2Dは更新継続する回帰テストを追加。関連58件成功（artifacts/test-runs/20261011T135458Z-ebdc49ea）、3Dエラー対応後の関連19件成功（artifacts/test-runs/20261011T140340Z-22e6f454）。追加の表示名保持調整後、最終全回帰436 passed / 0 failure / 0 error / 0 skipped（artifacts/test-runs/20261011T140643Z-642de743）。コード調整中の全回帰は中断し、最終コードで全件再実行しました。環境エラーはありません。指定デフォルトのoffscreen起動でReady・Diffuser 3断面も確認。実画面操作・TurboGrid実機Importは未確認、stage/commit/pushは未実施です。

2026-10-11 子午面数値入力の確定時更新（codex/meridional-defer-numeric-input）: 入力欄のkeyboardTrackingを無効にし、1桁ごとの再計算を止めました。フォーカス移動・Enterで反映し、スピン操作・数値計算・保存形式を維持します。変更: gui/meridional_editor.py、tests/test_edge_rz_gui.py、README.md・FEATURES.md・docs/ARCHITECTURE.md。関連83件成功（artifacts/test-runs/20261011T130852Z-d3b3a048）、全回帰423 passed / 0 failure / 0 error / 0 skipped（artifacts/test-runs/20261011T130905Z-94190929）。入力中の更新抑止、フォーカス移動・Enter確定、変更なし時の再計算抑止、1 UndoとRedoを自動確認しました。テスト失敗・環境エラーはありません。実画面操作は未確認、stage/commit/pushは未実施です。

2026-10-11 壁面編集優先への変更（`codex/wall-edit-adjust-blade-edges`）: ユーザーの最新指定に従い、LE/TEが新壁面から外れても寸法・種類・開始条件の編集を確定し、全翼列の端点を対応壁面の最近点へ投影します。壁面上に残る座標と未適用入力を保持し、1 Undoで一緒に復元します。従来の編集取り消し方針を置き換えました。初回関連試験は73 passed / 2 failed。1件は交差する壁面を作るテスト入力、1件は壁面出口へ投影した翼端で既存の保存検証が失敗するケースでした。前者は有効なArc→Line変換へ修正し、後者は壁面編集の確定と無効な翼の保存拒否を確認するテストへ修正しています。数値fixtureは変更していません。修正後の関連75件成功（artifacts/test-runs/20261011T113638Z-557754b9）、全回帰415 passed / 0 failure / 0 error / 0 skipped（artifacts/test-runs/20261011T113751Z-218db36d）。環境エラーはありません。前回の追加検証は利用上限により承認レビューが完了せず未実行でしたが、継続指示後に実行しました。今回の変更: geometry/blade_edge.py・gui/meridional_editor.py、tests/test_edge_rz_gui.py・test_undo_commands.py、FEATURES.md・README.md・docs/ARCHITECTURE.md。既存の未コミット作業を保持し、stage/commit/pushは未実施。実ディスプレイ操作とTurboGrid実機Importは未確認です。

2026-10-11 子午面編集時の翼端位置維持（`codex/preserve-edges-on-wall-edit`、旧方針の検証記録。上記の壁面編集優先へ変更済み）: 当時のユーザー指定に従い、全翼列のLE/TEのR/Zを維持できない寸法・種類・開始条件の編集は確定せず入力欄を元へ戻しました。関連107件成功（56件: `artifacts/test-runs/20261011T061754Z-49b799a0`、新規17件: `20261011T061858Z-aa6c445c`、GUI34件: `20261011T062018Z-444d0a7d`）、全回帰413件成功（`artifacts/test-runs/20261011T062209Z-29117831`）。数値fixtureは変更せず、既存の未コミット作業を保持。stage/commit/pushは未実施、実画面操作は未確認です。

2026-10-11 子午面区間の種類変更（`codex/meridional-segment-type`）: 区間表のType選択でLine/Arcを相互変更できます。経路長と所属IDを保持し、入力欄とプレビューを更新して1 UndoとJSON保存に対応します。関連56件成功（`artifacts/test-runs/20261011T055620Z-94986963`）、全回帰396件成功（`artifacts/test-runs/20261011T055946Z-93360ac4`）。変更: geometry/meridional_segments.py・gui/meridional_editor.py、tests/test_row_domain_gui.py、FEATURES.md・README.md・docs/ARCHITECTURE.md。実装失敗・環境エラーはありません。既存の未コミット変更を保持し、stage/commit/pushは未実施。Qt offscreen画像: `artifacts/segment-type-review/`。画像生成プロセスだけMeiryoを読み込み。実ディスプレイ操作は未確認です。

2026-10-11 区間追加時の翼端位置維持（`codex/preserve-edges-on-segment-add`）: 末尾へのLine/Arc追加時に、旧壁面距離を新全長で正規化し、全翼列のLE/TEのR/Zと未適用入力を保持します。追加と換算は1 Undoです。関連50件成功（`artifacts/test-runs/20261011T053930Z-51f202a3`）、全回帰390件成功（`artifacts/test-runs/20261011T054220Z-170ab0e1`）。変更: geometry/blade_edge.py、gui/meridional_editor.py・main_window.py、tests/test_edge_rz_gui.py、FEATURES.md・README.md・docs/ARCHITECTURE.md。実装失敗・環境エラーはありません。既存の未コミット変更を保持し、stage/commit/pushは未実施。実ディスプレイ操作は未確認です。

2026-10-11 翼列名の変更とRow表示同期（`codex/blade-row-names`）: 左に「名前変更 / Rename」を追加し、子午面Blade EdgesのRow名も翼列名へ同期します。関連25件成功（`artifacts/test-runs/20261011T051943Z-b91991b3`）、全回帰381件成功（`artifacts/test-runs/20261011T052120Z-1c071338`）。変更: gui/design_navigator.py・main_window.py・blade_edge_editor.py、tests/test_design_navigator_gui.py、FEATURES.md・README.md・docs/ARCHITECTURE.md。既存の未コミット変更を保持し、stage/commit/pushは未実施。Qt offscreen画像: `artifacts/row-name-review/`。画像生成プロセスだけMeiryoを読み込み。実ディスプレイ操作は未確認です。
初回関連試験は2 failed / 23 passed。テストが子午面選択を内部メソッドだけで切り替え、左の選択項目が翼列のまま「名前変更が無効」と期待していました。実際のTree選択操作へ修正後、関連25件成功。製品コードの不具合や環境エラーではなく、数値fixtureの変更もありません。

2026-10-11 子午面の翼端R/Z入力（`codex/meridional-edge-rz`）: 正規化0～1の表示を全8端点のR・Z [mm]入力へ変更。「R/Zを適用」で編集したペアだけを対応壁面へ投影してまとめて反映し、確定座標を表示します。関連65件・全回帰377件成功。関連レポート: `artifacts/test-runs/20261011T045847Z-1e331799`、全回帰: `artifacts/test-runs/20261011T050142Z-08aefad1`。変更: `gui/blade_edge_editor.py`・`meridional_editor.py`、新規`tests/test_edge_rz_gui.py`、FEATURES.md・README.md・docs/ARCHITECTURE.md。既存の計算・保存形式・ドラッグ・デフォルト・前回の変更を保持し、stage/commit/pushは未実施。Qt offscreen画像: `artifacts/edge-rz-review/`。画像生成プロセスだけMeiryoを読み込み。実ディスプレイ操作は未確認です。

2026-10-11 指定デフォルト更新・Hub/Shroud回転面（`codex/defaults-revolved-walls`）: blade_v03.json原本とアプリ内コピーのSHA256は`6511EA9186E18ACAD72EF055F0DBC1DE4AC0700C27DC75627ABAD065A9121BCE`で一致。原本は保持し、起動・Newと保存時の選択対象Diffuserへ反映します。Hub/Shroudは360度の半透明回転面で描画し、既存チェック・カメラ・全周翼・出力は維持します。関連27件成功、最終コードの全回帰 **366 passed / 0 failure / 0 error / 0 skipped**。記録: `artifacts/test-runs/20261011T044449Z-9a6fcccf/pytest.xml`と`result.json`。変更: `defaults/default_project.json`、`gui/preview_3d.py`、新規`geometry/revolved_surface.py`、新規`tests/test_revolved_surface.py`、`test_application_defaults_gui.py`・`test_spanwise_wireframe.py`、FEATURES.md・README.md・docs/ARCHITECTURE.md。前回の変更を保持し、stage/commit/pushは未実施。
初回関連試験は1 failed / 26 passed。新しいJSONの選択対象Diffuserに対し、テストがImpellerを想定していたため、対象を明示するよう修正しました。数値回帰fixtureは変更していません。環境エラーではありません。Qt offscreen画像: `artifacts/defaults-surfaces-review/`。画像生成プロセスだけMeiryoを読み込み。実ディスプレイでの操作は未確認です。

2026-10-11 中央子午面表示（`codex/central-meridional-view`）: 子午面選択時の中央上段を既存のMeridionalグラフへ切り替え、右側には数値・区間・所属の編集欄を残しました。翼列選択時は単翼/全周の設定を復元し、下段3D翼を維持します。関連43件成功、最終コードの全回帰 **357 passed / 0 failure / 0 error / 0 skipped**。記録: `artifacts/test-runs/20261011T042729Z-4e5c648c/pytest.xml`と`result.json`。実装失敗・環境エラーはありません。変更: `gui/main_window.py`、`tests/test_persistent_model_gui.py`・`test_target_layout_gui.py`、FEATURES.md・README.md・docs/ARCHITECTURE.md。前回の整理・円筒Cutoff変更を保持し、stage/commit/pushは未実施。
Qt offscreen画像: `artifacts/central-meridional-review/`。画像生成プロセスだけMeiryoを読み込み。実ディスプレイ・DPI/native操作は未確認です。

2026-10-11 インペラTEの円筒Cutoff（`codex/impeller-te-cylinder-cutoff`）: Hub側TEの直径を全Spanへ適用するユーザー指定に従い、PS/SSを円筒交点で切って閉じる処理へ変更。関連テスト43件成功、最終コードの全回帰 **354 passed / 0 failure / 0 error / 0 skipped**。記録: `artifacts/test-runs/20261011T040026Z-16a358da/pytest.xml`と`result.json`。保存済みデフォルトはD=162.40038390753767 mmで、Hub/TipのTE全点と基準半径との差は0。変更: `geometry/geometry_3d.py`・`blade_section.py`、新規`cylindrical_cutoff.py`、`tests/test_geometry_3d.py`、新規`tests/test_cylindrical_cutoff.py`、FEATURES.md・README.md・docs/ARCHITECTURE.md。前回の未コミット整理は保持し、stage/commit/pushは未実施。
途中の検証: 旧軸流Cutoffの期待値で1 failed / 21 passed。新仕様ではHub半径へ届かないTipを拒否する解析テストへ更新し、円形TEの既存範囲チェックは維持。追加テストの壁面終端ケースは、対応座標を設定せず壁面が重複する入力により1 failed / 86 passed。既存の壁面端対応ルールに合わせた入力へ修正後、関連43件成功。数値回帰fixtureは変更していません。環境エラーではありません。実ディスプレイの操作・TurboGrid実機Importは未確認です。

2026-10-11 ローカルのコード整理（`codex/refactor-gui-editors`）: 関連テスト46件成功、最終コードの全回帰 **322 passed / 0 failure / 0 error / 0 skipped**。記録: `artifacts/test-runs/20261011T005118Z-ec0f689c/pytest.xml`と`result.json`。共有グラフの一時Widget作成・付け替えを撤去し、表示更新の重複と未使用importを削除しました。数値計算、既定値、旧JSON互換API、CSV/TurboGrid形式を維持します。ユーザーデータ・履歴資料・既存ファイルは削除していません。実装失敗・環境エラーはありません。実ディスプレイの手動操作は未確認です。
変更ファイル: `gui/control_point_editor.py`・`profile_distribution_editor.py`・`main_window.py`・`export_settings_widget.py`・`meridional_editor.py`・`optimization_widget.py`、`geometry/designer.py`、`optimization/parameter_mapper.py`、`tests/test_editor_resources_gui.py`、FEATURES.md・README.md・docs/ARCHITECTURE.md。stage/commit/pushは未実施で、GitHubのv0.3.0最終版は変更していません。以下は前回の検証記録です。

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
