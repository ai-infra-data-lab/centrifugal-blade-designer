# 現行機能の実装監査

CAD採用格子追記: 同一snapshotの実CAD結果からMain/Splitter別の4 role格子を照合して参照面へ適用。失敗/不足/異設計の結果を拒否する。対象は結合/fillet前の基準翼面であり、最終solid/STEP後/全面品質は未検証。[契約](CAD_ADOPTED_SURFACES.md)。

Stage 3A-2c参照表示追記: CADと同じ接線・tensor splineの固定密度参照画面を追加。Impeller主翼/Splitter・格子・全周を選び、従来表示と分離して検査可能。実出力の自動密度・閉じたsolid・全面偏差・ANSYSの成立を意味しない。設計変更時は失効する。[契約](CAD_SURFACE_REFERENCE.md)。

Stage 3A-2b追記: 派生曲線の元集合・role・Span/indexと補間比を保持し、共通の円筒補間面を参照して再構成可能にした。外径切断後の位置をカット後indexと同一視しない。新加工TEは参照対象外。既存形状・JSON・出力は維持し、表示/CADの単一正本適用は残る。[派生由来](DERIVED_SOURCE_CONTRACT.md)。

Stage 3A-2a追記: 実表示点の対応写像と派生source_spanの読取り専用診断を追加。既定Impeller等の実wireframeを参照splineと比較できるが、物理対応・単一正本適用・全面保証は未完了。既存生成・出力は変更しない。[実対応座標](SURFACE_CORRESPONDENCE.md)。

Stage 3A-1追記: 共通の非Qt翼面評価器を追加。CADの係数構築と派生カットのSpan列補間を共通層へ移し、数値評価と実OCCTの内部点比較を追加した。現行のXYZ接続／円筒補間／CAD splineは異なる方式として保持する。G05は部分対応で、実経路の対応座標統一と単一正本の適用は未完了。[翼面評価の契約](SURFACE_EVALUATION_CONTRACT.md)。

Stage 2B-2追記: 3D生成に続き、row一覧ありのJSONを保存値の整合性と宣言翼種の実3D検証へ分離。未使用の旧2D順序・参考Impellerの幾何成立性によるLoad／Save拒否を除き、全宣言rowは検査する。row一覧なしの旧JSON／旧2D APIは従来契約を保持。G01は実3D最適化等が残るため部分対応。[生成時検証](ROW_VALIDATION_CONTRACT.md)、[保存検証・互換境界](ROW_PROJECT_VALIDATION.md)。

監査日: 2026-10-17。対象ソース: `6b8d3be`。対象はcentrifugal_blade_designerのみ。
本監査では設計アルゴリズム、設計値、ユーザーJSON、既存出力、テスト期待値を変更していない。
前作業の検証済みRC表示・既定モデル・折返し流路修正15ファイルを先に上記commitへ記録した。

追記: Stage 1BでE02のI/O途中公開を修正済み。最終860一意件成功、実CAD35件を含みskipなし。既存caseの保持バックアップ・中断復旧を検査。2回renameの一時不在、実停電・ANSYS未検証の限界は[出力品質](EXPORT_QUALITY_IMPROVEMENTS.md)を参照。以下の逐次公開の指摘は監査当時の履歴。

追記: 監査後のStage 1AでE01を修正済み。通常Impellerにも丸め後の輪郭・マーカー・Span点数検査を適用し、新規64件を含む全832一意件が成功した。下記の丸め不具合の再現値は監査時点の履歴であり、現行版は出力前に拒否する。原本・設計値・歴史的参照は不変。詳細は[出力品質](EXPORT_QUALITY_IMPROVEMENTS.md)。

## 判定の読み方

- **実装済み**: 記載した範囲のコードと自動試験が存在する。全設計での成立、製造・性能保証を意味しない。
- **一部対応**: 経路はあるが、対象形状・検査・連携の制約がある。
- **未対応**: コードで拒否する、または実行機能がない。
- **実機未検証**: 実装状態とは別の検証軸。Qt offscreen、OCCT、ファイル検査の成功をANSYSや実画面のPASSへ読み替えない。

