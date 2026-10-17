# 幾何・CAD・出力の品質レビュー

2026-10-17、対象`6b8d3be`。コードレビューと監査用プローブのみ。設計アルゴリズム・既定値・原本・テスト期待値の修正は行っていない。
機能表と検証履歴は[CURRENT_FUNCTION_AUDIT.md](CURRENT_FUNCTION_AUDIT.md)、対応順序は[DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md)に記載する。

## 評価基準

- P0: 広範囲の不可逆破損など緊急停止を要する問題。今回、確認できたP0はない。
- P1: 設計／出力の誤認や無効形状の受入れ、既存ケースの不整合につながる。対応する実務用途のリリース前に解決する。
- P2: 条件付き精度・操作性・検証範囲の不足。条件を明示し段階改善する。
- P3: 文書・保守性などの改善。

証拠Aは今回の再現、Bはコード上の検査欠落／方式の制限、Cは実行環境がない等で未検証。B/Cを「実形状で必ず発生する不具合」としない。
以下のファイルは、明記しない限り`blade_designer/`配下。

## 1. β・θ・回転方向、Hub/Tip対応

`geometry/blade_section.py::generate_section`は、流れ方向の物理子午面距離mを増加させ、

`θ(m) = θLE + rotation_sign ∫ tan(βm)/r dm`

とする。`RotationDirection.sign`はCCW=+1、CW=−1。+Zから見た幾何学的θの符号と一致する。RCは半径が減ってもmは増えるので、一律β反転やLE/TE交換は不要。
内向き直線での解析解は`Δθ = sign tan(β) log(RLE/R)`。`tests/test_return_channel.py::test_inward_meridional_flow_uses_positive_distance_and_correct_wrap`が±β×CW/CCW×TE3種類を検証し、今回も成功した。

Hub/Tipは`geometry/blade_edge.py::blade_wall_parameters`の共通参照LE/TE節点を介し、別々の壁面距離へ写像する。`geometry/span.py::interpolate_span_position`は対応するR/ZをSpan線形補間し、各断面はその壁面の物理距離で積分する。単にHubとTipの異なる長さのmを同じmmとして扱ってはいない。
`tests/test_blade_edge_span_interpolation.py`、`test_blade_normalized_meridional.py`が対応を検査する。ただしこの写像は幾何学的な対応で、流れ解析の流線・等ポテンシャル面ではない。

### G01 — 表示と旧指標／CSV／最適化の形状正本が異なる [P1・A/B]

**部分対応（Stage 2A／2B）**: 実断面指標とmaster XYZ CSVを追加し、旧経路をlegacyとして識別。旧計算／参考Impellerの失敗を静翼表示から分離し、生成時検証も翼種別にした。Stage 2B-2でrow一覧ありのLoad／Saveを保存値の整合性と宣言翼種の実3D検証へ分離。未使用の旧2D／参考Impellerへの幾何依存を外し、全宣言rowとroot編集snapshotを検証する。row一覧なしの旧契約・旧数値・XY CSVは維持。最適化の実3D制約化等が残るためG01全体の完了とはしない。[形状正本](GEOMETRY_SOURCE_CONTRACT.md)、[生成時検証](ROW_VALIDATION_CONTRACT.md)、[保存検証](ROW_PROJECT_VALIDATION.md)。以下は監査時の記録。

