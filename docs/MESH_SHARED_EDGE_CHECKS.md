# 共有edgeの接続と局所重なり（Stage 3B-2a）

前段の三角形接触候補では、同じrole内で1/2頂点IDを共有する面をすべて除外していた。そのうち**2頂点IDを共有するedge隣接面**を調べる明示的な追加モードを実装した。既定は従来どおり無効で、旧試験/数値参照は変更しない。元の形状生成・通常表示・CAD生成・保存/出力形式・出力ガードには接続しない。

## 使い方と互換性

```python
report = mesh_contacts(vertices, faces,
                       tolerance_mm=1e-9, area_epsilon_mm2=1e-16,
                       check_shared_edges=True)

report = screen_blade_grids(main_grids, blade_count,
                           splitter=splitter_grids,
                           tolerance_mm=1e-9, area_epsilon_mm2=1e-16,
                           check_shared_edges=True)
```

`geometry/mesh_adjacency.py`が共有edgeの幾何関係とedge incidenceを担当する。`mesh_contacts`が既存BVHの組ごとに呼び、`blade_contacts`は各roleの自己検査にだけモードを渡す。別のmesh間で同じindex値でも同じ頂点とは扱わない。low-levelで別meshを指定したまま追加モードを有効にするとValueError。モード値はPython boolに限る。

`check_shared_edges=False`の検査対象・既存結果フィールドは維持し、診断情報だけを追加した。`True`でも、入力頂点のweld/移動・面向きの修復・再分割・代替形状の生成は行わない。`tolerance_mm`は既存の明示投影許容量をそのまま使い、別の隠れた角度公差を設けない。上例の閾値は測定用で、CADや製造の合否公差ではない。

## 共有edgeの幾何関係

共有edgeをE、各面の第3頂点からEへの垂直ベクトルをp/qとする。

1. Eの長さ、またはp/qの長さが`tolerance_mm`以下なら、位置関係を絞れないとして**UNRESOLVED**にする。有限な面でも短すぎることがあり、接続正常/接触なしに置き換えない。
2. 両面の単位法線を使い、第3頂点から相手面までの距離を双方向に測る。どちらかが許容量を超えていれば異なる平面として**EXPECTED_EDGE**にする。
3. 両距離が許容量内なら近接同一平面の帯域として扱う。p/qの内積が正なら**OVERLAP_CANDIDATE**、それ以外なら**EXPECTED_EDGE**にする。

非退化の2三角形がedgeを共有する場合、異なる平面の交線は共有edgeの直線であり、各三角形のその直線上の部分は共有edgeに限られる。同一平面で第3頂点がedgeの反対側なら共有edgeだけ、同じ側なら正の面積で重なる。この実数モデルの性質を利用する。面の頂点並びを反転しても幾何関係は変えない。面の向きが外向きであることやdihedral角の設計上の適否は検査しない。

非零許容量では、実際にはわずかに異なる平面でも近接帯域へ入る。そこでの候補は実交差/貫通の確定ではない。float64の丸めを保証する述語ではなく、`roundoff_certified=False`のまま。連続曲面の保証へも置き換えない。

## edge incidenceと不完全性

有効な非退化faceからedge→元face IDの対応を作り、1edgeに3面以上が集まる箇所を記録する。境界edge（1面）は許容し、2面の接続もそれだけで異常にしない。退化faceは前段どおり記録して走査を不完全にし、incidenceには混ぜない。非有限な中間演算は既存と同じValueErrorで中止する。

3面以上のedgeは、すべての2面組が共有edgeだけで接続していても**INCOMPLETE**に残す。これは閉鎖/向き/全vertex link/solid妥当性を保証するmanifold検証ではない。1頂点で別の面群が接続するbow-tie等は未検査である。

各reportに`adjacency`を追加した。

- `enabled`、`checked_shared_edge_pairs`、`expected_shared_edge_pairs`、`overlap_candidates`。
- `unresolved_count`と元face ID組の`unresolved_examples`。未判定例は`max_contacts`まで保存し、超えれば`unresolved_examples_truncated=True`。走査した範囲の件数は保持する。
- `nonmanifold_edge_count`、edgeの頂点ID/face件数/face例。モード無効ではcountはNoneで、検証済み0にしない。edge例と各face例も`max_contacts`以内で、全件数と例数を区別する。
- `vertex_neighbor_pairs_excluded`と`vertex_links_checked=False`。

接触候補の`contact_pairs`には従来のSAT候補と共有edge重なり候補を保存し、同順の`contact_kinds`で理由を区別する。共有edgeの分類はSAT候補とは別の処理なので、`aabb_candidates`は従来どおり非隣接SAT用候補の件数。モード有効時の`adjacent_pairs_excluded`は1頂点だけの隣接組で、正常edgeを検査せず除外した件数ではない。

