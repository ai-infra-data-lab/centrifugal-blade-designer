# 既存機能一覧

確認日: 2026-10-08。対象: Centrifugal Compressor Blade Designer v0.3。
実装は現行ソースを調査し、動作は既存277件のテスト再実行で判定しました。
**動作確認済み（自動）はWindows .venv / Qt offscreenでの確認**です。実ディスプレイ・VS Codeボタン操作・TurboGrid実機まで確認した意味ではありません。

| 機能 | 実装状態 | 動作状態・根拠 |
|---|---|---|
| main.py起動、design / optimization、--project | 実装確認済み | 動作確認済み（自動）: test_simultaneous_editors、test_optimization_gui。native画面は未確認 |
| Blade View常時表示、右Editor・下部Context | 実装確認済み | 動作確認済み（自動）: test_gui、test_flow_area_gui |
| Impeller / Diffuserの独立した角度・厚さ・LE/TE | 実装確認済み | 動作確認済み（自動）: test_target_profiles、test_target_editor_gui |
| Hub/Tip角度・厚さを同じグラフで表示・表編集・Add/Delete/Drag | 実装確認済み | 動作確認済み（自動）: test_simultaneous_editors。重なるHub中心/Tip外輪もQt mouseイベントで検証 |
| 共通PCHIP、control pointを通り単調列のovershootを抑える | 実装確認済み | 動作確認済み（自動）: test_shared_pchip、test_distributions、test_thickness |
| 共通Impeller LE/TEタイプ・楕円比、Diffuser側は独立 | 実装確認済み | 動作確認済み（自動）: test_shared_edges_annulus_gui、test_edges |
| Hub/Shroud Line/Arc chain、G1接線、解析的長さ | 実装確認済み | 動作確認済み（自動）: test_meridional_line/arc/arc_arc/tangent/length |
| invalid geometry、負の半径、交差、非finiteの検出 | 実装確認済み | 動作確認済み（自動）: test_meridional_invalid、test_validation、test_checks |
| Flow Path、Component Stations、翼端位置、normalized meridional | 実装確認済み | 動作確認済み（自動）: test_flow_path、test_component_stations、test_blade_edge_position |
| Hub/Tip・中間Span、追加/削除、線形Span対応 | 実装確認済み | 動作確認済み（自動）: test_blade_sections、test_preview_3d、test_blade_edge_span_interpolation |
| Copy Hub→Tip / Tip→Hub（角度・厚さの上書きコピー） | 実装確認済み | 動作確認済み（自動）: test_shared_edges_annulus_gui。Undo可能 |
| 2D Camber/PS/SS/LE/TE、surface mapping | 実装確認済み | 動作確認済み（自動）: test_camber、test_surface、test_pitch、test_edges |
| XYZ/RTZ断面、XY/XZ/YZ projection | 実装確認済み | 動作確認済み（自動）: test_geometry_3d、test_target_editor_gui |
| Full Annulusの対象・選択断面・投影追従 | 実装確認済み | 動作確認済み（自動）: test_annulus、test_shared_edges_annulus_gui |
| Diffuser Curvature（Impellerでは非表示） | 実装確認済み | 動作確認済み（自動）: test_curvature、test_shared_edges_annulus_gui |
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
| VS Code launch/tasks/Test Explorer設定 | 実装確認済み（設定作成） | JSON・対象ファイル・CLIテスト確認済み。F5/Testing画面のクリック実行は未確認 |
| Codex VS Code拡張のサインインと依頼実行 | 未確認 | 拡張導入状況は環境報告へ記載。本人の認証・対話は未実施 |
| WSL2 / Ubuntu 24.04実行 | 未確認 | 現在の環境では問題あり: distroなし、WSL2を使える構成ではない。Linux実行は未実施 |

## 検証上の問題と扱い

通常のpytest -q -W errorは、sandbox内TEMPの作成失敗（47 setup errors）と過去のcacheへのアクセス拒否で終了しました。
テストコード・比較値は変更せず、tools/run_tests.pyでプロジェクト内の専用TEMPを使いcacheproviderを無効化した再実行は **277 passed / 0 failure / 0 error / 0 warning**。
キャッシュを使わないため--last-failed等のcache依存機能はこの設定では使いません。

解析解で比較する試験と、過去実装の座標を保つ試験を区別してください。NPZの一致を実機の正しさの保証にしないでください。説明はdocs/DEVELOPMENT.mdの「数値の基準」を参照。

未実装・今回対象外: Splitter、tip clearance、専用lean/sweep/rake、optimization探索、CFX実行、自動meshing、STEP/IGES・Solid CAD。
詳細の手動確認手順はdocs/DEVELOPMENT.mdにあります。
