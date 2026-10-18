# 3D翼面の三角形接触候補検査（Stage 3B-1）

既存の局所Jacobian/法線診断と別に、明示的なXYZ面格子の三角形近似を調べる非Qt/非OCPのAPIを追加した。既存の形状生成・通常表示・CAD生成・JSON/CSV/TurboGrid・出力ガード・公差は変更しない。GUIへの接続、連続曲面の干渉なし保証、Stage 3B全体の完了ではない。

## 追加した入口

- `geometry/mesh_contacts.py::grid_mesh`: S×T×3の明示XYZ格子を、各quadの固定対角線で2三角形へ分割する。頂点・面IDの順序は決定的で、元格子を変更しない。
- `geometry/mesh_contacts.py::mesh_contacts`: indexed三角形mesh間、または同じmeshの非局所自己接触候補を検査する。
- `geometry/blade_contacts.py::screen_blade_grids`: Mainおよび任意のSplitterの4role格子を対象とし、自己検査と最近接周期コピーの組合せを作る。面の再生成や密度の自動選択はしない。

```python
from blade_designer.geometry.blade_contacts import screen_blade_grids

report = screen_blade_grids(main_grids, blade_count,
                           splitter=splitter_grids,
                           tolerance_mm=1e-9, area_epsilon_mm2=1e-16,
                           max_work_per_pair=200000,
                           max_contacts_per_pair=20)
```

各gridsは`le/ps/te/ss`の全4キーと、各roleの有限な実XYZ格子を持つ。XYZはmm、回転軸は+Z、周期角は2π/N。既存`annulus.rotate_xy`と同じ変換で、元格子を変更せずコピーを回す。Splitterの位相はすでに格子へ反映されていること、1主翼ピッチに1Splitterで同じ周期枚数であることが前提。row ID/snapshot、元面の種類、Span/xi座標と採用密度はcallerが対応付けて別途記録する。本APIは入力の由来を推測しない。

閾値はcallerが有限・非負で明示する。上例は試験/診断値であり、CADや製造の合否公差ではない。三角形の面積（外積ノルムの半分、mm²）が`area_epsilon_mm2`以下なら退化として元face IDを列挙し、その面はSAT検査から除外して結果を不完全にする。前段のパラメータ面積密度Jとは別の量である。

## 検査方法

1. triangle AABBから重心位置で二分するBVHを作り、離れたnode/triangle組を除く。元face IDを保持し、自己検査で同一組を重複出力しない。
2. 残った組に分離軸検査（SAT）を行う。両面法線、両面edgeどうしの外積に加え、各面法線とそのedgeの外積も使用し、同一平面上でAABBだけが重なる離れた三角形を区別する。
3. 軸を正規化し、両triangleの投影区間が許容量より離れた軸があれば除外する。大きな共通原点の影響を減らすため、投影前に片側の先頭頂点を差し引く。

交差/頂点接触/edge接触/同一平面の重なりをまとめて接触候補とする。貫入深さや接触と貫通の分類は行わない。非零`tolerance_mm`は**分離軸への投影の許容量**であり、Euclidean最小隙間を測定する値ではない。許容量内の近接を実交差と断定しない。また三角形の接触候補を観測しても、元の連続曲面が接触したとの確定ではない。

実数モデルの分離軸の性質とfloat64実装を区別し、`roundoff_certified=False`を必ず返す。区間丸め保証、曲面からmeshへの誤差包絡はない。座標・面index・型・上限の不正、非有限な中間演算はValueErrorとし、修復や代替形状を作らない。

## 対象と未検査範囲

