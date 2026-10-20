# 継ぎ目の境界曲線の全Span差（Stage 3B-3h）

## 今回の範囲

`geometry/boundary_gap.py`に、LE/PS/TE/SSの宣言済み4継ぎ目について、
同じSpanパラメータの境界曲線間の位置差を評価するAPIを追加しました。
標本点が一致しても、その間の曲線差が予算内とは限らない問題を扱います。
設計値・形状生成・GUI・JSON・出力条件は変更しません。
座標の結合・補正・再fit・自動的な出力許可は行いません。

```python
from blade_designer.geometry.boundary_gap import role_boundary_gap_envelope

report = role_boundary_gap_envelope(
    surfaces, gap_tolerance_mm=1e-8,
    span_range=(0.0, 1.0), refinements=1, max_intervals=2048,
)
```

`surfaces`は4roleのCartesian基準SplineSurfaceです。作業用コピーを使い、source識別値を返します。
単位はXYZ・曲線差・gap_toleranceともmm。例の数値は製造/解析公差の推奨ではありません。
対象の継ぎ目は既存SEAMSと同じです。

| 第1境界 | 第2境界 |
|---|---|
| LE ξ=0 | SS ξ=0 |
| LE ξ=1 | PS ξ=0 |
| TE ξ=0 | PS ξ=1 |
| TE ξ=1 | SS ξ=1 |

`boundary_gap_envelope(first, first_end, second, second_end, ...)`で1組だけ評価できます。
endは0または−1（最後のξ=1）です。下位APIを単独で使う場合は、callerが評価中のsource不変性を管理します。
Span/ξともclamped degree 1–3の既存表現を対象とし、境界曲線のSpan方向は連続C0以上が必要です。
不連続なSpan knotは拒否します。全曲面の正則性をこの条件から推定しません。

## 同じSpanで比較する

これは`max_s |C_a(s)−C_b(s)|`の評価です。両曲線の同じSpanが同じ物理的な位置に対応することを
callerが保証する前提で、`parameter_correspondence_assumed=True`を明示します。
曲線間の最近接距離やHausdorff距離を求めるものではありません。
同じ曲線集合でもSpanが逆向き/異なる再パラメータ化なら、位置差が出ることがあります。
Spanの反転・θのunwrap・端部の自動選び直しで結果を合わせません。

## 境界抽出と全区間の上限

ξ方向がclampedなので、元のtensor control netの最初/最後の列が境界曲線を表します。
両曲線のSpan knotと指定範囲端を共通化し、元面を再fitせずknotを挿入してBézier区間に分けます。
`refinements`（0–4）は各区間をさらに二分する回数です。
Span degreeが異なる場合は、各区間で最大degree（1–3）へBézier次数を上げます。
これは表現の変換であり、元曲面の形状変更ではありません。

共通degree kの区間で差のcontrol vectorをD_iとすれば、

`C_a(u)−C_b(u) = Σ B_i^k(u) D_i`、従って`|C_a(u)−C_b(u)| ≤ max_i |D_i|`

です。Bernstein基底が非負・総和1であることから、区間の全点に対する実数モデルの上限が得られます。
全区間の最大値を`max_upper_mm`として返します。
元の境界曲線を区間端と中点で別に評価し、`sample_max_mm`も返します。
これは最大差の観測値で、全点での最小距離ではありません。

## 結果と不完全性

| 状態/field | 意味 |
|---|---|
| `NUMERIC_WITHIN_GAP_TOLERANCE` | 全区間の数値上限と標本差が指定予算以下 |
| `GAP_OBSERVED` | 対応Spanの標本に予算超過を観測 |
| `UNRESOLVED` | 上限は予算超過だが標本では超過を観測していない。隙間の確定ではない |
| `RESOURCE_LIMIT` | 共通区間数がmax_intervalsを超過。部分区間で成功扱いしない |
| `same_float64_boundary_representation` | 抽出した元のfloat64 Span knots・degree・control係数がそのまま一致 |
| `all_seams_within_tolerance` | 4継ぎ目すべてで予算内の数値条件を満たす |
| `scan_complete` | 4継ぎ目とも資源上限による未処理区間がない。品質PASSの意味ではない |

等号は予算内として扱います。GAP_OBSERVEDがあれば上位statusへ伝播しますが、
別の継ぎ目が資源上限でも`scan_complete=False`とそのreportを残します。
`max_intervals`は各継ぎ目の上限で、knot挿入・区間report配列の割当て前に確認します。
入力型/範囲不正・不連続Span・非有限演算はValueErrorです。

