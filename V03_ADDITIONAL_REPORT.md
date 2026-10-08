# v0.3 Additional Requirements 実装報告

2026-10-04。正本: [V03_ADDITIONAL_SPEC.md](V03_ADDITIONAL_SPEC.md)。
既存v0.3へRotation Direction、Undo/Redo、Spanwise Wireframe、独立Blade Edgeを追加しました。
最終pytestは **249 passed、0 failure、0 warning**。TurboGrid実機Importと人によるNative GUI操作は未実施です。

## 既存確認・保存

models / geometry / fileio / gui / testsを確認し、既存189件の回帰テストを実行しました。
変更前のソースはartifacts/v0.3-before-additional.zipに保存しています。
全面再実装は行っていません。Geometry EngineはQtに依存せず、PCHIP、Line/Arc G1接続、Sectionモデル、従来CSV、Project Save/Load、独立Export点数と有効桁を維持しています。

## 変更ファイル一覧

今回変更した既存ファイルは19件です。

- blade_designer/fileio/project_io.py
- blade_designer/geometry/blade_section.py
- blade_designer/geometry/camber.py
- blade_designer/geometry/designer.py
- blade_designer/geometry/geometry_3d.py
- blade_designer/geometry/surface.py
- blade_designer/gui/context_meridional.py
- blade_designer/gui/control_point_editor.py
- blade_designer/gui/main_window.py
- blade_designer/gui/meridional_editor.py
- blade_designer/gui/output_editor.py
- blade_designer/gui/plot_widgets.py
- blade_designer/gui/preview_3d.py
- blade_designer/models/geometry.py
- blade_designer/models/parameters.py
- blade_designer/models/validation.py
- README.md
- tests/test_component_stations.py
- tests/test_project_flow_path_migration.py

## 新規ファイル一覧

ソース・テスト・仕様・報告の新規ファイルは18件です。

- V03_ADDITIONAL_REPORT.md
- V03_ADDITIONAL_SPEC.md
- blade_designer/fileio/blade_edge_migration.py
- blade_designer/geometry/blade_edge.py
- blade_designer/geometry/wireframe.py
- blade_designer/gui/blade_edge_editor.py
- blade_designer/gui/blade_edge_handles.py
- blade_designer/gui/undo_commands.py
- blade_designer/models/blade_edge.py
- tests/fixtures/flow_path_before_additional.json
- tests/fixtures/flow_path_before_additional.npz
- tests/test_blade_edge_position.py
- tests/test_blade_edge_span_interpolation.py
- tests/test_blade_normalized_meridional.py
- tests/test_rotation_direction.py
- tests/test_spanwise_wireframe.py
- tests/test_undo_commands.py
- tools/v03_additional_smoke.py

生成物はartifacts/v0.3-additionalに保存しています。
file_changes.json、stage_results.json、smoke_result.json、5枚の画面画像、Default CCW / 5-Span CCW / 5-Span CWの3つのTurboGrid case、5-Span Project JSONを含みます。
reference_engineは変更前backupから抽出した比較用コードで、アプリ本体から使用しません。
ユーザーの既存blade.json/blade.csvはSHA-256照合で不変でした。

## GUI・View

Blade Viewを常時表示する既存構成を維持しました。
ToolbarへRotation DirectionのCCW/CW、Viewed from +Z axis、Reverse Rotation、Undo/Redoを追加しました。
右Meridional EditorへIMP/DIFの独立Hub LE / Shroud LE / Hub TE / Shroud TE表を追加しました。
2つのMeridional Viewに4本のBlade Edge Line、名前・色の凡例と8個のDrag handleを表示します。
翼端が傾く場合、可視のIMP/DIF領域境界も翼端の線に合わせます。Component StationデータとArea計算は別に保持します。
数値Editorを含むCtrl+Z / Ctrl+Y / Ctrl+Shift+Zを実装しました。

