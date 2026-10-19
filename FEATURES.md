# 既存機能一覧

スプリッター形状の部位別配色: 2D・3Dとも主翼と共通のLE＝黄、PS＝水色、TE＝橙、SS＝ピンクを使用。2DではSplitterを破線として主翼の実線と区別し、凡例にも反映する。単翼・全周・全翼列表示に適用し、設計値・生成形状・出力は維持。全1,609一意件成功（通常1,564・実CAD45、失敗/error/skip/漏れ/重複なし、固定309入力不変）。実画面の視認性・DPIは未確認。[配色・検証](docs/SPLITTER_DISPLAY_COLORS.md)。

Impellerのスプリッター付きTurboGrid Profile Points: 主翼とSplitterを公式`##`区切りの同一profileへ出力し、Blade Setsは主翼枚数・Blades Per Setは2。主翼連動/専用分布、CW/CCW、クリアランス付きの各実TipとShroud延長断面へ対応。両翼の所属/丸め/マーカー/Span点数を完成前に検査し、無効時は既存ケースを保護する。主翼のみ16ファイルは修正前hash/生バイト列を維持。新規60件を含む全1,593一意件成功（通常1,548・実CAD45、failure/error/skip/漏れ/重複なし、既存1,533 ID・固定308入力不変）。ANSYS Import/Meshは未検証。[操作・形式・検証](docs/TURBOGRID_SPLITTER.md)。

円・楕円の常時接線接続: 既存`circular`/`elliptical`もPS/SS上の接点を動かすG1接続へ変更。楕円は指定軸比のアフィン変換を介して単一楕円弧を求める。JSONの設定値/原本・camber/角度/厚さ・Cutoffは保持するが、旧半円/半楕円の端部座標再現は終了。新規47件を含む全1,533一意件成功（通常1,488・実CAD45、旧契約試験の更新/再試験込み、最終failure/error/skip/漏れ/重複なし）。参照fixtureの値は保持。[現行仕様・互換性変更](docs/ROUNDED_EDGE_TANGENCY.md)。

子午面の翼列距離表示: 所属壁面の入口順にImpeller 0–1、Diffuser 1–2、RC 2–3等の整数区間へ換算し、線/円弧の始終とLE/TEのHub/Shroud位置をR/Zと併記する。範囲外は赤字、所属不足/分断/順序不一致は未設定。R/Z編集・内部0–1・角度/厚さ横軸・既定値・JSON/出力を維持。新規35件を含む全1,486一意件成功（通常1,442・実CAD44、失敗/error/skip/漏れ/重複なし、既存1,451 ID・固定297入力不変）。[契約・操作・検証](docs/MERIDIONAL_ROW_COORDINATES.md)。

LE/TEの単一接線円弧（初期導入時の記録。現行の円/楕円は上記の常時接線接続）: Typeに`Tangent arc (G1)`を追加。PS/SS上の接点を端部近傍で移動し、両側に接する単一円弧を生成。2円弧へ退避せず、不成立は明示エラー。元の角度/厚さ分布とcamber、旧半円・楕円・Cutoff・既定JSONを保持。選択・Undo/Redo・保存/読込と、実CADの単一閉solid/STEP再読込を確認。全1,451一意件成功（通常1,407・実CAD44、失敗/error/skip/漏れ/重複なし、既存1,381 ID・固定294入力不変）。[操作・一般手順・検証](docs/ROUNDED_EDGE_TANGENCY.md)。

共有vertexの局所診断（Stage 3B-2b）: 明示モード`check_shared_edges=True, check_shared_vertices=True`で1頂点だけの接続と重なり候補を区別し、vertex linkの分断・分岐・重複や未判定を不完全として記録。既定/edge-onlyの既存値、形状/GUI/保存/出力は維持。新規31件を含む関連117件成功。全1,381一意件成功（通常1,338・実CAD43、失敗/error/skip/漏れ/重複なし、既存1,350 ID・固定290入力不変）。[契約・全回帰](docs/MESH_VERTEX_CHECKS.md)。

共有edgeの局所診断（Stage 3B-2a）: 明示モード`check_shared_edges=True`で正常なedge接続と同じ側へ折り返す重なり候補を区別し、短edge/高さは未判定、3面以上のedgeは不完全として記録。既定Falseの検査範囲・既存結果フィールド、形状/GUI/保存/出力は維持。新規32件を含む関連86件、全1,350一意件成功（通常1,307・実CAD43、失敗/error/skip/漏れ/重複なし、既存1,318 ID・固定288入力不変）。1頂点だけの接続・role継ぎ目・連続面/solidは残る。[契約・検証](docs/MESH_SHARED_EDGE_CHECKS.md)。

3D接触候補検査（Stage 3B-1）: 明示XYZ格子を三角形化し、BVH/SATで非局所自己接触・最近接周期翼・Main/Splitterの候補を調べるAPIを追加。同一平面接触にも対応し、退化/打切り/局所隣接面等の未検査範囲を明示する。連続曲面・包含・全周の保証や出力ゲートではなく、既存形状・GUI・保存・出力条件は維持。新規54件を含む関連129件、全1,318一意件成功（通常1,275・実CAD43、失敗/error/skip/漏れ/重複なし、既存1,264 ID・固定286入力不変）。[範囲・検証](docs/MESH_CONTACT_SCREENING.md)。

同一対応基準翼面の法線角包絡: 共通Bézier区間で微分外積どうしの内積/外積をBernstein積に展開し、向き付き角度の数値上限を計算するAPIを追加。J下限を確保できない区間はNone、正の内積を確保できない正則区間は保守的に180度とし、標本最大を全面保証に置き換えない。既存生成・GUI・保存・出力条件や公差は維持。関連80件、全1,264一意件成功（通常1,221・実CAD43、失敗/error/skip/漏れ/重複なし、既存1,238 ID・固定282入力不変）。現既定の実測は[契約・検証](docs/SURFACE_NORMAL_ENVELOPE.md)を参照。

