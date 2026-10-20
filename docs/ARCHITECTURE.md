# アプリ構造（2026-10-08 調査）

`geometry/boundary_identity.py`は保存float64 knot/poleを有理数へ正確に変換し、共通区間のp+1点で差多項式の恒等性を決める。別次数/knot表現の同一曲線と非ゼロ反例を分け、評価数/pole数/整数bit数で資源を制限する。物理的gapや既存chartの採用条件へ自動昇格させない。[契約](BOUNDARY_CURVE_IDENTITY.md)。

`geometry/seam_chart_union.py`は局所chartの全leaf対を覆う。隣接部は重複chartと遠方凸包、非隣接部は元spline制御点凸包の分離で検査する。既存のsource/mapping照合を候補入口へ引き継ぎ、旧分割/候補reportは保持する。明示的な別APIであり、既存GUI/出力判定を変更しない。[契約](SEAM_CHART_UNION.md)。

継ぎ目診断の`projection_strategy`は従来の`average`を既定にし、`balanced_transverse`では横断接線の方向和から基準投影だけを選ぶ。元微分の包絡・要求領域・閾値・source/mapping照合は維持し、分割/候補APIにも明示的に伝達する。生成や出力ゲートを変更しない。[契約](SEAM_PROJECTION_STRATEGIES.md)。

`geometry/seam_contact_refinement.py`はface IDを元role/Span/ξへ戻し、source/mapping snapshotを照合して親セル全域を含む共通chartへ対応付ける。未達Span範囲の分割木と停止理由を記録するが、異なる投影の局所成功をrootや既存接触reportの成功へ昇格させない。GUI/出力条件は変更しない。[契約](SEAM_CONTACT_REFINEMENT.md)。

`geometry/seam_injectivity.py`は2面の同一表現の元境界に限って片側領域を共通chartへ写像し、全セルで1つの固定投影による強単調性の下限を調べる。微小gapの移動や結合、別投影の成功の集約を行わない。局所の数値的十分条件であり、既存接触report/GUI/出力ゲートへ自動接続しない。[契約](SEAM_INJECTIVITY.md)。

`geometry/boundary_gap.py`はclamped ξ端の境界曲線を抽出し、同じSpanの共通knot区間とdegreeへ変換して差の凸包上限を評価する。4宣言継ぎ目のsource snapshot、予算内/観測gap/未判定/資源上限、標本の上限超過を報告する。予算内と境界表現一致を分離し、welding/再fit/片側chart判定は行わない。既存GUI/出力へ自動適用しない。[契約](BOUNDARY_GAP_ENVELOPE.md)。

`geometry/surface_injectivity.py`は元splineの選択矩形全体に一つの投影を固定し、微分control netの対称成分から強単調性の数値下限を評価する。同じroleの隣接元領域はsnapshotを検査して矩形unionで評価し、別roleは継ぎ目chart不足として未判定にする。既存Jacobian/接触reportを改変せず、GUI/出力ゲートへ自動適用しない。[契約](SOURCE_INJECTIVITY.md)。

`geometry/contact_sources.py`が診断source/mappingの識別とface→元role/cell/対角半分の対応を担当する。`merged_role_error.py`は成功meshのsnapshot識別情報を追加し、旧数値fieldは保持する。`geometry/contact_refinement.py`が元Bézier区間を抽出し、元三角形領域内だけを適応細分して選択2領域の誤差付き診断を行う。作業用sourceをコピーし、変更済みsnapshotを拒否する。独立葉のmeshは位相検査へ渡さず、GUI/出力へ自動適用しない。[契約](CONTACT_PATCH_REFINEMENT.md)。

`geometry/error_aware_self_contacts.py`は共有ID数で局所と非局所を分け、既存edge/vertex/link診断と誤差付き投影下限を組み合わせる。正常な三角形接続でも正の元面位置誤差は局所未判定として保持する。例保存上限は走査を止めず、資源/退化/位相の不完全性と非局所だけの分離を別fieldへ返す。形状/GUI/保存/出力には接続しない。[契約](ERROR_AWARE_SELF_CONTACTS.md)。

`geometry/error_aware_contacts.py`は独立した2meshと三角形別の元面誤差を受け取り、拡大AABB/BVHと単位軸投影gapの下限から要求距離込みの数値分離・未判定・接触候補を分類する。既存mesh診断の入力検証/BVHを利用するが、従来SATの投影公差をEuclidean距離として流用しない。結合済みrole meshの誤差を直接渡せる。自己隣接・包含・最終CAD・丸め保証は別契約とし、GUI/保存/出力へ自動接続しない。[契約](ERROR_AWARE_CONTACTS.md)。

`geometry/merged_role_error.py`は整合格子のセル上限を三角形順へ対応づけ、結合による実頂点移動の最大値を各三角形へ加算する。`role_seams.py::_role_mesh`を既存接触診断と共有し、誤差対象の頂点/face参照を一致させる。元面や旧診断fieldは変更せず、出力ゲートへ自動適用しない。[契約](MERGED_ROLE_ERROR.md)。

`geometry/conforming_role_grids.py`は局所細分の境界集合から共通Span・role別xiのtensor格子を作る。合計三角形上限を割当て前に検査し、整合後のcontrol netと実評価頂点に対して誤差を再計算する。継ぎ目gapと数値目標を分離し、元座標を修復・結合しない。既存生成・GUI・出力へは接続しない。[契約](CONFORMING_ROLE_GRIDS.md)。

`geometry/surface_triangulation.py`は基準SplineSurfaceをBézier化し、S−双一次面のcontrol netと双一次面−対角三角形のtwistから数値誤差上限を返す。worst-firstの4分割は元面を再fitせず、未達セルを保持する。局所セルはT junctionを許す診断資料であり、整合mesh・干渉検査・出力へ自動適用しない。[契約](TRIANGLE_ERROR_ENVELOPE.md)。

`geometry/role_seams.py`は4roleの明示的な境界対応だけを共有ID化した診断meshへ組み立て、既存のedge/vertex/link・接触検査をrole間へ適用する。元座標は変更せず、診断移動量・接続ずれ・不完全性を報告する。生成/GUI/保存/出力への自動接続は行わない。[契約・限界](ROLE_SEAM_CHECKS.md)。

解析用Shroudは`geometry/analysis_shroud.py`が既存の実Tipを読み取り、図面ケーシング法線と別の隙間から派生壁面を作る。`ImpellerGeometry.analysis_shroud`へ保持し、通常の`shroud`・翼断面を置換しない。TurboGrid ASCIIの整形時だけ解析用壁面を選び、Mechanical CAD・通常の流路面積/Throatは図面用を参照する。選択壁面の所属は元壁面の距離へ対応付ける。定義・検証は[解析用Shroud](ANALYSIS_SHROUD.md)。

対象は遠心圧縮機アプリ。親フォルダの家計簿は今回の対象外です。
初回コミット時はPython package内65ファイル、test_*.pyは54ファイルです。2026-10-11の翼端R/Z入力追加後はPythonファイル70、テスト65ファイルです。

