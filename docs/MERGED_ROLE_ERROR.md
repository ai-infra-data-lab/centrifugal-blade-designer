# 継ぎ目結合の移動量を含む誤差（Stage 3B-3c）

## 変更範囲

`geometry/merged_role_error.py::merged_role_error_envelope`を追加しました。
整合格子の結合前上限と、診断用の継ぎ目結合で実際に動く頂点を対応づけます。
元spline/設計値・GUI・JSON・各出力を変えず、既存出力ゲートにも自動適用しません。

```python
from blade_designer.geometry.merged_role_error import merged_role_error_envelope
report = merged_role_error_envelope(
    surfaces, target_mm=0.02, join_tolerance_mm=1e-8,
    max_depth=6, max_seed_cells=1024, max_triangles=20000,
)
```

例は製造公差の推奨値ではありません。各roleの基準SplineSurfaceと物理Span対応の前提は
[整合格子](CONFORMING_ROLE_GRIDS.md)を継承します。最終CAD/STEP面を表すとは限りません。

## 接触診断と同じ結合規則

`role_seams.py`の既存の組立てだけを`_role_mesh`へ分離し、旧診断と新APIの両方から呼びます。
4本の宣言済み継ぎ目だけを結合し、早いroleの座標を採用、内点の空間的weldingや平均化はしません。
旧診断のfield・検査範囲・顔順は維持します。新規試験では同じ組立てを直接mesh_contactsへ渡した結果と
旧診断のmesh_reportが一致することを確認しています。

返す`mesh.vertices`は元頂点テーブル、`mesh.source_faces`は結合前、`mesh.faces`は結合後の頂点IDを参照します。
`vertex_roots`は対応ID、`face_roles`は三角形順のroleです。未使用となる頂点スロットもテーブルに残します。
描画/計算ではfacesの参照を使います。sourceの係数や格子配列そのものは変更しません。

## 誤差の式と対応

結合前三角形の頂点P_i、結合後Q_i、同じ重心係数λ_i≥0・Σλ_i=1とすると、
`|Σλ_i Q_i−Σλ_i P_i| ≤ Σλ_i |Q_i−P_i| ≤ max_i |Q_i−P_i|`です。
したがって各三角形fについて

`E_merged(f) = E_unmerged(f) + max_vertex_displacement(f)`

と評価します。結合前上限は整合後の基準spline対三角形誤差と四隅評価差をすでに含みます。
結合上限値を一律に加えず、実際に動いた頂点から三角形ごとのallowanceを求めます。
元の三角形の配列順は各roleの格子セルrow-majorでABC/ACDの2枚。セル上限を各2枚へ対応づけます。
`unmerged_triangle_upper_mm`・`triangle_move_allowance_mm`・`merged_triangle_upper_mm`は
返した`mesh.faces`と同じ順序/件数です。`error_applies_to=merged_role_triangles`を明示します。

この議論は実数モデルの対応点での上限です。float64の丸めは区間保証せず、
`roundoff_certified=False`を維持します。厳密な製造公差証明ではありません。

## 失敗と未達

整合格子で資源上限または継ぎ目不一致があれば、その状態を引き継ぎ`mesh=None`とします。
粗い代替面や部分結合メッシュで成功を装いません。
結合前が目標以下でも追加移動で目標を超えれば`UNRESOLVED`、超過三角形数も記録します。
自動的な目標緩和・座標修復・再fit・追加細分はしません。
全三角形で数値上限が目標以下のときのみ`NUMERIC_TARGET_MET`とします。

`contact_ready=False`、`whole_geometry_verified=False`のままです。
三角形の退化・接触・包含・遠い周期コピーは検査せず、法線/windingや閉solidも保証しません。
三角形に候補がないことを、その間の連続曲面の非干渉証明へ読み替えてはいけません。
SATの投影公差とEuclidean誤差も同一視しません。誤差を接触判定へ使う条件は次の課題です。

## 試験

新規`tests/test_merged_role_error.py`17件：ゼロ移動、結合だけで予算超過するnegative、
無移動roleへの非加算、密な重心係数点による独立照合、旧接触診断とのmesh_report一致、
資源/接続ずれ/元誤差未達、型/範囲、回転・並進・尺度、目標境界と件数対応、入力不変を確認します。
基礎63件、最終関連55件が成功。最初の関連51件中1件は、新規試験の`>=0.01`が
実際の0.009999999999999787を拒否しました。独立した解析値0.01に対する許容差付き比較へ修正し、
APIの計算値・目標や既存fixtureは変えていません。

共通化前に保存した正常/公差内gapの2ケースと、共通化後の旧screen_role_seams出力の全fieldが一致。
記録は`artifacts/quality-merged-error/old-seam-reports.json`。限定Ruffも成功しています。

同梱既定fit65、目標0.02 mm、join tol=1e-8 mm、合計20,000三角形で4ケースを試行しました。
全ケースで`NUMERIC_TARGET_MET`。これは数値誤差の確認で、実CAD/ANSYSや非干渉のPASSではありません。

| 対象 | 三角形数 | 最大頂点移動 [mm] | 結合後最大数値上限 [mm] |
|---|---:|---:|---:|
| Impeller Main | 5,152 | 1.11e-16 | 0.01300642 |
| Impeller Splitter | 3,264 | 1.00e-14 | 0.01130303 |
| Diffuser Main | 512 | 2.01e-14 | 0.00485078 |
| RC Main | 512 | 2.84e-14 | 0.00404232 |

試行は`artifacts/quality-merged-error/probe.py`・`default-probe.json`、
全回帰の収集/実行IDと固定入力hashは同フォルダの`final-test-coverage.json`へ記録します。

最終全回帰は**1,810一意件成功**（通常1,765・実CAD45）。既存1,793 IDを維持し、新規17 IDを追加。
最終failure/error/skip/実行漏れ/重複/想定外IDは0。固定328入力（原本・同梱既定JSONを含む）はhash不変。
通常7区分とCAD1区分をrunnerで実行し、全IDを照合しました。環境エラーはありません。
Ruff・差分検査も成功。CAD45件は既存経路の回帰であり、新APIの最終CAD面適用ではありません。
native GUI/F5・ANSYS Import/Meshは未実施です。

変更は`blade_designer/geometry/role_seams.py`（組立て共通化）、`blade_designer/geometry/merged_role_error.py`
（結合後誤差）、`tests/test_merged_role_error.py`、本書、
`FEATURES.md`、`docs/ARCHITECTURE.md`、`docs/CONFORMING_ROLE_GRIDS.md`、`docs/DEVELOPMENT_ROADMAP.md`の8ファイル。
設計アルゴリズム・数値fixture・設計JSON・既存出力・親フォルダの家計簿は変更していません。

次は誤差を含む接触/近接の判定条件です。丸め保証、遠いコピー/包含、実CAD照合、
全面誤差予算、小R根元fillet、native GUI、ANSYS実機も未完了です。
