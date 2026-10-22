# STEP境界面の双方向標本検査

## 検査の対象

`cad/boundary_samples.py`はCAD workerの出力直前に、元のBREPとSTEP再読込み形状の
全faceを双方向に調べる。Qtやファイル形式には依存せず、OCPの実境界面を受け取る。
`cad/worker.py::export`は従来のnative妥当性・単位・体積・bbox・edge公差の検査後に呼び、
標本検査を通るまでartifactを公開候補にしない。

同じbbox/体積でも、内部の空洞だけを移動した形状を従来検査は区別できない。
10 mm角から1 mm角の空洞を除いた独立例で、空洞をX=2から6 mmへ移すと
体積と外形は同じだが、双方向の標本距離は最大2.75 mmとなる。
この不正例は実STEP書出し・再読込みでも再現し、新しい出力前検査で拒否する。

## 方式と受入れ条件

- 各faceのUV範囲から既存の`trimmed_face_parameters`を用い、実trim内/境界上と
  分類された最大9点を選ぶ。狭いfaceの補助meshはtopology copy上で作り、元面を変更しない。
  一つも測れないface、未定義/非有限の位置や法線、距離計算失敗は拒否する。
- 点から**targetのface群**へ距離を測る。点がsolid内部にある場合に0を返す
  solidへの内包距離を、境界への距離として使わない。
- source→importedとimported→sourceを両方実行する。保存公差込み・三角形なしの
  BREP boundsで候補を絞り、実point–face距離の最近点を調べる。
  下限の差は負方向へ一段補正し、利用できない下限では候補を除外しない。
- native距離計算が返したface上のUVを優先し、再投影の重複を避ける。
  edge/vertex解だけはsupport surfaceへ投影する。
  faceの向きと配置を反映した法線を比較し、最近点の同距離候補（1e-9 mm以内）で
  最小の法線角度を採る。90度以上は方向が整合しないものとして拒否する。
- 距離の上限は既存の`surface_tolerance_mm`を使い、新しい公差や自動修復は導入しない。
  全faceの非空な標本、face index、target参照、有限値、集計との整合を要求する。
- `cad_validation.step_roundtrip`は元/再読込み双方のsolid数、体積、面積、bbox、
  edge公差と比較公差を明示検証する。NaN、欠落、不正な符号・型、計算予算のoverflowを
  比較式のFalseや無限の許容値として通さない。従来の有限正常値の予算式は維持する。

結果は`roundtrip.boundary_surface_samples`へ記録する。
成功名は`PASS_SAMPLED`、`global_surface_error`と`global_normal_alignment`、
`boundary_role_correspondence`は`NOT_TESTED`を維持する。
各方向の全face・標本数・最大距離・法線角度・最近target faceを保持する。

## 保証しないこと

有限標本の成功は、標本間を含むHausdorff距離・全法線・微小な局所変形の不在を証明しない。
trim境界curve全体の偏差、roleの一対一対応、master→CADの全面偏差、corner全面G1、
構造/流体共通境界の逆向き法線対応は別検査である。
この比較は同一bodyのSTEP前後なので、法線は同方向を要求する。
Mechanical solidと隣接fluidの境界に同じ方向規約を流用しない。
ANSYS Import/Meshは今回も対象外・`NOT_TESTED`。

## 検証

新規テストは`tests/cad/test_step_boundary_samples.py`。
配置だけを持つ剛体移動の空洞body、全12面108点の被覆、入力BREP不変、
内部面移動、単独faceの法線反転、欠落/NaN/overflow、公差不正を確認する。
法線反転faceの単体試験を、有効な閉立体の試験とは扱わない。
メトリクス異常はpolicy用のmock backendであり、native CAD成功の証拠ではない。

故障注入は数値blade generatorだけを独立した空洞bodyへ置き換え、exporterが
同bbox/体積の別bodyを実STEPに書く例である。従来のroundtrip単体はPASSのまま、
workerの新しい境界検査がFAILとなり、既存Mechanicalファイルと主要検証reportを保護した。
実R8 fixtureの周期Mechanicalとfluidでも、全faceの双方向標本と従来半径を確認した。
関連34件＋3件、quick 63件、変更PythonのRuffは成功。全2,303一意ID成功（通常2,206・実CAD97、新規31・既存2,272保持、最終の失敗/error/skip/漏れ/重複0・固定365入力不変）。初回のGUI待機1件は失敗記録を保持し、該当組全体の単独再実行で成功を確認。

製品workerの現既定22枚・明示R0.1 mmの全周Mechanical STEPでも、元BREPと再読込みの
各331面・各方向2,913点を測定した。source→STEPの最大距離2.244e-9 mm、逆方向
2.877e-9 mm、最大法線角度1.479e-6 degで標本検査は成功した。
実CAD97件と通常2,206件は最終の採用記録ですべて成功。これは仮ディスクのMechanical経路であり、
現既定の流体domain成立やANSYS Import/Meshの証拠ではない。
記録は`artifacts/test-runs/20261022T122202Z-b930f701/`。

新しい重い既定全周テストの実行上限は、追加の双方向標本に合わせ2700→3600秒とした。
これは待ち時間の上限であり、数値期待値・公差・native checker条件の変更ではない。
全回帰は資源競合を避け、CADを単独で完了してから通常2組を実行する。
記録先は`artifacts/quality-step-boundary-samples/`と各JUnit/raw log。

初回全回帰は全2,303 IDを重複/漏れなく実行したが、通常2組の並列実行で
`test_async_calculation_displays_both_splitter_passages_and_changes_clear_results`の
30秒待機が1件失敗した。ログはfutureが計算結果を返した状態を示すが、GUI反映は未完了だった。
全件成功とは扱わず元の失敗記録を保持する。同じソース・期待値・待機時間で単独1件は成功。
負荷だけが原因とは断定せず、該当1,030件の組全体を単独で再実行し、全件成功した。
初回controllerのBLAS等は1 thread、単独再実行は通常CLIの継承環境を使用する。
成功した他の通常1,176件と実CAD97件は、同じ365入力hashの下で記録を保持する。
再実行・最終ID照合先は`artifacts/quality-step-boundary-samples-retry/`。

採用前の独立プローブでは、過去の診断BREP対今回のSTEPの全331面・各方向2913点で
最大位置差約2.877e-9 mm、最大法線角度約1.479e-6 degだった。
UV再利用の有無でface/標本数・最大値は一致した。これは製品組込み後の全回帰の代用ではない。

最終採用記録は通常1,030件 `20261022T132235Z-e6020b55`、通常1,176件
`20261022T125952Z-31f87f8c`、実CAD97件 `20261022T122202Z-b930f701`。
初回の失敗した1,030件のrunは成功記録へ混ぜず、別途保持した。全2,303 IDの
漏れ/重複/予期しないIDと365入力hashの変更はいずれも0。原本と既定JSONは
互いの一致を要求せず、開始時の内容をそれぞれ保持している。