基準翼面のJacobian区間包絡: Bézier微分外積の係数から全区間のJ下限/上限を計算し、標本間の折返しを未判定として残す数値APIを追加。局所正則と内部交差を区別し、float丸めや最終CADの成立を保証しない。既存生成・GUI・保存・出力条件は維持。新規25件を含む全1,238一意件成功（通常1,196・実CAD42、失敗/error/skip/漏れ/重複なし、既存1,213 ID・固定279入力不変）。[契約・実測](docs/SURFACE_REGULARITY_ENVELOPE.md)。

基準翼面の位置差包絡: 共通knotへの挿入とcontrol net差により、同一Span/xiで対応するspline面全域のモデル上の位置差を評価。標本間の膨らみと現既定SS/Hub始端の見逃しを確認した。float丸めは未証明と明示し、既存生成・GUI・CAD・保存/出力条件は維持。新規29件、関連82件成功。全1,213一意件成功（通常1,172・実CAD41、失敗/error/skip/漏れ/重複なし、既存1,184 ID・固定276入力不変）。[契約・限界](docs/SURFACE_DISTANCE_ENVELOPE.md)。

開発用RTK: project内にchecksum固定のRTK OSSを配置し、読取りGit履歴と保存済みpytestログの任意圧縮helperを追加。失敗/error/skip/不完全結果は圧縮せず、元の終了コードとraw logを保持。全体hook/設定やアプリvenvは変更しない。短いpytestは既存briefを優先。関連23件成功、全1,184一意件成功（通常1,144・実CAD40、失敗/error/skip/漏れ/重複なし、既存1,161 ID・固定273入力不変）。[実測・操作](docs/DEVELOPMENT_TOOLS.md)。

開発用Skill: project内に`blade-designer-checks`を追加。関連資料だけの読込み、短時間/関連/全回帰、要約とraw log、限定Ruff、project限定Gitの使い分けを記載。skill-creator形式検証と相対参照を確認。新セッションでの自動選択は未確認。[手順](docs/DEVELOPMENT_TOOLS.md)。

開発用Ruff: 独立venvへ固定導入し、未定義名等の限定ルールを読取り検査。既存指摘0件、正常/未定義/構文エラーの終了コードを実確認。VS Codeへ短時間試験とRuffタスクを追加。アプリ用venv・計算・全体整形は変更しない。[手順](docs/DEVELOPMENT_TOOLS.md)。

開発検査の短時間対象/要約: 既存pytestランナーへ`--suite quick/full`と`--brief`を追加。完全ログ/JUnit・終了コード・失敗/collection error/skipの区別を保持し、短時間検査は全回帰の代用にしない。形状・GUI・保存値は変更しない。[開発補助](docs/DEVELOPMENT_TOOLS.md)。

曲面の局所品質診断: tensor splineの解析微分からJacobianの大きさ・向き付き法線を評価する読取り専用APIを追加。退化標本の法線は未定義とし、同一対応点の距離/法線角と比較可能点数を返す。既存生成・GUI・CAD・出力・保存値は維持し、全面保証や干渉PASSには使わない。新規29件を含む全1,161一意件成功（通常1,121・実CAD40、failure/error/skip/漏れ/重複なし）。既存1,132 IDと固定258入力不変。[契約・実既定の標本比較](docs/SURFACE_DIFFERENTIAL_DIAGNOSTICS.md)。

CAD参照の採用格子対応: `View → CAD Surface Reference`に実CADのrole別格子を使うモードを追加。同一snapshot・成功した翼面/単一閉鎖BREP・Main/Splitter別の完全な格子記録を照合し、LE/PS/TE/SSごとに再構成する。不足・失敗・異なる設計では参照を隠し、固定格子へ自動退避しない。従来の固定モード・生成・保存・出力条件は維持。新規31件を含む全1,132一意件成功（通常1,092・実CAD40、failure/error/skip/漏れ/重複なし）。既存1,101 ID・固定256入力不変。[操作・検証](docs/CAD_ADOPTED_SURFACES.md)。

品質改善Stage 3A-2cの参照表示部分完了: `View → CAD Surface Reference`を追加。CADと共通の端部接線・tensor splineによるImpeller主翼/Splitterの翼面を、固定格子33〜513・Full Annulusで読取り専用表示する。通常3D・設計値・保存形式を維持し、設計変更時は参照結果を失効する。新規22件を含む全1,101一意件成功（通常1,062・実CAD39、failure/error/skip/漏れ/重複なし）。既存1,079 ID・固定253入力不変、変更前と40曲面の接線・係数・評価点が一致。実CADの自動採用密度・cap/fillet/STEP・全面品質は別契約。静翼/RC・派生カットは拒否する。[操作・検証](docs/CAD_SURFACE_REFERENCE.md)。

品質改善Stage 3A-2b完了: 派生曲線へ元の翼集合・role・Span/index・補間比を内部metadataとして保持し、共通の円筒補間面から外径交点や表示再サンプル点を再構成可能にした。新しい加工TEは元TEと区別して再構成を拒否する。生成形状・保存形式・出力ガードは維持。新規30件を含む全1,079一意件成功（通常1,042・実CAD37、failure/error/skip/漏れ/重複なし）。既存1,049 ID・固定248入力不変。変更前と12条件648曲線の座標・従来metadataが一致。表示/CAD全面の単一正本適用は未完了。[派生元面の参照契約](docs/DERIVED_SOURCE_CONTRACT.md)。

品質改善Stage 3A-2a完了: 実表示indexからmaster/CAD xiへの写像、派生source_spanの由来、現行trimの共通index面、実wireframeと参照splineの標本比較を読取り専用APIとして追加。表示・生成・CAD・出力の既存経路は変更しない。新規21件を含む全1,049一意件成功（通常1,012・実CAD37、failure/error/skip/漏れ/重複なし）。既存1,028 ID・固定246入力不変。正本の全面適用、物理的対応、全面偏差保証は未完了。[実対応座標](docs/SURFACE_CORRESPONDENCE.md)。

