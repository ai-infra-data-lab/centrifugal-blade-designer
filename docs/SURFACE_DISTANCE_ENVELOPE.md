# 同一対応スプライン面の距離包絡

Stage 3Aの次の単位として、標本差だけでは見逃す領域を扱う`geometry/surface_envelope.py::surface_distance_envelope`を追加した。既存生成・GUI・CAD格子採用・出力ガード・保存値・数値fixtureは変更しない。Qt/OCP/ファイル形式へ依存しない読取り専用APIである。

## 対応と数学上の範囲

入力は同じSpan/role内xiで対応する2枚のCartesian tensor spline。両方向のdegreeが等しく、degree 1〜3、clamped、非周期、領域[0,1]²、有限な実XYZ係数を持つ`SplineSurface`に限定する。異なるdegree・周期wrap等の形式は拒否する。任意trimや別の物理座標対応は今回の適用対象外で、呼出し側が由来と対応を確認する。API自体がrole/row/trimの由来を判別するわけではない。knotを公差で丸めて併合したり、degreeを黙って変更したりしない。

各方向のknot集合を最大多重度で統一し、形状をrefitせずSciPyのknot insertionで同一basisにする。差のcontrol netをDij、基底をBi(s), Cj(xi)とすると、非負かつ和1の基底に対して次が成り立つ。

`ΔS(s,xi) = Σij Bi(s) Cj(xi) Dij`

`||ΔS(s,xi)|| ≤ maxij ||Dij||`

右辺は**実数演算での同一対応面全域の位置差上限**であり、標本の最大値とは異なる。knot挿入で区間を細分化すると、同じ面を保ちながらこの凸包を狭められる。距離の最小化や最近点対応の探索ではない。

基底のpartition of unityとknot insertionの根拠: [SciPy BSpline](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.BSpline.html)、[insert_knot](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.BSpline.insert_knot.html)。

## APIと数値上の制限

`surface_distance_envelope(first, second, refinements=0, max_control_points=250000)`は以下を返す。

- `control_upper_mm`: 共通control netの差の最大ノルム。
- `sample_lower_mm`: 両面を共通knotと区間中点で評価した最大距離。上限とは独立の有限標本による下側推定。
- `numerical_bracket_gap_mm`: 上記の差。浮動小数点で微小な負値になっても、黙ってclampしない。
- 共通control数、評価標本数、細分化回数、`roundoff_certified=False`。

**実装は通常のfloat64演算であり、knot挿入・係数差・ノルムの丸めを包含する区間演算ではない。** 返す数値を厳密な有限精度証明や製造/設計公差の合否へ使わない。工学的な許容値を新しく定めたり、CADの既存公差を緩和したりしない。モデル上の包絡と数値的な証明の不足を分ける。

refinementsは0〜4の整数。各非零区間へ中点を挿入する。共通control netの積が指定上限を超える場合は、そのnetを構築する前に拒否する。浮動小数点で中点を区別できない極小区間も拒否する。標本評価はSpanごとに行い、全XYZ格子の同時確保を避ける。入力knot/係数はコピーし、変更しない。

法線/Jacobianの全域包絡、自己交差、周期翼/Splitter干渉、CAD外向き、cap/fillet/STEP面、Preview/trimとの物理対応は対象外。513格子を真値にする機能でもない。Stage 3A全体・Stage 3Bの完了ではない。

## 独立したnegative fixture

平面`A(s,t)=(t,s,0)`に対し、`B(s,t)=(t,s,16s(1−s)t(1−t))`を比較する。四隅の距離はすべて0だが、中央の距離は1 mm。未細分の二次tensor control netは4 mmの包絡を返し、両方向へ中点を挿入すると1 mmまで狭まる。この解析値を固定試験にし、標本最大値を上限として返す実装を検出する。

周期wrapを有効にした面は同じ係数でも境界値が変わるため、同一面と誤認せず拒否する試験を含む。

