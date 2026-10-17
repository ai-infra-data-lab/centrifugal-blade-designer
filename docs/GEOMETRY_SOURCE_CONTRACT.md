# 形状正本・実断面指標・XYZ CSV（Stage 2A）

## 対象と操作

2026-10-17。G01の改善を互換経路と実3D経路に分けた最初の実装単位。

- `View → Selected Row Metrics`: 選択翼列の実断面を測定する。Main／SplitterとSpanを選べる。再計算ボタンで現在入力から形状と指標を更新する。
- `File → Export → Selected Row XYZ CSV`: 同じ生成器のmaster点を新形式のCSVへ出す。子午面だけの選択時は翼列を選ぶよう促す。
- 既存`Metrics`／`Diffuser Curvature`はLegacy radial 2Dと明記する。既存の符号付き2D曲率、XY指標、グラフ操作を維持する。
- 既存Diffuser Segments／Contour CSVは列・順序・値・改行を維持する。メニューのtooltipと保存画面／完了表示でlegacy経路を明示する。
- 最適化はLegacy radial 2D screeningのまま。baselineとcandidateを識別し、中央の子午面3Dや性能最適化の結果とはしない。

## 正本と識別

| 経路 | 形状の正本 | 識別 |
|---|---|---|
| 中央2D／3D、Passage、Selected Row Metrics、新XYZ CSV | Impeller: `generate_impeller`、静翼／RC: `generate_diffuser_3d`のmaster曲線 | row ID・名前・kind、`meridional_3d`、base/derived、snapshot hash。指標はMain/Splitter・Spanを別選択 |
| 既存Metrics／Curvature／XY CSV | `BladeDesigner.generate_diffuser`の独立した放射状2D | `legacy_radial_2d`。旧CSVの内容には新metadataを挿入しない |
| 最適化の候補・制約 | 旧2D mapper／generator／feasibility | baselineのrow context・snapshotと、実際に生成したcandidate設計の別snapshot。baselineは通常の編集で勝手に更新しない |

`models/geometry_source.py`は非永続の結果ID。`fileio/geometry_source.py`がCADと同じschema 0.4 canonical JSONからSHA256を計算する。geometry層はQt・JSON・CSV・CAD kernelへ依存しない。hashは設計入力全体を識別し、形状成立・衝突なし・出力ファイルの同一bytesを証明するものではない。旧2Dのrow名は選択行のcontextであり、子午面のLE/TEを使ったことを意味しない。

現既定のRCでは、実Hub camber R130→90 mm、Z95 mmが中央表示・新指標・新CSVの正本。旧camber R100→160 mmは互換経路として区別する。断面生成、β／θ／PS/SS、入力分布、既定値、JSON、TurboGridの方式は変更しない。

## 測定の定義と限界

`geometry/section_measurements.py`が渡された実断面だけを測る。

- Camber endpoint chord XYZ: camberのLEとTEのXYZ直線距離。丸いcapの最先端間距離とは定義を分ける。
- Camber polyline length XYZ: camberの隣接XYZ点間距離の和。描画投影の長さではなく、サンプル密度に依存する近似値。
- Pitch: camberの局所Rに対して2πR/N。Camber chord / Pitchはこの幾何比で、流体解析の性能指標ではない。
- PS/SS |curvature| XYZ: master曲線のchord arclengthをパラメータとするCubicSplineの、`|r'×r''|/|r'|³`。非負の空間曲率であり、旧2Dの符号付き曲率と同じ量ではない。LE/TE cap、Span方向曲率、面のG1/G2、曲面間距離・干渉を検査しない。
- Throat／閉塞は既存Passageの別解析を使う。断面指標から真の3D最小スロート面積を推定しない。

派生カットでは派生後の実断面を測定し、`derived`を示す。このvariantは派生カットの有無を示し、`base`にも設計値としてのRake／クリアランス／Splitterは含まれ得る。編集用の角度・厚さは従来どおり元の分布。クリアランス時のTipは実際の翼Tipであり、TurboGrid用Shroud延長断面とは別。Splitterも実生成した短い断面を使う。