| 場所 | 役割・依存 |
|---|---|
| main.py | argparseでdesign/optimizationとProjectを選び、QApplication・MainWindowを起動 |
| blade_designer/models/ | dataclass/Enum、入力・結果・Validation。数値配列はNumPy |
| blade_designer/geometry/ | PCHIP分布、子午面Line/Arc、G1接続、2D/3D断面、面積・曲率・スロート・全周投影。NumPy/SciPyとmodels |
| blade_designer/cad/ | 任意のCAD層。clientは数値snapshot、worker内だけでOCPを読み込みBREP/Fillet/STEP再読込を実行 |
| blade_designer/fileio/ | JSON保存・旧schema移行、CSV、TurboGrid固有形式。models/geometryに依存 |
| blade_designer/gui/ | PySide6 Widgets、PyQtGraph 2D、QPainterの3D wireframe、Undo。上記層を呼ぶ |
| blade_designer/optimization/ | パラメータ写像・制約・候補判定。models/geometryに依存。探索ソルバーを実行しない |
| tests/ | 解析解・幾何不変条件・旧座標fixture・Qt offscreen・入出力検証 |
| tools/ | GUI画像生成、開発用テスト実行。製品起動経路とは別 |
| docs/ / .vscode/ | 開発手順・調査結果・IDE設定 |

流れ: main → gui → models / geometry / fileio / optimization。

TurboGridの主翼/Splitterは`fileio/turbogrid_export.py`が既存`geometry.sections`/`splitter_sections`を翼別のASCIIに変換する。クリアランス時は既存のQt非依存`span_extension`を各翼へ適用し、両方の所属範囲と整形検証を済ませてからケースpublishへ渡す。数値generator/保存schemaを変更せず、Readinessも同じ非書込みprepareを使う。[契約](TURBOGRID_SPLITTER.md)。

## 翼面評価の数値層（Stage 3A-1）

`geometry/surface_evaluation.py`はrole別対応座標とSpanで区分線形面／tensor splineを評価する。NumPy／SciPyだけに依存し、OCP・Qt・ファイル形式をimportしない。`cad/occt_backend.py::create_surface`は共通の従来係数構築結果をOCPへ移し、`geometry/impeller_trim.py::_blend`は共通の列補間を呼ぶ。Previewの既存wireframeは維持する。XYZ／円筒座標、表示index／master m_norm、派生source_spanは同一視しない。対応点差は全面誤差保証や干渉判定ではない。[方式・検証・残課題](SURFACE_EVALUATION_CONTRACT.md)。

Stage 3A-2aの`geometry/surface_correspondence.py`は実表示index→CAD xi、派生source_spanと公称Span、trim共通indexを分離して読取り専用で診断する。既存generatorやGUI／CAD clientの依存先は変更しない。実wireframeとの対応点比較は全面偏差の保証ではない。[契約・限界](SURFACE_CORRESPONDENCE.md)。

Stage 3A-2bでは`models/geometry_3d.py::CurveSourceMap`と`geometry/curve_source.py`が派生曲線の元集合・role・Span/indexと合成重みを保持する。trimと表示用resampleは形状を変えず由来を継承し、共通数値層から元の円筒補間面を参照する。設計JSONへ保存せず生成時に再作成する。新加工TEは元TEの由来を持たない。[契約と検証](DERIVED_SOURCE_CONTRACT.md)。

Stage 3A-2cの参照表示では`geometry/cad_surface_reference.py`が旧CADの端部接線計算と固定密度の参照面を提供し、OCCT backendも同じ接線関数を呼ぶ。`gui/cad_surface_reference_widget.py`が読取り専用snapshot・表示設定・失効を管理する。通常Previewとは別widgetで描画し、設計JSONや計算方式を切り替えない。[契約](CAD_SURFACE_REFERENCE.md)。

`cad/reference_report.py`は最新のCAD結果と参照snapshotの一致・role別採用格子を検査する。MainWindowはCAD完了結果のコピーをセッション内で保持し、参照widgetがそれを使う。幾何層は完全なrole→密度mapを受け取り、reportやファイル形式を知らない。固定格子は互換維持。[採用格子](CAD_ADOPTED_SURFACES.md)。

## 翼種別の生成時検証（Stage 2B-1）

`models/validation.py::validate_row_settings`は3Dで使用する共通設定と翼種固有設定を検査する。実断面・Span・壁面・選択LE/TEは`geometry/geometry_3d.py`以下が検査する。旧`validate_parameters`はlegacy 2Dとrow一覧なしのJSONの従来契約を保持する。Stage 2B-1の検証記録は[検証契約](ROW_VALIDATION_CONTRACT.md)。

Stage 2B-2では`validate_stored_settings`と`project_io._check_stored_row`が全保存値の整合性を検査し、`_check_row_project`が全宣言rowを共通壁面と各kindで生成する。root編集snapshotもactive kindで検証する。rowデコードの途中では未選択翼種を生成せず、root contextが揃ってから検証する。GUI Load／Saveの参考Impeller必須依存を外し、旧2D不成立の読込み時はOptimizationWidgetのbaseline／candidateを解除する。生成式・schema項目は変更しない。[保存検証](ROW_PROJECT_VALIDATION.md)。

## TurboGridの整形後検査（2026-10-17、Stage 1A）

fileio/turbogrid_export.pyの_validate_profile_coordinatesは、実際に丸めたXYZ文字列を再読込みし、有限値・閉鎖・連続点重複・LE/TEマーカーと各Spanの輪郭点数対応を全Profile Points経路で検査します。geometryや出力文字列は修復せず、出力先作成前に拒否します。旧通常精度のbytesは維持します。3D干渉検査とは別です。定義・全回帰832件の記録は[出力品質](EXPORT_QUALITY_IMPROVEMENTS.md)を参照。

## RCと静翼の中央2D表示（2026-10-17）

中央2Dは、有効なgenerate_diffuser_3dのHub masterを直接XY投影します。Full Annulusは同じ断面をZ軸回転し、翼列名・Hub・XYを表示します。旧generate_diffuserの100→160 mm等の独立した半径設定を表示形状の正本にしません。RCは既存の子午面LE→TEで外径から内径へ生成でき、数値計算・LE/TE／βの符号・JSON kindを変更しません。旧2D計算・Metrics／Curvature・CSVは互換経路として維持し、Passage／TurboGridは実3Dの経路です。既定JSONは今回指定の原本から3翼列・RC選択の状態をコピーしました。詳細は[RETURN_CHANNEL_DISPLAY.md](RETURN_CHANNEL_DISPLAY.md)。

Passageの断面測定は、生成Hub camberのmeridional_distanceと壁面上の実Hub足点を対応させて、その翼列の実LE〜TE内に限定します。戻り部の法線が遠方の上流翼にも交わる場合の誤対応を除きます。局所的に壁面からずれた断面の検証は保持します。