Geometry更新・Undo/Redoでは既存Graphic ItemへsetDataし、自動Fitを実行しません。
目盛り文字幅によるView変動も避けるため、2D Plotの軸幅を固定しました。
3D Cameraのazimuth / elevation / scale / center / panを維持します。
起動・New・Open・Fit ViewだけがFitします。回転反転で形状が現在の表示範囲外へ移った場合は明示的なFit Viewで確認します。

## RotationとPS/SS

内部θの正をCCWとし、+Z側から原点を見る基準をGUI/READMEへ明記しました。

```text
dtheta/dm = rotation_sign * tan(beta_m) / R
CCW: +1
CW:  -1
theta_CW - theta_LE = -(theta_CCW - theta_LE)
```

βm Control Pointは変更しません。R/Zを維持して周方向だけを鏡映します。
2D、Hub/Tip、中間Span、Preview、Full Annulus、CSV/TurboGridの実座標へ反映します。
PS/SSの法線・端部接線も対応させています。+Normal/-NormalはCCW基準から運ぶ法線として扱い、Mapping設定を保持したまま名前付きPS/SSも鏡映します。
Circular / Elliptical / Cutoffと全Mappingの組合せ、非ゼロθ_LE、X/Y/Z軸のExportを検査しました。

## Undo/Redo

MainWindowにQUndoStack(self)、ProjectEditCommandにQUndoCommandを使用しました。
Geometryの大きな配列ではなく、Design Parameterの独立した深いコピーを保持します。
角度・厚さのPoint値/追加/削除/Drag、端部型/楕円比、Hub/ShroudのStart/Segment値/追加/削除/移動、Component Station、8個のBlade Edge endpoint、Rotation、Section copy/追加/削除、出力設定/ファイル名を取り消せます。
無効入力も履歴へ登録し、Undoで回復できます。選択Spanも復元します。

- 数値はeditingFinishedで1操作。
- Point/Blade EdgeのDragは開始前とリリース時の状態から1操作。
- Drag中は50ms間隔を目安にGeometryを更新し、リリース時に確定。
- New/Openでclear、Saveで保持。
- 最大200 command。履歴はメモリ内で、JSONには永続化しません。
- 別ページへ移したLE/TE・Output controls、Undo後に再生成したPoint表の数値Editorにも履歴とショートカットを接続しています。

## 共通PCHIP・Line/Arc・G1

既存geometry/distributions.pyの共通scipy.interpolate.PchipInterpolatorを維持しました。
角度・厚さは各断面のm_blade_normに対して定義し、Control Point通過と単調列のovershoot抑制を既存テストで検証しています。
MeridionalはLine/Arc Segment Chain、前Segmentの終点と単位接線の継承によるG1接続を維持しました。
解析弧長、Line–Arc / Arc–Line / Arc–Arc、有限値/正半径/自己交差/Hub-Shroud交差の検査も既存回帰テストで確認しています。

## 独立Blade Edge・Section・3D Geometry

BladeEdgePositionとBladeRowEdgeParametersを追加し、impeller_edges/diffuser_edgesへ保存します。
各hub_m_flow_norm/shroud_m_flow_normは、その壁面の**入口から出口までの物理弧長fraction**です。
ComponentStation.m_flow_normは平均流路の弧長fractionで、別の値です。
旧blade_le_fraction/blade_te_fraction APIはComponent IMP_LE/TEの互換aliasとして保持します。

Lineは解析射影、Arcは中心からの角度と有限Sweep・端点の候補から最近点を選び、対応壁面へ拘束します。
Hub/Shroud位置を指定した独立対応パラメータから壁面列を作り、Spanで線形補間します。
interpolate_edge_position、blade_wall_parameters、project_to_wallを独立関数にしました。
各Sectionの累積物理mからm_LE/m_TEを求め、m_blade_norm=(m-m_LE)/(m_TE-m_LE)でLE=0、TE=1にします。
厚さ・角度入力を変えず、新しい翼端位置へ追従します。