品質改善Stage 3A-1完了: 非Qt／非OCPの翼面評価器を追加し、従来CADのtensor spline構築と派生カットのSpan列補間を共通数値層へ移した。XYZ／円筒座標の区分線形面とCAD splineの対応点差を測定可能にしたが、表示／カット／CADの方式は変更しない。新規26件を含む全1,028一意件成功（通常991・実CAD37、failure/error/skip/漏れ/重複なし）。既存1,002 ID・固定244入力不変。変更前と40曲面の全pole／knot／degree、30カット曲線が一致。共通正本の適用・全面誤差保証・3D干渉検査は未完了。native／ANSYS未検証。[翼面評価の契約](docs/SURFACE_EVALUATION_CONTRACT.md)。

品質改善Stage 2B-2完了: row一覧のあるJSONを、保存値の整合性と宣言翼種の実3D成立性に分けて検証。未使用の旧半径の順序・参考Impellerの幾何成立性への依存を除き、全宣言rowとroot編集snapshotは検証する。row一覧なしの旧JSON／移行／旧2D APIは従来契約を維持。GUI Load／Saveも対応し、旧2D不成立のprojectを読んだ最適化画面では以前のbaselineを解除する。新規46件を含む全1,002一意件成功（通常967・実CAD35、failure/error/skip/漏れ/重複なし）。既存956 ID・固定241入力不変。原本・既定・生成式・JSON項目・数値期待値は変更なし。native／ANSYSは未検証。[保存検証の契約](docs/ROW_PROJECT_VALIDATION.md)。

品質改善Stage 2B-1完了: 3D生成の検証を翼種別に分離。未使用の旧2D半径・別翼種のLE/TEの幾何成立性や分布が、有効な選択3Dを止めないようにした。両翼種のLE/TE端点の有限性・0〜1範囲、ImpellerのRake／trim／clearance／Splitterと選択対象の幾何検査は維持。旧2D APIとJSONの全体検証・保存時の既存ファイル保護を保持し、値の置換は行わない。修正後の関連93件成功、新規50件を含む最終全回帰956一意件成功（通常921件・実CAD35件、failure/error/skip/漏れ/重複なし）。固定239入力、原本・既定JSON・数値fixture不変。native／ANSYS未検証。JSON受入れ自体の分離はStage 2B-2に残す。詳細は[翼種別検証](docs/ROW_VALIDATION_CONTRACT.md)。


2026-10-17 品質改善Stage 2A: `View → Selected Row Metrics`で中央表示と同じ実断面のXYZ弦長・翼線長・空間曲率を測定し、Main/Splitter・Spanを選択可能にした。`File → Export → Selected Row XYZ CSV`へ同じmaster点・単位mm/Z軸・row ID・snapshot・有効桁数を含む新CSVを追加。既存Metrics／Curvature／XY CSV／最適化はlegacy radial 2Dと明示して互換維持。旧2D計算や参考Impellerの計算エラーは有効な静翼表示から分離し、旧結果をcurrentとして扱わない。新規34件を含む最終全回帰906一意件成功（通常871件・実CAD35件、failure/error/skip/実行漏れ/重複なし）。固定237入力、原本と既定JSONの不変を確認。native操作・高DPI・ANSYSは未検証。点編集のcurrent cellと選択範囲が独立に変わる場合の端点削除ボタン保護も補強。共通入力検証／Load・Saveのlegacy依存の分離はStage 2Bとして残す。設計値・JSON・TurboGrid・既存数値fixtureは変更しない。[形状正本と測定の契約](docs/GEOMETRY_SOURCE_CONTRACT.md)。

2026-10-17 品質改善Stage 1C: `File → Export → Export Readiness`へ選択翼列の読取り専用診断を追加。Profile Points／Mechanical STEP／TurboGrid CADを分け、入力段階の制限・所属・ディスク・backend実行ファイルの有無を表示。CAD kernel、指定Rのフィレット、全面3D干渉、ANSYS Import/Meshは未実施として区別する。設計・Undo・Camera・原本・出力を変更せず、編集後は古い診断を失効させる。新規12件、関連19件成功。最終全回帰872一意件成功（通常268/262/307件、実CAD35件）、failure/error/skip/実行漏れ/重複なし。固定229入力・原本／既定JSON不変。native操作・対象形状の根元fillet成立・ANSYS Import/Meshは未検証／未解決。[出力品質の記録](docs/EXPORT_QUALITY_IMPROVEMENTS.md)。

2026-10-17 品質改善Stage 1B: TurboGrid／CADケースを別領域で完成・検証してからディレクトリを切替。既存ケースをバックアップへ保持し、中断復旧・OSロック・容量不足・hash不一致・metadata失敗を検査。2回のrename間は保存先名が一時不在となるため、単一の原子的切替や実停電耐久性は保証しない。全860一意件成功（実CAD35件を含む）、skipなし、従来16出力のraw bytes不変。出力用の専用フォルダを指定し、保持バックアップは内容確認後に整理する。[詳細・制約](docs/EXPORT_QUALITY_IMPROVEMENTS.md)。
確認日: 2026-10-17。対象: Centrifugal Compressor Blade Designer v0.3と任意CAD機能v0.4。

2026-10-17 品質改善Stage 1A: 通常Impellerも含め、TurboGrid Profile Pointsの丸め後の閉鎖・連続点重複・LE/TEマーカー・Span間点数を出力前に検査するよう修正。無効なら既存出力を変更せず、新規出力先も作成しない。点削除・桁数自動変更・形状変更は行わない。新規64件を含む全回帰832一意件成功（通常259/247/291件、実CAD35件）、実行漏れ・失敗・error・skipなし。歴史的ASCIIハッシュと原本JSONは保持。ANSYS Import/Mesh・native操作は未検証。[出力品質の記録](docs/EXPORT_QUALITY_IMPROVEMENTS.md)を参照。

