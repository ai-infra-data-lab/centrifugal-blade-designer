# 曲面–三角形の誤差包絡と局所細分（Stage 3B-3a）

## 変更範囲

`geometry/surface_triangulation.py::adaptive_triangle_envelope`を追加しました。
callerが選んだ`SplineSurface`の基準面を評価し、元面を変更・再fitしません。
GUI、生成、JSON、各出力、既存のmesh/role接触診断へ自動適用しません。
CADの最終cap/fillet/STEP面や、円筒補間のtrim面そのものを評価するAPIではありません。

```python
report = adaptive_triangle_envelope(
    surface, target_mm=0.02, max_depth=6, max_cells=4096,
)
```

目標はmm、細分深さは0～12。正のセル数上限を明示できます。数値目標の例は製造公差の推奨値ではありません。
入力は既存のclamped次数1～3 tensor splineの契約に従います。
内部knotの重複度は次数以下（C0以上）を受け付け、不連続面は拒否します。
元knot全区間をBézier化し、初期セル数が上限を超える場合は細分前に拒否します。

## 誤差上限の式

局所単位区間(u,v)の曲面Sを次数(p,q)のBézier control netで表します。
4隅をA=S(0,0)、B=S(1,0)、C=S(1,1)、D=S(0,1)とします。
同じ四隅の双一次面Lを次数(p,q)へ上げたcontrol netは、各(i/p,j/q)でのLです。
S−Lのcontrol net最大ノルムをEとすると、Bernstein基底の非負性・和が1であることから
実数演算では領域全体で`|S−L|≤E`です。

対角A–Cで分けた三角形ABC/ACDをTとし、W=A−B+C−Dとすると、
u≥v側はL−T=−W v(1−u)、u≤v側はL−T=−W u(1−v)。
したがって`|L−T|≤|W|/4`、全体で`|S−T|≤E+|W|/4`と評価します。
対応するパラメータ点での評価なので、実数モデルでは局所の双方向距離の上限にもなります。
最短距離や曲率・干渉・面の正則性を直接測定する式ではありません。

計算はfloat64で、knot挿入・係数差・norm・細分の丸めを区間保証しません。
`roundoff_certified=False`を維持し、厳密公差証明とは呼びません。

## 適応細分と未達

数値上限が目標を超えるセルを大きい順に選び、de Casteljauで両軸を半分にして4分割します。
面の係数を再fitせず、分割前の区間を子セルで完全に覆います。最小セル数・最適な異方性分割は保証しません。
深さ/セル数上限に達してもセルを捨てず、未達として残します。
各最終セルは元splineの3×3点も独立に評価し、対応三角形との差を記録します。

セルの`reason`は`target`／`max_depth`／`max_cells`／`sample_above_target`。
上限と標本誤差が目標以下のセルだけ`numeric_target_met=True`とし、全セルが満たすときのみ
`NUMERIC_TARGET_MET`、残りは`UNRESOLVED`です。数値上限より標本誤差が大きい場合は
`sample_exceeds_upper`と総数を省略せず記録します。標本が目標を超えた場合を黙って採用しません。
この数値矛盾について追加細分する機能はなく、未達として返します。非有限演算は例外です。

## メッシュの意味と未対応

返すのは各セルの範囲・深さ・四隅[A,B,C,D]と誤差です。
セル間やrole間で分割線をそろえないため、T junctionが生じ得ます。
`contact_ready=False`のままとし、そのまま共有edge/vertex診断やCAD出力へ渡してはいけません。
まず分割整合・role継ぎ目対応を実装する必要があります。
`NUMERIC_TARGET_MET`は非干渉/閉solid/設計成立のPASSではありません。
regularity、周期コピー、包含、他翼列・Splitter干渉、最終CAD面は別の検査です。

## 検証

`tests/test_surface_triangulation.py`の新規22件で、厳密な平面、z=uvの鞍型面の
対角誤差1/4と細分ごとの1/4収束、四隅で見えない内部bump、資源上限と区間被覆、
回転・並進・尺度、C0 knot、入力不正/非有限値、未達理由、独立した密な解析点を確認します。
基礎63件、関連96件、限定Ruffが成功。既存期待値・fixtureは変更していません。

同梱既定JSONのfit65基準面16枚を、目標0.02 mm、max_depth=6、max_cells=1024/roleで試行。
全16枚で`NUMERIC_TARGET_MET`、標本が数値上限を超えたセルは0でした。
各面の初期セルは64。代表値は以下のとおりです（数値保証範囲は上記の制約どおり）。

| 対象/role | 初期上限 [mm] | 細分後上限 [mm] | 最終セル数 |
|---|---:|---:|---:|
| Impeller Main LE | 0.02910315 | 0.01859195 | 76 |
| Impeller Main PS | 0.14060233 | 0.00875154 | 1024 |
| Impeller Main SS | 0.17613208 | 0.01300642 | 1024 |
| Impeller Splitter PS | 0.09226858 | 0.01996156 | 310 |
| Impeller Splitter SS | 0.11711742 | 0.01998629 | 316 |

Diffuser/RCの各4roleは初期64セルのまま目標以下。全16枚の記録は
`artifacts/quality-triangle-envelope/probe.py`・`default-probe.json`。
全回帰の収集/実行ID・原本/既定値を含む固定入力hashは同フォルダの`final-test-coverage.json`へ記録します。

追加の独立数値試行：`S(s,t)=(t,s,s³t³)`を両方向3次で表し、目標0.01 mmで115セル、
上限0.00994863 mm、各セル17×19の解析点の最大誤差0.00858446 mmを確認しました。
解析点の上限超過は0（照合時の算術allowance 1e-12 mm）、元係数も不変。
これは新規回帰試験22件とは別の補助試行です。
記録は`cubic-analytic-probe.json`。この照合allowanceはAPIの目標値や係数を緩和する設定ではありません。

最終全回帰は**1,777一意件成功**（通常1,732・実CAD45）。既存1,755 IDを維持し、新規22 IDを追加。
failure/error/skip/実行漏れ/重複/想定外IDは0。固定324入力（ユーザー原本・同梱既定JSONを含む）はhash不変。
前回のJUnit時間を利用して通常試験をファイル単位7区分、CADを1区分に分けてrunnerで実行し、全IDを照合しました。
Ruff・差分検査も成功。製品試験の失敗・環境エラーはありません。
CAD45件は既存経路の回帰であり、新しい診断を最終CAD面へ適用した確認ではありません。
native GUI/F5、ANSYS Import/Meshは未実施です。

変更は`blade_designer/geometry/surface_triangulation.py`、`tests/test_surface_triangulation.py`、本書、
`FEATURES.md`、`docs/ARCHITECTURE.md`、`docs/DEVELOPMENT_ROADMAP.md`の6ファイルです。
既存の生成コード・数値fixture・設計JSON・既存出力・親フォルダの家計簿は変更していません。

次は整合する三角形化とrole継ぎ目の分割対応、接触診断への近似誤差の伝播条件です。
遠い周期コピー・包含、実CAD照合、全面誤差予算、小R根元fillet、native GUIとANSYS実機も未完了です。