- **対象**: `geometry/designer.py::generate_diffuser/diffuser_design_parameters/generate`、`gui/main_window.py::_display_geometry/update_geometry/export_to_path`、`optimization/feasibility.py::evaluate_candidate`。
- **再現**: 現既定のRCを選択。実3D HubはR130→90、Z95 mmだが、旧camberはR100→160。`artifacts/implementation-audit/probe-results.json`に両値を保存。
- **影響**: 中央2Dと3D／TurboGridは一致しても、Metrics・Curvature・status Throat・CSV・最適化制約が別形状を評価する。`update_geometry`は先に旧2Dを生成するため、旧パラメータエラーが実3Dの更新を止める経路もある（後者はコード確認、今回のGUI再現は未実施）。
- **修正案**: まず各結果にgeometry種別・row ID・snapshot hashを明示。互換CSVは明示的legacy経路として保持。別ワーク単位で実3Dから指標を算出し、旧2D fixtureを維持したまま新経路へ接続する。
- **完成条件**: RC／Diffuser／Impeller別に表示・指標・出力の正本を照合し、意図的legacyとの差をUIで判別できる。

### G02 — 個別断面の検査は周期翼・Span翼面全体の干渉検査ではない [P1・A/B]

- **対象**: `geometry/blade_section.py::generate_section`、`geometry/geometry_3d.py::_generate_row`、`geometry/splitter.py::generate_splitter`、`fileio/turbogrid_export.py::export_turbogrid`。
- **再現**: `BladeParameters()`で翼枚数を1000にする。生成成功・Profile Points4ファイル出力成功。Hub中央のPS/SS角幅0.0292298 radに対しピッチ0.00628319 rad。同じ生成形状に別途`calculate_passages(points=21, mean_points=501)`を実行するとm=0.2〜0.8で`Main blade blocks/overlaps adjacent pitch.`となり、throatは0件。単独輪郭が正しいことだけでは有効流路にならない。
- **既存検査**: `generate_section`は非交差壁面上の(m,θ)輪郭交差を検査。`passage.py::_area_cut/_throat`はサンプル位置で主翼／Splitterの重なりを検出するが、明示解析時のみ。CAD Hub付きassemblyは`worker.execute`で実体間干渉を調べる。Blade Onlyはassembly検査をしない旨をレポートする。
- **未証明**: 既存Spanの間、LE前後、異なるstreamwise位置同士、主翼とSplitterの全3D面交差。中間Spanごとに正常でもその間のloftは保証されない。
- **修正案**: 全経路に共通の幾何品質レポートを置き、局所断面・全Span surface・周期翼・Splitterを別検査にする。高速広域候補検査→局所面交差／CAD実体検査の順で実装。解析を開かないと出力前検査が走らない設計を解消する。
- **完成条件**: 高翼数、強いSpanねじれ、Splitterのpitch端寄せ／厚み増加を独立した不成立fixtureとして拒否し、正常な旧fixtureは変えない。

### G03 — LE/TEのG0接続とG1接線連続性が異なる [P2・A/B]

- **対象**: `geometry/blade_section.py::generate_section`、`geometry/edges.py::generate_edge`、`cad/occt_backend.py::_join_tangents/create_blade_solid`。
- **確認済み**: 端部とPS/SSの座標は最後に一致させ、G0を確保している。円／楕円端部の接線はcamber方向を基準にするが、PS/SSには厚み勾配・β勾配・壁面曲率の寄与がある。一般入力でG1を強制する処理ではない。Cutoffの角は意図的な不連続なので別扱い。
- **再現**: `BladeParameters()` HubのLE→PS、PS→TEの隣接ポリライン接線角。profile/edge密度1001点で約1.712°／2.697°、4001点で約1.773°／2.781°。細分化でゼロへ近づく傾向ではない。有限差分診断であり、連続曲線の厳密角度証明ではない。
- **影響**: Profile Pointsの局所折れと、CADの共有接線を与える近似曲面は厳密同一ではない。見た目が丸いことを曲率連続の保証に使えない。
- **修正案**: まず接線・曲率の定量診断と厚み勾配のある独立解析fixtureを追加。端部方式を変える場合は互換モードと明示選択を設け、無断で旧輪郭を再定義しない。

### G04 — 厚みとPS/SSの意味を物理的な面法線厚さと区別する [P2・B]

