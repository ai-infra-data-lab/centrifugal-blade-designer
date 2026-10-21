# 共有ID継ぎ目候補の集約（Stage 3B-3n / 3o）

## 対象と採用条件

`geometry/seam_candidate_summary.py::seam_candidate_summary`は記録済みmerged-role meshの
共有頂点IDを持つ**別role**の全face対を列挙し、決定的な順序の先頭候補を診断する。
元sourceとmappingのfingerprintを照合し、作業用snapshotだけを用いる。
Qt、JSON、GUI、形状生成、既存接触report、出力ゲートへは接続しない。

各候補は宣言済み継ぎ目と両親セルの端位置を確認し、両セルを囲むSpan区間について
次の3つのreportを別々に保存する。

1. 保存float64係数モデルの厳密な同一Span曲線判定。
2. 明示した`gap_tolerance_mm`に対する数値的な位置差包絡。
3. 既定の`average`投影による局所chart・分割領域間の十分条件（3oの明示選択は下記）。

3は既存APIをそのまま呼ぶ。元の境界表現が異なる場合は未判定のままとする。
厳密同一だが表現が異なる場合や、微小差が予算内の場合も自動採用しない。
期待接続のみという局所判定は、既存chart unionが数値条件を達成した場合に限る。
`UNDECLARED_ROLE_PAIR`と`OUTSIDE_DECLARED_BOUNDARY`も除外せず記録する。
曲線恒等性とgapは同じ継ぎ目/Span区間で再利用するが、返すreportは候補ごとに独立させる。

`DIAGNOSTICS_RECORDED`は調べた結果の記録完了を意味し、すべての幾何条件成立を意味しない。
各候補の`UNRESOLVED`、詳細report内の`RESOURCE_LIMIT`は保持する。
`whole_geometry_verified`、`export_ready`、`physical_gap_certified`、
`roundoff_certified`、`continuous_surface_certified`は常にFalse。

## 被覆と資源上限

頂点→faceの索引を作り、頂点ID順・face ID順に対を訪問する。
同じface対が複数の頂点を共有していても1候補に集約する。
`max_pair_visits`（既定100,000）は同roleや重複の組も含む訪問回数の上限。
`max_candidates`（既定4,096）は発見した一意な別role候補の保存上限。
どちらかで走査を止めた場合、`inventory_complete=False`、
`candidate_count_is_total=False`と停止理由を返す。件数は発見済み下限だけを示す。
mesh自体は`max_triangles`（既定20,000）で入力拒否する。

走査で発見したface対を昇順に並べ、先頭`max_evaluated`（既定64）組だけを調べる。
残りは`UNEXAMINED`、3つのreportはNone、`evaluation_complete=False`。
走査または評価の件数上限に達した場合、集約statusは`RESOURCE_LIMIT`になる。
走査完了と診断完了は独立で、前者だけでは全面評価済みと扱わない。
個々のchart/厳密比較/gapにも既存の資源上限があり、詳細reportを捨てない。

この索引は**共有IDを持つ別role対だけ**を対象とする。結合許容値外の未接続境界、
同roleの局所fold、非局所対、遠方周期翼、完全包含、実CADは検査対象外。
すべての候補が期待接続でも全面非干渉や品質合格にはしない。
物理的対応、生成誤差、float丸め、gap許容時の採用条件は別課題として残す。

## 検証

解析的な四面tubeについて、独立した全face対総当たりと候補集合を照合する。
重複排除、決定的順序、元係数/mesh不変、source/mapping不整合拒否、件数上限、
未検査、微小差が予算内でも期待接続へ昇格しないこと、ゼロ予算での差の観測、
返却report間の独立性をテストする。歴史的数値fixtureの期待値は変更しない。

quick63件、関連121件、新規20件、変更PythonのRuffは成功。
packaged defaultのfit65基準面とtarget 0.03 mm、join 1e-8 mmの記録meshで調査した。
gap予算は1e-8 mm、参照最小値1e-12 mm、単調性marginと遠方分離要求は0。
この単位での`max_evaluated=64`、他はAPI既定値とした。

