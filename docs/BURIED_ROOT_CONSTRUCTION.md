# 根元の内部延長と実フィレット

2026-10-21。現既定Impeller＋Splitterと仮ディスクの根元位相を修正する。
設計値・原本JSON・同梱既定・指定R・CAD公差は変更しない。

## 構成

`geometry/spline_root_extension.py::extend_spline_root`はSpan最初の多項式を負のSpanへ延長する。
元の次数と内部knotを維持し、Greville点の係数変換で既存0〜1の数学的面を保つ
（float丸め差は存在する）。Qt/OCP/出力形式には依存しない。

CAD assemblyでは全role共通のSpan延長率を使用する。基準延長寸法は
`max(0.1 mm, 20 × 指定CAD公差)`、率はHub/Tipの標本対応距離から計算し、0.1超を拒否する。
これは内部構築量であり、全位置で一定の法線距離を意味しない。元の翼TipとSpan 0〜1は維持する。
結合前に延長capからHubを差し引き、外に残るfaceがないことを実カーネルで確認する。
capが隠れない場合は拒否し、延長を自動で増やさない。

2026-10-25追記：丸め端部の指定位置拘束に伴い、**仮ディスクに限り**構築capの
実内包検査が失敗したときだけ延長を倍増する有界再構築を追加した。
最大4試行・Span 10%上限・同じ元面/公差/指定Rを維持し、ユーザー指定ディスクは上記の拒否を維持する。
成立しなければ出力しない。[条件と検証記録](EDGE_END_POSITION.md)。

主翼・Splitter・Hubを先に1solidへ結合し、distinct隣接faceが2枚の根元だけを使用して
一度に指定Rのフィレットを生成する。内部shellの恣意的な削除や公差緩和は行わない。
フィレット後のMain/Splitter間はblend同士と他方の元側面との距離を測定し、
指定公差以下の接触・計算不能・role不足を拒否する。周期コピーは既存の実Boolean干渉検査を保持し、
公差を含むAABBが離れた組だけを安全に除外する。

## roleと半径

OCCTのNewFaces/GeneratedにはHub支持面の分割片も含まれる。半径値で面を選別せず、
旧支持面のgeometry handle＋locationと履歴で支持面を除外する。
元edge由来のrolling面とvertex由来のcorner遷移面を区別し、主翼/Splitterの由来も記録する。
cornerは一般に主曲率半径一定ではないため、指定Rのrolling面測定へ混在させない。

狭いtrim面では元trimの分類に通るUV点だけを使う。通常UV格子、重心投影、
最後にtopology copyの三角形UV重心を試す。元faceのmeshやtrimは変更しない。
測定点がない場合は成功にしない。STEP前後でrolling面の半径標本を検査し、
欠測・非有限・不一致を出力受入れ前に拒否する。許容値は従来の`max(0.01 mm, R×0.005)`。
cornerの全面G1、全球面の厳密半径、全面STEP偏差は別課題で、NOT_TESTEDを維持する。

## 検証

`tests/test_spline_root_extension.py`は独立多項式、非一様Span、元領域保持と不正入力を検査する。
`tests/test_fillet_radius_guard.py`は偽PASS・NaN・欠測・過大差を拒否する。
`tests/cad/test_root_interface_reconciliation.py`は現既定＋仮ディスク＋明示R0.1 mmの
Blade+Hub、STEP再読込み、半径、元設定不変を実OCCTで検査する。
空洞保持・四面共有根元拒否・露出cap拒否・狭trim・周期干渉・別翼blend接触のnegativeも含む。

途中の逐次fillet経路におけるR0.25の明示試行はSplitterで未成立だった。現一括経路のR0.25/R8は未試験。入力Rを自動縮小しない。
R0.1の成立はR8・任意R・現既定全周/周期・TurboGrid CADの成立を意味しない。
仮ディスクはPROVISIONAL、ANSYS Import/MeshはNOT_TESTED/今回対象外のまま。

最終全回帰は2,227一意件成功（通常2,174・実CAD53）。既存2,192 ID保持、新規35、
失敗/error/skip/漏れ/重複0、固定356入力不変。根拠は
`artifacts/quality-buried-root-verified/final-test-coverage.json`と各JUnit/raw log。
短縮63件、関連42件（Blade Only同時出力を含む）、別の実既定/関連42件、
既存汎用立体fillet 1件の再現試験、最終Ruffも成功。
実既定は主翼rolling 11/corner 2、Splitter rolling 7/corner 2。
STEP前後のrolling 18面の半径標本は成功し、corner全面G1/全球面厳密半径は未検査のまま。
実コピー5組はAABBで3組を分離、2組をBooleanで検査した。
Main/Splitterのblend/他方側面距離は最小約6.1743 mmで、要求0.01 mmを上回る。

途中の全回帰2回はBlade Only混入の修正と汎用fillet API互換の修正のため中断し、成功に数えない。
`quality-buried-root-final/nonfinal-interruption.json`、
`quality-buried-root-stable/nonfinal-interruption.json`に記録。
短縮試験の最初の誤引数`--quick`は起動エラーであり、正しい`--suite quick`で再実行した。
失敗を削除したり既存の期待値を変更したりせず、最終固定ソースで全件を取り直した。