2026-10-17 根元フィレットの受入れ条件更新: 利用者指示に基づき、R8を必須とせず対象形状に成立する指定Rで生成・STEP再読込み・半径確認を行う方針へ変更。同じ現既定＋仮ディスクをR2／R1／R0.5 mmで実OCCT処理したが、3件とも主翼の根元で`ChFi3d_Builder:only 2 faces`となり、小径成功は未確認。原本・既定R・数値計算・公差・既存出力は変更せず、位相修復後も小さいRでの確認を認める。[品質レビューの小径試行](docs/GEOMETRY_QUALITY_REVIEW.md)と[改善計画](docs/DEVELOPMENT_ROADMAP.md)に記録した。全回帰の再実行・ANSYS検証はこの追記では行っていない。

2026-10-17 実装・品質監査: 直前の検証済みRC修正15ファイルを`6b8d3be`へ記録し、設計アルゴリズム・入力・既存出力を変更せずレビュー資料を追加。[現行機能](docs/CURRENT_FUNCTION_AUDIT.md)、[幾何・CAD品質](docs/GEOMETRY_QUALITY_REVIEW.md)、[改善順序](docs/DEVELOPMENT_ROADMAP.md)を参照。固定済み全回帰768件の記録・221入力hashを照合、追加の既存試験81件成功。通常Impellerの丸め後重複点、周期干渉の出力前検査不足、途中I/O失敗時のcase部分更新を再現。現既定＋仮ディスクの実OCCT R8はFAILで、根元候補10本中7本が4面共有することを別診断で確認。既存fixture R8成功・Blade Only成功・実モデルR8失敗・ANSYS未検証を区別。今回これらの問題のアルゴリズム修正は実施していない。利用者の指示に基づき今後の機能修正は検証後commitまで行い、pushは別指示とする。

2026-10-17 RC表示と既定形状: 指定`blade_v03.json`を既定JSONへ同一内容でコピーし、Impeller／Diffuser／RCの3翼列・RC選択を起動／Newへ反映。元ファイルは保持。静翼の中央2Dが旧R=100→160 mm、3Dが子午面RCのR=130→90 mmを使っていた不一致を修正し、正常時の単翼・全周とも実3DのHub masterをXY投影します。内向き流れの生成式・LE/TE／β・JSON・旧2D API／Metrics／CSV・TurboGridを保持。新規解析12件成功、修正後の新規GUI3件成功（44.96秒、20261017T063211Z-56294681）。折り返し部の遠方交点を別翼列の断面と誤認しないよう実Hub距離で範囲を限定し、補正後の関連69件成功。新規19件を含む最終全回帰768件成功（非CAD256／273／204件、CAD35件）。改行正規化後の照合1件を再確認し、769実行・768一意の収集ID一致、実行漏れ・失敗・error・skipなし。製品コードと既定値は最終回帰開始時から不変、照合テスト1件の改行対応は再実行済み。最終221入力のハッシュと原本／既定JSONの一致も確認。実画面・実機Importは未確認、stage・commit・pushは未実施。定義・互換経路・変更ファイルは[RC表示](docs/RETURN_CHANNEL_DISPLAY.md)を参照。

2026-10-17 Impeller派生カット: `LE / TE → 派生設計 / Shroud・外径カット`に、元平均線の基準Gross断面の一定面積削減率と、指定外径／元Hub TE径からの切削率を追加。元のLine/Arc・LE/TE・角度・厚さを変更せず、主翼・Splitterの元離散翼面から切り出します。派生casingとTip、絶対クリアランスを扱い、中央2D/3D・全周・流路解析・元設計グラフ・翼列別設定・Undo/JSONへ接続。派生TurboGrid/CAD出力は未対応で、書込み前に拒否。新規36件成功（77.44秒、20261017T025609Z-ab303068）。最終全回帰749件成功（非CAD276／262／176件、CAD35件、収集ID照合で実行漏れ・重複・失敗・error・skipなし）。固定した217ソースのハッシュと既定JSONの不変も確認。解析面積、元頂点／分布保持、円筒切断、組合せ、無効形状、既存出力保護を確認。offscreen画像で設定・子午面を確認。実画面・CFD／実機性能は未確認です。詳細は[派生カットの定義・制約](docs/IMPELLER_TRIM_SPEC.md)。stage・commit・pushは未実施。

2026-10-17 Aboutメニューと専用Splitter補間: 画面内の大きなヘッダーを除き、About → About Blade Designerへ移動。専用スプリッターの角度・厚さは可視LE〜TEの点だけで主翼と同じPCHIP補間を行い、2点なら直線です。非表示点による区間内の傾きと、下流編集によるLE値の移動を除去。既存の専用分布・コピー直後にも新補間を適用するため形状が変わる場合があります。連動モード・主翼・静翼・既定値・保存形式を維持。関連67件成功（99.87秒、20261017T012147Z-065d842d）。新規10件を含む最終全回帰713件成功（非CAD194／281／203件とCAD35件、収集ID照合で実行漏れ・失敗・error・skipなし）。210ソースのハッシュ一致、Qt offscreenの画面と2点の直線を確認。実画面未確認。詳細は[About](docs/ABOUT.md)と[専用補間](docs/SPLITTER_INTERPOLATION.md)。stage・commit・pushは未実施。

2026-10-17 クリアランス付きTurboGrid Profile Points: 実Tipを保持し、最後の2つのSpanからShroudまで延長した断面をprofileファイルの最後へ追加します。実Tipは`Tip_clearance`、延長は`Shroud_extension`と明示し、出力完了時とBladeGen.infコメントに実TipのProfile Numberを案内します。設計・表示・保存・ゼロ隙間／静翼出力を維持。到達不能・縮退・自己交差・不完全な所属・丸め縮退を出力先作成前に拒否します。新規23件を含む関連83件成功。最終全回帰703件成功（非CAD235／228／205件、CAD35件。収集ID照合で実行漏れ・失敗・error・skipなし）、固定した207 Pythonソースの一致も確認。既定モデルコピーで実Tip輪郭と解析Shroudへの到達を確認、実機Import／Meshは未確認。TurboGrid CAD・Splitter付きの制限は継続。詳細・試行記録は[クリアランス付きTurboGrid](docs/TURBOGRID_CLEARANCE.md)。stage・commit・pushは未実施です。