| ケース | 列挙済み候補 | 期待接続のみの数値条件成立 | 未判定 | 未検査 |
|---|---:|---:|---:|---:|
| Impeller Main | 110 | 9 | 55 | 46 |
| Impeller Splitter | 78 | 0 | 64 | 14 |
| Diffuser | 14 | 4 | 10 | 0 |
| RC | 14 | 7 | 7 | 0 |
| 合計 | 216 | 20 | 136 | 60 |

全4ケースで候補列挙は完了。Main/Splitterは評価上限による未検査を残す。
前段の選択32組とは候補集合・投影方式が異なり、成功率の改善比較には使わない。
未判定136組を不正形状/干渉と断定せず、詳細reportの境界差・chart条件未達等を保持する。
調査結果は`artifacts/quality-seam-summary/default-probe.json`、再実行用`probe.py`に保存した。

続いて`max_evaluated=4096`を明示した追加調査を行い、同じ216候補の診断を完了した。
Mainは27組成立/83組未判定、Splitterは0/78、Diffuserは4/10、RCは7/7。
合計38組成立/178組未判定/未検査0で、全ケースのinventory/evaluationは完了した。
厳密同一曲線は86組、係数モデルに差がある曲線は130組。
数値gapは216組すべて予算1e-8 mm以内だが、それを厳密一致やchart成立へ昇格させない。
同一曲線でも48組はchart条件未達のままであり、境界一致だけでは合格へ進めない。
候補診断の完了と3B全体の完了は区別する。
追加調査は`complete_probe.py`、`complete-probe.json`、`reasons.py`に保存した。
全回帰2,166一意件成功（通常2,121・実CAD45）。既存2,146 IDを維持し、新規20件。
失敗/error/skip/漏れ/重複/予期しないIDは0、固定350入力のSHA256は検査中不変。
原本`blade_v03.json`とpackaged defaultはそれぞれ保持した（両者は同一ファイルではない）。
通常7群・実CAD1群を選択`.venv`の`tools/run_tests.py`で実行し、全収集IDとJUnitを照合した。
証跡は`artifacts/quality-seam-summary/final-test-coverage.json`、`source-hashes.json`、
`collected-tests.txt`、`group-*.log`と各実行の`artifacts/test-runs/`に保存した。
native GUI/F5、ANSYS Import/Meshは今回未実行。

## Stage 3B-3o：方式の明示選択と未判定理由の集計

集約APIに`projection_strategy`を追加し、既存chart APIの`average`（既定）と
`balanced_transverse`を選べるようにした。全候補に指定方式を伝達し、root/leaf/collarで
同じ選択を使う。方式名は列挙や部分診断の前に検証する。自動切替や方式間の結果の合成はしない。
元係数、親セル領域、対応Span、ξ幅、margin、rank閾値、境界表現一致条件は維持する。

新しい`diagnostic_counts`は各候補の詳細reportから、以下を独立した軸として集計する。

| キー | 件数の意味 |
|---|---|
| `identity_status` | 厳密同一/係数差/資源上限等。全発見候補が分母 |
| `gap_status` | 数値予算内/差の観測/未判定/資源上限等。全発見候補が分母 |
| `chart_status` | chart unionの数値条件成立/未判定/資源上限等 |
| `chart_root_reason` | root chartの境界表現、rank、対称微分下限等の理由 |
| `chart_union_reason` | root成立/leaf条件未達/領域間条件未達等の理由 |
| `chart_stop_reasons` | 各停止理由を持つ候補数。同候補内の停止node数は数えない |
| `unresolved_identity_status` | `UNRESOLVED`候補だけを厳密比較の状態で分類した件数 |

未検査や宣言外のため当該診断を行わなかった場合は、`NOT_EVALUATED:<候補status>`として残す。
停止理由は1候補に複数あり得るので、その軸の合計は全候補数と一致するとは限らない。
rootが失敗しても分割・和集合で成立する場合があり、root理由の件数を未判定総数と混同しない。
同じ候補に係数差と予算内gapが同時に記録される。どちらか一方の原因へ丸めない。
既存`counts`、詳細reportと候補statusの意味は変えない。

