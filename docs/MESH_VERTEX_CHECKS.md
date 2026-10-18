# 共有頂点だけの局所接触とvertex link（Stage 3B-2b）

## 契約と変更範囲

`mesh_contacts(..., check_shared_edges=True, check_shared_vertices=True)`と
`screen_blade_grids(..., check_shared_edges=True, check_shared_vertices=True)`を明示して使う。
両flagはPython boolのみ。vertex検査にはedge検査が必要で、mesh入口ではself checkだけが対象。
blade入口では4roleそれぞれのself checkだけに適用し、別meshの同じindexは同一頂点と扱わない。
既定Falseとedge-onlyモードの既存フィールド値・検査範囲は維持し、結果にvertex情報を追加した。
生成・GUI・設計値・原本/同梱既定JSON・保存/出力ゲートは変更しない。

```python
report = mesh_contacts(
    vertices, faces, tolerance_mm=1e-9, area_epsilon_mm2=1e-16,
    check_shared_edges=True, check_shared_vertices=True,
)
# statusだけでなくscan_completeと未検査範囲も読む。
local = report["vertex_adjacency"]
```

上の公差は例であり、任意形状に推奨する製造公差ではない。

## 幾何と位相を分ける

`geometry/mesh_vertex_adjacency.py::_vertex_relation`は、1頂点Oだけを共有する2三角形を扱う。
三角形は凸なので、O以外にも交差するならOから伸びる共通線分を持つ。
Oから各三角形の2辺ベクトルが作るconeを調べる。
異なる平面では法線外積の正負2方向、同一平面の帯域では4本の辺方向を調べる。
共通方向の係数a,bと辺長L0,L1から、三角形内の半径距離を
`1 / (a/L0 + b/L1)`で求める。共通線分がtoleranceを超えれば
`shared_vertex_overlap_candidate`、短い線分や短辺/短高さ・不安定な方向は未判定とする。

`tolerance_mm`は既存SAT/edgeと共通の明示値で、同一平面の帯域・辺長による角度allowanceにも使う。
近接平面は片側平面へ投影するため、候補は厳密な交差証明ではない。
float64丸めは未保証。`EXPECTED_VERTEX`はこの数値モデル内の点接続という意味に限る。
非有限演算は例外として返し、正常結果に置き換えない。

`_vertex_links`は有効な各三角形から、頂点の向かい側のedgeを集める。
内部頂点のlinkは単一のsimple cycle、境界頂点は単一のsimple pathであることを調べる。
分断・3本以上への分岐・重複link edgeを非多様体頂点として数える。
未使用頂点は対象外。退化三角形は除外し、その退化は元のレポートで不完全にする。
座標welding・頂点順修復・外向き法線判定・閉solid判定は行わない。

2枚の面が1頂点で接するだけでも、独立した2つのfanならlinkは分断される。
この場合、幾何分類は正常な点接続でもscanは不完全となる。
幾何候補、位相不良、未判定を同一の不具合と解釈しない。

## レポートと資源上限

追加の`vertex_adjacency`へ、検査組数、点接続数、候補数、未判定数と例、
link検査有無、非多様体頂点数と例を保存する。
既存`adjacency.vertex_links_checked`も明示モード時だけTrueとなる。
未判定または非多様体頂点があれば`scan_complete=False`。
候補がある場合のstatusは従来同様`CONTACT_CANDIDATES_FOUND`を優先し、
不完全な場合も`scan_complete`を別途確認する。

BVHのwork/contact上限は従来のまま。link前処理はwork_unitsの対象外で、
`max_triangles`（各patch既定20,000）に制約される。
例の保存は`max_contacts`で制限し、総数は省略せず記録する。
未判定例の切詰めは明示flag、位相例は総数と例数の差で確認する。

## 独立解析テスト