調査対象はAGENTS.md、README.md、FEATURES.md、docs/ARCHITECTURE.md、V03_FLOW_PATH_SPEC.md／V03_ADDITIONAL_SPEC.md、CAD_V04_SPEC.md、各機能仕様と下記Python／テスト。要求仕様の記述だけでは実装済みと判定しない。

## 機能と根拠

パスはプロジェクトルートからの相対パス。表のテストは代表例で、成功範囲は後述する記録に限定する。

| 機能 | 実装判定・範囲 | ソース・主要関数 | 代表テスト | 残る確認・制限 |
|---|---|---|---|---|
| Meridional Hub/Shroud | 実装済み。Line/Arc、G1接続、所属翼列、R/ZによるLE/TE、円弧中心／端点表示 | `geometry/meridional_segments.py`, `blade_edge.py::blade_wall_parameters/project_to_wall`, `gui/meridional_editor.py`, `context_meridional.py` | `test_meridional_line.py`, `test_meridional_arc.py`, `test_meridional_tangent.py`, `test_meridional_invalid.py`, `test_edge_rz_gui.py`, `test_row_domain_gui.py`, `test_meridional_coordinates_gui.py` | 壁面編集時は旧端点が残れば保持、外れれば最近点へ投影。流体解析から求めた流線ではない。native全操作未検証 |
| Impeller 3D Geometry | 実装済み。各Spanのβ積分、曲面上の厚み付け、各端部、Hub TE円筒Cutoff | `geometry/geometry_3d.py::generate_impeller/_generate_row`, `blade_section.py::generate_section`, `cylindrical_cutoff.py` | `test_blade_sections.py`, `test_blade_normalized_meridional.py`, `test_cylindrical_cutoff.py` | 通常の表示は離散断面と接続線。Span間の全翼面交差・周期翼干渉を常時保証しない |
| Diffuser Geometry | 実装済み。実3Dは共通分布をHub/Tipに配置 | `geometry_3d.py::generate_diffuser_3d`, `designer.py::generate_diffuser` | `test_diffuser_3d.py`, `test_stator_turbogrid_export.py` | 3Dと旧radial 2Dの2系統。静翼中間Spanの独立設計は未対応（意図した2断面方式） |
| Return Channel Geometry | 一部対応。kindはdiffuserのまま、内向き子午面を生成。中央2Dは実3D HubのXY投影 | 同上、`gui/main_window.py::_display_geometry` | `test_return_channel.py`, `test_return_channel_gui.py` | RC専用の物理モデル／独立kindはない。Metrics・Curvature・CSV・最適化は旧外向き2D経路。3DおよびProfile Pointsと区別する |
| Splitter | 実装済み。1主翼ピッチに1枚、開始割合・周方向位置・厚さ倍率、主翼連動／専用分布 | `geometry/splitter.py::generate_splitter/splitter_active_profile`, `gui/splitter_editor.py` | `test_splitter.py`, `test_splitter_gui.py`, `test_splitter_local_interpolation.py`, `test_splitter_edit_range_gui.py` | 複数種類・複数枚/ピッチは未対応。専用分布は可視LE〜TEのPCHIP。主翼との全3D衝突検査は通常生成では未対応 |
| Blade Angle / Thickness | 実装済み。PCHIP、主翼／Splitter共有グラフ、Hub/Tip／Impeller中間Span編集 | `geometry/distributions.py`, `thickness.py`, `gui/profile_distribution_editor.py` | `test_shared_pchip.py`, `test_combined_distribution_gui.py`, `test_simultaneous_editors.py` | βは子午面方向基準、厚みは局所曲面の内在座標オフセット。厳密な空間最短厚さではない |
| LE/TE / Stacking / Rake | 一部対応。R/Z端点、丸・楕円・Cutoff、Impeller TE Rake目標とβ保持Mapper | `blade_section.py`, `edges.py::generate_edge`, `impeller_parameter_mapper.py::map_te_rake/measure_te_rake` | `test_edges.py`, `test_impeller_te_rake.py`, `test_impeller_te_rake_gui.py` | 独立LE Sweep/Rake目標、任意Stacking曲線、局所Span Rake一定は未対応。G0接続とG1を区別 |
| Tip Clearance | 実装済み。固定ケーシングからHub側法線オフセット。LE/TE mm、ケーシング距離で線形補間 | `geometry/tip_clearance.py::make_tip_geometry/_frame`, `span_extension.py` | `test_tip_clearance.py`, `test_tip_clearance_gui.py`, `tests/cad/test_tip_clearance_cad.py` | Tipは実際に内側へ移動。熱／回転変形・漏れ流量・境界層は未対応。ケーシング法線とHubの対応は幾何学的 |
| Shroud/外径派生カット | 実装済み（表示・幾何面積）。元データを保持して離散翼面を切り出す | `geometry/impeller_trim.py::apply_trim/_casing/_span_curve` | `test_impeller_trim.py`, `test_impeller_trim_gui.py` | 面積率は元平均線基準断面。CFD流量率・圧力比の保証はない。TurboGrid/CADは未対応で事前拒否 |
| CAD / Fillet | 一部対応。別OCP環境で曲面・solid・Hub・Boolean・真の可変Rフィレット | `cad/occt_backend.py::create_surface/create_blade_solid`, `worker.py::execute` | `tests/cad/test_blade_surface.py`, `test_boolean_union.py`, `test_root_fillet.py`, `test_fillet_failure.py` | 独立fixture R8成功と、ユーザー既定形状R8成功は別。現既定＋仮ディスクでもR8失敗を再現。詳細は品質レビュー |
| TurboGrid Profile Points | 一部対応。主翼、選択静翼Hub/Tipと所属壁面、単位・軸・端部マーカー | `fileio/turbogrid_export.py::export_turbogrid/closed_profile/_external_xyz` | `test_turbogrid_export.py`, `test_stator_turbogrid_export.py`, `test_turbogrid_clearance.py` | Splitter／派生カット未対応、フィレットなし。主翼のみの丸め後検査に欠落を再現。ANSYS Import/Mesh未検証 |
| TurboGrid CAD | 一部対応。フィレット付き実体を差し引いた流体領域STEPと境界role | `cad/worker.py::execute`, `occt_backend.py::create_flow_passage`, `fileio/turbogrid_cad_export.py` | `tests/cad/test_turbogrid_export.py`, `test_edge_classification.py` | **CONVERSION_REQUIRED**。対応CAD形式への変換器なし。静翼・正クリアランス・派生カット未対応。ANSYS未検証 |
| Mechanical STEP | 一部対応。Blade Only、Blade+Hub、周期／全周、再読込み、検証済みbytesの公開 | `cad/client.py::prepare_job/publish_job`, `cad_validation.py::step_roundtrip`, `fileio/mechanical_step_export.py` | `tests/cad/test_step_roundtrip.py`, `test_step_error_budget.py`, `test_mechanical_export.py`, `test_cad_regeneration.py` | Impellerのみ。Hub付きは成立するディスク／根元が必要。仮寸法はPROVISIONAL。Workbench/Mechanical Import/Mesh・強度未検証 |
| Flow Area / Throat | 実装済み（幾何学的近似）。Gross、厚み控除Net、主翼間参考・Splitter両側 | `geometry/flow_area.py::calculate_flow_area`, `passage.py::calculate_passages/_area_cut/_throat` | `test_flow_area_axial.py`, `test_flow_area_radial.py`, `test_flow_area_general.py`, `test_passage.py`, `test_folded_passage.py`, `test_passage_gui.py` | 局所直交切断・既存Spanの台形積分。曲面スロート幅はXYZ弦の下限、面積はSpan別最小幅の近似。CADフィレットは含まない |
| Optimization | 一部対応。変数写像・境界・幾何制約判定・候補適用 | `optimization/parameter_mapper.py`, `presets.py`, `feasibility.py::evaluate_candidate/check_feasibility`, `gui/optimization_widget.py` | `test_optimization_mapper.py`, `test_optimization_constraints.py`, `test_optimization_gui.py` | `BladeDesigner.generate`の旧2Dが評価対象。探索ソルバー、実CFD、流量／圧力比／効率目的関数は未対応。3D設計の適否判定ではない |

