# 近似誤差と自己接続近傍の診断（Stage 3B-3e）

## 今回の変更範囲

`geometry/error_aware_self_contacts.py::error_aware_self_contacts`を追加しました。
1つのmeshの異なる三角形組を、共有辺・共有頂点・非局所に分けて診断します。
既存生成・GUI・設計値・JSON・出力ゲートは変更しません。
Qt・CAD kernel・ファイル形式への依存はありません。

```python
from blade_designer.geometry.error_aware_self_contacts import error_aware_self_contacts

# envelope = merged_role_error_envelope(...) の結果。meshがあることを先に確認。
mesh = envelope['mesh']
report = error_aware_self_contacts(
    mesh['vertices'], mesh['faces'], envelope['merged_triangle_upper_mm'],
    clearance_mm=0.0, adjacency_tolerance_mm=1e-9, area_epsilon_mm2=1e-16,
    max_work=500000, max_examples=100, max_triangles=20000,
)
```

XYZ・位置誤差・clearance・接続診断許容幅はmm、面積閾値はmm²です。
例の閾値は製造公差の推奨値ではありません。誤差は三角形順の有限・非負ベクトルです。
対応する元面patch全体を覆い、継ぎ目の移動も含む必要があります。
`error_bounds_assumed_valid=True`はcallerの前提であり、元面を照合したという意味ではありません。
meshがない上流の不成立結果を、部分meshや粗い代替へ置き換えません。

## 三角形の正常接続と元面の未判定を分ける

共有する頂点IDが2個なら既存`_edge_relation`、1個なら`_vertex_relation`で
三角形の接続・局所重なり候補・幾何的未判定を分類します。
同一座標でもIDが異なる頂点は共有接続にせず、空間weldingは行いません。
3個共有は重複faceの接触候補です。
3面以上の辺とvertex linkの分断・分岐・重複も既存の独立診断を使います。
境界辺と単純な境界linkは許容し、閉solidの成立判定はしません。

正常な接続では三角形間距離が0です。位置誤差上限Ea/Ebが正なら、
元曲面は共有部の近くで誤差範囲内の折返し・重なりを持つ可能性があります。
位置上限だけでは局所単射性や、元面の継ぎ目が本当に一致することを証明できません。
そのため正常三角形接続でも`Ea+Eb>0`は`LOCAL_SOURCE_UNCERTAIN`と記録します。
誤差が両方0の正常接続だけを数値上の期待接続として受理します。
誤差を0に丸める、近傍の候補を黙って除外する、Jacobianの点標本を全面証明とみなす処理はありません。

位置上限だけでは不足する独立した例として、基準平面を`(s,t,0)` [mm]、
元面を`(s+0.01*sin(200πs),t,0)` [mm]（s,tは0–1）とします。
位置差は常に0.01 mm以下ですが、s方向微分は`1+2π*cos(200πs)`で符号が変わり、
局所退化と折返しが生じます。これは位置誤差から単射性を推論できない理由の解析例で、
同梱既定形状にこの折返しを観測したという意味ではありません。

`expected_edge_pairs`・`expected_vertex_pairs`は三角形の正常接続数です。
`local_error_uncertain_pairs`はそのうち元面が未判定の数で、**前者の内数**です。
`local_relation_unresolved_pairs`は短辺/高さなどで三角形の関係自体が未判定の別の数です。
三角形の折返し等は`local_contact_candidates`として誤差の有無にかかわらず残します。
これは元面の物理的衝突確定数ではありません。

## 非局所の組と資源管理

頂点IDを共有しない組は、[独立2meshの診断](ERROR_AWARE_CONTACTS.md)と同じ単位軸投影gap下限Lを用い、
`L > Ea + Eb + clearance_mm`のときだけ数値分離にします。等号は未判定です。
clearanceは非局所の組だけに適用し、意図した共有接続へ正の間隔を要求しません。
各AABBを`E+clearance/2`で拡大してBVHを走査します。
共有接続は元のAABBも接するため枝刈りされず、自分自身の三角形は比較しません。
`nonlocal_separated_pairs`は明示的に投影評価した分離数で、BVHの枝刈り分を含みません。
最小距離・最接近組は計算していません。

通常の面でも局所未判定は多数になるため、`max_examples`は例の保存数だけを制限します。
その上限に達しても走査・総件数集計を続け、後続の異常接触を隠しません。
`issue_pairs`と`examples_truncated`で例の省略を明示します。
例は走査順で先着保存するため、先行する局所未判定が例の枠を使い切る場合があります。
その場合でも後続の局所/非局所の候補・未判定の件数と全体状態は失われません。
省略された組の再現には保存上限を増やした再診断等が必要で、全face組を記録したレポートではありません。
辺/頂点位相の例も上限付きで、総数は別に返します。
`max_work`はBVH節点と三角形組の走査、`max_triangles`は入力meshの三角形数を制限します。
退化三角形は列挙して未検査のまま残し、全体を不完全にします。
非有限・型/範囲不正・算術overflowはValueErrorです。

## 結果の読み方