解析的な横断速度比0.1のkinkでは、averageは十分条件未達、balancedは下限2/11で成立する。
元領域・閾値・係数・境界比較・gapが同じことをテストする。gapを持つ例では両方式とも未判定。
既定/明示average一致、未知方式の先行拒否、未検査の全診断軸への伝達、
停止nodeではなく候補の件数を数えることも検査する。quick63件、関連87件、
新規13件と変更PythonのRuffは成功。
全2,179一意件成功（通常2,134・実CAD45）。既存2,166 IDを維持し、新規13件。
失敗/error/skip/漏れ/重複/予期しないIDは0、固定351入力のSHA256は検査中不変。
原本`blade_v03.json`とpackaged defaultもそれぞれ保持した。
通常7群・実CAD1群を選択`.venv`の`tools/run_tests.py`で実行し、全収集IDとJUnitを照合した。
証跡は`artifacts/quality-seam-findings/final-test-coverage.json`、`source-hashes.json`、
`collected-tests.txt`、`group-*.log`と各実行の`artifacts/test-runs/`に保存した。
native GUI/F5・ANSYS Import/Meshは今回未実行。

同じpackaged default、fit65、target 0.03 mm、join/gap 1e-8 mm、各max_evaluated=4096で
両方式の全216候補を照合した。元sourceとmapping、親セルの範囲、全閾値は同じ。

| ケース | 候補数 | average成立 | balanced成立 | balanced未判定 |
|---|---:|---:|---:|---:|
| Impeller Main | 110 | 27 | 55 | 55 |
| Impeller Splitter | 78 | 0 | 20 | 58 |
| Diffuser | 14 | 4 | 4 | 10 |
| RC | 14 | 7 | 7 | 7 |
| 合計 | 216 | 38 | 86 | 130 |

averageの追加2メタデータfield（方式名と診断集計）を除く**全report**が前段の保存値と一致した。
両方式で候補face ID・厳密比較・数値gapの全reportも一致。
balancedの86組はroot70組とchart union16組（Main8/Splitter8）で数値条件が成立した。
averageで境界が一致していた48未判定組は今回すべて成立したが、
方式間で一般に優劣が保証されるという意味ではなく、自動切替も行わない。
残る130組は係数モデルの境界差と一致し、微小差がgap予算内でも未判定を維持した。
全候補の未検査0、各chartに今回の資源上限到達なし。
証跡は`artifacts/quality-seam-findings/default-probe.json`、再実行用`probe.py`。
元面・物理対応・丸め・全面の非干渉・最終CAD/出力ゲートの保証とは分ける。

追加の読取り専用調査で、`reference_surfaces`に渡るmaster断面の対応する端点は
全16継ぎ目でfloat64の完全一致だった。一方、`fit_surface_spline`の沿翼方向補間を経た
`along.c`の端部poleには10継ぎ目で差があり、Span方向補間後の`across.c`でも
同じ10継ぎ目に差が残った。差の最大ノルムは約2.8422e-14 mm。
今回観測した最初の不一致は元断面端点でなく、沿翼方向spline係数を得た段階にある。
浮動小数点丸めと整合する規模だが、丸め誤差の保証や全入力での原因証明ではない。
証跡は`artifacts/quality-seam-findings/source-trace.json`、`trace_sources.py`。
`geometry/cad_surface_reference.py::reference_surfaces`と
`geometry/surface_evaluation.py::fit_surface_spline`の処理は変更していない。
共有境界の生成契約を明示し、必要なら独立した方式で誤差/接線/CAD互換性を評価してから
採用を検討する。事後のwelding、片側poleの無条件コピー、公差緩和で隠さない。

## 次の作業

残る130候補の境界差について、沿翼方向spline係数の生成契約・同じ物理境界への対応・誤差予算を扱う。
非共有/未接続の境界、非局所候補を含む被覆も引き続き必要。
微小差を許容する採用条件を設ける場合は、
生成精度と物理対応を別予算で示し、境界移動や公差緩和で未判定を消さない。
最終CAD/fillet/STEPと出力ゲートへの統合は引き続き未完了。