2026-10-17 主翼・スプリッターの共有グラフ／表示時Fit: Blade Angle／Thicknessで両方の分布を比較し、主翼／スプリッターのタブで編集対象を選びます。円／三角の操作点と線種・色を区別し、LE〜TE限定編集・連動／専用・Undo／JSONを維持。Splitterタブから共有編集へ移動できます。2Dはタブ／解析ウィンドウを開いた後に全体表示し、対象・表示種類切替にも対応。3Dも表示時は方向を保って全体表示。編集中のズームと数値計算・既定値・保存／出力を維持。関連36件、新規15件を含む最終全回帰680件が成功（非CAD207／225／213件の分割再実行とCAD35件、収集ID照合で実行漏れ・失敗・error・skipなし）。初回の3失敗は表示時Fitの旧期待値を更新し、点のない場所のドラッグで空配列判定が例外になる不具合を修正しました。実画面未確認。操作・画像・試行記録・確認範囲は[共有グラフ](docs/SHARED_GRAPHS.md)。stage・commit・pushは未実施です。

2026-10-17 スプリッターのLE–TE専用編集: 横軸の主翼LE=0・TE=1を保ち、角度／厚さの表とドラッグ点を各SpanのスプリッターLE〜TEだけにしました。LE値を編集でき、開始位置・追加／削除・Undo／JSONへ追従します。補間用の上流データは内部保持し、コピー・読込直後の形状と旧形式を維持。生成本体・主翼・静翼は変更しません。新規12件・関連48件成功。最終コードの全回帰630件（944.67秒、20261016T215230Z-a08eb145）とCAD35件（655.74秒、20261016T215233Z-70495b50）が成功し、全665収集IDの実行漏れ・失敗・error・skipは0件です。既定モデルのoffscreen画像で表示範囲とコピー前後の形状一致を確認、実画面未確認。詳細・試行記録は[スプリッター編集範囲](docs/SPLITTER_EDIT_RANGE.md)。stage・commit・pushは未実施です。

2026-10-17 子午面の区間座標表示: Hub／Shroudの区間行を選ぶと、円弧の中心・始点・終点のR/Z [mm]を読み取り専用で表示します。直線の中心は「—」。既存の解析的な形状結果を使い、行選択で設計・履歴を変更せず、入力確定・上流編集・種類・追加／削除／移動・Undo／JSONへ追従します。数値計算・既定値・保存／出力形式と以前の未コミット変更を保持します。新規6件成功（6.88秒、20261016T212134Z-dfa7382e）、関連60件成功（125.19秒、20261016T211943Z-2e07a2c6）。最終コードの全回帰618件（936.83秒、20261016T212202Z-4fc772b0）とCAD35件（656.47秒、20261016T212203Z-e860eca2）が成功し、全653収集IDに対する実行漏れ・失敗・error・skipは0件です。既定モデルのoffscreen画像でHub／Shroudを確認、実画面未確認。詳細は[子午面座標表示](docs/MERIDIONAL_COORDINATES.md)。stage・commit・pushは未実施です。

2026-10-16 オープンインペラの翼端クリアランス: LE / TEでLE・TE隙間[mm]を指定し、固定Shroud（ケーシング）からHub側法線へTipを生成します。ケーシング弧長で線形補間し、一定外径CutoffとSplitterへ反映。独立翼列・Undo・JSON 0.4、子午面と3DのTip／Casing表示、実翼高さでの閉塞・スロートと翼端開口面積を追加しました。未指定・ゼロの従来経路と出力を維持します。正の隙間のTurboGridは書込み前に拒否。実CADは一定隙間厚翼／可変隙間薄翼2例成功、厚翼の可変隙間例は自己交差で拒否され未解決です。関連56件成功。全回帰612件（973.03秒、20261016T124857Z-a4ed18b5）・CAD35件（681.31秒、20261016T124857Z-3371f22b）・同名翼列表示修正後GUI3件（26.45秒、20261016T125532Z-8f3e430e）の650実行から重複を除く全647収集IDを照合し、実行漏れ・失敗・error・skipは0件です。既定モデルのoffscreen表示と335面積断面・エラー0を確認。実画面・ANSYS・別PCは未確認。詳細・試行記録・未確認項目は[翼端クリアランス](docs/TIP_CLEARANCE.md)。stage・commit・pushは未実施です。

2026-10-16 流路面積・スロート追加: View → Passage Area / Throatで選択翼列の実3D masterから子午面直交総面積、翼厚差引きNet、Main–Main、Main–Splitter、Splitter–Mainを表示します。主翼間はSplitter付きで参考値、両側の面積は全SpanにSplitterが存在するときのみ表示。円筒／円錐の展開幅、曲線壁の3D弦下限推定、Hub–Tip幅積分の近似面積を区別します。開始時コピーの非同期処理、編集・選択時の結果消去、遅延結果破棄、無効入力後の同一翼列再選択時の再検証を追加。既存の計算・既定値・保存／出力・CADと前回の未コミット作業を保持します。最終検証は全収集626件に対し実行漏れ・失敗・error・skipは0件。全回帰591件（1130.31秒、20261016T115031Z-377c1b3f）、CAD33件（736.14秒、20261016T115032Z-5beb9224）、境界補正後の関連33件（72.59秒、20261016T115927Z-cd35acc7）、最終コードの全GUI254件（892.54秒、20261016T120447Z-0f429c89）と再選択保護のGUI3件（8.23秒、20261016T121043Z-e376e285）をJUnit／収集IDで照合しました。重複を含む914実行で、一意の626件です。既定モデルのコピーにSplitterを加えたoffscreen画面では335断面・エラー0を確認。実画面／CFD照合は未確認、stage・commit・pushは未実施。操作・定義・制限と試行記録は[流路解析](docs/PASSAGE_ANALYSIS.md)を参照してください。