- **対象**: `geometry/blade_section.py::generate_section`の`dm=-t sinβ/2`、`dy=t cosβ/2`と`mapped`、`models/parameters.py::SurfaceMapping`。
- **条件**: 高曲率壁面、大きなt/r、Spanねじれ、βが正負を跨ぐ分布。tは局所曲面の内在座標でのオフセット量で、生成後PS/SSの空間最短距離や翼面法線厚さとは一般に異なる。AUTOは平均βからsideを選ぶため、解析された圧力側／負圧側を示すものではない。
- **影響**: 製造上の最小肉厚・応力評価でtをそのまま保証値として扱えない。平均β近傍でのラベル選択も説明が必要。
- **修正案**: 今の定義を保存し、実空間の肉厚測定とside判定の根拠を別結果として表示する。モデル変更は明示仕様と解析解・回転反転・β符号反転の試験を先に用意する。

### G05 — Span間の連続面とCAD近似の一致保証に穴がある [P1・B]

**部分対応（Stage 3A-1）**: 非Qt／非OCPの共通数値評価器を追加し、CAD spline構築とtrim列補間を共通化。独立解析面と実OCCT内部点比較を検証した。既存の3方式は変更しておらず、同一面にはなっていない。診断用の対応座標を揃えたモデル差を、現行preview／trimの誤差や公差超過と断定しない。実対応座標・source_spanの統一、正本の適用、全面保証はStage 3A-2以降。[方式・誤差の区別](SURFACE_EVALUATION_CONTRACT.md)。以下は監査時の記録。

- **対象**: `geometry/span.py::interpolate_span_position`、`gui/preview_3d.py::_section_lines`、`cad/occt_backend.py::create_surface/create_blade_solid`、`geometry/impeller_trim.py::_span_curve`。
- **条件**: Impellerに3断面以上を置き、Spanごとに大きくβ／厚み／Stackingを変える。CADはSpan方向に最大3次の補間、通常previewは既存断面間の接続線、派生カットは円筒座標の区分線形補間。2断面の静翼には同じ3次overshoot問題をそのまま適用しない。
- **証拠**: CADのmaster偏差は入力した各Span上のmaster点で測定し、Span間の密な対応点は検証していない。CAD補間の連続性と交差の不存在は別。実形状で規定公差を超えたと今回断定してはいない。
- **修正案**: 非Qtの共通surface評価器と対応座標を定義し、preview・trim・CADで同一正本を評価する。曲線／曲面の双方向距離、Span間のJacobian／法線反転・交差、密度収束を追加する。既存CAD入力点の公差だけを緩めない。

### G06 — Tip Clearanceは実形状だが連続曲面全域の保証ではない [P2・B]

- **対象**: `geometry/tip_clearance.py::_frame/make_tip_geometry/_check_open_curve`、`geometry/span_extension.py::extend_tip_to_shroud`。
- **確認済み**: 固定Shroudから内向き法線にmm指定で離し、LE〜TEをケーシング沿い距離で補間。実Tipとケーシングは別。正半径・幅上限・側反転・cusp・離散Tip自己交差を拒否し、Hub TE円筒を保つ。円錐でR/Z両方動く解析試験あり。
- **条件**: 小半径Arcに大きいgap、複雑な戻り流路、サンプル間の高曲率。Hub側の向きは等壁面距離対応から決める幾何方式で、実CFDの流線対応ではない。サンプル間／3D面全域の厳密最小gapは未証明。
- **修正案**: 解析Line/Arcの曲率によるoffset成立条件とadaptive密度収束、実Tip→ケーシングの最小距離を別途検証する。熱・遠心変形や漏れ流量は別解析Stage。
- **出力注意**: TurboGrid Profile Pointsは実Tipを中間断面として残し外側へ延長。読込み後のProfile Number設定を含む実機確認が不可欠。延長は実翼設計を変更する処理ではない。

### G07 — TE Rake達成と、Stacking後の設計成立は別 [P2・B]

