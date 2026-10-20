# 共通継ぎ目chartの局所単射診断（Stage 3B-3i）

## 対象と契約

`geometry/seam_injectivity.py::seam_projection_injectivity`は、2つの元splineの
ξ端点をつなぐ局所領域について、**同じ1つの投影**による強単調性の数値的十分条件を調べる。
Qt/外部ファイル形式に依存せず、既存生成・CAD・JSON・GUI・出力ゲートへ自動適用しない。
以前の`local_source_pair_injectivity`のcross-role未判定も書き換えない。

入力は2面と各ξ端点`0/-1`、各側の`width`（ξ全域に対する割合、0より大きく1以下）、
Span範囲、明示的なrank閾値`reference_min_mm`と無次元`monotonic_margin`。
内側に不連続knotを持つ面を拒否し、C0の連続な区分面は片側微分の全セルを調べる。
各sourceをdeepcopyしてfingerprintを記録し、呼出し時点の元係数を保持する。
このfingerprintは以前のmesh reportとの同一性検証の代用ではない。

両境界の**元のfloat64 Span knot、次数、境界poleが完全一致**することを前提とする。
異なる表現なら`UNRESOLVED/boundary_representation_mismatch`。
1e-8 mm以内等のgap予算で代用せず、境界の移動・weld・refit・次数変換による同一視は行わない。
同じ幾何曲線でも表現が異なるものは保守的に未判定になる。
Spanの物理的対応は呼出し側の前提であり、このAPIは逆向きのSpanを並べ直さない。

## 共通chartと十分条件

共通領域は`u∈[0,1], v∈[-1,1]`。
Spanは指定範囲へ線形写像する。端点位置をe（0または1）、内向き符号をi
（ξ=0なら+1、ξ=1なら−1）、各側の幅をwとすると、

- 第1面（v≤0）: `ξ=e+i*w*(-v)`、`dF/dv=-i*w*dS/dξ`
- 第2面（v≥0）: `ξ=e+i*w*v`、`dF/dv=+i*w*dS/dξ`

Span中央・継ぎ目で両側の正規化微分を平均し、その3×2行列のSVDから左逆P（2×3）を選ぶ。
最小特異値が指定mm閾値以下なら`reference_rank`で未判定とし、擬似逆や公差緩和で救済しない。
**同じPを両側・全セルに固定する。** 面ごとに別の投影で成功しても結合成功とはしない。

元knotと指定境界でBézier区間へ分解し、元面をrefitせず微分control netを求める。
Span長と上記の符号付き幅を掛けて共通座標の微分へ換算する。
対称行列`Sym(P*DF)`の対角成分の下限a,dと、非対角成分の区間[l,h]から、

`λ_lower=(a+d)/2-hypot((a-d)/2, max(|l|,|h|))`

を全セルで評価する。**すべての下限が指定marginを厳密に上回る**場合だけ
`NUMERIC_INJECTIVE_ON_JOINED_CHART`を返す。
実数演算で境界連続性とこの不等式が成立すれば、凸な共通領域の線分積分による
強単調性から単射となる。G1は必要条件ではなく、折れた連続接続でも成立し得る。
非正値は十分条件未達であり、自己交差の観測とは区別する。

浮動小数点でのknot挿入・差・SVD・固有値下限・パラメータ変換の丸めを包む区間保証はない。
したがって`roundoff_certified=False`、`continuous_surface_certified=False`、
`whole_geometry_verified=False`を成功時も維持する。
完全一致は元係数の表現比較であり、独立評価器の全点のbit一致という主張ではない。
片側で個別に成功した既存診断、既存接触レポートや出力許可状態を上書きしない。

両側の必要セル数の合計を事前に確認する。
`max_cells`超過は`RESOURCE_LIMIT`とし、途中までの正値セルで成功を返さない。
refinementsは0〜4。端点で表現できないほど小さな幅は空領域として扱わず入力エラーとする。

## 既定形状の試行

packaged defaultを既存生成器で生成し、CAD参照と同じfit65の4群
（Impeller Main/Splitter、Diffuser、RC）を評価した。
各群4継ぎ目、Span全域・両側ξ幅0.01・refinements=1、rank閾値1e-12 mm、margin=0。
幅は明示した局所試行範囲であり、翼全体やそれ以外の幅へ一般化しない。

| 群 | 数値的十分条件を満たす接続 | 同一境界だが十分条件未達 | 表現不一致で未判定 |
|---|---|---|---|
| Impeller Main | TE–PS（下限0.07970） | TE–SS（−0.07836） | LEの2接続 |
| Impeller Splitter | なし | TE–SS（−0.11466） | 残る3接続 |
| Diffuser | TE–SS（0.08908） | なし | 残る3接続 |
| RC | LE–PS（0.11119）、TE–SS（0.15096） | なし | 残る2接続 |

16組中4組で条件成立、2組は共通投影の下限未達、10組は表現不一致。
2組の負値を実際の折返しと断定しない。10組の微小差を勝手に結合しない。
試行と各セル・投影・source識別値は
`artifacts/quality-seam-chart/probe.py`、`default-probe.json`へ保存した（ローカル検証資料）。

## 検証と残課題

新規34件は、4種の端点組合せ、幅/Span範囲、剛体変換/scale、C0内部knot、
G1でない連続接続、個別に単射でも重なる2面、基準点から離れた折返し、
微小gap・異次数同一曲線の保守的拒否、閾値/資源上限、入力検証、独立微分下限照合、元係数不変を確認する。
quick63件、関連101件、変更PythonのRuffは成功。

全回帰は2,021一意件成功（通常1,976・実CAD45）。既存1,987 IDをすべて保持し、
新規34件を追加。失敗/error/skip/漏れ/重複/予期しないIDはいずれも0。
通常7群・実CAD1群へ既存の実測時間で分割し、各群を選択`.venv`の
`tools/run_tests.py`で実行した。各JUnitを収集ID全体と照合し、固定341入力のSHA256不変も確認した。
原本`blade_v03.json`とpackaged defaultはそれぞれ元から異なる内容を保っており、同一化していない。
全回帰の証跡は`artifacts/quality-seam-chart/final-test-coverage.json`、
`source-hashes.json`、`collected-tests.txt`、各`group-*.log`に保存している。

未達例への適応的な領域分割と接触候補への紐付け、微小gapを持つ境界の扱い、
既存mesh/source fingerprint照合を伴う集約条件は次の課題。
局所chartを異なる投影で個別に証明しても、その和集合の単射や非隣接部との非干渉は保証しない。
遠い周期翼/包含、最終CAD/fillet/STEPとの照合、全面精度予算、丸め保証も残る。
native GUI/F5・ANSYS Import/Meshは今回未実行でありPASS扱いにしない。
