# 近似誤差を含む2面間の接触・近接診断（Stage 3B-3d）

## 対象と使い方

`geometry/error_aware_contacts.py::error_aware_mesh_contacts`を追加。
独立した2つの三角形meshと、各三角形に対応する元面の位置誤差上限を受け取ります。
形状生成・設計値・GUI・JSON・既存出力条件は変更せず、自動出力ゲートには適用しません。
Qt・OCP・ファイル形式に依存しません。

```python
from blade_designer.geometry.error_aware_contacts import error_aware_mesh_contacts

# a, b は merged_role_error_envelope の結果。mesh があることを先に確認。
ma, mb = a['mesh'], b['mesh']
report = error_aware_mesh_contacts(
    ma['vertices'], ma['faces'], a['merged_triangle_upper_mm'],
    mb['vertices'], mb['faces'], b['merged_triangle_upper_mm'],
    clearance_mm=0.0, area_epsilon_mm2=1e-16,
    max_work=500000, max_records=100, max_triangles=20000,
)
```

mm単位のXYZと誤差を使います。上記数値は製造・解析公差の推奨値ではありません。
周期コピーはcallerが第2meshを剛体回転して渡します。剛体変換で誤差上限は不変です。
尺度変更ではXYZ・誤差・clearanceを同じ比率、面積閾値をその2乗で変更します。

誤差は1三角形につき1値の有限・非負ベクトルで、暗黙のscalar broadcastはしません。
単なる頂点の測定誤差や標本誤差ではなく、対応する**元面の全patch**を覆う上限が必要です。
結合済みmeshには[結合移動を加えた上限](MERGED_ROLE_ERROR.md)を渡します。
`error_bounds_assumed_valid=True`はこのcaller前提を明示する値であり、与えた上限を元面と照合したという意味ではありません。
上流の目標未達でも保守的な有限上限が存在すれば利用可能ですが、上流の状態を成功へ変更しません。
資源上限・継ぎ目不一致でmeshがないときは呼び出せません。

## 分離の式

三角形A、Bと単位軸nについて、投影区間の正のgapは、三角形間のEuclidean距離の下限です。
Cartesian軸、面法線、辺の外積、同一平面用の法線×辺を調べ、その最大値をLとします。
Lは距離の**下限**であって、最近接点間の正確な距離ではありません。

対応する元面の誤差をEa、Eb、要求距離をc≥0とすると、三角不等式から

`distance(sourceA, sourceB) >= distance(A, B) - Ea - Eb >= L - Ea - Eb`

です。したがって`L > Ea + Eb + c`のときだけ、その組を数値上分離とします。
等号は分離扱いせず未判定です。従来SATの投影公差をEuclidean距離に流用しません。
投影前に共通原点を差し引きますが、float64の丸めを区間保証する処理ではありません。

各AABBをそれぞれ`E + c/2`だけ各座標方向へ拡大し、既存BVHの走査を使います。
この箱はEuclidean誤差球を包含します。拡大箱が重ならない部分木は同じ不等式で分離でき、
元箱が離れているだけの組を誤差を無視して落としません。
BVHを通った組も改めて投影下限と**その2三角形の**誤差和を比較します。
一律の最大誤差への置換や座標修復・再fit・公差緩和は行いません。

## 状態と不完全性

| 状態 | 意味 |
|---|---|
| `NUMERIC_SEPARATED` | 全走査完了、退化なし、全対象組が誤差と要求距離を含めて数値上分離 |
| `UNCERTAIN` | 完全走査だが、正の投影gapが誤差和＋要求距離を超えない組がある |
| `CONTACT_CANDIDATES_FOUND` | 投影で分離できない三角形の接触候補がある。元面の衝突確定ではない |
| `INCOMPLETE` | 接触候補がない場合でも、退化や走査上限で完了できない |

接触候補があればその状態を優先しますが、`scan_complete=False`を隠しません。
`numeric_separated=True`は全走査完了かつ候補/未判定なしの場合だけです。
`records`は元face ID、分類、投影下限、必要下限（Ea+Eb+c）を返します。
`max_records`到達は上限打切りとし、最終候補だった可能性があっても完了扱いにしません。
件数は検査済み範囲の件数で、打切り時の総数ではありません。
`explicitly_separated_pairs`も実際に投影評価した組数のみで、BVH枝刈り分を含みません。
全体の最小距離・最接近組は返していません。