## 現既定Impellerでの結果

同梱既定JSONの主翼/Splitter、各4roleを513格子と比較した。以下は4roleを通じた最大値。refinements=1。位置差は同一Span/xiでの基準スプライン比較であり、元の設計寸法誤差・通常Preview誤差・最終CAD/STEP偏差ではない。

| 集合 | 比較格子 | 標本による下側推定 [mm] | controlによる上側推定 [mm] |
|---|---:|---:|---:|
| Main | 65 | 0.0261292 | 0.0263643 |
| Main | 129 | 0.0138795 | 0.0145150 |
| Main | 257 | 0.00608860 | 0.00733885 |
| Splitter | 65 | 0.0176034 | 0.0177618 |
| Splitter | 129 | 0.00935130 | 0.00977943 |
| Splitter | 257 | 0.00410215 | 0.00494450 |

Main129の旧41×101標本最大0.00331300 mmに対し、新しい標本は0.0138795 mmを捉えた。位置はSS面のHub（Span=0）、xi=0.0029296875。Main257も旧0.000734799 mmに対し0.00608860 mm（SS/Hub、xi=0.001953125）。旧標本の間にある始端付近の差を、旧評価が見ていなかった。以前の記録は有限標本差として保持し、都合よく置換しない。

全roleの未細分/1回細分と位置は`artifacts/quality-surface-envelope/default-probe.json`、再現は`probe.py`。原本/同梱既定は不変（SHA-256 `aa724c8253463289caec919960d7d486d698765cee35202c13e4efd17a603dd6`）。

## 検証と次の課題

新規29件（純数値28・実OCCT1）。解析平面/平行移動/中央の膨らみ、異なる非等間隔knot/多重度、細分化による包絡縮小、入力不変、不正型/degree/周期/domain/係数/精度限界/資源上限を確認した。実OCCTは33/129格子の4role基準面を13×23点で比較し、包絡内にあることを確認する。既存のnative/数値比較と同じ5e−12 mmを演算比較に使い、CADの公差を変更しない。実OCCT標本比較を全面の有限精度証明とは扱わない。

新旧関連82件成功（`20261018T065106Z-68b396d5`）、限定Ruff成功。全回帰は**1,213一意件成功**（通常1,172・実CAD41）。既存1,184 IDを維持、新規29 IDを追加。failure/error/skip/実行漏れ/重複/想定外IDは0。固定276入力は回帰開始から不変で、原本/同梱既定JSONも一致した。既存数値fixture/期待値は変更していない。次は丸めを含む誤差予算・法線/Jacobianの全域評価と、物理対応/互換条件を扱う。根元filletの未成立、native操作、ANSYS Import/Meshは今回の成功とは別である。

追加の独立解析プローブでは、Span側/xi側の両方で異なるknotを持つ面を比較し、既知の最大差0.05 mmを細分化0/1/2回とも包絡内に確認した。`artifacts/quality-surface-envelope/nonuniform-both-axes.json`へ元knotと結果を保存した。この追加プローブを全回帰の件数へ加算しない。


全回帰の根拠: `artifacts/quality-surface-envelope/final-test-coverage.json`、`source-hashes.json`、`collected-tests.txt`。通常6群/CAD1群のJUnitと収集IDを照合した。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 298.318 | 20261018T065139Z-8e91c69b |
| 通常1 | 143 | 263.880 | 20261018T065139Z-a5989de2 |
| 通常2 | 122 | 308.343 | 20261018T065139Z-98a6af92 |
| 通常3 | 191 | 217.989 | 20261018T065139Z-bd62bed0 |
| 通常4 | 146 | 285.262 | 20261018T065139Z-0b03c908 |
| 通常5 | 454 | 371.093 | 20261018T065139Z-72afcac3 |
| 実CAD | 41 | 730.029 | 20261018T065139Z-a363a388 |
