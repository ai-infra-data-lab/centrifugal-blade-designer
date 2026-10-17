# 実経路の対応座標（Stage 3A-2a）

Stage 3A-1の同一座標モデル比較に続き、実際の表示用点と派生カットの対応を読取り専用で調べる。`geometry/surface_correspondence.py`と`tests/test_surface_correspondence.py`を追加した。GUI、形状生成、CAD client、出力処理の呼出し先は変更しない。これはStage 3A-2全体や単一正本への移行の完了ではない。

## 対応座標の契約

| API | 入力と意味 | 制限 |
|---|---|---|
| `cad_curve_coordinates` | 現行CAD clientと同じrole内のm_norm始終端正規化。metadataなしはmaster index | CAD client自体は今回変更しない。非単調・定数mを修復しない |
| `display_master_coordinates` | 実masterのXYZ長による再サンプリング位置をCAD xiへ写す | 表示indexを一律のCAD xiとしない。現在のmasterからのresampleでない表示は拒否 |
| `curve_provenance` | 公称Span、raw index、CAD xi、各点のsource_spanと由来を別々に返す | source_spanがない場合は`nominal_section`。派生元を復元できたと主張しない |
| `trim_index_surface` | 現行trimと同じ最大点数の共通indexへの再標本化とr/theta/Z補間 | CADのm_norm軸と異なる。外径カット後の新TEを復元するものではない |
| `compare_preview_to_spline` | 現行wireframeの同じindexを結ぶXYZ線と指定splineを比較 | 対応点での標本距離。外挿・形状修復・合否判定はしない |

Preview比較では、各表示点に対応するmaster xiを断面ごとに求め、同じ表示indexのxiを公称Span内で線形補間して参照splineを評価する。表示側XYZは`build_spanwise_wireframe`の実点から同じSpanで線形補間する。roleはLE/PS/TE/SS別、主翼とSplitterは別集合とする。返す`max_row_xi_spread`は同じ表示indexの断面間xi差であり、mm単位の誤差ではない。

このxi対応は明示した比較規約であり、流線・法線などの物理的対応の証明ではない。異なる点の対応を採れば測定距離も変わる。Callerは同じ断面・role・CAD接線条件・密度のsplineを渡す必要がある。静翼の汎用spline診断は、静翼CAD出力の対応完了を意味しない。

Rake mapperはmasterと表示を再サンプリング後に別々に剛体回転する。その後にXYZ長を再計算すると浮動小数点丸めが生じるため、resample同一性の確認に`64 × machine epsilon × max(1, master XYZ最大絶対値)`の成分差上限を使う。これは読取り専用診断の入力同一性確認であり、CAD/BREP/fillet/STEPの公差変更ではない。数値差を消すために設計形状を書き換えない。

## 派生形状の追跡と不足情報

Shroudカットは共通indexの各列で元翼のSpanを探索し、その値を`source_span`へ残す。公称Tip=1が元翼のSpan=1を意味するわけではない。独立した円筒補間の解析例と、現行`_span_curve`が返す点を同じ共通index・source_spanで再構成して照合する。

外径カットは既存頂点を残し、末尾交点を補間する。source_spanは保持されるが、**カット前共通indexは別metadataとして保持されていない**。カット後の0〜1 indexを元の0〜1 indexとして扱ってはならない。新TEはPSとSSの端点から機械加工面として生成するため、元TE面との同一点比較は不適切。m_normが定数の新TEはCAD xiへの可逆写像もない。今回この制限を隠すfallbackや出力ガード解除を行わない。

## 正本適用と誤差予算の次の単位

1. 断面master、表示の線、CAD face、trim元面、加工後境界を別の対象IDとして扱う。Stage 2のrow/snapshot識別を維持する。
2. CADとの比較用参照は現行tensor spline＋join接線条件とし、密度を必ず記録する。表示やtrimの生成方式を自動切替えしない。
3. 加工前indexを含む派生由来の内部結果型を検討する。既存JSON項目を増やす必要と、既存派生計算の保存・再生成の互換性を先に確認する。
4. 誤差を「表示サンプリング」「対応規約」「XYZ/円筒/高次のモデル差」「CAD近似」「STEP変換」に分ける。密度513を真値とせず、より密な標本・境界・法線・独立形状で収束を測る。
5. 物理対応と要求精度が定義できた経路から、互換モードと数値回帰を用意して正本を適用する。全経路一括切替えや、新診断値だけを根拠に既存形状を拒否する変更はしない。

