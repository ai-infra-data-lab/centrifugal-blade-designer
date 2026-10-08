# v0.3 Flow Path / Gross Flow Area 実装報告

2026-10-04。正本仕様: [V03_FLOW_PATH_SPEC.md](V03_FLOW_PATH_SPEC.md)。
実装と自動検証は完了しました。TurboGrid実機Importは未実施です。

## 1. Existing code inspection result

既存のmodels / geometry / fileio / gui / optimization / testsを確認しました。
初期状態はv0.3のLine/Arc・Hub/Tip・3D Wireframe・TurboGrid Exportが実装済みで、161 passedでした。
既存2D Diffuser、CSV、Project Save/Load、Throat/Curvature、最適化パラメータ層を維持して拡張しました。
変更前のソースはartifacts/v0.3-before-flow-path.zipに保存しました。

## 2. Modified files

今回変更した既存ファイルは27件です。

- README.md
- V03_IMPLEMENTATION_REPORT.md
- blade_designer/fileio/project_io.py
- blade_designer/fileio/project_migration.py
- blade_designer/geometry/blade_section.py
- blade_designer/geometry/designer.py
- blade_designer/geometry/distributions.py
- blade_designer/geometry/geometry_3d.py
- blade_designer/geometry/meridional_segments.py
- blade_designer/geometry/span.py
- blade_designer/geometry/thickness.py
- blade_designer/gui/control_point_editor.py
- blade_designer/gui/main_window.py
- blade_designer/gui/meridional_editor.py
- blade_designer/gui/metrics_widget.py
- blade_designer/gui/optimization_widget.py
- blade_designer/gui/output_editor.py
- blade_designer/gui/preview_3d.py
- blade_designer/models/geometry_3d.py
- blade_designer/models/meridional.py
- blade_designer/models/parameters.py
- tests/test_gui.py
- tests/test_meridional_length.py
- tests/test_normalized_meridional.py
- tests/test_preview_3d.py
- tests/test_turbogrid_export.py
- tools/v03_smoke.py

## 3. New files

今回追加したファイルは21件です。

- V03_FLOW_PATH_REPORT.md
- V03_FLOW_PATH_SPEC.md
- blade_designer/geometry/flow_area.py
- blade_designer/geometry/flow_path.py
- blade_designer/geometry/resolution.py
- blade_designer/geometry/station_alignment.py
- blade_designer/gui/context_meridional.py
- blade_designer/gui/flow_area_widget.py
- blade_designer/models/flow_area.py
- blade_designer/models/flow_path.py
- blade_designer/models/resolution.py
- tests/fixtures/old_v03_flow_path.json
- tests/fixtures/old_v03_profiles.npz
- tests/test_component_stations.py
- tests/test_flow_area_axial.py
- tests/test_flow_area_general.py
- tests/test_flow_area_gui.py
- tests/test_flow_area_radial.py
- tests/test_flow_path.py
- tests/test_geometry_resolution.py
- tests/test_project_flow_path_migration.py

画面・case・テスト記録はartifacts/v0.3-flow-pathにあります。生成物は上記ソース一覧に含めていません。
旧座標fixtureはバックアップした変更前のエンジンで生成し、新実装を期待値生成に使っていません。

## 4. GUI architecture changes

左Blade Viewを常時表示し、右Section Selector + Editorを保持しました。
右EditorはAngle / Thickness / LE・TE / Meridional / Outputと従来機能です。
下部Context ViewへMeridional / Flow Area / Metrics / 3D Previewを配置しました。
上下はQSplitterで調整でき、下部の6 Station表と全カーソル情報が重ならない最小表示領域を確保しました。
領域名・Station値は文字で読める表示にし、密集する出口ラベルの重なりを避けました。

## 5. View preservation implementation

