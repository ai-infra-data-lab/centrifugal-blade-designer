# ANSYS以外の品質改善作業

通常面の非同期完成画像、filletクリックの候補絞り込み、作成済み私有preview jobの保持5件、入力取得失敗時の回復を追加。既存形状/保存/出力を維持し、関連78件・quick63件・限定Ruff・native画像一致を確認。全2,466一意ID成功（通常2,369・実CAD97、既存2,428保持・新規38、失敗/error/skip/漏れ/重複0・固定386入力不変）。Windows単独実行の完成frame/Camera/終了も確認。[範囲・検証](NORMAL_PREVIEW_RESOURCES.md)。

通常UI再計算の最終検証：全2,428一意ID成功（通常2,331・実CAD97、既存2,375保持・新規53、失敗/error/skip/漏れ/重複0・固定381入力不変）。Windows実画面の翼列切替・Camera保持、通常取消/close、仮ディスク準備との同時closeも確認。ANSYSと全操作の人手確認は未実施。 [記録](ASYNC_PREVIEW_COMPUTATION.md)。

通常UIからの選択形状・Flow Area・全行再計算をprocessへ移し、取消メニューと最新入力のみ採用を実装。GUI履歴・翼列操作・表の再構築・未確定文字・同時CAD終了を検査する。通常描画/当たり判定、同期APIや最適化/出力検証は別途追跡し、全GUI処理の非同期化とはしない。[検証](ASYNC_PREVIEW_COMPUTATION.md)。

一般再計算の分離に向け、選択3D/参考計算/Flow Areaと全行生成をQt非依存の同期serviceへ移す。所属解析壁面の失敗行を一括省略し、面積失敗時に中途の壁面を採用しない。既存数値・JSON・Camera契約を維持する。全2,375一意ID成功（通常2,278・実CAD97、新規17、失敗/error/skip/漏れ/重複0・固定375入力不変）、関連42件/quick63件/Ruff/native切替を確認。一般再計算workerの取消/世代/closeは次段階に残す。[検証範囲](PREVIEW_COMPUTATION_SERVICE.md)。

queue前の同期仮ディスク算出を、画面操作時だけ別processへ移す追加対応を実装。既存同期API・計算・寸法を維持し、未確定入力/設計変更の破棄、取消/closeを扱う。全2,358一意ID成功（通常2,261・実CAD97、既存2,333保持・新規25、失敗/error/skip/漏れ/重複0・固定373入力不変）。同じ最終snapshotのnative実CAD操作で開始0.063 s/最大gap0.328 s、別のclose/取消も確認。[範囲](ASYNC_PROVISIONAL_DISK.md)。

Stage 6AのCAD読込み/描画へ任意の数値cacheと最新要求だけを扱うQImage workerを追加。全2,333一意ID成功（通常2,236・実CAD97、既存2,303保持・新規30、失敗/error/skip/漏れ/重複0・固定369入力不変）。関連52件/quick63件/Ruff、native製品viewでの画像一致と取消/closeも確認。通常形状の同期再生成や全export GUI操作とは区別する。[範囲](CAD_PREVIEW_RENDERING.md)。

2026-10-22に利用者が形状方式を確定：現行のXYZ表示／円筒補間カット／CAD splineを
維持し、差と未検証範囲を明示する。単一面への移行は今回の未完了タスクに含めない。
各方式内の不一致や出力変換の品質検査は継続する。過去の統一案は履歴として残す。

C02/Stage 5の標本検査を製品STEP出力へ追加。全faceの双方向距離・法線と計測値の有限性を要求し、同体積/bboxの内部面移動を拒否する。関連37件・quick63件・Ruff成功、全2,303一意ID成功（通常2,206・実CAD97、新規31・既存2,272保持、最終の失敗/error/skip/漏れ/重複0・固定365入力不変）。初回のGUI待機1件は失敗記録を保持し、該当組全体の単独再実行で成功を確認。標本間の全面保証、trim境界curve、role対応、一般GUI再計算/描画は引き続き未完了。[範囲](STEP_BOUNDARY_SAMPLES.md)。

2026-10-22：全周一体化後filletを製品経路へ追加し、現既定22枚・R0.1 mmのMechanical STEPと全924配置対比較が成立。全2,272一意ID成功（通常2,206・実CAD66、新規5・既存2,267保持、失敗/error/skip/漏れ/重複0・固定363入力不変）。中断組は成功件数から除外し、通常2組を再実行した。[構築・証拠](FULL_FILLET_ASSEMBLY.md)。