2026-10-16 根元R・仮ディスク追加: CAD / Filletの根元半径を「根元フィレットR」と明記し、Enter/フォーカス確定・再生成・Undo・JSON保存へ接続します。「仮ディスクを作成・表示」で構造CAD用の仮寸法を作成し、元の翼ワイヤーフレームとディスク単体の実CADを表示します。既定モデルは内径20 mm、外径約251.86 mm、裏面Z=75 mmです。PROVISIONALを画面・保存・レポートへ明示し、手動寸法とTurboGrid所属を保護します。任意R2.5の実CAD/STEPと可変Rの出力手順、仮ディスクの解析体積と再読込を検証。現在の既定翼とのR8結合は4面共有エッジの位相制約で未成立で、単体ディスクにフィレット成功と表示しません。

最終回帰は574 passed / 1062.67秒（20261016T095006Z-c81ecb14）、CAD33 passed / 747.63秒（20261016T095020Z-95c3b48b）、出力手順等の追加10 passed / 163.66秒（20261016T095409Z-534becc3）。重複を除く全608収集IDとJUnitを照合し、実行漏れ・失敗・error・skipは0件です（artifacts/provisional-disk-review/final-test-coverage.json）。単一実行の件数ではありません。実画面/F5/ANSYS実機は未確認、stage・commit・pushは未実施。詳細は[仮ディスク追加報告](docs/PROVISIONAL_DISK_REPORT.md)。以下は前回CAD実装の検証記録です。

2026-10-16 CAD / Fillet追加（`codex/cad-export-v04`）: 別環境Open CASCADE / cadquery-ocp 8.0.1.1.0でmaster座標からB-spline・閉solid・明示裏面のHub・真の根元R8を生成し、自己交差・干渉・STEP再読込を検証します。CADタブ、QProcess、開始時snapshot/hash、Undo/JSON 0.4、実BREPプレビューとカメラ保持を追加。CAD未使用の既定JSON schema 0.3、既存geometry/CSV/TurboGrid Profile Pointsと数値参照は維持します。実機ディスク寸法は未指定で推定せず、Blade OnlyはNO_FILLETです。TurboGrid CADは別の流体領域STEP中間成果物でCONVERSION_REQUIRED、Parasolid変換とANSYS実機Import/Meshは未実施です。

最終回帰は既存558 passed（`artifacts/test-runs/20261015T230934Z-42da3606`、972.19秒）、CAD/GUI31 passed（`20261015T231329Z-3ca0ca45`、533.72秒）、STEP誤差予算/R1の5 passed（`20261015T231415Z-8435ef7a`）です。R1の重複1件を除く全593個別IDを収集一覧とJUnitで照合し、実行漏れ・失敗・error・skipは0件でした（`artifacts/cad-review/final-test-coverage.json`）。単一実行の件数ではありません。途中の保存済みJSONのbbox比較は13 passed / 1 failedで、元BREPの実edge toleranceに整合する比較へ修正後、再検証は成功しました。設計公差0.01 mm・体積比較式・既存数値参照は維持します。編集前の全回帰558件と各関連試験の記録も実装報告へ残しています。

