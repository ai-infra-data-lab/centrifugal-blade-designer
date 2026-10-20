# 異なるrole間の継ぎ目診断（Stage 3B-2c）

## 変更範囲と操作

`geometry/role_seams.py::screen_role_seams`はcallerが渡したLE/PS/TE/SSのXYZ格子を
1つの診断用三角形メッシュに組み立て、既存のBVH/SAT・共有edge・共有vertex/link検査を使います。
生成・GUI・JSON・CSV/TurboGrid/CAD・既存`screen_blade_grids`の検査範囲は変えません。
診断APIの追加であり、3Bの共通品質レポートや出力ゲートの完成ではありません。

```python
from blade_designer.geometry.role_seams import screen_role_seams
report = screen_role_seams(
    grids, join_tolerance_mm=1e-8, tolerance_mm=1e-9,
    area_epsilon_mm2=1e-16, max_work=500000,
    max_contacts=100, max_triangles=20000,
)
```

単位はmm。格子の第1軸は**同じ物理Span位置を表す同じ順序の行**、第2軸は各role内の輪郭位置です。
roleごとの輪郭点数は違っていてもよく、Span行数は一致必須です。
行数だけでは物理対応を証明できないため、その責任はcallerに残します。
上記公差は使用例であり、任意形状への推奨製造公差ではありません。

## 接続と座標の保持

接続はLE始端–SS始端、LE終端–PS始端、TE始端–PS終端、TE終端–SS終端の4本だけです。
各Span行の対応端点間距離が`join_tolerance_mm`以内なら診断用の頂点IDを共有させます。
座標はrole順LE/PS/TE/SSの早い方を採用し、平均化はしません。
継ぎ目ごとに一致数・不一致数・最大gap・最大移動量・不一致行の例を返します。
入力配列と実形状を変更せず、内点や宣言外の境界は同じ座標でも結合しません。

非ゼロの接続公差では、検査対象は元格子そのものではなく、報告した微小変位を含む
`seam_merged_triangle_approximation`です。元座標に対する厳密な非干渉証明ではありません。
誤った対応を、公差を広げて正常扱いにしてはいけません。
接続ずれが残ればmesh側が正常でも上位の`scan_complete=False`とします。

## 判定範囲と上限

全roleを同じmeshへ入れることでrole内自己検査に加え、roleをまたぐ接触を扱います。
通常接続は既存のedge/vertex分類で除外し、折返しや別role内点との重なりは候補として返します。
`contact_role_pairs`は`mesh_report.contact_pairs`と同順。face IDは連結メッシュ内のIDです。
正常なedge接続はG0の局所接続を意味し、G1接線・曲率連続の確認ではありません。
Hub/Tipの開口は境界pathであり、閉solidとは判定しません。

接触があれば`CONTACT_CANDIDATES_FOUND`を優先し、完了可否は別途`scan_complete`を読みます。
未判定、非多様体edge/link、退化、接続ずれ、work/contact上限は完全扱いにしません。
資源上限は4role合計に適用。不一致行の例数は`max_contacts`まで、総数は省略しません。
入力不正や非有限演算を正常結果に置き換えません。

`NO_CONTACT_OBSERVED`は指定メッシュで候補がなかったという意味です。
三角形間の曲面、密度収束、float丸め、法線の外向き・winding、遠い周期コピー、他翼列、
主翼とSplitter間、solid包含、Hub/Tip cap・壁・ディスク・filletは保証しません。
主翼–Splitter/近接周期診断は`blade_contacts.py`の別APIとして保持します。

## 試験と既定モデル

新規`tests/test_role_seams.py`は22件。解析的な開口矩形チューブ、4本それぞれの接続ずれ、
明示公差内の移動量、edgeでの折返し、同座標の別role内点、回転・並進・尺度、
不正入力、退化、非有限演算、work/contact/triangle上限を確認します。
既存117件と初回新規20件の関連137件、追加後の新規22件が成功。
既存期待値・fixtureを変更せず、限定Ruffも成功しました。

同梱既定JSONからfit65の基準splineを5×33でサンプルしました。
join tol=1e-8 mm、contact tol=1e-9 mm、area threshold=1e-16 mm²、max_work=500,000、max_contacts=20。
全ケースで三角形数1,024、正常edge組1,408・正常vertex組3,714、候補/未判定/link不良/接続ずれ0。

| 対象 | work units | 最大診断移動量 [mm] |
|---|---:|---:|
| Impeller Main | 56,604 | 1.12e-16未満 |
| Impeller Splitter | 63,416 | 1.01e-14未満 |
| Diffuser Main | 30,844 | 2.01e-14未満 |
| RC Main | 32,902 | 2.85e-14未満 |

これは指定密度の数値試行で、全域保証・実機CAD/ANSYSの確認ではありません。
記録は`artifacts/quality-role-seams/probe.py`・`default-probe.json`。
全回帰の収集/実行ID・固定入力ハッシュは同フォルダの`final-test-coverage.json`へ記録します。

最終全回帰は**1,755一意件成功**（通常1,710・実CAD45）。既存1,733 IDを維持し、新規22 IDを追加。
failure/error/skip/実行漏れ/重複/想定外IDは0、固定322入力（原本・同梱既定JSONを含む）はhash不変。
前回のJUnit所要時間を使ってファイル単位で通常7区分へ分割し、CAD1区分を加えた8区分をrunnerで実行し、全IDを照合しました。
CADの成功は既存経路の回帰であり、本診断をCAD面や出力ゲートへ適用したという意味ではありません。
基礎63件、関連137件、追加後の新規22件、限定Ruff、差分検査も成功しました。製品試験で失敗・環境エラーはありません。
実画面・ANSYS Import/Meshは未実施です。

変更は`blade_designer/geometry/role_seams.py`、`tests/test_role_seams.py`、本書、
`FEATURES.md`、`docs/ARCHITECTURE.md`、`docs/DEVELOPMENT_ROADMAP.md`の6ファイルです。
既存生成コード・数値fixture・設計JSON・既存出力・親フォルダの家計簿は変更していません。

## 次の課題

曲面–triangle誤差と適応細分、遠い周期コピー・包含、実CADとの照合を整備してから、
共通品質レポートと出力ゲートの採用条件を決めます。3Aの全面誤差予算、実モデル小R根元fillet、
native GUI応答性、ANSYS Import/Meshも未完了です。Hypothesis/uvは追加しません。