## インペラ派生カット（2026-10-17）

後流選択`shroud_downstream_mode`は既定`cut`／任意`restore`。`geometry/impeller_trim.py::_restore_downstream`が従来の翼カット・外径カットの後に壁面だけを五次補間で復元し、翼座標を再計算しません。実Tip全輪郭の最下流投影から元壁面終端までを使い、元所属区間とTip距離を写像します。後続の解析用Shroudもこの結果を参照します。旧JSONは既定補完・既定値省略、GUIは既存の翼列snapshot／履歴に接続します。詳細・制約は[派生カット仕様](IMPELLER_TRIM_SPEC.md)。

models/parameters.pyの任意`impeller_trim`は翼列snapshotに保持し、未指定の既定値・JSONには追加しません。数値・モードはmodels/validation.pyで検証します。geometry/impeller_trim.pyは元のImpeller生成・TE Rake・Splitter処理の後に、固定した元平均線の断面面積から派生ケーシングを求め、元の離散翼面を円筒座標でSpan補間して切り出します。外径は元のPS/SS・camberを円筒で切断し、平らなTEを接続します。Qt・ファイル形式へ依存しません。

ImpellerGeometry.source_geometryは元設計の結果、trim_reportは径・元基準面積比です。派生Curve3D.source_spanとm_blade_normは元座標との対応を保持します。DerivedWallは元壁面上の距離・区間境界との対応を持ち、既存の解析Line/Arcは置換しません。sample_meridional・wall_tangent・crossflow_intersectionsは派生ポリライン用の分岐を持ち、元の解析的経路を維持します。描画用の所属区間は元距離から派生距離へ写像します。

GUIは中央2D/3D・Flow Area・Passageへ同じ派生結果を渡し、角度・厚さグラフとLE/TEハンドルは元の設計結果を編集します。子午面には派生Tip・ケーシングを重ねます。無効入力では従来の最終有効表示を明示し、Passageの計算元を解除します。fileio/trim_export_guard.pyで派生TurboGrid/CADを出力先作成前に拒否します。詳細は[IMPELLER_TRIM_SPEC.md](IMPELLER_TRIM_SPEC.md)。

## 子午面区間の座標表示（2026-10-17）

MeridionalEditorは既存update_previewで生成した有効な壁面結果と曲線定義のコピーを保持し、選択行に対応する解析的なstart／center／endをR/Z [mm]で表示します。選択変更だけで再計算信号を送らず、更新前後の曲線定義が異なる場合や無効壁面では表示を消去します。派生座標を設計値・JSONへ追加しません。詳細は[MERIDIONAL_COORDINATES.md](MERIDIONAL_COORDINATES.md)。

## 流路面積・スロート（2026-10-16）

geometry/passage.pyは選択翼列と同一のImpellerGeometry master断面から、子午面直交開口の周方向幅をSpan積分し、隣接主翼とSplitter両側の輪郭間最小幅を測定します。円筒／円錐は展開ポリライン、曲線壁はXYZ弦の下限推定、スロート面積は各Spanの最小幅の近似積分です。結果型はmodels/passage.pyで、既存の幾何生成・歴史的数値参照を変更しません。

gui/passage_widget.pyはView → Passage Area / Throatで明示計算し、ThreadPoolExecutorへ開始時のdeepcopyを渡します。Qt更新はGUI側のQTimerで行い、編集・選択・入力不正で世代を更新し、旧世代の結果を破棄します。MainWindowは選択対象の実3D（静翼はgenerate_diffuser_3d）を接続し、子午面選択時は解析を無効化します。JSON項目やCSV／TurboGrid／CAD出力を追加・変更しません。詳細は[流路解析](PASSAGE_ANALYSIS.md)を参照してください。

## CAD層（2026-10-16）

geometry/provisional_disk.pyはユーザー指定の仮ディスクを数値層で作成します。実際のHub側根元R/Zを既存の解析的壁面投影へ渡し、構造CAD専用の前面範囲と裏面を決めます。DiskGeometryParameters.provisional/front_end_m_mmへ仮状態・範囲を保存し、非仮の旧JSONでは追加キーを省略します。clientはmechanical_hub_segmentsを従来の所属壁面と分離して渡し、workerは仮寸法をレポートへ記録します。TurboGridの所属検証は維持します。disk actionは単体の閉solid・STEP再読込を検証し、Preview3Dは元の翼ワイヤーフレームを保持してNo CAD Blade/No Root Filletを表示します。Blade Blend手順の半径もsnapshotの値から生成します。

既存geometry層はCAD/Qt/ファイル形式に依存しません。models/cad.pyの設定は純粋なdataclassです。CADを使用しない既定値はJSONから省略しschema 0.3を維持し、設定変更時に0.4へ保存します。旧JSONには未設定ディスク・R8を補い、ユーザー原本を変更しません。

cad/client.pyは選択Impellerの深いコピーから既存generate_impellerを呼び、master座標・対応パラメータ・所属壁面の厳密Line/Arc・snapshot/hashを保存します。出力点数はCAD入力へ影響しません。通常のGUIプロセスにはOCPをimportせず、gui/cad_export_worker.pyが別Python環境でcad/worker.pyを起動します。B-spline曲面、閉shell/solid、明示裏面の回転Hub、Boolean、意味と履歴によるRoot Edge、真の指定半径フィレット、干渉、STEP round tripを処理します。

fileio/mechanical_step_export.pyは検証済みstaged bytesとSHA256だけを受け、同一ディレクトリの一時ファイルから置換します。失敗レポートは別名で保存します。TurboGrid CADは機械用ディスクと別の流体領域を生成し、STEP中間形式・変換必要・ANSYS未検証を区別します。既存turbogrid_exportは変更せず、Profile Pointsは未フィレットです。スプリッター付きProfile Pointsの既存拒否も維持します。

Preview3DへはBREPのtessellationと実edge座標のみを渡します。カメラは保持し、現在の全Project snapshot hashと一致する場合だけCADを表示します。途中編集が非同期ジョブへ混入しません。CAD設定は既存Undo/Redoと翼列別保存へ接続します。CAD専用の設定・GUI・実カーネルテストはtests/cad/とtest_cad_gui.pyです。詳細は[CAD操作手順](CAD_EXPORT.md)を参照してください。

## インペラTE RakeのParameter Mapper（2026-10-15）

BladeParameters.impeller_te_rake_degは任意の目標角（Noneで従来処理）です。generate_impellerは既存β積分と端部/外径処理後、geometry/impeller_parameter_mapper.ImpellerParameterMapperへ生成形状を渡します。MapperはHub固定、β・R/Z・厚さを保持して各断面を軸まわりに剛体回転します。既存の静翼最適化用optimization/parameter_mapperとは役割を分離し、Qt/ファイル形式へ依存しません。