main.pyの既定JSON起動経路からQt offscreenのQProcessでBlade Only STEPを生成・再読込・表示し、カメラ保持も確認しました。Blade OnlyはNO_FILLETで干渉はNOT_TESTEDです。詳細な変更一覧・測定・未検証項目は[CAD実装報告](docs/CAD_IMPLEMENTATION_REPORT.md)、操作とANSYS手順は[CAD操作手順](docs/CAD_EXPORT.md)を参照してください。実画面/F5/DPI/ANSYS/別PC/CAD環境のPython 3.11は未確認。stage・commit・pushは未実施です。
2026-10-15 スプリッター（主翼連動/専用分布）: インペラのSplitterタブで追加・解除し、Hub/Tip開始位置・ピッチ割合・厚さ倍率を編集します。主翼は不変、元のβ/厚さ分布を開始位置から切出し、端部・TE Rake・一定外径Cutoffを継承。2D/3D/全周/全翼列3D・独立翼列保存・Undo/Redoへ接続しました。連動機能追加時の関連63件成功（artifacts/test-runs/20261015T124700Z-3531e1f1）。独立編集追加時は34 passed / 1 failed（20261015T125300Z-c78391ed）で、専用分布の入力途中の確定を検出しました。新規入力欄をEnter/フォーカス移動で確定する修正後、関連90件成功（20261015T125435Z-42ee36a7）。最初の全回帰（20261015T125741Z-a3bf25f2）は既存test_guiの4タブ固定期待を検出して中断。個別再現（20261015T130314Z-ce5ba2f2）は1 failed、Splitter追加後の5タブへ期待を更新後1 passed（20261015T130421Z-404154b8）。数値参照は変更せず、更新後のWindows .venv / Python 3.12.14の全回帰は558 passed / 0 failure / 0 error / 0 skipped、695.44秒（artifacts/test-runs/20261015T130432Z-f12017b4）。最終回帰の実装失敗・環境エラーはありません。画面画像artifacts/splitter-review/linked.png・independent.pngで配置と緑色のスプリッター表示を確認（画像取得プロセスのみMeiryoを使用）。既存の未コミットTE Rake変更・ユーザー原本・既定値・数値参照を保持します。初期は主翼連動で、主翼からコピー後は専用β・厚さを編集可能（コピー時の形状不変、再コピー/連動復帰とUndoへ対応）。複数種類・スプリッター付きTurboGridは未対応。出力は主翼だけを誤出力しないよう書込み前に拒否します。実画面操作・3D翼間干渉・実機検証は未確認、stage/commit/pushは未実施です。
今回の変更箇所: models/parameters.py・geometry_3d.py・validation.py（設定/断面保持/検証）、geometry/splitter.py・blade_section.py・geometry_3d.py（開始位置・分布・TE整合）、gui/splitter_editor.py・main_window.py・plot_widgets.py・preview_3d.py（編集/履歴/表示）、fileio/project_io.py・turbogrid_export.py（保存/不完全出力防止）、tests/test_splitter.py・test_splitter_gui.py・test_gui.py・test_target_layout_gui.py（数値/GUI/タブ検証）、README.md・docs/ARCHITECTURE.md・本一覧（仕様と確認範囲）。
2026-10-15 インペラTE Rake目標: β・子午面・TE半径を維持し、ImpellerParameterMapperでTE周方向目標から各Spanを配置します。Hub固定、LE周方向位置は結果となります。角度はHub/Tip TEキャンバー端点の3D弦と中点子午面との符号付き角（+θ=正）、Noneは従来形状、0はRakeゼロ指定。数値/出力関連57件成功（artifacts/test-runs/20261015T113043Z-cfc8b622）、保存/入力検証等50件成功（20261015T112919Z-17b7b9bc）、GUI等28件成功（20261015T113221Z-11fb9174）、精度保持調整後GUI 5件成功（20261015T113405Z-d6c71e7f）。Windows .venv / Python 3.12.14の全回帰529 passed / 0 failure / 0 error / 0 skipped、777.47秒（artifacts/test-runs/20261015T113652Z-905871c7）。実装失敗・環境エラーはありません。画面画像artifacts/te-rake-review/rake25.pngで25°目標・実測25°と入力配置を確認（画像取得プロセスのみMeiryoを読み込み）。ユーザー原本・既定値・歴史的数値参照は変更せず、stage/commit/pushは未実施。実画面操作、実機TurboGrid、面全体の3D干渉/応力/CFDは未確認です。
2026-10-14 ツールバーのメニューバー統合: ツールバーを削除し、EditへCCW/CW回転方向・反転、ViewへXY/XZ/YZ投影面を追加しました。既存のFile/Edit/View/Toolsの操作・ショートカットを維持し、チェック状態をUndo・読み込み・翼列切替へ同期します。関連26件成功（artifacts/test-runs/20261014T102958Z-dbd08540）。Windows .venv / Python 3.12.14の全回帰506 passed / 0 failure / 0 error / 0 skipped、465.79秒（20261014T103145Z-4ff1bdb4）。実装失敗・環境エラーはありません。画面画像artifacts/menubar-only-review/top.pngで1段のメニューバーとツールバー非表示を確認（画像取得プロセスのみMeiryoを読み込み）。前回の未コミット修正を保持し、数値計算・ファイル形式は変更しません。実画面操作は未確認、stage/commit/pushは未実施です。
2026-10-13 上部メニュー整理: File/Edit/View/Toolsへ統一し、ExportをFile内、最適化モードをTools内へ移動。ツールバーのProject/Edit/View/Exportの重複ドロップダウンを直接操作へ置き換え、共有QActionでショートカットと既存callbackを維持します。初回関連試験は30 passed / 1 failed（artifacts/test-runs/20261013T140121Z-f30eaaf6）。新規テストの記録callbackがQt triggered(bool)を操作名として受け取ったため、boolを受けるテスト側の署名を修正しました。既存機能の期待値や数値参照は変更せず、修正後の関連31件成功（20261013T140324Z-ecf822ef）。Windows .venv / Python 3.12.14の全回帰504 passed / 0 failure / 0 error / 0 skipped、873.41秒（20261013T140325Z-1e471854）。環境エラーはありません。画面画像はartifacts/menu-reviewに保存し、File/Edit/View/Toolsと直接操作ツールバーを確認しました。画像取得プロセスのみMeiryoを読み込み、製品のフォント設定は変更していません。前回のトラックボール修正を保持し、設計計算・出力形式は変更しません。実画面操作は未確認、stage/commit/pushは未実施です。
2026-10-13 3Dトラックボール/視点ボタン: Preview3Dの上下±89度制限を自由回転行列へ置き換え、中央/別ウィンドウに正面・上面・側面・等角・全体・リセットを追加。平行移動/ズーム・旧角度API・編集/Undo/翼列切替時のカメラ保持を維持。新規操作テスト9件成功（artifacts/test-runs/20261013T132634Z-30b80264）、既存関連23件成功（20261013T132504Z-4ab1b985）。Windows .venv / Python 3.12.14の全回帰499 passed / 0 failure / 0 error / 0 skipped、809.37秒（artifacts/test-runs/20261013T132717Z-426f8570）。実装失敗・環境エラーはありません。設計座標・数値参照・JSON/CSV/TurboGridは変更せず、実画面操作・今回変更後のPython 3.11再検証は未確認、stage/commit/pushは未実施です。確認画像はartifacts/trackball-reviewに保存（画像取得プロセスだけMeiryoを読み込み、アプリのフォント設定は変更しません）。
2026-10-13 Diffuser/RC TurboGrid出力: 選択静翼の独立snapshotと共有子午面からHub/Tipの2断面・所属Hub/Shroud・BladeGen.infを出力します。中間Span・JSON schema・Diffuser CSV・3D生成本体は変更しません。子午面選択は出力を拒否し、無効な現在値や丸め縮退では既存ケースを保護します。出力/所属関連46件成功（artifacts/test-runs/20261013T114027Z-980016ca）、GUI/関連形状58件成功（20261013T114153Z-5dfc7c61）。Windows .venv / Python 3.12.14の全回帰490 passed / 0 failure / 0 error / 0 skipped、489.85秒（20261013T114334Z-9664fb0c）。Impeller互換基準は変更前3ケース/12ファイルのLF正規化ASCIIハッシュで、すべて一致しました。解析的円錐座標、Diffuser/RC独立設定、軸/単位、所属壁面、JSON、保留編集、表示との対応、Full Annulusによる出力不変、前回の有効表示の誤出力防止も確認。実装失敗・環境エラーはありません。実画面操作とTurboGrid実機Importは未確認、stage/commit/pushは未実施です。Python 3.11の今回変更後の再検証は行っていません。
2026-10-12 Python 3.11互換確認: Windows Python 3.11.9の独立環境へrequirements.txtから新規インストール成功、pip check成功。tools/run_tests.pyで457 passed / 0 failure / 0 error / 0 skipped（920.82秒）。通常設計・最適化のQt offscreen起動・形状計算は両方Ready。記録: artifacts/test-runs/20261012T113836Z-e2f25019/pytest.xml・result.json、artifacts/python311-compat/startup.json。再現用requirements-windows-py311.lock.txtとREADME・docs/DEVELOPMENT.mdを追加・更新。既存3.12環境・アプリ本体・数値fixture・ユーザー原本は変更せず、stage/commit/pushは未実施。今回の別PC・実画面操作・F5・TurboGrid実機Importは未確認です。
保存先はアプリ専用GitHub `ai-infra-data-lab/centrifugal-blade-designer`。ソース・テスト・資料・デフォルト用JSONを対象とし、ユーザーJSON原本・仮想環境・キャッシュ・成果物・家計簿は除外します。v0.3.0タグの167ファイルの記録は維持します。実画面の未確認事項は維持します。
公開済みv0.3.0は全回帰318件成功。中央3Dの全翼列/所属壁面表示までのローカルコードは全回帰450件が成功しました。その後の「全翼列に独立したLE/TE欄を追加する」修正は、再開後の拡張関連108件と全回帰457件が成功しました。静翼TurboGrid出力追加後は全回帰490件、トラックボール操作追加後は全回帰499件、メニュー整理後は全回帰504件、ツールバー統合後は全回帰506件、インペラTE Rake目標追加後は全回帰529件、スプリッターの主翼連動/専用分布追加後の最終コードは全回帰558件成功です。Git status・差分チェックも確認しています。
**動作確認済み（自動）はWindows .venv / Qt offscreenでの確認**です。実ディスプレイ・VS Codeボタン操作・TurboGrid実機まで確認した意味ではありません。