同一CAD objectのバイナリBREPが不変の場合に限る検査再利用を追加。
別object/変更/失敗は実検査を維持し、全2,267一意ID成功（通常2,206・実CAD61、
既存2,261保持、新規6、失敗/error/skip/漏れ/重複0・固定361入力不変）。
[契約・検証](CAD_VALIDATION_REUSE.md)。

2026-10-22追記：全周CAD診断から、OCCT生成履歴にだけ残る中間面の半径を測定する
分類不具合を特定。完成BREPのfaceと照合する修正を追加。
[詳細](FINAL_FILLET_TOPOLOGY.md)。診断用の全周組立て方式の製品採用とSTEP受入れは別課題。

2026-10-21の利用者指示により、ANSYS Import/Meshの実機連携を今回の実行対象から外す。
それ以外の既存ロードマップを継続する。下記は完了条件を削らないための作業記録であり、
全項目が実装・検証済みという意味ではない。詳細な制限はDEVELOPMENT_ROADMAP.mdを参照。

| 項目 | 現在の状態 | 次の完了条件 |
|---|---|---|
| 共有境界spline | 生成契約の修正・全回帰完了 | 異なる接線/密度でも厳密一致、実入力gap保持、旧数学的補間との差を測定。全2,192一意件成功、既存2,179保持、固定352入力不変。全面誤差/丸め保証は別課題 |
| 元面の局所/非局所接触 | 部分対応 | 境界一致後の残候補を分類。未接続境界・周期コピー・包含を含む被覆とnegative fixture。資源上限/未判定を保持 |
| 全面誤差・対応 | 部分対応 | 表示/基準面/CAD/trimの物理対応、位置/法線/Jの予算と丸めの保証範囲を区別 |
| 実モデル根元fillet | Blade+Hubと全周製品経路のR0.1を実CAD/STEP検証。既存R8周期・流体CADと全回帰の監査も成功 | 現既定の周期sector・所属範囲を満たす流体CAD、全面STEP精度は別条件。R8必須ではない |
| 最終CAD/STEP精度 | 部分対応 | 体積/bboxだけでなく共通境界の双方向偏差・法線・role照合。局所変形negativeで検出 |
| GUI応答/取消 | 通常選択/Flow Area/全行の数値準備、CAD数値準備、仮ディスクUI算出、所有tree取消をprocess化。通常/CADの大きい面をQImage workerへ、filletクリックを候補絞り込みへ対応。今回の関連78件とnative限定経路、全2,466一意件成功を確認 | 起動/Load/Save/出力検証の同期API、2D plot等は維持。全scope・長時間・人の操作は未検証。各測定の負荷/完了条件を区別。[今回の範囲](NORMAL_PREVIEW_RESOURCES.md) |
| 履歴/別画面同期 | 部分対応 | 全設計値の確定/Undo/Redo/JSON/Editor同期、Camera保持、設計/表示設定の責務分離 |
| 出力拡張 | 一部未対応 | 個別形式/翼種の仕様、拒否条件、出力保護、ローカルCAD/形式検証。ANSYS成功とは報告しない |
| 面積/スロート | 近似機能あり | 独立解析解、密度/Span収束、未定義の保持。真の3DスロートとCAD閉塞は別機能として検証 |
| 最適化 | legacy機能あり | 実3D幾何制約と既存評価の区別。実solverのない環境で流量/圧力比/効率を実解析値にしない |

## 今回の追加調査

共有境界の修正後、既定216候補すべての境界恒等性が成立。診断包絡を1回細分する既存APIで
局所数値条件も全216組で成立した。全面・非局所・包含の完了とは区別する。
根元CADは専用`.venv-cad`で再調査。Boolean後に2shellがあり、7根元edgeが4つのdistinct faceを共有。
片方のshellは翼根capとHub流路面だけで構成されていた。単なる面重複や余分なcompound子ではない。
内部要素の一般除去や同一面統合では解決しなかった。診断用に外側shellから組み直した場合も
指定R1は未成立。これを製品コードへ採用したり、任意のshell除去を修正として合格にしない。
その後、同じ診断形状でR0.5はBREP成立だがedge公差0.01362 mmで既存0.01 mm上限外。
R0.25とR0.1はBREP・閉鎖・正体積・1solidとedge公差約0.00412 mmを確認した。
この段階では診断のみで、製品のassembly経路・STEP半径/再読込みの完了とはしない。
結果は`artifacts/quality-fixed-endpoints/root-diagnostic/`に保存。既存出力への公開はしていない。
最初の標準`.venv`からのCAD診断はOCP未導入で停止したため、選定済みの専用環境で再実行した。
これは環境エラーとCADの幾何的未成立を区別して記録する。