- **対象**: `geometry/impeller_parameter_mapper.py::ImpellerParameterMapper.map_te_rake/measure_te_rake`。
- **確認済み**: Hub固定、各Span剛体回転でβ・R/Z・厚みを保持。TE Hub–Tip弦と中点子午面の角度を解き、小ねじれ側解を採用。符号は絶対+θでCW/CCWとは独立。TE θをSpan線形配置し、LE θは積分巻き角から決まる。
- **条件**: 到達可能な大Rake・異なるSpan長さ・Splitter併用。到達性試験と全3D衝突・強度／空力は別で、後者はMapperが検証しない。LE Sweep独立指定や任意Stacking曲線でもない。
- **修正案**: G02/G05の品質ゲートに接続し、目標達成・局所断面成立・assembly成立を別状態で返す。βを黙って書き換えて到達させない。

### G08 — 面積・スロートは近似定義と収束の明示が必要 [P2・B]

- **対象**: `geometry/flow_area.py::calculate_flow_area/crossflow_pair`、`geometry/passage.py::_area_cut/_section_gap/_throat/calculate_passages`。
- **定義**: 等壁面距離から作る平均線に直交する局所Hub–Shroud切断。Grossは`π(Rhub+Rshroud)×切断線長`。Netは実輪郭の周方向閉塞幅を既存Span間で台形積分し控除する。gapは幾何開口を含む。Splitter上流で片側通路未成立なら0ではなく未定義。
- **条件と制限**: 面積は有限のstreamwiseサンプルで、最小値の厳密位置ではない。円筒／円錐の幅は展開ポリライン、曲面壁では空間弦の下限。Spanごとの最小幅の位置が異なるまま積分するので、一枚の実スロート面を求めた値ではない。Hub/Tipのみなら2点積分。フィレット・粘性・境界層・漏れ流量・運転点補正なし。
- **折返し流路**: 遠方の翼への法線誤交差は直前修正で実Hub LE〜TE内に限定済み。多交点や一意でない断面を全域で解ける保証はなく、`strict=False`のerrorsを結果とともに扱う。
- **修正案**: sample数・Span数・曲面方式・未定義範囲を結果へ固定し、adaptive streamwise／Span収束と独立解析解を追加。真の3Dスロート面探索・CADフィレット閉塞量は後Stage。流量・圧力比を直接算出したと表示しない。

## 2. CAD

### C01 — 現既定＋仮ディスクのR8は未成立 [P1・A]

**受入れ条件の更新**: 利用者の追加指示により、対象形状で成立する小さい指定Rで実フィレットの生成を確認できればよく、R8成功は必須としない。下記R8の失敗は観測記録として残す。小径試行と、その成功／失敗は別に記録する。