| 対象 | 今回の範囲 |
|---|---|
| 各roleの非局所自己接触 | 共有頂点IDがないtriangle組を検査。3頂点IDが同じ重複faceも接触候補として残す |
| 各role内の局所隣接面 | 1/2頂点IDを共有する異なるface組は除外。正常な接続と、それを越える局所foldの区別は未実装 |
| 同じ翼の異なるrole間 | 未検査。正常なLE/PS/TE/SS継ぎ目と異常接触の区別が必要 |
| Main–Main / Splitter–Splitter | +1ピッチの全16role組。-1側は逆role組の回転対称性で同等。2ピッチ以上の距離の組は対象外 |
| Main–Splitter | 0/-1/+1ピッチの全16role組。枚数1/2では周期的に同じoffsetを重複しない |
| 完全なsolid包含 | 表面が接触しない包含は未検査 |
| Hub/Tip cap、壁面、ディスク、フィレット、最終STEP | 未検査 |
| 面の標本間、格子対角線依存、丸め誤差 | 連続面としての保証は未対応 |

入力頂点を距離閾値でweldしない。自己検査で共有する「頂点」は座標の近さではなく入力indexである。見かけ上同じ座標でも別indexなら接触候補になり得る。最近接ピッチ検査だけで、強く巻いた翼の全周の離れたコピーまで保証しない。入力gridが派生形状ならそのgridだけが対象で、元CAD面や別表示の形状に結果を流用しない。

Mainだけ・N≥2なら20check（N=1は4）、Splitterあり・N≥3なら88check。各checkは元のgroup/roleと相手、ピッチoffsetを持ち、接触face IDを返す。face IDから元格子のquad/triangleへ戻せる。実際の接触点や体積はまだ計算しない。

## 状態と上限

- `CONTACT_CANDIDATES_FOUND`: 指定した三角形・許容量で候補を観測。打切りがある場合でも観測は残すが、件数を全件数としない。
- `NO_CONTACT_OBSERVED`: 指定した**適格な三角形組**を走査し、候補がなかった。未検査範囲は残り、設計のPASSではない。
- `INCOMPLETE`: 候補未観測だが退化/計算上限等があり、指定範囲の走査も完了していない。

`scan_complete`は明示した範囲内の走査完了だけを表す。除外した局所隣接面等を検査した意味ではない。上位reportの`whole_geometry_verified`/`continuous_surface_certified`は常にFalse、`unchecked`に未検査範囲を残す。退化がある場合はface ID、打切り時は理由を保ち、上位にも`incomplete_checks`として伝える。

`max_work`は1node組検査または1leaf三角形組の列挙を1単位として制限する。元face数を`max_triangles`で制限し、記録した候補が`max_contacts`へ達したら保守的に打ち切る。最後の候補だった可能性があっても、その時点では全件走査済みとしない。上位APIの上限は**checkごと**で、全check合計の壁時計時間やメモリを保証するものではない。同期の重い診断をGUIへ自動接続していない。

## 独立試験

新規54件（mesh38・blade16）。解析的な交差/頂点・edge接触/同一平面重なり、AABBが重なる離れた三角形、正の尺度0.01/1/100と剛体変換、明示許容量、入力不変、BVHで元ID保持、重複face、退化、不正index/型/閾値/上限、非有限演算、計算/候補上限の不完全性を検証する。

`S(s,t)=((s−.25)(s−.75),(s−.25)(s−.75)(s−.5),t)`の非局所交差を検出する。解析Jが非零でも交差する既知例で、局所Jacobianの正則性を全体干渉へ置き換えない。逆に共有edgeの同じ側に重なる隣接triangleは現段階で除外されることをnegativeとして保持する。

`z=(s−.37)²−.001`の曲面はz=0と交差するが、s=0/.5/1だけで作るmeshは上側にあり、候補なしになる。内側tetrahedronを完全に包む外側tetrahedronにも表面接触はない。この2例で、候補なし・走査完了を連続面/solidの干渉なし保証にしない。