Geometry更新は既存graphic itemのsetDataで行います。
起動・New・Open・Fit View以外にPlotのAuto Fitを行いません。
Blade / Editor / Meridional / Areaの範囲保持、Areaが計算不能になる編集時の範囲保持もGUIテストしました。
3Dはcamera_positionのdeepcopyを更新前後に保存・復元し、Section・Station編集とContext切替でもCameraを保持します。

## 6. PCHIP common interpolator

Blade AngleとThicknessはgeometry/distributions.pyの共通interpolate_distributionを通ります。
scipy.interpolate.PchipInterpolator(extrapolate=False)を使用します。
制御点通過・単調分布のovershoot防止・共通補間使用は既存テストを含めて成功しました。
新しい配列・Control Point・3Dモデルではm_blade_normを使い、旧m_normは互換aliasとして残しました。
GUI操作も同一ControlPointEditorのAdd / Delete / Drag / 表編集です。

## 7. Meridional Line/Arc implementation

Start Z/R/angleからLineとCircular Arcを順に生成します。
結果にSegment始点・終点・単位接線・長さ、Arc中心・半径・符号付きSweepを保持します。
Line/Arc結果のmは解析弧長の累積値で、総長はLine長 + R|sweep|の総和に一致します。
一般曲線・平均流路の距離は累積hypot(dR,dZ)を使用します。
非正Length/Radius/R、無効Sweep、NaN/Inf、自己交差、Hub/Shroud交差・接触を検出します。

## 8. Arc-to-Arc G1 implementation

前Segmentの終点と終端単位接線を次Segmentへ継承します。
Arc中心は始点 ± R×局所法線、終点・終端接線はSweepで回転して求めます。
Line–Line / Line–Arc / Arc–Line / Arc–Arcを同じ接続方式で扱います。
R20→R40などの解析接続点、単位接線dot≈1、弧長・端点・接線のテストが成功しました。
Filletを基本Geometryにしていません。

## 9. Flow Path station implementation

INLET < IMP_LE < IMP_TE < DIF_LE < DIF_TE < OUTLETを厳密に検証します。
m_flow_normをProjectへfull precisionで保存し、Geometry変更で値を維持します。
流路全体はm_flow_norm=(m-m_inlet)/(m_outlet-m_inlet)、Blade Row内はm_blade_norm=(m-m_LE)/(m_TE-m_LE)です。
Impeller/DiffuserのRow座標変換関数を独立させました。
新規設計ではImpeller LE/TEの壁面座標をStationの法線交点へ揃えます。
従来blade_le_fraction / blade_te_fractionはIMP_LE/TEを参照する互換aliasで、JSON内の不一致を拒否します。
Station設定はMeridional Editor、同じIMP値の互換編集はOutputにあります。

## 10. Component region implementation

Inlet / Impeller / Vaneless Diffuser・Gap / Vaned Diffuser / Outletの5領域をStationから生成します。
Meridional Context Viewに全領域名・範囲とStation境界を表示します。
カーソル情報には選択位置の領域名を表示します。
DIF_LE/TEはFlow Path上の領域境界です。従来Diffuser 2Dの半径設定・指標を自動変更しません。

## 11. Gross Flow Area algorithm

Hub/Shroudを共通の壁面弧長fractionへ再サンプリングし、独立関数で平均流路を生成します。
平均流路の物理累積距離を正規化し、局所接線からR-Z法線を生成します。
平均点を通る無限法線と有限長のLine/Arcを解析的に交差させ、実際のPh/Psを得ます。
L_hs=|Ps-Ph|、Rc=(Rh+Rs)/2、A_gross=2π Rc L_hsを使用します。
複数交点は対応する壁面seedに近い局所枝から選び、同距離の曖昧な交点はErrorとします。
有限壁面に交点がない位置を外挿しません。GUIはその位置をN/Aにし、Area曲線も切り、理由を表示します。
A/A_IMP_LEと6 StationのArea表、物理m・Region・Area・Hub/Shroud R・L_hsを表示します。
Area上のマウス移動、Station表、Meridionalでの選択がCross-flow lineとArea Markerに双方向で連動します。
Blockage・Effective Areaは今回計算しません。

