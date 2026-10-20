# セル・role間の整合格子（Stage 3B-3b）

## 変更範囲とAPI

`geometry/conforming_role_grids.py::conforming_role_grids`を追加しました。
各roleの基準`SplineSurface`から局所細分を行い、その分割位置を格子全体へ伝播します。
元面の再fit、設計値・GUI・JSON・出力条件の変更はしません。

```python
result = conforming_role_grids(
    surfaces, target_mm=0.02, join_tolerance_mm=1e-8,
    max_depth=6, max_seed_cells=1024, max_triangles=20000,
)
```

`surfaces`はle/ps/te/ssの4面。Span/xiは各面の[0,1]パラメータです。
同じSpan値が同じ物理位置を意味することはcallerの前提で、自動証明しません。
例の数値は製造公差の推奨値ではありません。

## 分割整合と資源制限

1. 各面を`adaptive_triangle_envelope`で細分し、元knotを含むセル境界を得る。
2. 全roleのSpan境界の集合和を共通軸にし、各roleのxi境界もそのrole内で集合和にする。
3. 完全なtensor格子を作り、局所セルのT junctionをなくす。role間は共通Span行と既存の4本の境界対応を使う。
4. 変更後の三角形に対し、Bézier係数を挿入して誤差を再評価する。

近いknotを曖昧にまとめたり、座標を平均化したりしません。
各roleのxi列数は異なってもよく、Span行はすべて共通です。
細分深さ/セル数上限は局所seed用。整合のためのtensor格子はseedより大きくなる場合があります。
合計三角形数をtensor割当て・knot挿入の前に確認し、`max_triangles`超過なら
`RESOURCE_LIMIT`と必要数を返し、`grids`は空にします。部分格子や粗い代替面を返しません。
seedの初期knot数超過や入力不正は既存の診断契約どおり例外です。

## 誤差の再評価

整合後は対角A–Cの三角形が変わるため、seedの上限を流用しません。
各新セルに対してS−双一次面のcontrol netと双一次面−対角三角形のtwistから上限を再計算します。
また、挿入後control netの四隅と、元splineを実評価した格子頂点との差を測り、
その最大値を上限に加えます。三角形の頂点変位の凸結合で評価する数値的な補正です。
`role_reports.cell_upper_mm`は返した格子のセルと同じ並びです。
元面や目標値を変えず、未達セルは`unresolved_cells`として残します。
`max_corner_reconciliation_mm`も省略しません。float丸めの区間保証ではありません。

格子の継ぎ目のgapは共通Span行で測り、指定値を超えれば`SEAM_MISMATCH`。
座標は修復・結合せず、そのまま返します。行間の連続曲線一致は保証しません。
エラー上限は`error_applies_to=unmerged_role_triangles`です。
後続の`screen_role_seams`が公差内の端点を動かした場合、その追加変位を含む上限へ
読み替えてはいけません。結合移動量の誤差伝播は次の課題です。

## 状態の意味

- `parameter_conforming`：role内の格子にT junctionがなく、role間でSpan行が共通。
- `role_seam_input_ready`：共通行の継ぎ目gapが指定値内で、既存のrole診断へ明示的に渡せる。
- `numeric_target_met`：整合後の数値上限が全セルで目標以下。
- `NUMERIC_TARGET_MET`：上記数値目標とサンプル継ぎ目条件を満たす。製造/非干渉のPASSではない。
- `UNRESOLVED`：格子はあるが数値上限が未達。`SEAM_MISMATCH`はこれより優先する。

`contact_ready=False`を維持します。三角形の退化・非多様体・自己交差・包含・周期干渉は
この格子生成だけでは判定しません。`screen_role_seams(result['grids'], ...)`は別途、
その明示三角形を診断する呼出しです。そこでも連続曲面の非干渉証明にはなりません。
最終CAD/STEP、原本/既定値、既存出力ゲートへの自動適用はありません。

## 検証

新規`tests/test_conforming_role_grids.py`16件で、異なる次数/knot/列密度の整合、
局所bumpの解析点による新三角形の上限照合、既存継ぎ目診断との接続、入力不変、
正確な合計三角形数上限、超過時の空格子、未達・gap・非ゼロ結合公差の分離、入力不正を確認。
基礎63件、関連60件、試験整理後の新規16件、限定Ruffが成功。既存fixtureは変更していません。
全回帰と既定モデル試行は`artifacts/quality-conforming-grids/`へ記録します。

同梱既定のfit65基準面を目標0.02 mm、join tol=1e-8 mm、seed上限1024/role、合計20,000三角形で試行。
4ケースとも`NUMERIC_TARGET_MET`、継ぎ目gap超過なし。共通Span行数はImpeller各5、静翼各2です。

| 対象 | 整合三角形数 | 最大数値上限 [mm] | 既存接触診断のwork units |
|---|---:|---:|---:|
| Impeller Main | 5,152 | 0.01300642 | 376,650 |
| Impeller Splitter | 3,264 | 0.01130303 | 340,709 |
| Diffuser Main | 512 | 0.00485078 | 6,540 |
| RC Main | 512 | 0.00404232 | 6,680 |

整合格子を既存`screen_role_seams`へ明示的に渡した試行では、contact tol=1e-9 mm、
area threshold=1e-16 mm²、max_work=1,000,000、max_contacts=20とし、全4ケースで候補0・scan_complete=True。
この検査は結合後の明示三角形に対する結果で、上表の未結合誤差と結合移動の合成保証ではありません。
再評価頂点とcontrol net四隅の最大差は6e-14 mm未満、継ぎ目最大gapは3e-14 mm未満でした。
記録は同フォルダの`probe.py`・`default-probe.json`。実CAD/ANSYSや全面非干渉の確認ではありません。

最終全回帰は**1,793一意件成功**（通常1,748・実CAD45）。既存1,777 IDを維持、新規16 IDを追加。
failure/error/skip/実行漏れ/重複/想定外IDは0。固定326入力（原本・同梱既定JSONを含む）はhash不変。
通常7区分・CAD1区分をrunnerで実行し、収集/実行IDを全照合しました。
詳細は`artifacts/quality-conforming-grids/final-test-coverage.json`。Ruff・差分検査も成功。
製品試験の失敗・環境エラーはありません。CAD45件は既存経路の回帰であり、新診断の最終CAD適用ではありません。
native GUI/F5・ANSYS Import/Meshは未実施です。

変更ファイルは`blade_designer/geometry/conforming_role_grids.py`、`tests/test_conforming_role_grids.py`、
本書、`FEATURES.md`、`docs/ARCHITECTURE.md`、`docs/DEVELOPMENT_ROADMAP.md`の6ファイル。
既存生成コード・数値fixture・設計JSON・既存出力・親フォルダの家計簿は変更していません。

次は結合移動を含めた近似誤差の伝播と、接触診断の判定条件です。
遠い周期コピー・包含、実CAD照合、丸め保証、小R根元fillet、native GUI、ANSYS実機も残ります。