## 新XYZ CSV

UTF-8 BOM付きCSV。長さmm、回転軸Zの内部XYZをそのまま出力する。Full Annulusの複製ではなく、1主翼＋あれば1Splitterの全Span。各LE/PS/TE/SS master点を順方向に列挙する。SSを反転して一閉輪郭にする形式ではなく、segmentごとの端点も保持する。TurboGrid Profile Points、Mechanical STEP、旧XY CSVの代替フォーマットではない。

列: row_id, row_name, row_kind, engine, variant, snapshot_hash, significant_digits, blade_set, span, segment, index, m_blade_norm, x_mm, y_mm, z_mm, r_mm, theta_deg。

選択した有効桁数で数値を丸める。masterの再サンプル／修復／Shroud延長は行わない。元snapshotが同じでも桁数・形式が違えばファイルbytesは異なる。全点を検証・メモリ上で整形してから同じ親のtemporary fileへ書き、flush/fsync後に単一replaceする。無効形状・整形失敗では既存CSVを開かず、公開失敗では既存ファイルを保持する。

## 更新・失敗時の扱い

有効な選択静翼の生成が、旧2D計算や参考Impeller計算の失敗だけで止まらないようにした。旧2Dが失敗した場合、旧グラフと表を消し、エラーを明示する。`MainWindow.geometry`の最後のlegacyオブジェクトは互換APIのため残るが、currentなlegacy結果としては公開せず、`geometry_sources`のlegacy IDを除く。新指標とPassageは有効な選択実形状を使う。

現在の選択3D形状が無効なら、従来の最終有効プレビューを保持してエラーを示し、新指標とPassageの元を解除する。この場合でも旧2Dが有効なら、legacyとして旧指標・編集用分布・`MainWindow.geometry`を更新する。3Dの失敗と2Dの失敗を同一視しない。新CSVは表示キャッシュを使わず現在入力を再生成し、旧形状を誤出力しない。設計変更予約・project設定・CAD設定・子午面選択で新指標を失効させる。Camera・Undo・設計値は指標の閲覧や断面選択で変えない。

## 未完了の境界（Stage 2B以降）

これはG01の完全解消ではない。現行の共通`validate_parameters`は旧r_le/r_te等も検査し、3D generatorもその契約を使う。旧半径の不正など共通検証段階の失敗を、選択行専用検証へ分離する作業は残す。JSONのLoad/Saveも従来の全設計検証を維持し、不成立な旧2DやImpellerの保存・読込みを許す変更はしない。数値エラーを適当な既定値へ置換して迂回しない。

最適化の実3D制約化、全Span／周期翼／主翼-Splitter干渉、実スロート面、CADとの共通surface契約、根元フィレットの成立は未完了。native操作・ANSYS Import/Meshはこの変更では検証しない。

## 検証

新規34ケース（形状正本・断面・CSVの32件と、current-cell端点保護の2件）。独立解析解は直線・円筒らせんの空間曲率、弦長、長さ・密度収束、剛体変換不変・一様拡大の逆曲率。統合は3翼列の全master点、CW/Rake/gap/trim/Splitterの実断面、既存CSV bytes、未選択計算の故障注入、無効現在形状と既存出力保護、snapshot、camera／history、Main/Splitter選択保持を確認する。

実装途中の試験ではPassageのsourceがtupleである前提漏れ2件、Qt tuple itemDataの再選択失敗1件、既定6桁CSVを15桁相当で比較した前提漏れ1件を検出。前提漏れは既存API／有効桁数の数学的丸め限界へ合わせ、Qt選択は安定した文字列IDへ修正。既存の数値fixtureは変更していない。