ANSYSのImport/MeshはNOT_TESTED/対象外のまま。CADカーネル・STEP再読込みは
ANSYSなしで実行できるため対象に含む。外部solver、実機寸法、nativeでの人による
操作確認等が不足する項目は、その不足を記録し、テスト成功で代用しない。

作業単位ごとに関連試験・必要な全回帰・Ruff・差分確認後、アプリ内の明示pathだけをcommitする。
pushは別の明示指示があるときだけ実施する。Hypothesis/uvは追加しない。

## 根元修正とnative応答の追加調査

旧根元診断から製品修正へ進め、内部shellの削除は採用せず、元面の負Span多項式延長と
cap内包検証、一体化後の単一filletを実装した。支持面をfilletとして数えていたrole履歴も修正する。
詳細・失敗試行・検証範囲は[BURIED_ROOT_CONSTRUCTION.md](BURIED_ROOT_CONSTRUCTION.md)へ分離した。
Blade Onlyと流体CADの同時要求時も構築用延長をMechanical Blade Onlyへ混ぜない試験を追加。
最終ソースでの全回帰2,227一意件成功（通常2,174・実CAD53、新規35、既存2,192保持、失敗/error/skip/漏れ/重複0・固定356入力不変）であり、今回全項目完了とはしない。

Windows native Qtで専用の一時ウィンドウを表示し、Impellerをプログラム選択して計測した。
update_geometry 1.06285 s、prepare_job 0.581605 s、20 ms heartbeatの最大間隔1.07801 s。
217回のtick中100 ms超が4回あった。原本は不変。画面画像も確認したが、人のマウス操作検証ではない。
`artifacts/quality-root-interface/native-gui-impeller/result.json`と`window.png`に記録。
同期処理による停止は残課題として維持し、native表示ができたことだけで応答性PASSとはしない。

Stage 6の次の実装はimmutable snapshotの数値準備をGUIプロセス外へ移すこと、
取消/終了時に所有するworker treeだけを非同期に終了すること、編集中の古い結果を採用しないこと。
従来の同期APIと既存のUndo/JSON/Camera契約を維持する。CAD出力公開と画面更新は別状態として検査する。

## CAD開始/取消と全周の追跡

CAD数値準備、tree取消、close待機を非同期化した。[契約](CAD_ASYNC_PREPARATION.md)。全2,259一意件成功（通常2,206・実CAD53、新規32・既存2,227保持、失敗/error/skip/漏れ/重複0・固定359入力不変）で、一般再計算の同期箇所は継続する。
実既定11枚の全周Booleanは約60分で未完了となり、診断を停止した。フィレットと5コピーの干渉検査後のsingle/Hub BREPを保存し、同じ形状で並列実行設定を比較する。全周をPASSにしていない。`artifacts/quality-root-interface/full-current-default/profile/incomplete.json`。

全周の単純な直列化も600 s以内では完了せず、診断を停止した。終了コマンドのCP932出力をUTF-8で読んだ診断driver側の記録エラーは別に修正し、実プロセスの終了を確認した。`artifacts/quality-root-interface/cached-serial/watchdog.json`。高速な接合モードは公式の前提条件を満たす証拠なしに採用しない。

全周の追加診断：single−Hubの複製用差分は2solid/37face/遊離face0だが、BREP=Trueに対して自己交差検査=False。元singleはPASS。差分経路を使う高速接合の試行はこの入力検査で拒否し、実際の高速Booleanへは進めていない。元single全体の複製による通常/高速Booleanも300 s以内では未完了。段階logではBoolean開始まで確認し、完了は未確認。根元/pcurveの公差を変えず、次は全周を先に構築してからfilletを作る順序を調べる。診断は私有artifacts内のみで、ユーザー出力へ公開していない。