`geometry/`等はすべて`blade_designer/`配下。表で挙げたテストファイルの実在は監査チェックでも照合する。

## TurboGrid対応マトリクス

| 対象 | Profile Points | CAD経路 | 検証と制限 |
|---|---|---|---|
| 主翼のみ、gapなし | 対応。出力正本は3D生成断面 | Impellerのみ条件付き対応 | 旧出力fixture・軸・単位・閉輪郭試験あり。ただし丸め後重複点と周期干渉の監査指摘あり |
| 正Tip Clearance | 実Tipを残しShroud延長断面を追加 | 未対応、事前拒否 | `Tip_clearance`／`Shroud_extension`。TurboGridで実TipのProfile Numberを手動指定する必要があり、単にImportするだけでgap復元済みとは言えない |
| Splitterあり | **未対応、事前拒否** | 生成経路あり、実形状ごとに成立確認が必要 | CAD workerは主翼・Splitter実体とピッチ間干渉を検査する。代表CAD fixtureの成功を既定Splitter付きR8の成功としない |
| Diffuser | 対応。Hub/Tip＋所属壁面 | 未対応、Impeller選択が必要 | 単位／軸／輪郭一致の自動試験。静翼Spanは2断面のみ |
| Return Channel | 対応。内向きLE→TEのまま | 未対応 | 今回の既定RCはR130→90 mm、Z95 mmのHub。内外径を入れ替えたりβを一律反転しない |
| 派生Shroud／外径カット | **未対応、事前拒否** | **未対応、事前拒否** | 元形状を黙って出力しない。表示できることと出力対応は別 |
| CAD＋Fillet | Profile Points自体には含まない | 条件付き。流体領域STEP | 機械実体と同じフィレット付きfull実体を流体から減算。ただし変換・ANSYS Import・Meshは未検証 |