- **対象**: `cad/occt_backend.py::boolean_union/root_edges/apply_fillet`、`cad/worker.py::execute`、`geometry/provisional_disk.py::make_provisional_disk`。
- **再現**: 現既定JSONをメモリへ読込み、Impellerを選択。既存機能で仮ディスクを設定し、Mechanical Blade+Hub、R8、TurboGrid CAD無効で実OCCT処理。原本・元設定は書き換えない。現仮ディスク内径20、外径182、裏面Z75 mm。
- **結果**: 主翼solid、Splitter solid、Hub単体は有効。主翼Boolean後のroot分類を通過し、`TRUE CAD FILLET / main`で`R8: ChFi3d_Builder:only 2 faces`。`artifacts/implementation-audit/current-default-r8/result.json`。正式STEP成功はない。debugの`NO_FILLET_OR_INCOMPLETE.step`は完成出力ではない。
- **原因の範囲**: フィレットへ渡す根元の二面隣接が崩れている。元処理を変えずroot選択後の位相だけを計測した別診断では、**現既定の根元候補10本中7本が4個のdistinct faceを共有**した。重複occurrenceを数えただけではない。該当roleはHub流路面・`BLADE_HUB_CAP`・PS/SS/LE/TEのいずれかで、主翼capの残る結合位相をfillet builderへ渡している。`artifacts/implementation-audit/root-topology.json`、`diagnose_root.py`、`current-default-r8-topology/result.json`。同じR8例外を再現した。旧既定の「15本中4本」という記録とは別の測定である。
- **まだ特定していないこと**: 曲面Hubと近似capの位置関係、Booleanの面分割・内部面処理のどの段階がこの位相を作るかは追加調査が必要。今回の証拠は直接の二面隣接違反までで、修復後にR8が幾何的に収まることまでは示さない。
- **既存の検査**: BRepCheck、BRepAlgoAPI_Check、閉shell、正体積・積分収束、Boolean後1solidを確認する。それらの成功だけでfillet builderが必要とする根元の二面隣接・面履歴が保証されたことにはならない。`root_edges`はroleの一意性を検査するが隣接面数2を明示確認していない。
- **修正案**: 対象形状に合わせた小径を明示的に試す。小径でも失敗する場合はBoolean前後の根元face/edge履歴、重複occurrenceとdistinct face、内部面・微小エッジ・cap接続を定量化し、根元を二面隣接の一意なループへ修復する。根拠なしの候補間引き・公差緩和・入力値の無断縮小はしない。成立した指定Rについて幾何的収まり・干渉・STEP前後の半径を検証する。R8が収まらないだけでアプリ機能全体を未成立と判定しない。
- **回帰**: 独立曲がり翼R8、直線翼R1、可変R2.5、狭Span R8失敗／sentinel保護を維持し、今回の既定caseを追加する。

#### 小径での追加試行（利用者指示後）

同じ現既定Impeller＋仮ディスク、同じ入力master座標・公差0.01 mm・Blade+Hub条件で、指定Rだけを変えた独立snapshotを実OCCTへ渡した。主翼とSplitterは有効のまま。各ケースを最初から生成し直し、既存ケースへの公開は行っていない。

| 指定R [mm] | 結果 | 停止段階・例外 |
|---|---|---|
| 2 | FAIL | `TRUE CAD FILLET / main`、`R2: ChFi3d_Builder:only 2 faces` |
| 1 | FAIL | 同段階、`R1: ChFi3d_Builder:only 2 faces` |
| 0.5 | FAIL | 同段階、`R0.5: ChFi3d_Builder:only 2 faces` |

結果は`artifacts/implementation-audit/small-radius-results.json`、各`current-default-r2`／`current-default-r1`／`current-default-r0.5`の`result.json`、再現スクリプトは`try_small_root_radii.py`。snapshot hashと試行Rをケースごとに記録する。これは成功試験ではなく、不成立診断3ケースである。
今回の形状では半径を小さくするだけではフィレットを確認できなかった。同じ位相エラーが続くため、まず既に確認した四面共有の根元結合を修復する必要がある。修復後はR8を要求せず、形状に適した小さい指定Rで成功・STEP再読込み・半径を検証する。原本JSONと既定R8、形状生成コード、公差は変更していない。

### C02 — STEP再読込みの検査は全翼面の偏差保証ではない [P1・B]

- **対象**: `cad/cad_validation.py::step_roundtrip/fillet_samples`、`cad/worker.py::match_fillet_samples`、`cad/occt_backend.py::validate_solid/create_blade_solid`。
- **実装済み**: MMのSI_UNIT、solid数、BREP・閉鎖・自己交差、Gauss–Kronrod体積と収束、bbox、edge公差。bbox許容は元＋再読込みの実edge公差に基づき指定CAD公差で上限を設ける。過大bbox／edge／volume拒否の独立試験あり。
- **条件**: 同じ体積・bboxを持つ局所面変形は、この集約量だけでは識別できない。root filletの再対応と局所主曲率サンプルはあるが、全PS/SS・LE/TE・Span面の双方向幾何距離／法線偏差はない。現実のSTEPでその局所変形が発生したと今回断定するものではない。
- **修正案**: 元master→CAD、CAD→STEP再読込み、再読込み→元CADを個別の偏差予算で測る。面内部・trim境界・LE/TE・根元にadaptiveサンプルを置き、位置と法線、局所曲率を比較。最大位置と収束履歴を保存する。実edge公差・要求精度・丸め誤差を混同しない。