角度の基準はHub/Tip TEキャンバー端点の中点と軸を通る子午面です。chord=v、面法線=nθとしてgamma=atan2(v・nθ, |v-(v・nθ)nθ|)です。半径と軸方向距離から最大到達角を求め、小さいねじれ側の解をbrentqで求めます。正符号は絶対座標+θ（CCW）です。θTE(s)=θTE(Hub)+s*Δθ、θLE(s)=θTE(s)-積分巻き角とし、曲線配列の共有を考慮して一度だけ回転します。Hub/Tip全体の目標であり、Span毎の局所Rake一定や端部キャップ頂点基準ではありません。

JSONはNoneの項目をsnapshotも含めて省略し、旧schema 0.3を維持します。新規項目なしの旧JSON・デフォルト・数値参照を変更しません。GUIはLE/TEタブのチェック付き入力と実測表示を追加し、読み込んだ未編集値は画面丸めで上書きしません。_bind_history_inputsへRake入力を含めてCtrl+Zを維持し、翼列別snapshot・Undo/Redo・New・保存読込へ既存経路で接続します。静翼3D生成はマッピングしません。

tests/test_impeller_te_rake.pyは一定R=120 mm・Hub/Tip軸間隔20 mmの解析式Δθ=2 asin(20 tan(gamma)/(2*120))、β積分、R/Z不変、3D弦からの独立測定、JSON/出力一致、到達不能時の既存ファイル保護を検証します。GUIテストは独立翼列、Undo、入力確定、表示/保存、精度、無効時の表示保持を確認します。3D面全体の交差や空力/応力評価は追加しません。
geometryからQtを呼ぶ構成ではありません。3DはQPainterによる回転面と翼wireframeで、PyVista/VTK/OpenGLの依存はありません。

MainWindowの上部メニューはFile/Edit/View/Toolsの順で1つずつ作り、ツールバーは作りません。ExportはFile、最適化別ウィンドウはTools、回転方向/反転はEdit、投影面はViewへ配置します。回転方向は排他的QActionGroupから非表示の既存radio状態へ渡し、radio変更をメニューへ同期します。投影面も非表示の既存comboへ渡し、_sync_projection_menuで選択値と対象別の有効状態を同期します。非表示Widgetは既存の計算/保存/Undo経路との接続を維持するための内部状態です。ファイル操作や各解析ウィンドウのcallback・ショートカットを変更せず、入口と順序だけを整理します。

Preview3Dのカメラは従来のazimuth/elevation/scale/center/panに自由回転行列rotationを追加します。仮想球上のドラッグ位置の対応から回転を合成し、SVDで直交性を維持します。従来の角度APIは基底方向として残し、投影・面の奥行き/陰影・Fit Viewは同じ回転基底を使用します。正面/上面/側面/等角/リセットでは自由回転を初期化して全体を収め、Fitは回転を保持します。画面操作はパラメータ・Undo履歴・ファイル形式へ保存せず、形状計算と出力処理は変更しません。中央/別ウィンドウの両Previewで同じ操作を提供します。

## 複数翼列（2026-10-09）

`gui/design_navigator.py`は左の子午面・翼列選択と追加/削除/順番変更を提供します。
追加ボタンは名前とインペラ/静翼の種類を指定するモーダルダイアログを開き、確定時だけMainWindowへ種類・名前を通知します。空白名では確定できず、キャンセルでは設計を変更しません。
名前変更ボタンは選択翼列のIDと新しい名前をMainWindowへ通知します。rename_blade_rowはnameだけを変更し、既存のsnapshot履歴で1 Undoとして保存します。空白名・同名・キャンセルは変更しません。Navigator・子午面区間の所属名・Blade EdgesのRow名と形状タイトルを更新します。Blade Edgesは各種類の先頭翼列を表示名の基準とし、同種類の翼列を選択中はその翼列名を優先します。ID・数値・JSON schemaは変更しません。
`models/blade_rows.py`はQtに依存しない翼列snapshot・共通壁面適用・構造検証です。
`BladeParameters.blade_rows`は任意の`BladeRow(identifier, name, kind, parameters)`リスト、`active_blade_row`は現在の翼列IDです。
各snapshotは従来のBladeParametersを保持し、入れ子の翼列リストは禁止します。Hub/Shroud・Flow Path・resolutionは最上位プロジェクトを正本として適用します。
visible_edge_rowsは旧impeller_edges/diffuser_edges APIの互換参照先を、選択中の同種類翼列または最初の同種類翼列として求めます。画面では全翼列IDを管理し、get_parametersのapply_to_rowsで各欄の編集を所有snapshotへ保存します。起動・JSON読込時だけreconcile_visible_row_edgesでトップレベルの表示値を対応snapshotへ引き継ぎ、旧GUIで控えが古く残った場合の選択時の値変更を防ぎます。他の同種類翼列は更新しません。JSON loader/serializer・元のユーザーJSONは変更せず、Undo復元・通常の翼列切替には読込補正を適用しません。
GUIは選択翼列の設定を既存EditorとGeometry Engineに渡します。並べ替えは翼列リストの順序だけに作用し、数値計算・翼端位置を変更しません。
JSONの追加フィールドは任意です。旧Projectは従来のAPI・保存形式を維持し、翼列管理を開始するとsnapshotを初期化します。
保存時は非選択翼列も検証し、無効な翼列がある場合は書込み前に拒否します。CSV/TurboGridは対象種類に合う選択翼列のみを出力します。
別ウィンドウの最適化は選択中のDiffuser、または最初のDiffuserを対象にします。Diffuserがない場合は別ウィンドウ側に追加します。元の設計へ候補を自動適用しません。

## 対象別レイアウト

### 全翼列のLE/TE欄（2026-10-12）

BladeEdgeEditor.row_edgesは全翼列のIDを正本にし、row_controls/all_coordinate_controlsで各翼列の4端点を管理します。表は4×翼列数の行を持ち、名前と順序はNavigatorに追従します。get_parametersはapply_to_rowsで各所有snapshotへ独立した値を保存します。従来のedges/controls/coordinate_controlsはimpeller_edges/diffuser_edgesの互換参照として選択中または最初の同種類翼列を指します。visible_edge_rowsはこの旧APIとトップレベルJSONの互換参照にだけ使用し、画面の翼列数を2組に制限しません。
ContextMeridional.update_edge_groupsは翼列IDごとにLE/TEのBladeEdgeHandlesを作り、キーを同じIDにしてドラッグを正しい翼列へ届けます。名前変更はラベル・凡例へ反映し、削除された翼列のグラフィックスを除去します。既存Component Stationsの個数・Flow Areaデータは変更しません。子午面区間の追加・編集時は全翼列の端点と未適用R/Z入力を処理します。新しいJSONフィールドは追加せず、旧schemaと数値処理を維持します。
この節は従来の「各種類の先頭/選択翼列だけを画面に表示する」説明を置き換えます。再開後の拡張関連108件と最終全回帰457件が成功しました。Git status・差分チェックも実行できています。

