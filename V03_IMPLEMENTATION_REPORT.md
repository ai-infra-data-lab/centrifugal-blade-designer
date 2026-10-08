> この文書はFlow Path拡張前の実装記録です。最新結果は[V03_FLOW_PATH_REPORT.md](V03_FLOW_PATH_REPORT.md)を参照してください。

# v0.3 実装報告（2026-10-04）

実装・自動検証を完了しました。TurboGrid実機Importは未検証です。
対象ディレクトリ: C:\Codex\pythonのGUI作成\centrifugal_blade_designer
既存のblade.json / blade.csvは変更せず、Smoke checkでSHA-256が不変であることを確認しました。
修正前のソースをartifacts/v0.2-before-v0.3.zipへ退避しています。

## 1. 変更したファイル

- OPTIMIZATION_ARCHITECTURE.md
- README.md
- blade_designer/fileio/project_io.py
- blade_designer/geometry/designer.py
- blade_designer/geometry/distributions.py
- blade_designer/geometry/thickness.py
- blade_designer/gui/control_point_editor.py
- blade_designer/gui/main_window.py
- blade_designer/gui/metrics_widget.py
- blade_designer/gui/parameter_panel.py
- blade_designer/gui/plot_widgets.py
- blade_designer/models/parameters.py
- blade_designer/optimization/feasibility.py
- blade_designer/optimization/parameter_mapper.py
- tests/test_gui.py
- tests/test_thickness.py

## 2. 新規作成したファイル

- blade_designer/fileio/project_migration.py
- blade_designer/fileio/turbogrid_export.py
- blade_designer/geometry/blade_section.py
- blade_designer/geometry/geometry_3d.py
- blade_designer/geometry/meridional_segments.py
- blade_designer/geometry/span.py
- blade_designer/gui/meridional_editor.py
- blade_designer/gui/output_editor.py
- blade_designer/gui/preview_3d.py
- blade_designer/gui/section_selector.py
- blade_designer/models/geometry_3d.py
- blade_designer/models/meridional.py
- tests/test_blade_sections.py
- tests/test_geometry_3d.py
- tests/test_meridional_arc.py
- tests/test_meridional_arc_arc.py
- tests/test_meridional_gui.py
- tests/test_meridional_invalid.py
- tests/test_meridional_length.py
- tests/test_meridional_line.py
- tests/test_meridional_tangent.py
- tests/test_normalized_meridional.py
- tests/test_preview_3d.py
- tests/test_project_migration_v03.py
- tests/test_shared_pchip.py
- tests/test_turbogrid_export.py
- tools/v03_smoke.py
- V03_IMPLEMENTATION_REPORT.md

生成確認資料: artifacts/v0.3のPNG、stage_results.json、final_pytest.txt、smoke_result.json、default_v03.json、legacy_migrated_v03.json、Diffuser CSV、default_case / five_span_caseの各4ファイル。
公式サンプルの照合用控え: artifacts/turbogrid_reference/official_stator_BladeGen.inf.txt。

## 3. GUI構造

Blade Viewを左側に常時表示し、右側のEditorだけを切り替える構成です。
Blade Angle / Thickness / LE・TE / Meridional / Output / 3D Previewを分離しました。
既存のDiffuser Geometry、Full Annulus、Curvature、Metrics、Optimizationも保持しています。
1280pxの画面でBlade幅754px / Editor幅484pxをSmoke checkで確認しました。
起動・New・Open・Fit ViewでのみBlade/EditorをFitし、通常更新はsetDataです。
Angle/Thickness/LE・TE/Meridional変更時のZoom/Pan維持をGUIテストで確認しています。

## 4. PCHIP共通化

geometry/distributions.pyのdistribution_interpolator / interpolate_distributionを共通化しました。
Blade Angle、Thickness、既存Optimizationの角度評価・導関数も同じPCHIP実装を使用します。
v0.2のThickness端点勾配ゼロHermiteは、正本仕様に従い変更しました。
制御点通過、単調性、overshoot防止と同一共通関数の使用をテストしています。

## 5. Meridional Line/Arc Geometry

Start Z/R/angleとSegment列から解析Line/Arcを順次構築します。
LineはLength、ArcはRadius/Sweep/CWまたはCCWで指定し、任意個数を接続できます。
生成結果はSegmentの始点/終点/接線、Arc中心/半径/符号付きSweepとZ/R/m配列を保持します。
サンプルmは累積hypot(dR,dZ)、解析Segment lengthはLine length / Radius*|sweep|です。
NaN/Inf、非正Length/Radius、ゼロSweep、負R、子午面自己交差、Hub/Shroud交差・接触を拒否します。
360度以上のArcは非単純な流路を避けるため拒否します。

## 6. G1 Tangency

次Segmentの始点と単位接線を前Segmentから直接継承します。
Arc中心を始点から接線の左右法線方向にRadiusだけ移した位置に置き、終点と終接線を同じ符号付きSweepで回転します。
Line–Arc / Arc–Line / Arc–Arcの位置と接線一致を解析値で確認しました。

## 7. Hub/Tip Blade Profile

BladeParameters.sectionsにHub=0 / Tip=1を既定で保持し、任意の内部Spanに対応します。
各断面に独立したβm・Thickness・LE/TEを持ち、GUIで切替・コピー・追加・削除できます。
Hub/Tipの削除は禁止です。旧属性はHubを参照し、分布全体の再代入でも旧APIとの整合性を維持します。
HubはHub壁面、TipはShroud壁面、中間断面は全流路の対応station位置を線形Span補間した壁面上に配置します。
共通LE/TE stationを使用し、各断面の真の子午面距離でm_normを0～1へ正規化します。
Camber、PS、SS、Circular/Elliptical/Cutoff LE/TEを各断面について生成します。
内部masterと出力点数を分離し、既定21 / 101 / 21 / 101を維持しました。

