# 選択した元曲面範囲の単射性診断（Stage 3B-3g）

## 今回の範囲

`geometry/surface_injectivity.py`へ、固定投影と対称微分の下限による**十分条件**を追加しました。
同じroleの隣接三角形を含む矩形について、元曲面に期待接続以外の重なりがないという数値的な証拠を返します。
形状生成・設計値・GUI・保存・出力条件を変えず、従来の自己診断結果も書き換えません。
異なるroleの継ぎ目や、矩形外の干渉を代わりに成立扱いしません。

```python
from blade_designer.geometry.surface_injectivity import local_source_pair_injectivity

result = local_source_pair_injectivity(
    surfaces, envelope, first_face, second_face,
    reference_min_mm=1e-12, monotonic_margin=0.0,
    refinements=0, max_cells=4096,
)
```

`envelope`は同じsourceから生成した`merged_role_error_envelope`の結果です。
選択組は異なるfaceで、共有IDを持つ必要があります。
source/mapping識別を検査し、作業用に選択roleをコピーします。
変更済みsource・旧mapping・非隣接の組・同じfaceはValueErrorです。
`surface_projection_injectivity(surface, span_range=..., xi_range=..., ...)`は、
任意の矩形範囲を直接診断する下位APIです。単独呼出しではcallerがsourceの不変性を管理します。
両方向ともclamped degree 1–3、連続C0以上を対象とし、不連続knotは拒否します。
上記閾値は製造公差の推奨ではありません。

## Jacobianの非ゼロとは別の条件

Jacobianが非ゼロでも、別のパラメータ位置で同じXYZを通る曲面があります。
既存のJacobian包絡は局所正則性の証拠で、範囲全体の単射性には読み替えません。
本診断では、元の選択矩形を正規化したu,v∈[0,1]²と、曲面S(u,v)を使います。

中心の3×2微分AにSVDを行い、固定の左逆行列P（2×3）を作ります。
小さい特異値が`reference_min_mm`以下なら`UNRESOLVED/reference_rank`です。
rank不足を隠す擬似逆行列の打切りや、閾値の自動緩和は行いません。
`reference_min_mm`は正規化したパラメータに対する接線の長さ[mm]、
`monotonic_margin`は投影写像の無次元の対称微分下限へ要求する余裕です。
XYZと前者を同じ尺度で変えれば、後者はそのままです。

G=P Sとし、H=(DG+DGᵀ)/2を考えます。
各Bézierセルで元面の微分control netを投影し、Bernstein凸包性から各成分の範囲を得ます。
H₀₀≥a、H₁₁≥d、H₀₁∈[b_low,b_high]なら、b=max(|b_low|,|b_high|)を用いて

`lambda_min(H) >= (a+d)/2 - hypot((a-d)/2, b)`

という下限を評価します。Hの2つの非対角成分は同じ値なので、
別々の次数の微分netを無理に同じnetへ揃えず、それぞれの区間和を1/2倍して評価します。

すべてのセルでこの下限が`monotonic_margin`より**厳密に大きい**とき、
同じ固定Pのもとで矩形全体の正の下限mが得られます。
矩形は凸なのでx,yを結ぶ線分を積分すると

`(G(x)-G(y))・(x-y) >= m ||x-y||² > 0`（x≠y）

となり、G、従ってSはこの矩形で単射です。
連続C0の場合も区分多項式の線分上積分として評価し、knot境界を平滑化しません。
各セルで別のPを使った成功結果を継ぎ合わせる議論ではありません。

これは実数モデルの議論です。knot挿入・微分・SVD・区間端のfloat64計算を区間保証していないため、
`roundoff_certified=False`・`continuous_surface_certified=False`を保ちます。
特に下限が0付近の判定を、製造公差や厳密幾何証明として使用しません。

## 結果と不成立の意味

| 状態/field | 意味 |
|---|---|
| `NUMERIC_INJECTIVE_ON_RECTANGLE` | 指定矩形全体が同じ投影の十分条件を数値上満たす |
| `numeric_injective` | 下位APIの上記判定 |
| `expected_parameter_contact_only` | 同じroleの選択隣接三角形の元領域では、共有パラメータ境界以外の接触を数値上排除できる |
| `UNRESOLVED/reference_rank` | 中心の参照接線でrankを確保できない |
| `UNRESOLVED/symmetric_bound_not_positive` | どこかのセルで十分な正の下限を得られない |
| `UNRESOLVED/cross_role_requires_seam_chart` | 別roleの接続で、共通の継ぎ目chartの証拠がない |
| `RESOURCE_LIMIT/max_cells` | 矩形のBézier分割数が上限を超える。部分的な成功セルは返さない |

条件を満たさないことは折返しの証明ではありません。
例えばS(s,t)=(s,t+10s²,0)はs=X,t=Y−10X²という逆写像を持ちますが、
広い範囲ではこの固定投影の十分条件が不成立となります。
局所4範囲で別々の投影が成功しても、全体の成功へ昇格させません。
一つのPのまま`refinements`（0–4）でcontrol netの区間を狭められますが、必ず解消するとは限りません。

`local_source_pair_injectivity`は2つの三角形の元セルを含む矩形を診断します。
その間に他のセルがあれば、それらも含めて正の下限が必要です。
同じrole内のパラメータ三角形は内部が重ならないため、単射性が得られれば、
元の共有辺/頂点に対応する接触だけが残ります。
ただし近似mesh自体の接触候補を削除せず、正のEuclidean clearanceも保証しません。