`main.create_window`はユーザー指定のblade_v03.jsonをコピーした`blade_designer/defaults/default_project.json`を既存Project loaderで読み、MainWindowのdefault_parametersへ渡します。MainWindowは独立したsnapshotを保持し、起動・New・別の最適化ウィンドウで再利用します。`--project`は起動値を上書きします。プログラムからdefault_parametersを省略して作るMainWindowと数値モデルBladeParametersの既定値は、既存API・歴史的回帰ケースの互換性のため従来値を維持します。数値計算層からJSONへ依存しません。
翼枚数は既存ParameterPanel.controls["vane_count"]を右側上部へ移して使い、既存の更新・保存・Undo経路を維持します。所属する翼列の設定に追従し、子午面選択時は隠します。

中央の縦Splitter（model_splitter）上段のQStackedWidget（central_views）は、子午面選択時に既存meridional_editor.context、翼列選択時に単翼形状または全周形状を表示します。子午面グラフを中央へ移し、右Editorには数値・区間・所属翼列の表を残します。グラフとドラッグ信号・Undo・所属オーバーレイは同じインスタンスを使用します。角度・厚さのグラフは右Editorに置き、これらのタブ切り替えでは中央の翼形状を維持します。下段のmodel_preview_3dは子午面選択時に全翼列、翼列選択時にその翼と所属壁面区間を表示します。Full Annulusのチェックは保持し、子午面選択中の2Dチェック変更で子午面グラフを隠しません。翼列へ戻ると選択に従って単翼/全周を復元し、設計値・JSON・カメラを変更しません。
Preview3Dはbase_linesを保持し、全周表示時だけ選択翼列の翼枚数でZ軸回転して描画します。全周の各線は描画用に最大151点へ間引き、元の計算・出力座標は保持します。Impellerは既存3D計算、Diffuserはgenerate_diffuser_3dで子午面上の断面を生成します。Viewのpreview_3dも選択翼列の同じ3D形状を表示します。数値計算とドラッグ/Undo処理は共通です。点のクリックも選択として処理し、右側の狭いグラフでドラッグ開始距離に達しない操作を扱います。
右Editorは子午面選択時にMeridionalだけ、翼列選択時にBlade Angle / Thickness / LE / TE / Full Annulus（LE / TEは1タブ）を表示します。最適化専用モードではOptimizationも表示します。
Component Stationsの編集表を可視レイアウトから外し、子午面のStation値一覧を非表示にしました。旧station_table APIとFlowPathParametersは保存互換性・Flow Area計算のため維持します。Blade Edgesは引き続き独立して編集できます。
下部Contextは表示レイアウトから除去しました。解析Widgetと内部APIは保持し、Viewメニューからスクロール可能な別ダイアログで開きます。Outputも同じ仕組みです。
中央表示/右Editorは横方向Splitterで幅を調整できます。スクロールとサイズポリシーで編集内容の最小高さがメインウィンドウへ伝播することを防ぎ、起動時は利用可能画面サイズに合わせます。

## 中央下部の対象別3D（2026-10-12）

MainWindow._update_central_previewは子午面選択時に全翼列のrow_parametersを既存3Dエンジンへ渡し、Preview3D.update_rowsで名前・ID付きの翼線とSpanwise線を合成します。Full Annulusには線ごとの所有翼列の枚数を使い、共通壁面の回転面は1組だけ表示します。無効な翼列は名前付きエラーで除外し、他の有効な翼列と2D編集を維持します。
翼列選択時は既存の選択翼形状を維持し、geometry/row_domain.preview_wall_chunksでその翼列に所属するHub/Shroudの連続区間を解析的な端点を含めて描画用にサンプリングします。全未割当なら全壁面、割当がある場合は未所属の壁面は描かず、離れた区間同士を面で結びません。出力時の連続区間・翼包含検証とは独立し、保存データと計算は変更しません。
設計snapshotと表示対象をキャッシュし、タブ・全周表示だけの変更では翼を再計算しません。形状更新時にキャッシュを無効化し、Project復元中の入力再構築からは更新せず、完成した幾何形状で中央3Dを更新します。カメラ・表示チェックを保持します。Viewの別3D Previewは従来どおり選択翼列を表示します。

## Hub/Shroud回転面（2026-10-11）

回転面描画: geometry/revolved_surface.pyはHub/ShroudのZ/RからZ軸回りの閉じた全周quadを返します。描画用に子午面最大49点・周方向48区間を使用し、元の計算・壁面サンプリング・出力は変更しません。Preview3Dは面をカメラ奥行き順に半透明で描き、その上へ従来の翼wireframeを描きます。Hub/Shroudの元の線配列は内部API用に保持し、線としては描画しません。既存の表示チェックは面に作用します。全周翼表示で壁面を重複生成せず、常に1組の回転面を保持します。Fit Viewは回転面の全頂点を含めます。中央とViewの別3D Previewへ同じ描画を適用します。

## 編集Widgetの整理（2026-10-11）

ProfileDistributionEditorは共通PlotWidgetをControlPointEditorのshared_plot引数へ渡します。断面ごとの一時PlotWidgetを作成・破棄せず、曲線・ハンドルだけを共有グラフへ追加します。グラフの所有者はProfileDistributionEditorのままです。ControlPointEditorの単独利用、表編集・ドラッグ・既存転送APIは維持します。Impeller表示では直後に上書きされるDiffuser曲線の更新を省き、選択断面を直接表示します。数値計算・既定値・ファイル形式は変更しません。

## インペラTEの円筒Cutoff（2026-10-11）

geometry_3d.generate_impellerは解析的なHub壁面上の指定TE位置から共通半径Rを取得します。Cutoffの断面だけへ渡し、blade_section.generate_sectionは各Span壁面のR交点のうち指定TEに最も近いものを選びます。断面の正規化座標はLEから実際の円筒切断位置までの0～1へ対応します。PS/SSの長い側を交点で切り、短い側は終端角度・厚さを一定として交点まで延ばします。延長に必要な仮想camberが有限壁面を越える場合は終端の壁面接線を継続して角度だけを求め、実際の翼座標は有限壁面上に置きます。TEはR一定・Span内Z一定でPS/SS端点をつなぎます。円形・楕円TE、LE、2D Diffuserの処理は維持します。

cylindrical_cutoff.pyはサンプリング済み子午面の交点・展開面上の切断と延長を扱い、Qtや出力形式に依存しません。到達不能、LE以前の切断、外径を越える輪郭は拒否します。表示・TurboGrid出力は同じ3D形状を使用します。新しい設定フィールドはなく、元JSON・デフォルト用JSONは変更しません。従来のCutoffを含むJSONは読込後に新しい円筒Cutoffで再計算します。

## 子午面区間の所属と出力