**上記すべてのANSYS Import/MeshはNOT_TESTED。** Python・OCCT側PASS、CONVERSION_REQUIRED、ANSYS PASSを独立して記録する。

## GUI・保守性

| 観点 | コード照合結果 | 根拠と不足 |
|---|---|---|
| 別画面から機能が消えないか | 対象に応じたタブとメニュー入口あり。Meridional／翼列は意図して切替 | `MainWindow._configure_editor_tabs/_show_tool_dialog`、`test_target_layout_gui.py`, `test_standard_menus_gui.py`, `test_editor_resources_gui.py`。現在の全組合せをnativeで操作した保証はない |
| Undo/Redo | 設計全体をdeepcopyした`ProjectEditCommand`。行追加削除、R/Z、分布、Rake、gap、trim、CADを接続 | `_bind_history_inputs/get_parameters/commit_edit/_restore_design`、`test_undo_commands.py`と各機能GUI試験。履歴上限200、新規/Openで履歴初期化。すべての任意未確定入力・将来項目への網羅保証はない |
| Geometry同期 | 行別snapshot、共有壁面、現在値から再生成。CADはsnapshot hash不一致で非表示 | `models/blade_rows.py::row_parameters`, `_display_geometry/_sync_cad_preview`, `test_cad_gui.py`。無効入力では最終有効3Dが残る。旧Metrics/CSV経路の不一致は残る |
| Camera保持 | 通常updateでcameraを変更しない。trackball・pan・zoom・視点ボタン | `preview_3d.py::update_geometry/_rotate_trackball/fit_view/showEvent`、`test_preview_3d.py`, `test_trackball_preview.py`, `test_contextual_3d_gui.py`。表示時のFitは中心・scale・panを変えるため「常に全値不変」ではない |
| 設計値と表示設定 | Camera、可視checkbox、projectionは表示側。翼数・回転方向は設計値 | `models/parameters.py`, `MainWindow.get_parameters`。active rowもprojectに含むためCAD全project hashは無関係な他行編集／選択にも影響し得る。表示状態の独立保存は未整備 |
| 長時間処理 | CADは別`.venv-cad` QProcess、20分timeout。PassageはThreadPoolExecutorと世代照合 | `gui/cad_export_worker.py`, `passage_widget.py`。`update_geometry`、Flow Area、全行preview、CADの`prepare_job`はGUI側同期。全面的な非停止保証はない |
| MainWindow責務 | 層分離は部分的に良い。数値geometryはQt独立、OCPはworkerへ隔離 | `main_window.py`は約1,280行。UI構築・行状態・履歴・同期再生成・解析・出力・CAD完了を兼務。修正範囲を限定して段階分離すべきで、全面再生成は不要 |