## 12. Axial analytical test result

Hub R=50 mm、Shroud R=70 mm、長さ100 mmで、π(70²−50²)=7539.8223686155 mm²へ一致しました。
異なる壁面表示点数でも相対許容誤差1e-13のテストが成功しました。

## 13. Radial analytical test result

R=50→150 mm、軸方向幅b=20 mmで、全位置のA=2πRbへ相対許容誤差1e-13で一致しました。
両壁交点のR一致、面積の増加も検証しました。
斜め流路、同心円弧の解析交点・面積、微小変更時の面積連続性も成功しました。

## 14. Hub/Tip Blade Section implementation

独立したHub/Tipのβm・Thickness・Circular/Elliptical/Cutoff端部を保持しています。
任意の中間Spanを追加でき、コピー後は独立して編集できます。Hub/Tipは削除できません。
新規設計は法線断面へ揃えたLE/TEの壁面位置を通る対応座標をSpanで線形補間します。
LE/TEの非グリッド位置を明示的な補間knotsへ加え、Stationとの一致を保持します。
各断面自身の物理距離でβm/厚さを補間し、tanβm=R dθ/dmを積分します。

## 15. 3D geometry implementation

各Camber/PS/SS/LE/TEでR・Theta・Z、X=Rcosθ・Y=Rsinθ・Zを保持します。
Master Geometryから出力点数へ再サンプリングします。
resolution設定の既定値はProfile2001 / Edge401 / Wall8001 / Mean4001 / Area501です。
内部解像度をProjectで変更でき、Output点数から独立しています。
3Dは既存のQt Software Wireframeで、PyVista/VTK/OpenGLを必須にしません。CAD面の生成は行いません。

## 16. TurboGrid export implementation

既存fileio/turbogrid_export.pyを維持し、新しいStation・内部Geometryにも適用しました。
hub.curve / shroud.curveは上流→下流のXYZ、profile.curveはHub→中間Span→Tipです。
各輪郭はLE→PS→TE→SS reverse→LE、接続点は一度だけ、最後に閉じる頂点を一度繰り返します。
非縮退の既定輪郭は241座標行で、LE/PS/TE/SSは21/101/21/101です。
有効桁は既定6、1〜15。Project JSONと内部float64は丸めません。
MM/CM/M単位、X/Y/Z回転軸への右手系変換はExporter側へ分離しています。
座標順序・断面数・Closure・NaN/Inf排除・Station変更を検証しました。
無効StationのExportで既存4ファイルが変わらず、新規出力先も作成されないことを確認しました。

## 17. .inf format verification status

Ansys 2026 R1の公式資料と取得済みstator.zipのBladeGen.infを照合した既存実装を使用しています。