## 8. 3D Geometry / Preview

dtheta/dm=tan(beta_m)/Rを積分し、R/theta/ZとXYZを保持します。
厚さを局所子午面・周方向の法線方向へ配置して壁面座標へ写像し、端部を共通Edge Engineで生成します。
constant-Rの解析解、座標変換、端部接続、中間station、出力点数からの独立性をテストしました。
master輪郭の自己交差/厚さ縮退も検査します。
PyVista/VTK/OpenGLは未導入のため、QtによるSoftware Wireframeを実装しました。
回転/Pan/Zoomが可能で、更新前後のcamera_position保存・復元をGUIテストで確認しました。

## 9. TurboGrid Export形式

fileio/turbogrid_export.pyでhub.curve / shroud.curve / profile.curve / BladeGen.infを生成します。
内部Z軸・mm座標を設定したX/Y/Z軸、MM/CM/M単位へ変換します。
壁面はラベルなしXYZの上流→下流列、既定501点です。
翼断面はHub→内部Span→Tip、#行区切り、LE→PS→TE→SS逆順→LEの閉輪郭です。
通常のSegment接続頂点を重複させず、閉鎖点は最後に1回だけ出力します。鋭い端部の連続重複点も除去します。
通常の既定輪郭は241点で、le/teマーカーを第4フィールドに出力します。
有効桁は1～15、既定6、JSONはfull precisionです。
Init FileはBlade Count・軸・単位・3ファイル名・Blades Per Set=1と確認済みLE/TE設定を含みます。
Geometry EngineにはTurboGridの書式・座標順序処理を入れていません。

## 10. .inf形式の確認資料

Ansys 2026 R1の以下の一次資料を使用しました。

- [User's Guide 2.1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i998527.html): Init Fileの構文、単位、Blade 0 LE/TEのEnum。
- [User's Guide 10.3.6](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i016457045820452615547.html): 壁面・翼の座標列、断面順序、le/teマーカー。
- [公式stator.zip](https://ansyshelp.ansys.com/public/Views/Secured/Doc_Assets/v261/TurboGrid/stator.zip): 実際に取得し、BladeGen.infの軸/Blade Sets/単位/ファイル名構文を照合。

このPCではANSYS/TurboGridのインストールおよびAWP_ROOT等の環境変数を確認できませんでした。
確認対象形式は公式2026 R1資料であり、インストール済みTurboGridとの実行確認はありません。

## 11. pytest結果

| Stage | 完了時の全体pytest成功件数 | Failure |
| --- | ---: | ---: |
| 1 | 109 | 0 |
| 2 | 110 | 0 |
| 3 | 111 | 0 |
| 4 | 127 | 0 |
| 5 | 128 | 0 |
| 6 | 129 | 0 |
| 7 | 137 | 0 |
| 8 | 138 | 0 |
| 9 | 143 | 0 |
| 10 | 161 | 0 |

最終: .\.venv\Scripts\pytest.exe -q -W error → 161 passed in 23.17s、exit code 0。
元の109件を含む回帰検証です。既存テストの変更はGUIレイアウトと正本仕様によるThickness PCHIPへの変更に対応するものです。
Schema 0.1/0.2移行、Schema 0.3 full precision、5断面、四つのExportファイル、点順序/閉鎖/有限値、GUI保存・再読込・Export接続を検証しました。

## 12. Manual / Smoke確認

tools/v03_smoke.pyを実行し、Default 2断面・5断面の4ファイル生成、旧blade.jsonの読込と別名保存、既存JSON/CSVが不変であることを確認しました。
QtでBlade Angle / Meridional / Output / 3D Preview / LE・TE / 5-Span Previewを描画し、画面画像を目視確認しました。
GUIのMouse Dragやダイアログ処理接続はQtイベント・ダイアログMockによる自動テストです。
OS標準ダイアログを人が操作する試験は未実施です。
TurboGrid起動・Import・Hub/Tip/LE/TE方向・反転・Geometry Errorの実機確認は未実施です。
READMEに再現手順と実機Import確認項目を記載しました。

## 13. 既知の問題・制限

- TurboGrid実機Importが未検証のため、すべての設計・バージョンでのKernel受入れを保証しません。
- 3DはWireframe Previewで、CAD品質のSurfaceではありません。Throat/Curvature/Optimizationの継続機能はDiffuser 2D用です。
- Span補間は線形です。複雑な壁面対応やSpan方向Surface/隣接翼の3D交差保証は対象外です。
- PS/SS Autoは幾何学的推定です。実際の流れ条件に応じてmappingを明示できます。
- Rounded/CutoffがSpanで混在するauto端部は.infの該当キーを省略し、profile markersとTurboGrid判定へ委ねます。実機確認が必要です。
- 翼輪郭検査は有限master点です。低い有効桁では別々の点が同じ文字列になることがあり、Import前に十分な桁数を使用する必要があります。
- New/Open/Exitでは未保存変更を保持しません。

## 14. 次Versionへ残した項目

Fillet編集コマンド、より高度なSpan補間、PyVista Surface Preview、TurboGrid実機Import検証。
今回の仕様対象外であるSplitter / Tip clearance / 専用Lean・Sweep・Rake / CFD・自動Meshing・Optimization実行 / STEP・IGES・Solid CADは実装していません。
