# 分割継ぎ目領域の組合せ検査（Stage 3B-3l）

## 対象と入口

`geometry/seam_chart_union.py::seam_union_injectivity`は、前段の局所chartを再計算し、
選択した2面の継ぎ目近傍について、異なるleaf領域同士も含めた数値的十分条件を調べる。
`local_seam_union_injectivity`は既存のface ID・source/mapping照合を通した候補用入口。
旧APIや既存reportを変更せず、明示的に呼び出す別APIとした。
Qt/外部ファイル形式から独立し、GUI・保存・出力ゲートへ自動接続しない。

元境界の同一float64表現、同じSpan対応、元の幅/範囲/閾値/投影方式を保つ。
局所chartの1つでも未判定なら和集合の成功へ進めない。
rootの1つの投影で既に要求全域の条件が成立する場合は、その証拠で終了し、
不要な領域間検査は行わない（`reason=root_chart`、組合せ検査フラグはFalse）。

## 全領域対を覆う十分条件

leafはSpan区間で要求領域を分割し、各leafが両側のξ幅全体を覆う。
同じleaf内の単射性は前段の共通投影で確認済み。
異なるleafについて、すべての`N*(N-1)/2`組を調べる。
各chartで正規化したSpan座標が異なっても、元のSpan/ξへの写像と幅は共通なので、
比較対象は一貫した同じ元面上の点となる。

### 隣り合うleaf

左区間を[a,b]、右を[b,c]とする。
`collar_fraction=f`（0<f<1、既定0.5）から重複領域
`[b-f*(b-a), b+f*(c-b)] = [l,h]`を作る。
この領域の両側全体に1つの共通投影を固定して単射性を調べる。

両方の点がこの領域内なら、そこでの単射性が期待接続以外の一致を排除する。
それ以外の点の組は次の2比較で**すべて覆う**。

1. 左の遠方部分[a,l] と、右の全体[b,c]。
2. 左の全体[a,b] と、右の遠方部分[h,c]。

この2比較を元面の制御点凸包で分離できることも必須とする。
境界付近の共通chartが正でも、離れた端部が重なる形状を成功にしない。
重複領域をfloat64で表現できない場合や共通chartが未達の場合は未判定。
全leafを一括した失敗を、そのまま隣接2leaf全体へ再要求するのではなく、
重複領域と遠方部分の被覆で調べる。

### 隣り合わないleaf

両leafの全域（各2面分）を元面の制御点凸包で比較する。
指定矩形の端でknotを挿入し、内部knotをまたぐ場合も含めて有効な全poleを抽出する。
再fit・標本だけへの置換・元係数の書換えは行わない。

XYZ各軸、および局所投影のSpan方向の行を単位化した軸へpoleを投影する。
両区間の投影gapの最大値は、凸包に含まれる元領域間の距離の下限となる。
その数値下限が`nonadjacent_clearance_mm`を**厳密に上回る**場合のみ分離とする。
等号は未判定。gapが得られない場合も、実曲面の交差を観測したとは言わない。
凸包は実形状より広いので、正しい形状でも未判定になり得る。

このclearance値は、上記の遠方部分/非隣接leafの比較用であり、
翼全体の最小隙間や、正常な共有境界を含む全点対の最小距離ではない。
元面全域を包むpoleを直接使うので、triangle近似誤差やweld量で代用しない。

同leaf、隣接leafの重複/遠方、非隣接leafのすべてを覆えば、
要求した継ぎ目近傍の和集合に対する実数演算での単射性の十分条件となる。
floatのknot挿入・投影・微分下限の丸めを包む区間保証はまだないため、
数値的証拠にとどめ、`roundoff_certified/continuous_surface_certified/whole_geometry_verified`はFalseを維持する。

## 結果と上限

- `NUMERIC_INJECTIVE_ON_JOINED_CHART`: 従来のrootだけで要求領域の条件成立。
- `NUMERIC_INJECTIVE_ON_CHART_UNION`: 全leaf条件と全領域対の被覆/分離条件が成立。
- `UNRESOLVED`: 局所条件、重複領域、凸包分離のいずれかが未達。
- `RESOURCE_LIMIT`: 局所chartまたは組合せ数の上限に達した。

