# 継ぎ目の投影方向選択（Stage 3B-3k）

## 調査で分かったこと

前段の未判定は、必ずしも形状の折返しを意味しない。
Impeller Main/SplitterのTE–SSで、共通chartの符号付き横断接線の長さに大きな差があった。
Span中央・両側ξ幅0.01での長さと向きは次のとおり。

| 群 | TE側接線長[mm] | SS側接線長[mm] | 向きの内積cos |
|---|---:|---:|---:|
| Main | 0.044141 | 0.532513 | −0.803070 |
| Splitter | 0.043947 | 0.350423 | −0.796065 |

長さの比は約12倍・8倍。単純平均の向きが大きい側へ寄り、
小さい側の投影微分が中央ですら負になる。
これは現在の投影による**十分条件未達の原因の一つ**であり、形状不良の断定ではない。
元形状やG1接続の全域成立をこの調査だけで主張しない。

## 追加した明示的な選択肢

`seam_projection_injectivity`、`subdivide_seam_neighborhood`、
`local_seam_pair_injectivity`に`projection_strategy`を追加した。

- `average`（既定）：これまでの両側微分の単純平均。数値処理を維持する。
- `balanced_transverse`：両側の横断接線を単位化して向きを均等に扱い、投影を選ぶ。

継ぎ目中央での、既存chart座標に換算した符号付き横断微分をc₁,c₂、長さをL₁,L₂とする。
新方式は基準行列の第2列だけを

`b = (c₁/L₁ + c₂/L₂) * (L₁/4 + L₂/4)`

へ変更する。第1列は従来と同じSpan微分の平均。
この3×2行列のSVD左逆から**1つの固定投影P**を選び、両側の全セルに使う。
半分の単位方向和に平均長さを掛けているので、基準列の単位は引き続きmm。
この選択が常に最適という主張や、全形状で旧方式以上に成功するという保証はない。
方式を自動切替せず、呼出し側が明示する。

**実際に評価する元微分・ξ幅・Span範囲・セル・marginは変更しない。**
元の接線の長さを消すのは投影選択の段階だけであり、微分包絡では元の長さのまま使う。
同じSpan境界表現の要件、全セルの対称微分下限の正値条件、source/mapping照合、
元領域の被覆、資源上限、分割leafの非集約規則も維持する。

いずれかの横断長が`reference_min_mm`以下なら
`UNRESOLVED/reference_transverse`として未判定に残す。
逆向きの単位接線が打ち消す場合やSpan方向のrank不足も、従来のSVD閾値で未判定となる。
ゼロ除算の回避、擬似逆による救済、閾値緩和や座標移動は行わない。
未知の方式名は入力エラーとする。

全reportに選択した`projection_strategy`を追加した。
既定モデルの旧16継ぎ目と選択32候補を`average`で再実行し、
追加メタデータ以外の全reportが前段の保存結果と一致することを照合した。
設計JSON/CSV/TurboGrid形式・生成アルゴリズム・GUI/出力条件は変更しない。

## 既定モデルの結果

前段と同じpackaged default、fit65、refinements=1、rank閾値1e-12 mm、margin=0、
深度上限4・chart総数上限31で、方式だけを変えて比較した。

固定ξ幅0.01の16継ぎ目では、root条件成立は両方式とも4組。
元境界表現不一致の10組は未判定のまま。
残るTE–SSの2組は新方式でもrootの条件を満たさないが、全leafで個別条件を満たした。

| 群 | 旧root下限 | 新root下限 | 新方式の分割結果 |
|---|---:|---:|---|
| Main TE–SS | −0.078358 | −0.024270 | 9 chart、5 leafで個別条件成立 |
| Splitter TE–SS | −0.114661 | −0.037421 | 7 chart、4 leafで個別条件成立 |

これは`LOCAL_CHARTS_ONLY`であり、rootの`numeric_injective`はFalseのまま。
異なる投影を使ったleaf同士の非干渉を検証したことにはならない。

親セル全域を覆う選択32候補では次の結果となった。

| 群 | 候補数 | 新方式でroot条件成立 | leafのみ条件成立 | 境界不一致 |
|---|---:|---:|---:|---:|
| Impeller Main | 12 | 5 | 1 | 6 |
| Impeller Splitter | 12 | 2 | 1 | 9 |
| Diffuser | 4 | 1 | 0 | 3 |
| RC | 4 | 2 | 0 | 2 |
| 合計 | 32 | 10 | 2 | 20 |

旧方式のroot成功6組は今回も成功。新方式では4組追加でroot条件成立。
leafのみの2組や境界不一致の20組を、期待境界以外の接触がないと扱わない。
すべての接触候補を網羅した検査や、実CADの非干渉証明ではない。
数値的十分条件であり、丸め区間保証・最終面・全翼面の保証フラグはFalseを維持する。

## 検証と残課題

新規24件は、独立した解析的な不等速の折れ面（旧方式未達、新方式の下限`2*L₁/(L₁+L₂)`）、
元微分を正規化しないこと、剛体変換/scale、旧既定方式の一致、未知の方式名、
ゼロ横断/反対方向/Span rank不足、閾値・gap・資源上限、
中央が正でも途中で折返すnegative、分割と候補照合への方式伝達を確認する。
quick63件、関連125件、変更PythonのRuffは成功。

全回帰は2,080一意件成功（通常2,035・実CAD45）。既存2,056 IDを保持し、新規24件を追加。
失敗/error/skip/漏れ/重複/予期しないIDはいずれも0。
通常7群・実CAD1群を選択`.venv`の`tools/run_tests.py`で実行し、全収集IDとJUnitを照合した。
固定344入力のSHA256は検査中不変。原本`blade_v03.json`とpackaged defaultもそれぞれ維持した。
全回帰の証跡は`artifacts/quality-seam-projection/final-test-coverage.json`、
`source-hashes.json`、`collected-tests.txt`、各`group-*.log`に保存している。

調査と比較のローカル証跡は`artifacts/quality-seam-projection/`の
`reference-inspection.json`、`average-default-probe.json`、
`balanced_transverse-default-probe.json`、`strategy-comparison.json`に保存した。
最初の調査補助スクリプトでは投影行列とprojectに同じ変数名を使ったため1度失敗し、
補助スクリプトの名前を分けて再実行した。アプリ・テストの失敗や環境エラーではない。

後続Stage 3B-3lで[異なる局所chart間の全組検査](SEAM_CHART_UNION.md)を追加した。
従来の分割reportは保持し、重複/遠方領域を覆った別の和集合reportとして評価する。
微小gap境界を含む候補の扱いと全候補の集約は引き続き課題。
最終CAD/fillet/STEP、遠い周期翼/包含、丸め保証・全面誤差予算も残る。
native GUI/F5・ANSYS Import/Meshは今回未実行。