未判定や3面以上のedgeがあれば`scan_complete=False`、上位の`incomplete_checks`にも伝える。観測した重なり候補があればCONTACT_CANDIDATES_FOUNDを優先して返すが、不完全性を消さない。正常edgeの件数が多いだけでPASSとはしない。計算/候補上限での打切りも従来どおり不完全。edge incidenceの前処理は`max_work`に含まれず、既存のtriangle数上限で制限する。

## 検証

新規32件。正常な平面の反対側接続、異なる平面、同じ側の面積重なり、正の尺度0.01/1/100・剛体変換・頂点順反転、近接同一平面の候補帯域、短edge/短高さの未判定、3面以上のedge、退化face、例数の上限、既存work/contact打切り、重複face、元座標不変と上位伝播を確認する。

3×5格子では内部edge数が8対角線+6+4=18となり、BVHで各組を一度だけ検査することを解析的に確認した。1頂点だけの隣接組は除外が残ることも記録する。前段の「共有edgeの同じ側に折り返す」negativeは、旧試験を変えずに維持し、新しいモードでは候補へ変わることを別試験で確認した。

関連86件成功（`20261018T083527Z-fa0a9f79`）、限定Ruff成功。

## 現既定形状での確認

同梱既定のrow-1/Impeller（主翼11枚、Main/Splitter×4role）を基準spline fit65で固定し、前段と同じ閾値1e−9 mm/1e−16 mm²、work200,000/候補20をcheckごとに指定した。

| Span×xi | 追加モード | check数 | 共有edge組を検査 | 正常edge | 重なり候補 | 未判定 | 3面以上のedge | 不完全check |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 5×33 | False | 88 | 未検査 | — | — | — | 未検査 | 0 |
| 5×33 | True | 88 | 2,784 | 2,784 | 0 | 0 | 0 | 0 |
| 9×65 | True | 88 | 11,712 | 11,712 | 0 | 0 | 0 | 0 |

全体のSAT/edge候補も3ケースとも0。Falseの5×33は前段の保存済み88checkと照合し、**従来存在した全フィールドが一致**した。追加フィールドはこの比較から除く。Falseの9×65は今回再測定していないので、その個別一致を今回の検証済み結果とはしない。

共有edgeを有効にして残る1頂点だけの除外数は5×33で7,240、9×65で32,872。全体のworkは83,194/481,988で、edge関係の追加計算を実時間へ反映する一方、workの定義は従来のnode/face組の列挙回数のまま。これらの候補0/正常edge数は明示triangle範囲の数値診断であり、元曲面や全体の干渉なしを示さない。

3ケース合計の壁時計は全回帰と同時実行で236.797秒。単独性能やGUI応答性の保証ではない。根拠は`artifacts/quality-mesh-adjacency/probe.py`、`default-probe.json`。row/source hash・格子・モード・全checkと旧フィールド一致を保存した。原本/同梱既定のSHA256は`aa724c8253463289caec919960d7d486d698765cee35202c13e4efd17a603dd6`で、書込みは行わない。

## 全回帰の確定記録

**全1,350一意件成功**（通常1,307・実CAD43）。既存1,318 IDを維持し、新規32 IDを追加した。failure/error/skip/実行漏れ/重複/想定外IDは0。検証開始時に固定した288入力はhash不変、原本/同梱既定JSONも一致した。既存試験の期待値・数値fixtureは変更していない。限定Ruffも成功。

根拠は`artifacts/quality-mesh-adjacency/final-test-coverage.json`、`source-hashes.json`、`collected-tests.txt`。通常6群と実CAD1群のJUnitを全収集IDと照合した。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 464.080 | 20261018T083617Z-13a3ac61 |
| 通常1 | 143 | 412.779 | 20261018T083617Z-c1d2f195 |
| 通常2 | 122 | 478.840 | 20261018T083617Z-f12b876a |
| 通常3 | 191 | 347.064 | 20261018T083617Z-30b24b2b |
| 通常4 | 146 | 449.453 | 20261018T083617Z-ea4b2547 |
| 通常5 | 589 | 575.728 | 20261018T083617Z-fdd3bf9d |
| 実CAD | 43 | 922.029 | 20261018T083617Z-788e218d |

実CAD43件は既存回帰であり、今回の共有edge診断と実solidの交差を照合した試験ではない。これを既定根元fillet成立・ANSYS Import/Mesh成功へ置き換えない。

## 未完了の範囲

1頂点だけで接する面・vertex link、異なるrole間の正常継ぎ目/異常交差、遠い周期コピー、完全包含、曲面–triangle誤差/適応細分、cap/fillet/STEPと実solidの照合。GUI/出力ゲートは未接続。native GUI/高DPI、ANSYS Import/Meshは未検証。Stage 3B全体や既定根元fillet成立を完了とはしない。