`max_pairs`（既定256）はleaf対の総数の上限。
必要総数を事前に計算し、超過時には部分的な組合せ結果を成功として返さない。
既存の深度/chart総数/個別セル上限も保つ。
`pair_scan_complete`と`cross_chart_pairs_checked`は全組の検査を試みたかを表し、
個々の未判定を含み得る。成功にはさらに全組の`numeric_compatible=True`が必要。
`leaf_chart_indices`はSpan順のleaf番号と元の分割木node IDの対応を保持する。
各組には重複領域・元Span範囲・投影方向・下限・未達理由を残す。

候補用入口では、旧`candidate_report`をそのまま残し、別の`union_report`を返す。
旧root条件がFalseでも、新しい全組検査で条件成立する場合がある。
旧結果の意味を変えたり、以前の接触候補・既存出力条件を消したりしない。

## 既定モデルでの確認

前段と同じpackaged default・fit65、`balanced_transverse`、refinements=1、
rank閾値1e-12 mm・margin=0、深度4・chart上限31、ξ幅0.01ずつを使用。
今回の追加条件はf=0.5、遠方clearance=0 mm、組合せ上限256。
16継ぎ目のうち、root条件成立4組、和集合条件成立2組、境界不一致10組となった。

| 和集合で追加成立した継ぎ目 | leaf数 | 全leaf対 | 重複領域の検査 | 凸包比較数 | 投影gapの最小数値下限[mm] |
|---|---:|---:|---:|---:|---:|
| Impeller Main TE–SS | 5 | 10 | 4 | 14 | 0.525480 |
| Impeller Splitter TE–SS | 4 | 6 | 3 | 9 | 1.422803 |

これはξ幅0.01の選択領域の結果であり、LE/TE role全体や翼全体の非干渉とは異なる。
元の親セルを覆う選択32候補では、従来のrootで10組、新しい和集合条件で2組が成立。
残る20組は元境界表現不一致で未判定のまま。微小gapを勝手に結合していない。
前段の16分割reportと32候補reportは、今回の結果に内包した旧reportと全項目一致を照合した。

試行は`artifacts/quality-seam-union/probe.py`、`default-probe.json`、
`union-comparison.json`へ保存した（ローカル証跡）。

## 検証と残課題

新規30件は、解析的shearの全leaf対被覆、自己交差する正則曲線の押出し、
重複領域は正常でも遠方端が重なる閉ループ、広すぎる重複領域の未達、
資源上限・厳密な分離閾値・gap、剛体変換/scale、内部knotを含む凸包と密標本の照合、
端点4組合せ/部分幅、source候補照合、旧report/source不変を確認する。
quick63件、関連123件、変更PythonのRuffは成功。

全回帰は2,110一意件成功（通常2,065・実CAD45）。既存2,080 IDを保持し、新規30件を追加。
失敗/error/skip/漏れ/重複/予期しないIDはいずれも0。
通常7群・実CAD1群を選択`.venv`の`tools/run_tests.py`で実行し、全収集IDとJUnitを照合した。
固定346入力のSHA256は検査中不変。原本`blade_v03.json`とpackaged defaultもそれぞれ維持した。
全回帰の証跡は`artifacts/quality-seam-union/final-test-coverage.json`、
`source-hashes.json`、`collected-tests.txt`、各`group-*.log`に保存している。

追加テストの最初の候補例では、局所条件自体が未達な強い曲がりの形状を
全体成功のfixtureとして使っていたため1件失敗した。
その形状は未判定を維持するnegativeに残し、成功例は既知の解析的shearを
2roleへ分けた別fixtureで確認した。実装・閾値・既存fixtureは変更していない。

残課題は、境界表現が異なる候補の扱い、全候補の集約、遠い周期翼/包含、
最終CAD/fillet/STEPとの照合、丸め保証と全面誤差予算。
後続Stage 3B-3mで[境界曲線の正確な係数モデル比較](BOUNDARY_CURVE_IDENTITY.md)を追加したが、
微小差を持つ20候補を同じ曲線として結合する変更は行っていない。
native GUI/F5・ANSYS Import/Meshは今回未実行。