現時点では面全域の許容偏差や設計上のPASS閾値を定義していない。今回の標本値をその代わりにしない。全面偏差、Jacobian・法線反転、周期翼や主翼/Splitterの干渉、実モデル根元fillet、native Windows表示、高DPI、ANSYS Import/Meshは別課題として残る。

## 検証記録

新規21件。非等間隔のmaster indexと曲線長、m_normの局所化、入力不変、stale表示拒否、不正対応座標拒否、異なる断面点数を持つ実trim補間、解析的なねじれchord、既定Impeller/Diffuser/RC、Rake＋gap＋専用Splitter、Shroud/外径カット後の由来を確認する。既存の数値fixtureと期待値は変更しない。

初回関連試験は79件成功・新規2件失敗（`20261017T222201Z-ed4ff7a8`）。Rake後の浮動小数点丸めを厳密一致で拒否していた診断を修正し、関連81件成功（42.13秒、`20261017T222310Z-0043acf8`）。その後、実trim再構成の独立解析2件を追加し、新規21件成功（8.84秒、`20261017T222416Z-73f72df7`）。初回失敗を既存形状の不成立とは扱わない。

全回帰と実経路プローブの結果を以下へ記録する。原本`blade_v03.json`、packaged default、設計値、出力ファイルは変更しない。


## 実表示線の標本比較

`artifacts/quality-stage3a2/probe.py`で5条件・主翼/Splitter計28patchを調査した。現行CADのjoin接線条件を用いた数値splineを密度65/129/257/513で構築し、公称Span 21点と全表示Spanwise線を比較した。以下は各条件の最大値。未対応の静翼CADを出力した結果ではない。

| 条件 | 最大距離・密度65 [mm] | 最大距離・密度513 [mm] | 最大断面間xi差（無次元） |
|---|---:|---:|---:|
| 既定Impeller・主翼/Splitter | 0.242960208 | 0.242960032 | 0.0416463 |
| 既定Diffuser | 0.00489323 | 0.00000703665 | 4.39e-15 |
| 既定RC | 0.0100175 | 0.00000841569 | 6.33e-15 |
| Rake12°＋gap0.4/0.8＋専用Splitter | 0.00133617 | 0.00133609 | 3.81e-8 |
| 強ねじれ・3断面β=20/−10/50° | 18.1301811 | 18.1301811 | 0.00301125 |

既定Impellerでは密度を増やしても主翼PSに約0.243 mmの標本差が残る。強ねじれ例の最大差はTEだった。この比較規約では、単なるCAD格子不足だけで説明できない差がある。全形状や要求公差に対する不合格判定ではない。Rake/gap例の標本距離も単調には減らず、Spline密度だけを増やして全経路が一致すると期待してはならない。Stage 3A-1の同一xiモデル間比較とは対象が異なる。

Shroud面積10%＋外径5%カットの派生Tipは、公称Span=1でも元翼source_spanが主翼約0.891817〜0.895833、Splitter約0.891817〜0.893781となった（PS/SS/LE標本）。この由来と加工後公称Spanを区別する。カット後の新TEを元TEとの一致試験へ混ぜない。詳細値・129/257密度結果は`artifacts/quality-stage3a2/probe.json`に保存した。


## 最終全回帰

**1,049一意件成功**（通常1,012・実CAD37）。既存1,028 IDを全て維持し、新規21 IDを追加した。failure/error/skip/実行漏れ/重複/想定外IDは0。回帰開始時に固定した246入力（package/test Python、main、既定JSON、原本JSON）は終了時までhash不変で、原本と既定JSONの一致も確認した。既存数値fixture・期待値は変更していない。

単一processではなく7群で実行し、収集IDとJUnitを照合した。根拠は`artifacts/quality-stage3a2/final-test-coverage.json`、`source-hashes.json`、`groups.json`。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 396.466 | 20261017T222457Z-2ebbdc41 |
| 通常1 | 143 | 357.272 | 20261017T222457Z-4b6b6e43 |
| 通常2 | 122 | 413.955 | 20261017T222457Z-8ab4d543 |
| 通常3 | 191 | 292.178 | 20261017T222457Z-8f3ad74f |
| 通常4 | 146 | 384.104 | 20261017T222457Z-9a18b91f |
| 通常5 | 294 | 424.232 | 20261017T222457Z-c71fa076 |
| 実CAD | 37 | 827.985 | 20261017T222457Z-10634990 |

実OCCT試験の成功は、現既定形状の根元フィレット成立・全面の形状一致・native Windowsの操作・ANSYS Import/Meshの成功を意味しない。今回追加した診断はGUIから自動実行する品質ゲートではなく、数値APIと再現プローブとして提供する。