既存関連30件成功（20261017T140610Z-07e009ae、108.51秒）。新規を含む関連37件成功（20261017T141149Z-e631483a、81.35秒）。その後、既存CSVの比較2件とtooltip／Fit Viewの整合を追加し、全回帰を開始。実行途中に失効／測定失敗時のtooltipへ旧snapshotが残る箇所を修正し、tooltipの試験も加えた。修正前の全回帰は管理下の専用プロセスツリーだけを停止し、成功件数へ数えず、最終ソースで全904件を再開した。その後のoffscreen表示確認で小画面時にgraph下端が隠れたため、指標表とplotの最小高さ／stretchを調整し、最初のダイアログでouter scrollなしに全graphが見えることをGUI試験へ追加した。最終表示コードで通常869件を再実行。CAD35件はGUIをimportしないことをcollect時のmodule一覧と依存ソースASTで確認し、CAD／geometry／models／fileio／CAD試験のhash不変を証明して継続した。初期に中断した通常群は成功件数へ含めない。根拠はartifacts/quality-stage2/cad-import-boundary.json、cad-source-boundary.json、source-hashes-before-layout.json。通常群で既存test_target_angle_thickness_and_section_isolationの不一致を検出。旧2Dが有効でも静翼3Dの失敗で旧結果更新まで止めていた回帰を、`_display_legacy_geometry`へ分離して修正した。既存テストと数値期待値は変更せず、入力分布グラフの既存サンプルを保持し、旧計算が失敗した場合だけ実断面へフォールバックする。修正後の対象切替＋新GUI13件成功（20261017T142804Z-3ade75e8、76.97秒）。その最終コードで通常869件を再実行し、CAD35件は依存ソース不変を再確認して保持する。静翼3Dエラーの従来prefixも維持し、該当1件を修正後に再検証（20261017T144122Z-cfd65b02、成功）。続く六群実行ではUndo試験→基本GUI試験の順序で点削除ボタン2件が失敗した。既存ControlPointEditorが選択範囲変更のみを監視していたため、current cellだけが変わる実Qt操作を旧Git実装で単独再現し、currentCellChangedも監視する2行の補強を加えた。端点／内点の直接検査2件を追加し、再現順序の既存42件と合わせ44件成功（20261017T145104Z-16ec93a9、150.50秒）。根拠はartifacts/quality-stage2/selection-baseline-comparison.json。既存テスト・数値期待値は変更しない。最終コードで通常871件を六群で再実行し、依存が不変のCAD35件と全906 IDへ照合する。最終全回帰は**906一意件成功、failure/error/skip/missing/unexpected/duplicateはすべて0**。以前の872 IDを全て維持し、追加34 IDも照合した。固定237入力のhashと原本／既定JSON不変を確認。履歴参照・旧GUI期待値は変えていない。最終集計はartifacts/quality-stage2/final-test-coverage.json。単一pytestプロセスの結果ではなく、次の7群のID照合である。

| 群 | 件数 | 結果・時間 | 実行ID |
|---|---:|---|---|
| 通常0 | 116 | PASS 393.95秒 | 20261017T145443Z-7215eb57 |
| 通常1 | 143 | PASS 390.03秒 | 20261017T145443Z-1b8db71e |
| 通常2 | 122 | PASS 401.71秒 | 20261017T145443Z-b9e76cd6 |
| 通常3 | 191 | PASS 380.00秒 | 20261017T145443Z-89b71452 |
| 通常4 | 146 | PASS 373.61秒 | 20261017T145443Z-ef96e84b |
| 通常5 | 153 | PASS 384.64秒 | 20261017T145443Z-5be14e01 |
| CAD（依存ソース不変を検査） | 35 | PASS 732.73秒 | 20261017T141713Z-c7d4d930 |

途中で検出したGUI回帰・選択状態の問題は上記の通り修正済み。最終回帰に試験失敗・環境エラーはなかった。native GUI／高DPI、ANSYS Import/Mesh、現既定形状の根元fillet成立は未検証／未解決のまま。

画像の確認は、検証プロセスにWindows既存Meiryoを明示ロードしたQt offscreen環境でRCとSplitter Tipを対象に実施した。最初のplot全体と説明が有界ダイアログ内に収まることを確認。製品のフォント設定は変更せず、native操作・高DPIの検証とは区別する。