`tests/test_mesh_vertex_adjacency.py`の新規31件：平面/非平面の点接続と線分/面の重なり、
同じ座標の別index、回転・並進・尺度・winding、短高さ/短線分、近接平面の候補、
regular格子のpath/cycle、tetrahedronのcycle、分断fan、分岐・重複link、退化除外、
例数/資源上限、flag型と前提条件、blade入口への伝播、従来モードの除外を確認。
3×5格子はedge18組・vertex-only35組を正常とし、候補/位相不良なし。
既存86件と合わせ関連117件成功、限定Ruff成功。

初回の新規短線分テストは想定と異なり、45度方向の共通長がtoleranceを超えて失敗した。
解析で境界方向を絞ったfixtureへ直し、tolerance未満の共通長を確認した。
既存テスト期待値・数値fixtureは変更していない。

## 既定形状と全回帰

原本/同梱既定のSHA256:
`aa724c8253463289caec919960d7d486d698765cee35202c13e4efd17a603dd6`。
`row-1 / Impeller / impeller`、主翼枚数11、Main/Splitterの4role基準面（fit65）、
一様Span/xi格子で、各88checkを実行した。tol=1e-9 mm、area threshold=1e-16 mm²、
max_work=200,000/check、max_contacts=20/check。

| 格子 | vertex検査 | edge正常組 | vertex正常組 | 候補/未判定/link不良 | work units |
|---|---|---:|---:|---|---:|
| 5×33 | off（edge-only） | 2,784 | 未検査 | 候補0、未判定0、link未検査 | 83,194 |
| 5×33 | on | 2,784 | 7,240 | 0 / 0 / 0 | 83,194 |
| 9×65 | on | 11,712 | 32,872 | 0 / 0 / 0 | 481,988 |

全ケースのincomplete checkは0。旧edge-onlyの5×33について既存フィールドが
前回の記録と再帰的に一致することを確認した（追加キーは許可）。
3ケースの合計284.032秒は全回帰と並行した壁時計で、単独性能やnative GUI応答時間ではない。
根拠は`artifacts/quality-mesh-vertex/probe.py`と`default-probe.json`。
格子座標を検査するだけで、原本・生成値・CAD公差は変更していない。

**全1,381一意件成功**（通常1,338・実CAD43）。既存1,350 IDを維持し、新規31 IDを追加。
failure/error/skip/実行漏れ/重複/想定外IDは0。
検証開始時に固定した290入力はhash不変、原本/同梱既定JSONも一致した。
前回の固定288入力との比較では既存のmesh/blade診断入口2ファイルだけが変わり、
新helperと新テストを追加。既存テスト入力・数値fixtureはすべて不変。
限定Ruffも成功した。

根拠は`artifacts/quality-mesh-vertex/final-test-coverage.json`、`source-hashes.json`、
`input-change-audit.json`、`collected-tests.txt`と各群のraw log/JUnit。
通常6群と実CAD1群の全IDを照合した。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 475.821 | 20261018T090853Z-23a4b199 |
| 通常1 | 143 | 427.329 | 20261018T090853Z-733580c0 |
| 通常2 | 122 | 491.559 | 20261018T090853Z-6b81ab0f |
| 通常3 | 191 | 356.724 | 20261018T090853Z-e0f7574a |
| 通常4 | 146 | 458.220 | 20261018T090853Z-05b92619 |
| 通常5 | 620 | 584.192 | 20261018T090853Z-4ae24a51 |
| 実CAD | 43 | 930.218 | 20261018T090853Z-a8101602 |

実CAD43件は既存回帰であり、新規のvertex診断と実solidの交差を照合した試験ではない。


## 残る範囲

異なるrole間の正常継ぎ目と異常接触、遠い周期コピー、完全包含、
曲面–triangle誤差・適応細分、cap/fillet/STEP・最終solidとの照合は未完了。
幾何の全体PASSや出力ゲートとして使用しない。実CAD回帰は実solidとの一致の証明ではない。
native GUI/高DPIとANSYS Import/Meshは未検証。Stage 3B全体と既定根元fillet成立は未完了。