## 自動検証と今回の再現確認

前作業の最終全回帰は**一意768件、failure/error/skip/missing=0**。単一実行ではなく複数JUnitの個別ID照合。今回その結果と221入力ハッシュを照合してからcommitした。CAD35件には現既定JSONのBlade Only（主翼・Splitter）STEP検証を含む。これを現既定のHub付きR8成功としない。

- 集計: `artifacts/return-channel-review/final-test-coverage.json`。
- ソース固定: `artifacts/return-channel-review/final-source-hashes.json`。
- 通常群: `20261017T064954Z-f014dfc8` 256件、`20261017T064955Z-bff702ba` 273件、`20261017T064953Z-bcef194c` 204件。
- CAD群: `20261017T063309Z-1a63b178` 35件。
- 改行正規化を考慮したprovenance試験の追加1件は重複IDで、一意件数に足していない。

今回の独立プローブ: `artifacts/implementation-audit/probe.py`と`probe-results.json`。ユーザー出力を使わず、新規の監査用フォルダにのみ書き出した。

1. 現既定の3行を生成。Impeller TE R81、Diffuser R85→130、RC R130→90。ImpellerはSplitter有効で、さらに所属範囲がLE/TEを包含しない。静翼2行の所属範囲は通る。
2. `BladeParameters()`の主翼枚数1000: Hub中央のPS/SS角幅0.0292298 radに対しピッチ0.00628319 rad。生成も4ファイル出力も拒否されない。
3. `BladeParameters()`、有効桁数1、gap/Splitterなし: export成功だがHub147箇所、Tip180箇所で連続点が同一点へ丸められる。
4. 監査用sentinelケースで2回目の`os.replace`にOSErrorを注入: `hub.curve`のみ更新され、残り3ファイルは旧値。形状検証失敗の保護と、I/O途中失敗時のケース一括保護は別。
5. LE/TE接線の細分化プローブは品質レビュー参照。新しいテスト期待値として登録していない。

今回の既存試験再実行は**81 passed / 162.81秒、failure/error/skipなし**（`20261017T121411Z-58abb40a`）。`test_return_channel.py`、`test_turbogrid_export.py`、`test_stator_turbogrid_export.py`、`test_undo_commands.py`、`tests/cad/test_step_error_budget.py`を実行した。実OCCTのR8試験はこの81件とは別の診断であり、結果は失敗として下記に記録する。文書のみの追加なので全768件を今回もう一度実行したとは報告しない。

現既定のImpellerをメモリ上で選び、既存の仮ディスク生成を適用してMechanicalを実行した（原本未変更）。`artifacts/implementation-audit/current-default-r8/result.json`で主翼・Splitterのsolid生成とHub単体は通り、`TRUE CAD FILLET / main`で`R8: ChFi3d_Builder:only 2 faces`となった。現仮ディスクは内径20 mm、外径182 mm、裏面Z75 mm。STEPの正式出力はなく、debug STEPを完成品としない。元処理を変えない別診断でも同じ失敗を再現し、根元候補10本中7本で4個のdistinct faceの共有を確認した（`root-topology.json`）。詳しい原因範囲は品質レビュー参照。