### C03 — MechanicalとTurboGrid CADの一致は共通境界として評価する [P2・B/C]

- **対象**: `cad/worker.py::execute`の`single/full`、`create_flow_passage/subtract/sector`、`fileio/turbogrid_cad_export.py`。
- **確認済み**: 同一snapshotのフィレット済みfull実体を流路から引く設計。Mechanicalは構造solid、TurboGridはその外側の流体であり、体積が同じになるべきではない。
- **条件**: 仮ディスクの構造前面範囲と所属壁面の流体範囲が異なる場合。TurboGridは所属検証を省略せず、現既定ImpellerはLE/TE包含で拒否する。Blade Onlyの成功は流体CAD成功ではない。
- **不足**: 各経路の共通翼／Hub／フィレット境界の全面幾何一致と変換後role保持、ANSYSでのImport/Meshは未検証。
- **修正案**: 同snapshotで構造表面と流体境界の向き反転を考慮した双方向距離・role集合・周期面を照合し、変換後とANSYS内でも確認する。

## 3. 出力保護・現既定・GUI

### E01 — 主翼のみのProfile Pointsは丸め後に重複点を出力する [P1・A]

**対応済み（Stage 1A）**: 通常Impellerを含む全経路の整形後検査を追加。下記の低精度再現は現在、書込み前に拒否される。新規64件＋既存768件、全832一意件成功。既存ASCII参照は不変。[実装・検証記録](EXPORT_QUALITY_IMPROVEMENTS.md)。以下の原因・再現値は修正前の監査記録。

- **対象**: `fileio/turbogrid_export.py::export_turbogrid`の`if stator or clearance`、`_coordinates`。
- **再現**: `BladeParameters()`、significant_digits=1、Splitterなし、gapなし。設定範囲内だが出力後Hub147箇所、Tip180箇所で連続点が一致する。閉輪郭の先頭と終点の一致とは別の内部重複。
- **原因**: 丸め後の重複・marker数・断面点数対応の検査が静翼または正gapに限られる。通常主翼は同じ検査を通らない。
- **修正案**: 全Profile Points経路に共通の「整形後」検証を適用。重複・消えたLE/TE・向き・断面対応が崩れる場合は出力先作成前に拒否。旧通常精度のbytes fixtureは保持し、勝手な桁数増加や輪郭点削除で隠さない。

### E02 — 複数ファイル公開はケース全体のトランザクションではない [P1・A/B]

**対応済み（Stage 1B）**: 別領域で一式を完成させ、保持バックアップと復旧journalを伴う2回のディレクトリrenameへ変更。最終860一意件成功、Windowsロック／強制終了／容量不足／CAD公開失敗を確認。単一原子的操作・実停電耐久性は保証しない。[詳細](EXPORT_QUALITY_IMPROVEMENTS.md)。以下は修正前の監査記録。

