# 翼面評価の基盤（Stage 3A-1）

## 今回の到達点

Qt・OCP・ファイル形式に依存しない`geometry/surface_evaluation.py`を追加した。既存CADのBスプライン構築と、派生カットのSpan列補間をこの数値層へ移した。生成式・係数構築順・公差・既定値・設計値・JSON／CSV／TurboGrid書式は変更しない。

これはStage 3A全体の完了ではない。現在は異なる翼面定義が存在し、その差を測れる評価基盤を作った段階である。表示・CAD・カットを単一方式へ切り替える変更は行わない。previewのwireframeも従来の経路を維持する。

## 現行3方式と対応座標

| 経路 | Streamwise側の対応 | Span間の方式 |
|---|---|---|
| PreviewのSpanwise接続 | role別の表示用再サンプル曲線の同じindex。PS/SS等は曲線長で再サンプルされる。輪郭線自体はmaster点 | 入力断面を結ぶXYZの直線群 |
| 派生Shroudカット | role別master曲線を最大点数の共通index格子へ再サンプル。metadataも同じ格子 | r／連続theta／Zの区分線形補間。各streamwise列で異なる`source_span`を求める |
| CAD | PS/SS等の`m_blade_norm`をそのroleの始終端で0〜1に正規化。座標がない端部はindexを使用 | Cartesian XYZのtensor Bスプライン。Streamwise／Spanとも最大3次。従来のjoin接線条件を維持 |

従って、同じ数値の0〜1を渡しただけで同じ物理位置に対応するとは限らない。role（LE／PS／TE／SS）と、master／表示用曲線、index／曲線長／`m_blade_norm`を明示する必要がある。全閉輪郭のindexを跨いで補間しない。

派生断面の`section.span`は新しい公称Spanであり、元翼面上の`source_span`はstreamwise列ごとに異なる。これらを無断で同一視しない。Splitterの短いLE〜TEも、主翼の全区間と自動で一致させない。

## 共通API

- `validate_surface_rows`: 有限なNx3行、Hub=0→Tip=1の厳密なSpan順、各role内の0→1対応座標を検査する。
- `interpolate_span_columns`: 既存カットと同じ重み・演算順で列ごとのSpanを補間する。thetaのwrap補正・壁面投影・データ修復はしない。
- `SectionSurface`: 指定された対応座標で区分線形面を評価する。XYZとr/theta/Zを明示的に区別する。円筒座標のthetaはcallerが連続値を供給する。
- `fit_surface_spline`／`SplineSurface`: 従来CADと同じ格子・接線・knot・degree・coefficient順を使う。OCPへのpole転送はCAD adapterに残す。
- `compare_surfaces`: 同じ対応格子での最大距離・RMS [mm]を返す。Hausdorff距離、全面偏差の上限、法線反転・交差の証明、PASS判定ではない。

queryのNaN・範囲外・空配列は拒否し、自動clamp／外挿はしない。入力行を所有する`SectionSurface`はcallerの入力変更を取り込まない。既存CAD adapterの省略／空parametersの扱いは維持する。

## CAD／派生カットの互換性

`cad/occt_backend.py::create_surface`から係数構築を移しただけで、33→65→129→257→513の候補格子、master点での既存偏差検査、境界接線、cap、sewing、BREP、フィレット、STEPの条件は維持する。新評価器はCADとは別の点評価を提供し、OCPを通常編集processへimportしない。

`geometry/impeller_trim.py::_blend`は共通の`interpolate_span_columns`へのimport aliasにした。境界探索42回、円筒カット、元頂点保持、beta／厚さ／source_spanの追跡は従来どおり。新たなCAD出力制限の解除は行わない。

## 検証

新規26件（数値24・実OCCT 2）。独立した平面・3次多項式曲面、2断面間のXYZ chordと円筒arcの解析差、非等間隔Span／Streamwise格子、端部接線、密度9／17／33、入力不変、不正入力・外挿拒否を確認する。実OCCTは独立backend processで23×29の内部点を評価し、共通数値評価器と比較する。CAD未導入環境では既存CAD試験と同じoptional skipとし、skipを成功として扱わない。

最初の実装ではSciPyが評価軸を元のaxis=1へ戻すことを取り違え、新評価器の6件が失敗した（既存を含む79件成功、`20261017T215921Z-359f393b`）。軸を正しい順へ戻して修正し、新規26件成功（3.40秒、`20261017T215957Z-f73ac5a4`）、既存生成・カットを含む関連85件成功（41.14秒、`20261017T220059Z-ce5c2165`）。解析解や既存期待値は変更していない。