利用者の追加指示により、根元フィレットの完成条件を「R8必須」ではなく「対象形状に合う指定Rで実生成・STEP再読込み・半径測定を確認」に変更した。同じ現既定＋仮ディスクでR2／R1／R0.5 mmを独立snapshotとして実OCCTへ渡したが、3ケースとも主翼の根元フィレット段階で同じ`ChFi3d_Builder:only 2 faces`となった。小径での成功はまだ確認できていない。結果は`artifacts/implementation-audit/small-radius-results.json`。原本、既定値、計算コード、公差、既存出力は不変。この追記は文書変更と診断であり、新たな全回帰実行やANSYS確認を行った意味ではない。

調査用コマンドでは最初のsandbox内Gitに親ディレクトリへのアクセスエラー、資料一覧の標準出力にCP932エンコードエラーが発生した。権限付きGitとUTF-8の出力で再確認した。アプリ／pytestの失敗ではない。数値プローブの成功、CAD失敗、環境エラーを混同しない。

## 文書とコードの差異

- READMEの仮ディスク外径約251.86 mm・裏面Z75 mmは旧既定形状の記録。現既定の算出結果を保証する数値ではない。
- READMEの「最新490件」やFEATURESの558件などは履歴値が併存する。現時点の全回帰根拠は上記768件。履歴数値を置換して過去結果を改変しない。
- 旧説明にある「Diffuser 2D」は中央表示については更新済みで、現在は3D Hub投影。旧Metrics/CSV/Optimizationについては依然該当する。
- CAD仕様の到達目標と実装済み範囲を分離する。既定R8、CAD変換、ANSYS Import/Mesh、性能・強度の完成を示す根拠はない。

## 実機で必要な確認

Windows native/F5で、3行切替・全タブ／別ウィンドウ・未確定入力・Undo/Redo・DPI・Camera保持・CAD実行中の編集／取消を確認する。
ANSYSはリリースとライセンスを固定し、上記対応マトリクスごとにImport、単位、軸、翼枚数、LE/TE認識、Hub/Shroud接続、gap実Tip番号、周期境界、メッシュ生成と品質を記録する。
Mechanicalはsolid数・結合・根元半径・実機ディスク寸法・周期拘束を確認する。これらの外部確認は今回PASSにしていない。

## Stage 1Cの追記

選択翼列の出力入力条件を`File → Export → Export Readiness`で診断する。根拠は`fileio/export_readiness.py`、`gui/export_readiness_widget.py`、`MainWindow.show_export_readiness`。新規`test_export_readiness.py`9件と`test_readiness_widget.py`3件、既存メニュー7件の関連試験が成功。3経路の未対応理由を別々に表示し、CAD生成やANSYS実行の成功にはしない。原本・既定・出力・設計値を変えない。全面3D干渉や対象形状の根元filletの成立は未検証／未解決のまま。最終回帰記録は[実装ログ](EXPORT_QUALITY_IMPROVEMENTS.md)を参照。

## Stage 2Aの追記（G01は部分対応）

新経路の実断面指標とXYZ CSVは中央表示のmeridional_3d masterを使い、row ID／snapshot／geometry種別を付ける。旧Metrics／Curvature／XY CSV／最適化はlegacyとして明示する。根拠: `geometry/section_measurements.py`、`models/geometry_source.py`、`fileio/geometry_source.py`、`fileio/row_xyz_csv.py`、`gui/row_metrics_widget.py`とMainWindowの接続。新規34ケースは`test_section_measurements.py`、`test_row_xyz_csv.py`、`test_row_measurements_gui.py`。その後のStage 2Bで3D生成時とrow一覧ありのLoad／Save検証を分離したが、両翼種LE/TE端点の入力整合性は維持する。最適化の実3D制約化等は未完了。精度と検証結果は[GEOMETRY_SOURCE_CONTRACT.md](GEOMETRY_SOURCE_CONTRACT.md)、[生成時検証](ROW_VALIDATION_CONTRACT.md)、[保存検証](ROW_PROJECT_VALIDATION.md)。