MeridionalEditorのType列はLine/ArcのQComboBoxです。geometry/meridional_segments.convert_segment_typeで経路長とblade_row IDを保持したパラメータを生成し、選択区間だけを置換します。Line→Arcは既定Sweep=35°と長さからRadiusを求め、Arc→LineはR×|Sweep(rad)|をLengthへ渡します。数値処理はQtに依存せず、非正・非finiteの長さは拒否します。表の種類別入力欄と中央プレビューを更新し、既存editFinishedで1 Undoになります。JSON schemaは変更しません。

翼端R/Z入力: gui/blade_edge_editor.pyは全8端点のR/Zを表示し、Applyで編集された座標ペアだけをgeometry/blade_edge.project_to_wallの解析的なLine/Arc最近点へ投影します。結果の壁面距離を既存BladeEdgePositionへ保存し、表示を実座標へ戻します。座標入力中は設計を変更せず、ApplyのparametersChanged/editFinishedで一括更新・1 Undoとなります。MeridionalEditorの有効な壁面更新と翼端ドラッグで表示座標を再取得します。既存normalized controls APIは非表示で保持し、JSONフィールド・計算・出力は変更しません。
末尾への区間追加では、geometry/blade_edge.rescale_extended_wall_edgesが追加側のLE/TE正規化距離に旧全長/新全長を掛け、既存壁面上の物理距離とR/Zを維持します。MeridionalEditorは現在の端点を換算し、wallExtendedでMainWindowの非選択翼列snapshotも換算します。追加と換算は既存editFinishedで1 Undoとなり、未適用座標入力は表示更新後に復元します。JSON形式は維持し、削除・移動とProject読込には換算を適用しません。
子午面の開始条件と区間数値のCompactDoubleSpinBoxはsetKeyboardTracking(False)でキー入力中のvalueChangedを保留し、フォーカス移動・Enterの確定時だけ既存の計算経路へ渡します。setValue・スピン操作・種類/方向選択の既存経路は維持し、editingFinishedによるUndo記録も維持します。
寸法・開始条件・種類変更はMeridionalEditor._edit_wallで候補壁面を生成し、既存の流路検証を行います。geometry/blade_edge.adapt_wall_edge_coordinatesは旧端点を新壁面へ解析的に最近点投影し、壁面上に残る位置は維持、外れる位置は投影座標へ更新します。現在の2組とMainWindow._other_row_edgesで取得した非選択snapshotの全端点を計算してから、曲線と端点距離をまとめて反映します。壁面自体が無効な場合だけ入力欄とモデルを元へ戻して理由を表示します。翼端が壁面出口へ重なって生成翼が無効になる場合も壁面編集を優先し、既存の形状・保存検証を維持します。未適用のR/Z入力を保持し、壁面変更と翼端調整を既存Undo経路で1操作として記録します。新しいJSONフィールドはありません。

LineSegmentParameters / ArcSegmentParametersに任意のblade_row IDを保持します。Hub/Shroudはプロジェクト共有で、区間定義と所属を一緒に移動・削除します。MeridionalEditorは所属列と色・名前のオーバーレイを提供します。保存時は翼列IDとの整合性を検証し、未割り当ての旧JSONには新キーを出しません。翼列削除時は共有壁面と残るsnapshotの所属を解除します。
Qt・ファイル形式に依存しないgeometry/row_domain.pyが解析的な区間長から物理距離の連続範囲を返します。TurboGridの壁面サンプリングだけへ適用し、元の翼形状計算・プロファイル座標は変更しません。両壁面の連続性、LE/TEと輪郭の包含をファイル書込み前に検証します。全区間未割り当てなら旧来の全壁面出力です。Diffuser CSVは元々壁面を含まないため、所属では輪郭を切り詰めません。

## 翼Tipとケーシングの分離（2026-10-16）

`BladeParameters.tip_clearance`は任意の翼列別設定、`ImpellerGeometry.tip`は派生したサンプルTipです。既存`geometry.shroud`は常に解析的な固定ケーシングを保持します。Qt／I/O非依存の`geometry/tip_clearance.py`でケーシング法線・物理弧長補間・Cutoff交点を求め、主翼とSplitterのSpan壁面生成へ共通適用します。ゼロ／Noneは従来関数へ分岐します。派生TipをLine／Arcと偽って保存しません。任意設定のJSONは0.4、Noneキーは省略。GUIは同じ実断面を描画し、正の隙間のTurboGridはProfile PointsとCAD双方で書込み前に拒否します。流路解析は総面積のケーシングと実翼Tipを分けます。詳細は[TIP_CLEARANCE.md](TIP_CLEARANCE.md)。

## 依存環境

Windows 11 build 26300、Python 3.12.14の既存.venvを確認。
直接依存: NumPy 2.5.3 / SciPy 1.18.1 / PySide6 6.11.2 / PyQtGraph 0.14.0 / pytest 9.1.1。
pip checkは成功。標準ライブラリはdataclasses、enum、json、csv、pathlib、copy等。
requirements.txtは既存の非固定指定を維持。requirements-windows-py312.lock.txtは現在の全依存の記録で、新規環境への再インストール結果ではありません。

## Diffuserの子午面3D

geometry/geometry_3d.pyのgenerate_diffuser_3dはdiffuser_profileをSpan 0・1へ独立コピーし、diffuser_edgesのHub/Shroud LE/TEで壁面対応を作ります。共通の_generate_rowとgenerate_sectionを使い、子午面の実座標から各Spanの角度積分・厚さ・翼端を計算します。Impeller専用の一定外径TE Cutoffは適用せず、静翼Cutoffは従来の局所端部処理です。戻り値は既存のHub/Shroud/sectionsを持つ3D geometry型を共有し、Qtには依存しません。Preview3Dは既存の区間別Spanwise接続・回転面・全周描画を再利用します。上段2D・曲率・指標・CSVは既存generate_diffuserを維持し、JSON schema・保存検証・旧データ移行を変更しません。 MainWindow._display_geometryは追加3D計算のエラーを独立して捕捉し、2Dを更新しながら3Dのみ前回の有効形状を保持して理由を表示します。従来の2Dとして有効な編集を新しい3D検証で阻止しません。

## リソース・入出力