初回全回帰は、新CAD試験のbackend未導入時の扱いを既存に合わせるため、管理下の専用process treeだけを停止し、結果を再利用しない。最終全回帰は別領域`artifacts/quality-stage3a1-final/`で実行した。

最終全回帰は**1,028一意件成功**（通常991・実CAD37）。既存1,002 IDを全て維持し、新規26 IDを追加。failure／error／skip／未実行／重複／想定外IDは全て0。固定244入力は回帰開始からhash不変、原本と既定JSONの一致を確認した。既存数値fixtureは変更していない。単一pytest processではなく、次の7群のJUnitと収集IDを照合した結果である。根拠は`artifacts/quality-stage3a1-final/final-test-coverage.json`、`source-hashes.json`。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 416.309 | 20261017T220248Z-e52ca171 |
| 通常1 | 143 | 375.831 | 20261017T220248Z-e5d5ebe5 |
| 通常2 | 122 | 431.709 | 20261017T220248Z-6f6f4b73 |
| 通常3 | 191 | 304.317 | 20261017T220248Z-97797c54 |
| 通常4 | 146 | 403.958 | 20261017T220249Z-da5b2631 |
| 通常5 | 273 | 432.183 | 20261017T220249Z-aa228940 |
| 実CAD | 37 | 825.911 | 20261017T220249Z-609f8b97 |

## 既存数値と診断用モデルの比較

変更前のGitソースを独立moduleとして読み込み、7条件・40patchでOCCTのdegree／knot／multiplicity／全poleと13×23の評価点が完全一致した。共通数値評価器と実OCCTの同格子での最大距離は6.0711e-14 mmだった。これは浮動小数点評価の比較であり、物理形状精度を示す値ではない。結合Rake／gap／Splitter／派生カットでは、主翼・Splitterの計30曲線のr／theta／Zとmetadata、beta／厚さ、派生壁面が変更前と完全一致した。原本JSONのhashも維持した。

以下は**masterの同一対応座標へ揃えた診断用モデル**を41×101点で比較した最大距離 [mm]。現行previewのindex接続や現行trimの共通index格子そのものの誤差ではない。数値splineは513格子・従来join接線を使う。各条件のLE／PS／TE／SS、主翼／存在するSplitterの最大値を記載する。

| 条件 | XYZ線形−円筒線形 | XYZ線形−spline | spline 65−513格子 |
|---|---:|---:|---:|
| 既定Impeller | 0.781813 | 0.000232510 | 0.0188224 |
| 既定Diffuser | 5.12e-14 | 8.40e-6 | 0.00403596 |
| 既定RC | 2.86e-14 | 9.24e-6 | 0.00784286 |
| 半径方向・3断面 | 0.00119464 | 1.55e-5 | 0.000474390 |
| 強ねじれ・3断面β=20/−10/50° | 11.4690 | 18.1302 | 0.0520928 |
| Rake 12°＋gap 0.4/0.8＋専用Splitter | 0.00174541 | 0.000995866 | 0.000548276 |
| 上記＋Shroud面積10%／外径5%カット | 0.000752415 | 0.000752393 | 0.000652960 |

129／257格子と513格子の差も保存した。全7条件で今回の標本差は格子増加に伴い小さくなったが、513格子が真値である保証や面全域の誤差上限ではない。Diffuser／RCと派生カットの汎用spline評価は診断用途であり、未対応CAD出力の成功としない。根拠は`artifacts/quality-stage3a1-final/surface-probe.json`と再現用`probe_surfaces.py`。

## 残るStage 3A-2

実際のpreview／trim／CADが使う異なる対応座標と、派生カットの`source_span`を明示して比較する。今回の診断用の同一座標モデル比較を、そのまま現行表示誤差として報告しない。密度差は参照513格子との標本差であり、誤差上限や収束保証ではない。

その結果から正本となる面定義と誤差予算を決め、互換性を保つ切替単位を設計する。全面偏差、密なSpan間品質、Jacobian・法線反転・周期翼／主翼-Splitter干渉、CAD cap・STEP後の全面偏差は未実装／未検証。実モデルの根元フィレット成立、native画面、高DPI、ANSYS Import/Meshも今回の成功とはしない。

## 変更ファイル

`geometry/surface_evaluation.py`、`geometry/impeller_trim.py`、`cad/occt_backend.py`、`tests/test_surface_evaluation.py`、`tests/cad/test_surface_evaluator.py`と関連資料。GUI・設計パラメータ・保存形式・既定JSON・数値fixtureは変更しない。
