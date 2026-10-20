# 接触候補と継ぎ目領域の対応付け（Stage 3B-3j）

## 元領域と識別値の照合

`geometry/seam_contact_refinement.py::local_seam_pair_injectivity`は、
記録済みのmerged-role envelopeと2つのface IDから元role・Span/ξセルへ戻す。
mesh/座標軸/face順のmapping fingerprintと、選択した元splineのfingerprintを照合する。
古いreport、変更済みのsourceやmapping、同じface、shared-IDのない組、
同じroleや宣言されていないrole対、宣言端点まで達していない元セルは拒否する。

4つの宣言継ぎ目の向きへ組を並べ直す。入力IDの順番は`query_faces`に残す。
Span範囲は**両方の親セルの全域を含むunion区間**、各側のξ幅は**親セルの全幅**。
source triangleの対角半分を含む、より大きい矩形の十分条件を調べる。
条件を通すために接点近くだけへ幅を狭めたり、不都合な領域を捨てたりしない。
元係数をsnapshotし、実形状・診断mesh・既存接触reportを変更しない。

最初の共通chartが条件を満たす場合に限り、
`expected_parameter_contact_only=True`とする。
これは記録された元領域間の数値的十分条件であり、merged meshの交差状態、
既存品質判定、出力許可条件、他の候補の結果を上書きするものではない。
元境界表現が一致しないものは、meshが微小差をmergeしていても未判定になる。

## 分割診断の契約

`subdivide_seam_neighborhood`は、[共通chart診断](SEAM_INJECTIVITY.md)のroot範囲が
rank不足または強単調性の下限未達の場合だけ、Span区間を中央で二分して再評価する。
各子では両側のξ幅と閾値を保ち、その子の全域に1つの投影を固定する。
rootで成功した領域は再分割しない。境界表現不一致やセル資源上限は分割で隠さない。

| 結果 | 意味 |
|---|---|
| `NUMERIC_INJECTIVE_ON_JOINED_CHART` | rootの1つの投影で要求全域の十分条件成立 |
| `LOCAL_CHARTS_ONLY` | root未達だがすべてのleafで個別条件成立。和集合の単射性は未判定 |
| `UNRESOLVED` | 境界不一致、深度上限、非正値/rank不足等がleafに残る |
| `RESOURCE_LIMIT` | chart総数または個別chartのセル上限に達した |

`numeric_injective`はrootの結果だけを表す。
`all_leaves_numeric_injective`をrootや接触候補の成功へ昇格させない。
異なる投影で証明したleaf同士には重なり得るため、`cross_chart_pairs_checked=False`。
局所条件の成立は丸め区間保証・全翼面・solid包含・最終CADの安全判定ではない。
`whole_geometry_verified/continuous_surface_certified/roundoff_certified`はすべてFalseのまま。

`charts`には親子index・深さ・領域・投影・各セル下限を保存し、
`leaf_indices`と`stop_reasons`から未判定の位置と理由を追跡できる。
分割できないleafを残すので、上限に達しても領域の穴や黙った切捨てを作らない。
`max_depth=0..8`、`max_charts`はrootを含む全評価回数の上限（既定31）。
`max_cells`は個別chartの上限であり、全体には最大`max_charts * max_cells`のセル予算がある。
分割境界がfloat64で表現できない場合もleafを未判定のまま残す。

## 既定モデルでの試行

packaged defaultのImpeller Main/Splitter・Diffuser・RCを既存生成器で生成し、
既存CAD参照のfit65を使った。元JSON・元制御点・生成方法は変更していない。

まず前段と同じ16継ぎ目（Span全域・ξ幅0.01ずつ、refinements=1）を
最大深度4・最大31 chartで評価した。rank閾値1e-12 mm・margin=0を固定した。
4組はroot条件成立、10組は元境界表現不一致のため分割しない。
Main TE–SSとSplitter TE–SSはそれぞれ31 chart・16 leafまで評価したが、
いずれのleafも条件未達で、16箇所の`max_depth`を記録した。
分割だけでは解決しなかったという結果を保ち、実交差とは断定しない。

次に既存`.03 mm`誤差envelopeの継ぎ目にある共有edgeのface対を選び、
各継ぎ目のHub側・中央・Tip側セルを試行した。
静翼はSpanセルが1つなので重複選択せず、各4組だけとなる。
これは選択した32組の試行であり、全接触候補の網羅検査ではない。
この試行ではface選択とsource/mapping識別値も記録している。

| 群 | 試行face対 | root条件成立 | 境界表現不一致 | 下限未達 |
|---|---:|---:|---:|---:|
| Impeller Main | 12 | 3 | 6 | 3 |
| Impeller Splitter | 12 | 0 | 9 | 3 |
| Diffuser | 4 | 1 | 3 | 0 |
| RC | 4 | 2 | 2 | 0 |
| 合計 | 32 | 6 | 20 | 6 |

証跡は`artifacts/quality-seam-candidates/probe.py`、`default-probe.json`に保存した。
試行候補の幅は各親セルから決まり、固定ξ幅0.01の16組とは異なる。
成功数を混ぜたり、未判定候補を元の接触reportから消したりしない。

## テストと残課題

新規35件で、root成功時の停止、異なる投影で子だけが成功する解析的shear、
深度/総chart数/個別セル上限、欠損しない領域被覆、微小gapの非修正、
候補IDの正逆順と4宣言継ぎ目、元領域全体の被覆、source/mapping変更の拒否、
旧report・不正ID・内部セルの拒否、既存report/sourceの不変を確認した。
quick63件、関連143件、変更PythonのRuffは成功。

全回帰は2,056一意件成功（通常2,011・実CAD45）。既存2,021 IDをすべて保持し、新規35件を追加。
失敗/error/skip/漏れ/重複/予期しないIDはいずれも0。
通常7群・実CAD1群を選択`.venv`の`tools/run_tests.py`で実行し、全収集IDとJUnitを照合した。
固定343入力のSHA256は検査中不変。原本`blade_v03.json`とpackaged defaultもそれぞれ維持した。
全回帰の証跡は`artifacts/quality-seam-candidates/final-test-coverage.json`、
`source-hashes.json`、`collected-tests.txt`、各`group-*.log`に保存している。

初回の関連試験では、mappingを変えるはずの新規テストが元と同じ値0を代入し、
期待した例外が発生しない1件の失敗となった。
新規fixtureを実際に値が変わる操作へ直して再実行した。
既存fixture・実装の例外条件・期待する拒否動作は緩和していない。環境エラーは発生していない。

次は未達となる共通投影と片側微分の関係を調べ、十分条件の選択方法を検討する。
異なる局所chart間の非干渉、微小gap境界の扱い、全候補の集約規則と丸め保証も残る。
最終CAD/fillet/STEP・遠い周期翼/包含の照合は別課題。
GUI/保存/出力条件へは未接続であり、native GUI/F5・ANSYS Import/Meshは今回未実行。