Hub/Tip・任意中間SpanのCamber / PS / SS / LE / TE、R/θ/ZとX/Y/Zを保持します。
finite、0～1、両壁面と各生成SpanのTE>LE、LE/TE接続線の交差・接触を検査します。
Blade Edge位置は既存Geometryの設計区間（CamberのLE/TE端）です。Rounded capのnoseは厚さ・楕円比に応じてこの区間の前後へ延び、有限壁面からはみ出す場合はErrorになります。

## Spanwise Wireframe

各Sectionの同じLE/PS/TE/SS Segment、同じExport indexを接続します。
SpanwiseLineにsegment / segment_fraction / segment_index / spans / xyzを保持します。
segment_fractionは各SegmentのXYZ弧長で再サンプリングされた0～1の位置です。
Hub/Tipは2点の線、中間Spanがあれば全Spanを通るPolylineになります。

既定LE21 / PS101 / TE21 / SS101から244本を描きます。
Topologyや点数、有限座標が合わない場合はValueErrorを返し、黙って省略しません。
Profiles / Spanwise Lines / Hub Curve / Shroud Curveを独立表示できます。DefaultはすべてONです。
Span gridを先に描き、色付きProfile outlineを後に描いて見えるようにしています。
Qtソフトウェア描画を維持し、PyVista/VTK/OpenGLの追加依存は導入していません。Surfaceは今回の任意項目として未実装です。

## Project Migration

Schemaは0.3を維持し、新しいRotation/Blade Edgeフィールドをfull precisionで保存します。
0.1/0.2のMigrationと初期0.3/Flow Path拡張済み0.3の読み込みを維持しています。
追加Migrationはfileio/blade_edge_migration.pyの純粋関数に分離しました。
旧ProjectはCCWで初期化します。初期0.3では従来の壁面fraction、Flow Path版0.3では従来法線断面と壁面の交点から翼端を初期化します。
対応knotsとサンプリング格子を独立Blade Edgeパラメータへ移し、その後のComponent Station編集は翼端へ伝播しません。

変更前のEngineから生成した3断面の15本のmaster座標をfixtureに保存して比較しました。
Flow Path版0.3の最大差は **0.0 mm**、初期0.3 fixtureとの最大差は **1.1404210908949608e-12 mm**です。
既存角度・厚さ・LE/TE情報、Hub/Shroud形状と任意Spanを保持します。元Projectを書き換えません。

## TurboGrid Export / .inf資料

既存fileio/turbogrid_export.pyへ新しい内部3D座標が渡るため、回転方向と独立翼端をExportへ反映します。
Exporter本体の構文は変更していません。

- hub.curve / shroud.curve: 上流→下流のXYZ、既定501点。
- profile.curve: Hub→内部Span→Tip、LE→PS→TE→SS reverse→LEの閉輪郭。
- Segment接続点を1回だけ出力し、閉鎖点だけ繰り返します。非縮退既定241行/Section。le/te markerを保持します。
- MM/CM/M単位とX/Y/Z軸へExporter内で変換。有効桁6、範囲1～15、内部/Projectは丸めません。
- BladeGen.inf: 既存の確認済みAxis / Blade Sets / Blades Per Set / Units / LE/TE / 3つのCurve filename構文を保持します。未確認のRotation Directionキーワードは出力せず、XYZそのものへ反転を反映します。

確認済み資料は前回取得したAnsys 2026 R1の公式資料とstator.zipです。
今回は保存済みartifacts/turbogrid_reference/official_stator_BladeGen.inf.txtを再読して保持構文を確認しました。