- [User Guide 2.1: Init File・端部Enum](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i998527.html)
- [User Guide 10.3.6: XYZ曲線・Profile Marker](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i016457045820452615547.html)
- [公式stator.zip](https://ansyshelp.ansys.com/public/Views/Secured/Doc_Assets/v261/TurboGrid/stator.zip)

参照Sampleはartifacts/turbogrid_reference/official_stator_BladeGen.inf.txtです。
Axis of Rotation / Number of Blade Sets / Geometry Units / Hub・Shroud・Profile Data FileをSampleと照合しました。
Number of Blades Per Set、EllipseEnd / CutOffEnd等は公式Guideの構文を使用します。
推測した.infを出力していません。
このPCのProgram FilesとAWP_ROOT環境変数からANSYS/TurboGridを確認できず、実機のVersion照合とImportは未実施です。

## 18. Project migration

0.1→0.2→0.3と、Flow Path拡張前0.3のUpgradeを純粋関数に分離しました。
0.1/0.2のAngle/Thickness/LE/TEを保持し、Hub/Tipへ独立コピーします。
旧0.3はHub/Shroud・Span対応・翼形状を維持し、旧流路fractionを平均流路m_flow_normへ換算します。
旧0.3のalign_blade_stations_to_crossflow=Falseは保存・再読込でも保持します。
変更前エンジンの3断面・5種類のMaster座標との比較で最大座標差は0.0 mmでした。
ユーザーのblade.json / blade.csvはSHA-256比較で変更されていません。
JSONはSchema0.3とfull precisionを維持し、Control Pointの新保存名はm_blade_normです。

## 19. pytest result

最終コマンド: .\.venv\Scripts\pytest.exe -q -W error。
189 passed in 33.92s、exit code 0、0 failure、0 warning。

| Stage | Result | Failures |
| --- | --- | --- |
| 1 | 161 passed in 21.21s | 0 |
| 2 | 161 passed in 22.31s | 0 |
| 3 | 161 passed in 29.12s | 0 |
| 4 | 163 passed in 27.01s | 0 |
| 5 | 170 passed in 27.88s | 0 |
| 6 | 176 passed in 39.00s | 0 |
| 7 | 178 passed in 44.38s | 0 |
| 8 | 178 passed in 43.52s | 0 |
| 9 | 185 passed in 79.39s | 0 |
| 10 | 185 passed in 32.49s | 0 |
| 11 | 186 passed in 30.27s | 0 |
| 12 | 189 passed in 33.92s | 0 |

各Stage成功後に次へ進みました。不成功の途中結果を成功として報告していません。
ログはartifacts/v0.3-flow-path/stage_results.jsonです。

## 20. Manual test result

Qt offscreenの実画面を生成して目視レビューしました。
Area表6行・カーソル情報・Station/Regionラベルの重なりを修正後の画像で確認しました。
Angle / Meridional / Output / LE・TE / Area / Metrics / 3D / 5-Spanの表示を保存しています。
tools/v03_smoke.pyはPASS。2断面・5断面・旧3断面のcaseをExportしました。
Save/Load、実Mouse EventのDrag、Editor/Section変更、View/Camera保持、CSV、Exportダイアログ接続はQt自動テストです。
OS標準ダイアログを人が操作するDesktop試験と、TurboGridの実機Importは未実施です。
手動チェック手順はREADMEにあります。未実施項目をPASSにしていません。

## 21. Known issues

- 有限壁面の端部を平均流路法線が横切らない位置では面積がN/Aになります。流路を適切に延長・整列して解消してください。
- 旧0.3は元のSpan/Station対応を維持する互換モードです。その設計では翼LE/TE接続線とAreaの法線断面が一致しない場合があります。
- 折返し流路の複雑な多重交点には、全体最適な枝追跡を保証しません。局所seed近傍の選択と曖昧性Errorを使用します。
- 従来Diffuser 2DのR設定・Throat/Curvature/Solidityは独立機能です。DIF stationへの自動拘束やDiffuserの新しい3D Row生成は今回行っていません。
- 3DはWireframe、Spanは線形補間です。CAD品質やSpan間/隣接翼の3D交差保証は対象外です。
- TurboGrid実機Import、OS標準ダイアログの手動操作は未確認です。
- 極端に少ない有効桁・点数では丸めや座標重複が起こりえます。GUIのNew/Open/Exit前には必要な設計を保存してください。

## 22. Remaining v0.4 items

Splitter / Tip Clearance / Blade Blockage / Effective Flow Area / Lean / Sweep / Rake、
高度なSpan補間、Fillet編集補助、PyVista Surface Preview、TurboGrid実機検証、
自動Meshing / Mesh quality checkを次版候補とします。
CFX setup→solve→post-processing→DOE→Surrogate→Optimizationは後続段階です。
今回それらの自動実行、STEP/IGES/Solid CADは実装していません。