## 追加: 曲面の局所微分診断

解析微分によるJacobian/法線と同一対応標本の比較APIは実装済み。新規解析29件と既定ImpellerのMain/Splitter標本比較を確認。GUI統合・全面品質ゲート・干渉検査・STEP後の面偏差は未対応で、native/ANSYSは未検証。[根拠・制限](SURFACE_DIFFERENTIAL_DIAGNOSTICS.md)。

## 追加: 基準spline間の距離包絡

同一対応/同degree/clamped/非周期面の位置差control包絡を実装した。純数値28件・実OCCT1件と現既定の主翼/Splitterで検証。float丸めの厳密保証、法線/Jacobianの全域包絡、干渉・cap/fillet/STEP後の面・GUI統合は未対応。既存生成/保存/出力条件は維持。[根拠](SURFACE_DISTANCE_ENVELOPE.md)。

## 追加: 基準splineのJacobian区間包絡

C1を形式上保証できるclamped基準面のJ下限/上限と未判定箇所のAPIは実装済み。数値24・実OCCT1の新規試験、現既定Main/Splitterの65〜513格子を確認。局所正則と自己交差なしを区別し、丸めの厳密保証・実干渉/法線比較・最終solid/STEPは未対応。[根拠](SURFACE_REGULARITY_ENVELOPE.md)。

## 追加: 同一対応基準splineの法線角包絡

同degree/C1面の向き付き角度上限と未判定区間のAPIは実装済み。純数値25・実OCCT1の新規試験を含む関連80件成功。標本点の間に90度超の方向差がある解析例を保守的な包絡に残す。実CADの一部LE区間はJ下限未確保としてNoneを維持する。外向き・物理対応の自動同定・丸め保証・自己/周期干渉・最終solid/STEP・GUI統合は未対応。[根拠・全回帰](SURFACE_NORMAL_ENVELOPE.md)。

## 追加: Stage 3B-1の三角形接触候補（部分対応）

明示XYZ格子の非局所自己/最近接周期/Main–Splitter接触候補APIを追加し、新規54件を含む関連129件を確認した。実1000枚のMainでLE–LE/TE–PSの35候補を観測。曲面の標本間交差・完全包含・隣接faceの局所foldを保証しないnegativeも保持する。全周・連続面・role継ぎ目・cap/fillet/STEPの検査、GUI/出力ゲート統合は未対応で、G02全体は未完了。[根拠・全回帰](MESH_CONTACT_SCREENING.md)。

## 追加: Stage 3B-2aの共有edge局所診断（部分対応）

明示モードで2頂点共有のedge接続と重なり候補を区別し、短いedge/高さを未判定、3面以上のedgeを不完全として記録する。新規32件を含む関連86件成功。既定モードと形状/出力は維持し、1頂点接続・vertex link・role継ぎ目・連続面・包含・実solid/ANSYSは未対応/未検証のまま。[根拠](MESH_SHARED_EDGE_CHECKS.md)。

## 追加: Stage 3B-2bの共有頂点局所診断（部分対応）

明示モードで1頂点共有の点接続と、その先への重なり候補を区別する。vertex linkの分断・分岐・重複を不完全として記録する。新規31件を含む関連117件成功。全1,381一意件成功（通常1,338・実CAD43、失敗/error/skip/漏れ/重複なし、既存1,350 ID・固定290入力不変）。既定とedge-onlyの検査範囲、形状/GUI/保存/出力は維持する。role継ぎ目・連続面・包含・実solid/ANSYSの検証は残り、G02全体は未完了。[契約・検証](MESH_VERTEX_CHECKS.md)。