実`BladeParameters()`の1000枚では5×33格子、基準spline fit33から最近接Mainとの35候補（LE–LE17、TE–PS18）を観測した。未完了checkは0。これはmesh候補の件数で、独立した接触領域の数や連続面の貫入数ではない。最初の追加50試験で1件、「PS–SSに限る」という新試験側の仮定が失敗した。実際のrole/faceを保存してその仮定を修正し、別に解析PS–SS交差を+1ピッチで作る試験を追加した。既存の数値参照/期待値は変更していない。記録は`artifacts/quality-mesh-contacts/1000-blades.json`。

最終コードの関連129件成功（`20261018T081120Z-14f65761`）。限定Ruffも成功。

## 現既定の測定

同梱既定JSONから最初のImpeller rowを選び、Main/Splitterの基準spline fit65を固定して、標本格子だけを増やした。主翼枚数は11。源面のモデル差と三角形の標本密度差を混同しない。

| Span×xi標本数 | triangle/role | check数 | 接触候補 | 不完全check | work合計 | 隣接組の除外数 |
|---|---:|---:|---:|---:|---:|---:|
| 5×33 | 256 | 88 | 0 | 0 | 83,194 | 10,024 |
| 9×65 | 1,024 | 88 | 0 | 0 | 481,988 | 44,584 |

閾値は1e−9 mm/1e−16 mm²、上限はcheckごとにwork200,000・候補20。最大workは細かい格子でも130,852で上限以内だった。BVHのAABB候補はそれぞれ32,230/237,496で、SAT後の接触候補は0。表の除外数は今回列挙した共有頂点の隣接組で、一意の物理接続箇所の数ではない。

全回帰との同時実行で2格子の壁時計時間は208.468秒。単独実行の性能保証やnative GUIの応答性測定ではない。どちらも指定したmesh範囲の走査完了であり、局所隣接面・role継ぎ目・遠いコピー・包含・元曲面の干渉なしを保証しない。

根拠は`artifacts/quality-mesh-contacts/probe.py`、`default-probe.json`。row ID/名前・元JSON hash・固定fit密度・標本数と全checkを保存した。原本/同梱既定のSHA256は`aa724c8253463289caec919960d7d486d698765cee35202c13e4efd17a603dd6`で、書込みは行わない。

## 全回帰の確定記録

**全1,318一意件成功**（通常1,275・実CAD43）。既存1,264 IDを維持し、新規54 IDを追加した。failure/error/skip/実行漏れ/重複/想定外IDは0。回帰開始時に固定した286入力はhash不変、原本/同梱既定JSONも一致した。既存数値fixture/期待値は変更していない。限定Ruffも成功。

根拠は`artifacts/quality-mesh-contacts/final-test-coverage.json`、`source-hashes.json`、`collected-tests.txt`。通常6群と実CAD1群のJUnitを全収集IDと照合した。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 461.355 | 20261018T081215Z-5b5900e7 |
| 通常1 | 143 | 409.849 | 20261018T081215Z-dffce860 |
| 通常2 | 122 | 479.838 | 20261018T081215Z-dd6c58bc |
| 通常3 | 191 | 345.387 | 20261018T081215Z-3ba376a8 |
| 通常4 | 146 | 446.273 | 20261018T081215Z-f3d337f8 |
| 通常5 | 557 | 569.796 | 20261018T081215Z-91474aa5 |
| 実CAD | 43 | 918.240 | 20261018T081215Z-4435e2ea |

実CAD43件は既存回帰であり、今回のmesh接触APIを実solidの交差・貫入体積と照合した試験ではない。既存CAD成功や候補0を現既定の根元fillet成立・ANSYS Import/Mesh成功に置き換えない。

## 次の段階

局所隣接面・role継ぎ目を越える異常交差の識別、曲面/三角形間の誤差と適応細分、離れた周期コピー・包含、実solidとの照合を追加する。その後に出力前の共通品質レポート/拒否条件を別ワーク単位で設計する。今回の候補検査だけで既存の出力可否を変えない。native GUI、高DPI、ANSYS Import/Meshは未検証である。