`max_triangles`はmeshごとの上限です。`max_work`はBVH節点と三角形組の走査に適用します。
退化三角形は元IDを列挙し、その組を未検査のまま不完全とします。
非有限・型不正・算術overflowはValueErrorで、分離成功へ変換しません。
両meshの同じ頂点IDは別の頂点として扱い、共有IDによる除外はありません。

## 今回保証しないこと

`roundoff_certified`・`continuous_surface_certified`・`whole_geometry_verified`は常にFalse。
近似誤差を考慮した数値診断であり、厳密な連続曲面非干渉証明ではありません。
同じmeshを両引数へ渡せば対応三角形自身も接触候補になります。自己隣接・role継ぎ目の
期待接続を除外するAPIではなく、`self_adjacency_checked=False`を明示します。
遠い周期コピー・全周自動探索、solid包含、cap/wall/disk/fillet、最終CAD/STEP面との照合、
物理Span対応、法線の向き、元面の局所Jacobian成立は別の検査が必要です。
既存mesh_contacts・blade_contacts・role診断の動作や結果fieldは変更していません。

## 検証

新規35件：平行平面の解析解、誤差なしmeshでは候補なしでも元面が接触し得るnegative、
要求clearanceと等号境界、同一平面/非同一平面接触、距離下限と正確な距離の区別、
剛体変換・尺度・引数順、退化/走査/記録上限、三角形別誤差と元ID、型/範囲/overflow、
結合済みrole meshと誤差の直接接続・入力不変、12×12全組の独立列挙とBVH結果一致を確認。
関連90件成功、限定Ruff成功。既存テスト・数値fixture・原本JSONは変更していません。

同梱既定fit65、三角形誤差目標0.02 mm、join tol=1e-8 mm、要求clearance=0 mm、
各組max_work=50,000/max_records=100で試行しました。全7組が`NUMERIC_SEPARATED`で完了し、
未判定・接触候補・退化・打切りはありませんでした。誤差上限自体は前段で目標以下を確認しています。

| 対象 | 周期offset | 投影を評価した三角形組 | 結果 |
|---|---:|---:|---|
| Impeller Main–Main | +1 | 0 | 数値分離 |
| Impeller Splitter–Splitter | +1 | 0 | 数値分離 |
| Impeller Main–Splitter | 0 | 70 | 数値分離 |
| Impeller Main–Splitter | −1 | 0 | 数値分離 |
| Impeller Main–Splitter | +1 | 72 | 数値分離 |
| Diffuser Main–Main | +1 | 0 | 数値分離 |
| RC Main–Main | +1 | 0 | 数値分離 |

0組は拡大AABBで分離できたもので、検査未実施をPASSにしたものではありません。
ただしこの7組以外や自己接続の分離・連続曲面・最終CADの保証へ拡張しません。
試行は`artifacts/quality-error-contact/probe.py`・`default-probe.json`に保存しています。

同じ既定Impeller Mainを1000枚相当のピッチ（2π/1000）で比較する異常試行では、
`CONTACT_CANDIDATES_FOUND`、接触候補44・未判定56で100記録上限に到達し、
`scan_complete=False`・`stop_reason=max_records`となりました。分離済みにはしていません。
件数は打切りまでの観測値で、総干渉数や物理的な衝突確定数ではありません。
記録は`crowded_probe.py`・`crowded-probe.json`です。設計JSONの枚数は変更していません。

全回帰は**1,845一意件成功**（通常1,800・実CAD45）。既存1,810 IDを維持、新規35 ID。
失敗/error/skip/実行漏れ/重複/想定外IDは0、固定330入力のhashは不変。
通常7区分と実CAD1区分をproject runnerで実行し、全収集IDと実行IDを照合しています。
収集/実行IDと固定入力hashは`artifacts/quality-error-contact/final-test-coverage.json`・
`source-hashes.json`・`collected-tests.txt`へ記録しました。
基礎63件・最終関連90件・限定Ruff・差分検査も成功。テストの環境エラーはありません。
CAD45件は既存出力経路の回帰で、新APIが最終CAD面を検査したという意味ではありません。
native GUI/F5・ANSYS Import/Meshは今回未実施です。

変更は新しい診断API・新規テスト・本書・FEATURES・ARCHITECTURE・DEVELOPMENT_ROADMAP・
MERGED_ROLE_ERRORの計7ファイル。既存設計アルゴリズム・GUI・出力・数値fixture・
原本/同梱既定JSON・親フォルダの家計簿は変更していません。

次は誤差を含めた自己接続近傍の扱い、未判定組の局所細分・再評価、遠い周期コピーと包含、
最終CAD照合を順に扱います。共通品質レポート/出力ゲートの採用はその後に判断します。