| 機能 | 実装状態 | 動作状態・根拠 |
|---|---|---|
| インペラスプリッター（主翼連動/専用分布） | 実装確認済み・全回帰558件成功 | Hub/Tip開始位置・ピッチ割合・厚さ倍率、主翼/TE Rake継承、2D/3D/全周、Undo/JSON。専用β/厚さへ切替可能。複数種類・TurboGrid出力は未対応、実画面未確認 |
| インペラTE Rake目標とβ保持Mapper | 実装確認済み | test_impeller_te_rake / test_impeller_te_rake_gui。解析式・CW/CCW・全端部種類・独立翼列・Undo/Redo・JSON精度・表示とTurboGridの一致・到達不能時の既存出力保護を自動検証。未指定時の従来形状を維持。実画面・実機TurboGrid・3D面全体の干渉/応力/CFDは未確認 |
| 翼列ごとに独立したLE/TE欄・子午面の線とドラッグ点を追加 | 実装確認済み | 拡張関連108件成功: test_all_row_edges_gui、test_design_navigator_gui、test_row_edge_selection_gui、test_edge_rz_gui、test_undo_commands、test_contextual_3d_gui。表は4×翼列数、LE/TE線は2×翼列数。RCの追加・独立R/Z編集・ドラッグ・名前変更/順番/削除/Undo/JSONを確認。再開後のGit status/差分チェックと最終全回帰457件は成功 |
| main.py起動、design / optimization、--project | 実装確認済み | 動作確認済み（自動）: test_simultaneous_editors、test_optimization_gui。変更前F5起動はユーザー確認済み。今回の変更後native操作は未確認 |
| 左の縦選択パネル・中央の選択対象形状・右Editor | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui、test_design_navigator_gui、test_gui、test_persistent_model_gui。中央上段は子午面選択時に子午面、翼列選択時に翼形状。角度・厚さのグラフと数値・所属編集は右側。対象切替でウィンドウサイズを維持し、初期サイズは画面内に収める |
| 中央3Dは子午面で全翼列、翼列で所属Hub/Shroudと選択翼 | 実装確認済み | 動作確認済み（自動）: test_contextual_3d_gui。全翼列合成・独立した全周枚数・所属壁面の端点と欠落/離れた区間・選択切替・入力変更/Undo/JSON・カメラ保持・無効翼列の理由表示を対象 |
| 中央上段2D・下段3Dの常時表示と高さ調整 | 実装確認済み | 動作確認済み（自動）: test_row_domain_gui。選択翼列に追従しカメラを保持。Impeller・Diffuserとも子午面上の断面とSpanwise接続を3D表示 |
| 子午面の直線・円弧ごとの所属翼列、色・名前表示、翼列別TurboGrid壁面範囲 | 実装確認済み | 動作確認済み（自動）: test_row_domain、test_row_domain_gui。所属をUndo/JSON保存、順番変更・翼列削除に追従。両壁面の連続性と翼輪郭の包含を出力前に検証。全未割り当てなら旧出力を維持。Diffuser CSV輪郭は変更しない |
| 子午面はMeridionalのみ、翼列はBlade Angle / Thickness / LE/TE / Full Annulus、ImpellerはSplitterも追加 | 実装確認済み | 動作確認済み（自動）: test_target_layout_gui。選択対象を中央表示し、角度・厚さ・子午面の数値は右側で編集。中央子午面の翼端ドラッグもUndo検証済み。最適化モードは専用タブを追加 |
| 上部File / Edit / View / Toolsへの全操作統合（ツールバーなし） | 実装確認済み | 関連自動試験成功: test_standard_menus_gui、test_target_layout_gui。回転方向/反転はEdit、投影面はView、ExportはFile、最適化はTools。解析/出力設定の別ウィンドウ・ショートカットを維持 |
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
| 選択Impeller/静翼のTurboGrid 3 curve + BladeGen.inf、軸・単位・順序 | 実装確認済み | 動作確認済み（自動書出し/Qt offscreen）: test_turbogrid_export、test_stator_turbogrid_export、test_stator_turbogrid_gui。静翼Hub/Tip・所属壁面・選択設定・丸め縮退拒否・既存ケース保護・旧Impeller互換。実機Importは未確認 |
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

未実装・今回対象外: 複数種類のSplitter・Splitter付きTurboGrid出力、tip clearance、専用lean/sweep/LE rake、optimization探索、CFX実行、自動meshing、STEP/IGES・Solid CAD。TE Rake目標スタッキングは上記で対応。
詳細の手動確認手順はdocs/DEVELOPMENT.mdにあります。