| field / 状態 | 意味 |
|---|---|
| `pair_scan_complete` | 上限打切りと退化がなく、対象三角形組の走査が完了 |
| `scan_complete` | 上記に加え、辺/頂点の位相不成立と局所三角形の関係未判定もない |
| `nonlocal_numeric_separated` | 非局所だけの誤差付き数値分離。局所の未判定/異常を含まない限定flag |
| `CONTACT_CANDIDATES_FOUND` | 局所または非局所に三角形接触候補あり。不完全でも候補状態を優先 |
| `INCOMPLETE` | 候補がない場合でも打切り・退化・位相問題・局所関係未判定が残る |
| `UNCERTAIN` | 走査完了だが元面の局所誤差または非局所の距離予算で未判定が残る |
| `NUMERIC_NO_UNEXPECTED_CONTACT` | 走査完了し、候補/未判定なし。正常共有接続は許容する |

`numeric_no_unexpected_contact=True`は最後の条件だけです。
非局所flagがTrueでも、局所foldの候補や位相不成立があれば全体の正常判定にはなりません。
非局所の組がない場合、その限定flagは空の対象についてTrueになり得ます。
`scan_complete=True`も品質PASSではなく、位置誤差による未判定が残り得ます。
打切り時の件数は観測済み範囲であり総件数ではありません。

## 未保証の範囲と次の作業

`whole_geometry_verified`・`continuous_surface_certified`・`roundoff_certified`は常にFalseです。
元面の物理Span対応・パラメータ写像の単射性・個々のpatch内部のJacobian成立、
連続継ぎ目の一致、法線/winding、完全包含、遠い周期コピー、最終cap/wall/disk/fillet/STEPは別検査です。
単独三角形の組比較が0件であることも、その元patch内部が成立する証明にはしません。
接続診断の許容幅は位置誤差やEuclidean clearanceへ流用しません。

次は未判定の元patch対応を保持した局所細分・再評価と、局所単射性/継ぎ目の証拠の追加です。
細分で位置上限を小さくするだけでは、共有部の問題を必ず解消できるとは限りません。
遠いコピー/包含・最終CAD照合・丸め保証・共通出力ゲート、小R根元fillet、native GUI/ANSYSも残ります。

## 検証

新規33件を追加。解析的な平面格子の正常edge/vertex/link、正誤差の局所未判定、
edge fold、vertex foldと位相分断、例の上限後に現れる非局所交差、距離誤差/clearance境界、
座標一致とIDの違い、重複face・3面edge、退化/走査上限・短い高さ、入力型/範囲/overflow、
回転/並進/尺度/winding、結合role meshと既存診断の接続数一致、
三角形別誤差の局所性・自分自身の比較除外・入力不変を確認しています。
基礎63件、最終関連131件、限定Ruffが成功。
全回帰は**1,878一意件成功**（通常1,833・実CAD45）。既存1,845 IDを維持、新規33 IDを追加。
失敗/error/skip/実行漏れ/重複/想定外IDは0。原本/同梱既定JSONを含む固定332入力のhashは不変。
通常7区分と実CAD1区分をproject runnerで実行し、全収集IDと実行IDを照合しました。
テストの環境エラーはありません。CAD45件は既存出力経路の回帰であり、新APIによる最終CAD面の検査ではありません。

同梱既定fit65、三角形誤差目標0.02 mm、join tol=1e-8 mm、clearance=0 mm、
adjacency tol=1e-9 mm、area epsilon=1e-16 mm²、max_work=500,000、max_examples=3で試行しました。
全ケースが走査完了の`UNCERTAIN`。局所/非局所の三角形接触候補、退化、局所関係未判定、
辺/頂点位相不成立、走査打切りはいずれも0です。位置誤差による元面の未判定は残ります。

| 対象 | 三角形数 | 正常edge / vertex組 | 元面の局所未判定 | 非局所未判定 | work units |
|---|---:|---:|---:|---:|---:|
| Impeller Main | 5,152 | 7,084 / 18,678 | 25,762 | 6 | 386,869 |
| Impeller Splitter | 3,264 | 4,488 / 11,834 | 16,322 | 3 | 350,706 |
| Diffuser Main | 512 | 512 / 514 | 1,026 | 0 | 6,540 |
| RC Main | 512 | 512 / 514 | 1,026 | 0 | 6,680 |

非局所未判定9組は、三角形の接触ではなく誤差和より大きい分離下限を得られなかったものです。
静翼の非局所が数値分離でも、共有部の元面単射性を証明したことにはなりません。
今回は例を先着3組へ制限したため、非局所未判定のface IDはその例には残っていません。
後続の局所細分では、対象組と元patch対応の保持を改善する必要があります。

wall時間はMain約239秒、Splitter約235秒、Diffuser/RC各約4.5秒。
全回帰と並行した今回の診断試行値で、単独性能やnative GUIの応答時間ではありません。
計算時間の短縮・取消可能性を確保せず、そのまま同期GUIや出力ゲートへ組み込まない方針です。
既存GUIは新APIを呼ばないため、今回の変更で既存操作へこの処理を追加していません。

試行`probe.py`・`default-probe.json`、全回帰の`source-hashes.json`・`collected-tests.txt`・
`final-test-coverage.json`は`artifacts/quality-error-self/`へ保存しました。
native GUI/F5・ANSYS Import/Meshは今回未実施です。

変更は新しい自己診断API・新規テスト・本書・FEATURES・ARCHITECTURE・DEVELOPMENT_ROADMAP・
ERROR_AWARE_CONTACTSの7ファイル。既存設計アルゴリズム・GUI・出力・数値fixture・
原本/同梱既定JSON・親フォルダの家計簿は変更していません。