- パッケージ内の常設画像リソースは見つかりません。グラフ・wireframeは座標から描画。
- blade.json / blade.csv: ユーザーの作業データ。変更せずGit対象から除外。
- tests/fixtures/*.json / *.npz: 旧プロジェクト・既存実装座標の回帰資料。Git対象。
- artifacts/: 過去の画像・検証結果・zip・ANSYS形式資料・今回のログ。Git対象から除外。
- 読込: Project JSON schema 0.1/0.2/0.3、起動時--project。
- 書出: Project JSON（内部精度）、Diffuser segments/contour CSV（有効桁）、選択Impeller/静翼のTurboGrid hub.curve/shroud.curve/profile.curve/BladeGen.inf。
- TurboGridで実際にImportする確認とCAD/CFD連携は今回実行していません。

### 静翼TurboGrid出力（2026-10-13）

fileio/turbogrid_export.pyは従来のImpeller計算経路を維持し、選択行のkindがdiffuserならrow_parametersで独立snapshotへ共有壁面等を組み合わせ、generate_diffuser_3dを呼びます。RCは名前であり同じdiffuser種類です。静翼のauto端部判定はdiffuser_profile.edge_parametersを参照します。geometry/row_domain.export_wall_intervalsへ対象edgesを渡し、所属IDは元プロジェクトから取得して両壁面の連続性と静翼LE/TE・全輪郭の包含を検証します。edges省略時のImpeller互換APIは維持します。

MainWindowは子午面選択中の出力を拒否し、翼列選択時は保留編集をcommit_editで確定して現在値を出力関数へ渡します。3D生成・JSON schema・CSV・Preview3Dは変更しません。静翼の丸め後の輪郭縮退/対応点数の不一致をファイル作成前に拒否します。書込みの個別os.replaceによるI/O障害時の原子性は従来どおりで、ケース全体のトランザクションは追加しません。

tests/fixtures/turbogrid_impeller_sha256.jsonは実装変更前のb751f27で生成した3ケース/12ファイルのLF正規化ASCIIハッシュです。歴史的な出力互換性の基準であり解析解ではありません。静翼は別途、円錐壁面の解析座標・回転/単位・所属端点・独立設定・GUI出力と現在3Dの一致を検証します。

既存の詳細仕様・変更報告はプロジェクト直下のV03_*.md、各EDITOR_REPORT.md等を維持しています。最新のユーザー要求を優先し、旧仕様から動作を勝手に戻さないでください。

## スプリッター（主翼連動/専用分布、2026-10-15）

BladeParameters.splitterは任意のSplitterParameters（Hub/Tip開始割合、ピッチ割合、厚さ倍率、任意の専用sections）です。Noneは無効で、JSONの追加キーをsnapshot内も含めて省略します。旧schema 0.3・既定値は維持し、任意フィールドのあるJSONは対応版で開きます。

generate_impellerは主翼とTE Rakeの生成を完了した後、geometry/splitter.pyへ渡します。主翼配列は変更せず、ImpellerGeometry.splitter_sectionsに別の断面リストを保持します。生成はQt/ファイル形式に依存しません。各Spanで主翼の実効m_LE/m_TE（Cutoff後）を使い、m_start=m_LE+f(s)*(m_TE-m_LE)、f(s)=(1-s)*fHub+s*fTipとします。generate_sectionの任意引数で開始位置・厚さ倍率・TE周方向目標を指定し、β・厚さの評価座標はf+(1-f)*m_splitterです。各断面のTE θを主翼TE θ + rotation_sign*2π/N*pitch_fractionへ配置し、主翼TE Rakeを継承します。新しいLE端部を生成し、既存の断面検証と一定外径Cutoffを再利用します。

GUIはImpeller専用のSplitterタブ内にSplitterEditorを配置します。未編集値の精度、入力確定、Undo、独立翼列snapshot、New/JSON読込へ接続します。2D・Full Annulus・中央/別3D・子午面選択時の全翼列3Dは同じsplitter_sectionsを描画し、各翼列の主翼数Nで複製します。初期はsections=Noneで主翼連動、独立チェック時に主翼の各Spanの制御点を深いコピーで取得します。専用β・厚さの座標軸も元の主翼の0〜1ですが、可視LE〜TEの点だけでPCHIP補間するため、コピー時に形状が変わる場合があります。専用ProfileDistributionEditorは初回使用時に生成し、共通グラフの追加・削除・ドラッグ・表入力・Undoへ接続します。厚さの曲線は倍率適用前です。主翼に新しいSpanが増えた場合、splitter.independent_profileで保存済み専用Spanの間を補間します。専用分布と主翼分布は保存/復元後も別オブジェクトです。複数種類・3D翼間干渉は追加していません。

TurboGridの複数翼セットに対応する出力形式はこの実装の範囲外です。export_turbogridはスプリッター付きImpellerをファイル作成前に拒否し、主翼だけの不完全な出力を防ぎます。静翼と無効時の既存出力は変更しません。tests/test_splitter.pyは解析β巻き角・分布切出し・主翼不変・Rake/Cutoff/CW/CCW・JSON精度・出力保護を、tests/test_splitter_gui.pyは編集確定・Undo・独立翼列・同一表示座標・全周枚数・保存読込を検証します。


## スプリッターのLE–TE編集範囲（2026-10-17）

SplitterControlPointEditorは元の0–1制御点を保持し、geometry/splitter.splitter_edit_pointsで得たLE境界と下流点だけを表示します。未編集の境界は保存データへ混入させず、可視点の編集・追加・削除時にLEも実制御点として固定します。専用分布はsplitter_active_profileで可視区間を計算用0〜1へ対応付け、generate_sectionのdistributions_from_le指定で同じPCHIPを使います。物理的なstart_fractionは保持します。通常の主翼・静翼・連動スプリッターは既定経路のままです。JSONには従来の主翼座標を保存します。詳細は[SPLITTER_EDIT_RANGE.md](SPLITTER_EDIT_RANGE.md)と[SPLITTER_INTERPOLATION.md](SPLITTER_INTERPOLATION.md)。

AboutメニューはMainWindowの画面内ヘッダー情報をQMessageBoxへ移したもので、設計モデルやUndo履歴には接続しません。


## 共有分布グラフと表示範囲（2026-10-17）

CombinedProfileEditorは主翼ProfileDistributionEditorを拡張し、既存スプリッターの実ControlPointEditor／曲線／操作点／表を同じグラフへ移します。状態や計算用制御点を複製せず、接続元のSplitterEditorの保存・Undo経路を維持します。グラフ再構築時は自分の凡例項目だけを除去し、相手の項目は保ちます。連動時は実生成分布を読み取り専用で描きます。plot_fittingはグラフ所有の単発タイマーでShow後にFitし、編集時には自動追従しません。詳細は[SHARED_GRAPHS.md](SHARED_GRAPHS.md)。

## クリアランス付きTurboGrid Profile Points（2026-10-17）

geometry/span_extension.extend_tip_to_shroudは実Tipと直前のSpanから円筒座標を線形延長し、解析Shroudとの交点から新しい断面だけを返します。実設計のgenerate_impeller・Mapper・CAD・表示の経路には組み込みません。fileio/turbogrid_exportが出力専用geometryへ断面を追加し、実Tip・延長断面の順で保存します。ゼロ隙間は従来経路です。GUIはprofileラベルから1始まりの実Tip番号を案内します。Profile Numberの指定はTurboGridで行い、未確認の初期化キーワードは追加しません。詳細・制約は[TURBOGRID_CLEARANCE.md](TURBOGRID_CLEARANCE.md)。

## ケース公開と復旧（Stage 1B）

`fileio/case_publish.py`が同一親の作業ケース・保持バックアップ・復旧journal・OSロックを管理する。TurboGridは`prepare_turbogrid_export`で書込み前にbytesを確定する。CADはworker artifact全体のhashを検証し、STEP・profile・metadata・reportを同じ作業ケースで完成させる。旧case退避→新case設置の2回renameで公開し、中断時は次回出力で安全な復旧を試みる。I/O失敗は候補全体を中断し、失敗reportはjob側へ保存する。計算上のartifact別部分成功は維持する。バックアップを自動削除しない。単一原子操作・実停電耐久性・別artifactのsnapshot統一とは区別する。[検証と運用制約](EXPORT_QUALITY_IMPROVEMENTS.md)。

## 出力入力条件の診断（Stage 1C）

`fileio/export_readiness.py`は設計のcopyから経路別Checkとsnapshot hashを返す。Qt／OCP・書込み・CAD起動に依存しない。Profile Pointsは共通のpure prepareを利用し、CADは入力条件と未実施のkernel検証を区別する。`gui/export_readiness_widget.py`が読取り専用表示を担当し、MainWindowはメニュー入口と失効通知のみを追加する。新たな設計値・永続設定・Undoコマンドは追加しない。既存出力の対応制限は維持する。詳細は[検証記録](EXPORT_QUALITY_IMPROVEMENTS.md)。

## 実断面の識別と測定（Stage 2A）

`models/geometry_source.py`は結果のrow context・engine・variant・snapshot IDを表す非永続型。`fileio/geometry_source.py`がCADと同じcanonical snapshot hashを付ける。`geometry/section_measurements.py`は実camber／master曲線からXYZ指標を計算し、`gui/row_metrics_widget.py`が読取り専用で表示する。中央2D／3DとPassageには同じ生成結果を渡す。新しい`fileio/row_xyz_csv.py`は現在入力を再生成したmaster点をmm/Z座標でatomicな単一ファイル出力にする。旧writer／旧数値生成器は変更しない。

MainWindowはlegacy計算失敗時にlegacy表・曲線・current sourceを解除し、有効な選択3Dの表示を継続する。静翼の参考Impellerが失敗しても共有壁面には選択静翼を使える。`MainWindow.geometry`の最後のlegacyオブジェクトは互換APIとして残るが、currentには使わない。Stage 2B-1で3D生成の入力検証、2B-2でrow一覧ありのLoad／Save検証を分離した。両翼種のLE/TE端点の有限性・0〜1範囲は共通の入力整合性として維持する。定義・精度・GUI・CSV・検証の詳細は[形状正本の契約](GEOMETRY_SOURCE_CONTRACT.md)、[保存検証](ROW_PROJECT_VALIDATION.md)。

## 解析微分による局所診断

`geometry/surface_diagnostics.py`は`SplineSurface`の解析微分から位置/接線/Jacobian/法線を評価する。Qt/OCP/ファイルへ依存せず、生成・表示・出力への適用は行わない。退化閾値をcallerが明示し、未定義法線と有効比較点数を区別する。向きはパラメータ依存で、CAD外向きや全面妥当性は示さない。[契約](SURFACE_DIFFERENTIAL_DIAGNOSTICS.md)。

## 同一対応面の位置差包絡

`geometry/surface_envelope.py`は同degree/clamped/非周期の基準splineを共通knotへ挿入し、差のcontrol netから実数モデル上の全域位置差包絡を計算する。refitや既存生成の切替は行わない。float丸めは未証明と返し、CAD/GUI/出力の合否へ自動接続しない。[契約](SURFACE_DISTANCE_ENVELOPE.md)。

## 基準面の局所正則性包絡

`geometry/surface_regularity.py`は既存splineをBézier区間へ分け、微分外積のBernstein係数からJの下限/上限を計算する。標本で見えない折返しを未判定として残す。元C1/同じパラメータ尺度が前提で、局所正則を自己交差なしに置き換えない。Qt/OCP/ファイルへ依存せず、既存生成/出力や公差は維持。[契約](SURFACE_REGULARITY_ENVELOPE.md)。

## 同一対応面の法線角包絡

`geometry/surface_orientation.py`は同degree/C1の2面を共通Bézier区間へ分け、微分外積の内積/外積係数から向き付き法線角の上限を返す。J下限未確保はNone、角度を絞れない正則区間は180度とする。物理対応はcallerの契約で、外向き・丸め保証・干渉検査を意味しない。Qt/OCP/出力条件に依存しない。[契約](SURFACE_NORMAL_ENVELOPE.md)。

## 明示三角形の接触候補

`geometry/mesh_contacts.py`は格子三角形化・BVH・分離軸検査を担当する。`geometry/blade_contacts.py`が4role×Main/Splitterの自己/近接ピッチ組を作る。入力はcallerが選択したXYZ格子で、生成や密度を切り替えず、結果もQt/保存/出力へ自動接続しない。非局所の三角形接触候補を返し、局所隣接面/role継ぎ目/遠いコピー/包含/連続面を未検査として残す。退化・計算上限を不完全として上位へ伝播する。[契約](MESH_CONTACT_SCREENING.md)。

`geometry/mesh_adjacency.py`が共有edgeの幾何関係と3面以上のedge incidenceを担当する。mesh/blade入口の`check_shared_edges=True`が各roleの自己検査だけを拡張する。既定Falseの範囲を維持し、別meshのindexを同一頂点とせず、1頂点だけの接続・role間・vertex link等は未検査として残す。[追加契約](MESH_SHARED_EDGE_CHECKS.md)。

## 共有頂点とvertex linkの追加診断

`geometry/mesh_vertex_adjacency.py`は1頂点共有のcone方向・線分長とlink graphを独立に診断する。mesh/blade入口の`check_shared_vertices=True`はedge検査を前提とし、role内自己検査だけへ適用する。点接続でもfan分断は不完全となる。既定/edge-onlyの結果値を維持し、Qt/OCP/GUI/出力条件へ自動接続しない。[契約・検証](MESH_VERTEX_CHECKS.md)。

## 接線円弧の端部生成

`geometry/tangent_arcs.py`は元PS/SS曲線上で接点を移動し、内向き法線と他方の接線拘束から単一円を構成する。Circular/Tangent Circularは同じ接円核を、Ellipticalは指定軸比の線形変換を介した接円核を使い、Cutoff以外は常に接線接続する。2D designerと3D sectionで核を共有し、3Dでは元側面の(m,theta)補間と壁面微分を使う。接点探索と残存側面の再標本化に同じ写像を使い、JSON構造・CAD公差・角度/厚さ入力を保持する。旧円/楕円の端部座標は利用者指定で変更される。[方式・検証](ROUNDED_EDGE_TANGENCY.md)。

## 子午面の翼列距離表示

`geometry/row_coordinates.py`が所属区間の解析長と入口順から各翼列を整数区間へ換算する。Qt/ファイル形式に依存せず、GUIだけが読取り専用のsを表示する。保存/生成/出力は既存の壁面全体0–1、角度/厚さは各翼LE–TEの0–1を維持する。所属不足や順序不一致を推測で補わない。[契約・操作](MERIDIONAL_ROW_COORDINATES.md)。