「予算内」は隙間ゼロや厳密なG0一致ではありません。
同じfloat64境界表現の一致は別fieldで報告しますが、Falseは曲線が異なるという証明ではありません。
異なるknot/degreeでも同じ曲線を表せます。位置予算を許して両側の座標をweldingする処理もありません。

`sample_upper_violations`と各区間の`sample_exceeds_upper`は、浮動小数点演算で
標本差がcontrol上限を上回った件数を隠さず報告します。
数値の予算内判定は上限と標本の両方が予算以下であることを要求しますが、
これは挿入/次数変換/評価の丸めを含む厳密な区間保証ではありません。
`roundoff_certified=False`・`continuous_surface_certified=False`を維持し、上限を公差証明と呼びません。

G1/法線、継ぎ目の両側の領域、曲面の単射性・非干渉、最終CAD/STEPを検査しません。
`seam_chart_ready=False`・`whole_geometry_verified=False`のままです。
隙間予算内だけを根拠に、前段のcross_role_requires_seam_chartを解消しません。

## 検証

新規35件：境界の同一性と入力不変、degree 1/2/3の6組の次数変換、
3標本が一致する隠れたcubic gapと細分後の検出、独立した解析最大値、
有限gapの予算境界と非ゼロ区別、剛体変換/尺度/異なるknots・部分範囲、
Span逆向き/端部違いを修復しないこと、C0/不連続、4宣言継ぎ目とsource識別、
GAP/資源上限の伝播と混在、入力型/範囲/端部/不足role/不正sourceを確認しています。
基礎63件、最終関連85件、限定Ruffは成功。
全回帰は**1,987一意件成功**（通常1,942・実CAD45）、既存1,952 ID維持・新規35 ID。
失敗/error/skip/漏れ/重複/想定外IDは0。原本/同梱既定JSONを含む固定339入力のhashは不変でした。
通常7区分と実CAD1区分をproject runnerで実行し、全収集IDと実行IDを照合しました。
CAD45件は既存出力経路の回帰で、新APIによる最終CAD継ぎ目の検査ではありません。
テストの環境エラーはありません。
既存テスト期待値・歴史的fixture・ユーザーJSONは変更していません。

## 同梱既定の16継ぎ目

fit65基準面、Span全体0–1、refinements=1、max_intervals=2048で試行しました。
各groupの4継ぎ目はすべてgap_tolerance=1e-8 mmの数値条件を満たし、走査完了です。
float64の境界表現が一致するのは合計6/16継ぎ目でした。
gap_tolerance=0での比較も保存しており、4groupすべてで微小な差を観測します。

| 対象 | 最大control上限 [mm] | 最大標本差 [mm] | 同じ元境界表現 |
|---|---:|---:|---:|
| Impeller Main | 8.33e-17 | 1.11e-16 | 2/4 |
| Impeller Splitter | 1.00e-14 | 1.00e-14 | 1/4 |
| Diffuser Main | 2.01e-14 | 2.01e-14 | 1/4 |
| RC Main | 2.84e-14 | 2.84e-14 | 2/4 |

標本がcontrol上限を上回る区間はMain 2・Splitter 1・RC 1で、最大超過は約7.11e-15 mmでした。
この差も記録し、丸めの保証や厳密な隙間ゼロに読み替えていません。
物理的な設計不良を観測したという意味でもありません。
試行`probe.py`・`default-probe.json`、全回帰の`source-hashes.json`・`collected-tests.txt`・
`final-test-coverage.json`は`artifacts/quality-boundary-gap/`へ保存しました。
native GUI/F5・ANSYS Import/Meshは今回未実施です。

変更は新設`boundary_gap.py`・`test_boundary_gap.py`、本書、FEATURES・ARCHITECTURE・
DEVELOPMENT_ROADMAP・SOURCE_INJECTIVITYの7ファイル。
既存生成/設計アルゴリズム・GUI・JSON/出力・数値fixture・ユーザー原本・親フォルダの家計簿は変更していません。

次は連続境界と片側領域を整合させる継ぎ目chartの条件、および位置差予算/丸めの扱いです。
遠い周期コピー/包含、最終CAD、全体の品質集約、小R根元fillet、native GUI/ANSYSも残ります。