- [公式 User Guide 2.1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i998527.html)
- [公式 User Guide 10.3.6](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i016457045820452615547.html)
- [公式 stator.zip](https://ansyshelp.ansys.com/public/Views/Secured/Doc_Assets/v261/TurboGrid/stator.zip)

Program FilesとANSYS/AWP環境変数でインストールを確認できませんでした。
**現在インストール済みTurboGridとの適合と実機Importは未検証**です。詳細は前回V03_FLOW_PATH_REPORT.mdにも記録しています。

## pytest / Stage結果

既存テストを含め、次の各Stageの完了時点で0 failureを確認して進みました。

| Stage | 内容 | 全pytest結果 |
|---|---|---|
| 1 | 既存構造・Baseline | 189 passed / 27.39 s |
| 2 | Rotation Engine/Save-Load | 199 passed / 58.87 s |
| 3 | 独立Blade Edge/Migration | 212 passed / 29.97 s |
| 4 | GUI/Undo/endpoint drag | 236 passed / 76.23 s |
| 5 | Spanwise/keyboard/legacy fixtures | 247 passed / 112.04 s、-W error |
| 6 | 描画・視認性・QA | 247 passed / 86.02 s、-W error |
| 7 | Reparented inputs/tilted boundaries/最終 | **249 passed / 92.69 s、-W error** |

修正過程では軸幅の変動、Undo後の数値ショートカット接続、Meridional更新順序の問題をテストで検出して修正しました。
0 failureになった後で次のStageへ進んでいます。
最終実行: .venv/Scripts/pytest.exe -q -W error。

追加指定の6テストファイルをすべて作成しました。
既存Component Stationテストは新仕様のデータ分離を確認する内容へ変更し、旧座標保持は独立したfixtureテストで検証しています。

## QA / Manual Test

tools/v03_additional_smoke.pyの結果はPASS、smoke_result.jsonに保存しました。

- CCW→CWの実座標鏡映、入力βm保持、Undo/Redo: PASS。
- 実際のQt Mouse Eventによるβm / Thickness / IMP LE Hub endpointの継続Dragを1回でUndo/Redo: pytestでPASS。
- 8個のIMP/DIF・Hub/Shroud・LE/TE値のUndo/Redo: PASS。
- Editor内Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z、コピー/Span追加削除、数値編集確定: PASS。
- Hub/Shroudで異なるLE/TE、0/1正規化、5-Span・244本の対応線: PASS。
- Zoom/Pan/Camera維持、New/Openの履歴clear、Saveの履歴保持: PASS。
- Save/Load、Default CCW / 5-Span CCW / 5-Span CWの4ファイル出力: PASS。
- 画面画像を目視確認: Rotationラベル、独立翼端表、常時Blade表示、Profile/Spanwise線と4つの表示切替を確認。
- 元blade.json/blade.csvのSHA-256不変: PASS。
- 人によるNative GUIの操作・OSファイルダイアログ: **未実施**。
- TurboGrid実機Import / Hub-Tip・LE-TE方向 / Geometry Error確認: **未実施**。

CWの画面画像は、自動View保持を検査した後に明示的Fit Viewを行って撮影しました。
Qt offscreen検証と実機Manual Validationは区別しています。Manualの追加手順はREADMEに記載しました。

## 既知の制限・次版へ残す項目

- 線形Span対応とソフトウェアWireframeです。CAD-quality Surface、Span間の3D自己交差保証は未提供です。
- 丸い端部のnoseと設計区間端点は異なります。極端な厚さ/楕円比では壁面の上流下流余白が必要です。
- 大きい回転反転やパラメータ変更で形状がView外へ移る場合もViewを保持します。Fit Viewを使用してください。
- 履歴は200操作/メモリ内。New/Openで消去し、Projectへ永続化しません。
- 既存Throat/Curvature/Metricsと従来CSVはDiffuser 2D用、今回TurboGrid出力はImpeller profilesです。Diffuser端点モデル/GUIは独立保持しますが、Diffuserの新しい3D翼列生成は対象外です。
- 中間Spanの高度な壁面対応、Curved LE/TE、Intermediate edge control、3D Surface Preview、TurboGrid実機検証を次版候補へ残します。
- Splitter、Tip clearance、専用Lean/Sweep/Rake、CFX実行、自動Meshing/Optimization、STEP/IGES/Solid CADは既存仕様どおり対象外です。