別roleでは、両面それぞれの正則性や単射性が成立しても、
連続継ぎ目・向き・片側領域が整合することは別の証拠が必要です。
今回はその条件を未判定として明示し、座標weldingや強制接続は行いません。

各セルの元Span/xi範囲、対角下限、対称非対角の区間、最小固有値下限、
共通Pと参照特異値を返します。resource limitはknot挿入/セル配列割当て前に検査します。
入力不正・不連続source・非有限演算・線形代数の失敗はValueErrorです。
`whole_geometry_verified`は常にFalseです。

## 検証

新規32件：平面の解析下限1・回転/並進/尺度・部分範囲・細分、正Jacobianでも自己交差するnegative、
標本の間のfoldと単調部分範囲、rank不足、閾値の厳密境界、連続C0と不連続の区別、
cubic面の独立した解析微分と密な固有値照合、資源上限、隣接sourceのsnapshotと矩形union、
別role未判定、古いsource・不正組の拒否、入力型/範囲、単射なshearでも十分条件が未達となる例、
別々の局所投影の成功を全体へ流用しないことを確認しています。
基礎63件・最終関連98件・限定Ruffが成功。
最終全回帰は**1,952一意件成功**（通常1,907・実CAD45）、既存1,920 ID維持・新規32 ID。
最終失敗/error/skip/漏れ/重複/想定外IDは0、原本/同梱既定JSONを含む固定337入力のhashは不変。
通常7区分と実CAD1区分をproject runnerで実行し、全収集IDと実行IDを照合しました。
CAD45件は既存経路の回帰で、この単射性診断が最終CAD面を検査したという意味ではありません。
最終試験の環境エラーはありません。

最初の関連試験では、新規C0/不連続fixtureのBSpline構築軸が誤っていた2件が失敗し、
新規fixtureの入力配列軸だけを修正しました。追加した2セル試験も隣接しないface 1/2を選んでいたため拒否され、
本来の隣接face 0/3へ修正しました。設計コード・既存fixture・数値期待値を変更して通したものではありません。
関連試験失敗の確認前に開始した初回全回帰は、所有する試験プロセスのみを停止し、完了/PASSには扱いません。
初回資料は`artifacts/quality-source-injectivity/`へ残し、最終全回帰は
`artifacts/quality-source-injectivity-final/`へ別に記録します。
native GUI/F5・ANSYS Import/Meshは今回未実施です。

最終証拠は同フォルダの`source-hashes.json`・`collected-tests.txt`・`final-test-coverage.json`。
変更は新しい`surface_injectivity.py`・`test_surface_injectivity.py`、本書、
FEATURES・ARCHITECTURE・DEVELOPMENT_ROADMAP・CONTACT_PATCH_REFINEMENTの7ファイルです。
既存生成/設計アルゴリズム・GUI・JSON/出力・歴史的数値fixture・ユーザー原本・親フォルダの家計簿は変更していません。

## 同梱既定形状での試行

同梱既定のMain/Splitter・Diffuser・RCからfit65の基準splineを作成し、
誤差目標0.02 mm・join tol=1e-8 mmのenvelopeでsource/mappingを固定しました。
単射性診断はreference_min=1e-12 mm、monotonic_margin=0、refinements=0、max_cells=1024です。
各roleで5セルの対角隣接組と、実際に共有IDを持つ2セル間の1組を選びました。
各groupで別roleの継ぎ目4組も指定し、未判定が維持されることを確認しました。

| 対象 | 同一セルの組 | 隣接2セルの組 | 別roleの組 | role面全体の数値条件 |
|---|---:|---:|---:|---|
| Impeller Main | 20組達成 | 4組達成 | 4組未判定 | PS/TE/SS達成、LE未判定 |
| Impeller Splitter | 20組達成 | 4組達成 | 4組未判定 | PS/TE/SS達成、LE未判定 |
| Diffuser Main | 20組達成 | 4組達成 | 4組未判定 | 4role達成 |
| RC Main | 20組達成 | 4組達成 | 4組未判定 | 4role達成 |

選択112組中、同じroleの96組は数値条件を満たし、別role16組は継ぎ目chart不足で未判定です。
これは全局所隣接組を列挙して検証したという意味ではありません。
role面全体（各[0,1]²、64 Bézierセル）では16面中14面で条件を満たしました。
Main LEの下限は約−0.18、Splitter LEは約−0.16で、十分条件未達です。
この負値を折返し・実干渉の観測とは扱いません。
局所範囲の成功でこれら全体の未達を上書きせず、元の接触診断/品質状態も書き換えていません。

試行のface ID・role・Span/xi範囲・共通投影・各セル下限・source/mapping識別値は
`artifacts/quality-source-injectivity-final/probe.py`・`default-probe.json`へ保存しています。
初回試行はMain/Splitterの2セル隣接組を選べず104組だったため、112組へ対象選択を補いました。
その補助スクリプトの変数名重複による一度の失敗も修正して再実行しました。
いずれも検証用artifactだけの修正で、アプリ/診断API/テスト期待値の変更ではありません。
初回の有効な104組の結果は`default-probe-initial.json`に保持しています。

次は別roleの連続継ぎ目と片側領域の整合、および局所証拠と接触再評価を集約する条件です。
遠い周期コピー/包含、最終CAD照合、丸め保証、全面精度予算、小R根元fillet、native GUI/ANSYSも残ります。