- **対象**: `fileio/turbogrid_export.py::export_turbogrid`、`fileio/mechanical_step_export.py::publish_verified_artifact`、`cad/client.py::publish_job`。
- **再現**: 専用sentinel4ファイルへexportし、2回目のos.replaceにOSErrorを注入。例外後`hub.curve`のみ新しく他3ファイルは旧値。実ユーザー出力には注入しない。
- **範囲**: 無効形状時は事前検証、CADはhash検証済みbytesだけ公開、JSON単体はtemporary→replaceで保護される。対して複数ファイルreplaceの途中I/O失敗・停電に対する一括整合性はない。CAD公開にも逐次replaceがあり同種の制限（CAD側故障注入は今回未実施）。
- **修正案**: 不変の世代別caseを別ディレクトリで完成・検証し、manifest/hash＋単一の参照切替で公開するか、既存caseへの完全rollback設計を用意。Windowsのファイルロック・クラッシュを含め設計する。失敗レポートが成功レポートを上書きしない既存方針は維持。
- **完成条件**: 全置換位置の故障注入で、旧一式または新一式のどちらかだけを参照でき、部分更新を完成品として扱わない。

### D01 — 現既定の表示成立と出力成立が異なる [P1・A]

- **対象**: `defaults/default_project.json`、`geometry/row_domain.py::export_wall_intervals`、`fileio/turbogrid_export.py::export_turbogrid`、READMEの既定寸法説明。
- **再現**: 現既定ImpellerはSplitter有効なのでProfile Pointsが拒否される。さらにメモリ上で所属検証すると`The assigned meridional export domain must contain the blade LE and TE.`。Diffuser／RCの所属は通る。仮ディスク生成は構造CAD用で、流体の所属制約を解除しない。
- **影響**: 「起動できる既定」から「出力できる既定」を期待すると誤認する。これは検証ガードの不具合ではなく、入力と出力成立条件の不一致。
- **修正案**: 非破壊のExport Readiness診断を先に表示し、どの条件で止まるか明示。原本のLE/TE／所属／Splitterを勝手に変更しない。出力用例題は別データとして後Stageで作る。

### U01 — CAD／Passage非同期化だけではGUI停止を防げない [P2・B]

- **対象**: `gui/main_window.py::update_geometry/_display_geometry/_update_central_preview/start_cad_job`、`cad/client.py::prepare_job`、`gui/passage_widget.py::calculate/_poll`。
- **条件**: 全行表示、密度増加、中間Span・Splitter追加。CAD本体はQProcess、Passageはthreadで旧世代を破棄するが、通常3D・全行再生成・Flow Area・CAD snapshot準備はGUIスレッドで実行する。150 ms debounceは計算を非同期にしない。
- **修正案**: まずUI heartbeatと各段階の実測を記録。純粋なimmutable snapshotの数値計算をworkerへ移し、取消／世代／例外／最終有効表示を統一する。描画Qt更新はGUIに残す。今回native操作の応答時間は未測定。

### U02 — 設計snapshotと表示／履歴の分離は部分的 [P2・B/C]

- **対象**: `gui/main_window.py::get_parameters/_bind_history_inputs/commit_edit/_sync_cad_preview`、`gui/undo_commands.py::ProjectEditCommand`、`gui/preview_3d.py::showEvent/fit_view`。
- **確認済み**: 各設計値をproject deepcopyでUndoする経路と多数のGUI回帰がある。Cameraの通常update保持も試験あり。未確定入力はwidget固有の確定処理が必要で、任意の全組合せを保証するものではない。
- **条件**: 選択翼列・他行編集も全project hashへ含み、計算上無関係でもCADをstaleとして隠す可能性がある。表示時のFitは中心・scaleを変える。カメラ・checkboxは設計JSONへ保存されない。
- **修正案**: DesignSnapshot／SelectionState／ViewStateを明示し、CADの依存入力hashと保存project hashを分ける。各設計項目のcommit信号・保留入力・Undo・JSON・別画面同期を列挙した契約試験を追加。大規模MainWindowはまずservice呼出し境界から段階分離する。

## 未検証境界

現既定R8の失敗は実OCCTで再現した一方、ANSYSのImport/Meshは実行していない。公開CADの適合性、回転体強度・振動・疲労、実流量・圧力比・効率、製造公差は未検証。
既存自動試験の成功をこれらのPASSに置き換えない。監査で挙げた方式変更は計画であり、今回実装していない。
