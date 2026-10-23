# 仮ディスク算出とGUI応答

## 対象

CAD開始時の自動仮ディスクと「仮ディスクを作成してpreview」の画面操作を、
Qt/CAD kernelを読み込まない専用processへ移す。
make_provisional_disk、hub_blade_extent、project_to_wallの数式・投影・全標本は変更しない。
既存の同期_create_provisional_disk()はプログラムからの呼出し用に保持する。
既定値、ユーザーJSON、既存出力、GUI配置は変更しない。

前段の実CAD操作では最大heartbeat gap9.859 sが残った。
独立profileではmake_provisional_diskが13.359 s、そのうちhub_blade_extentが12.966 s、
project_to_wallが9,458呼出しだった。profiling overheadを含むため同一の時間とは扱わない。
前段の記録と範囲は[CAD表示](CAD_PREVIEW_RENDERING.md)を参照。

## 処理と保護

cad/provisional_disk_job.pyは設計の小さいsnapshotだけを私有jobへ保存する。
元snapshotのhashを照合して同じ算出関数を呼び、入力が変わっていないことを再確認してから
完成resultを最後にrenameする。CAD形状、STEP、ユーザーcaseは生成しない。
入力hash、完成phase、disk digest、型と有限値を確認し、不完全/破損/取消結果を採用しない。
寸法算出では無関係なfillet選択の可否を検査せず、後段のCAD queueが従来どおり検査する。

gui/provisional_disk_worker.pyは既存CadExportWorkerの所有process tree取消を再利用する。
venv launcherだけを停止してchildを残す経路へ変更しない。起動失敗はCAD kernel未導入と区別する。
実行中はCancelを使用できる。closeは取消完了を待つイベント状態とし、GUI threadでwaitしない。
取消がcloseEvent内で即時完了する場合も、次のイベント処理でcloseして再入を避ける。

MainWindowは元の設計値と、編集可能な入力欄の未確定文字をGUI thread上で保持する。
完了までに設計値/未確定文字/編集対象が変わった場合は結果を破棄し、再実行を案内する。
保存済みの手入力ディスクを上書きしない。受入れ時だけCAD設定へ適用して履歴を確定し、
元のaction/targetで従来のCAD queueを開始する。旧来と同じ仮寸法のUndo/Redoを維持する。

## 検証状況

初回の関連試験は40成功・終了再入の1失敗だった
（20261023T020734Z-327d5a10）。期待値を緩めずcloseの再入を修正し、関連72件成功
（20261023T020941Z-45f60608）。追加後の関連75件成功
（20261023T021209Z-e63fe7ed）、変更Python6ファイルのRuff成功。

最終の全回帰は2,358一意ID成功（通常2,261・実CAD97、既存2,333保持・新規25）。
失敗/error/skip/漏れ/重複0、固定373入力のhash不変、全reportとcontrollerの終了codeは0。
前の2,333件成功を流用せず、新しいsourceで全IDを実行した。
記録はartifacts/quality-provisional-disk-async/final-test-coverage.json。
通常2組は20261023T025436Z-110b2eb2（1,045件）と
20261023T030819Z-2ce7bc71（1,216件）、実CADは20261023T021512Z-abc370a6（97件）。
最初のハーネス基準件数確認は更新前の定数により試験実行0件で停止した。
setup-attempt-1.jsonに保持し、件数を修正後に上記の全実行を行った。
native応答と実操作も下記の限定経路で確認した。

新規試験は同期寸法との一致、queueで計算しないこと、snapshot/resultの改変・欠落・取消、
無関係なCAD設定、実Python childのQt/OCP非依存、dirty text/設計変更/選択変更の破棄、
action/target継承、Undo、close、実process取消と起動失敗を対象とする。
以前の「自動作成直後に同期でCAD jobが存在する」GUI試験は、同じ寸法/actionのまま完了を待つ。

CADの数値準備/表示、一般の形状再生成、全翼列・Flow Area、通常描画は別の処理である。
この修正をStage 6全体完了とはしない。ANSYS Import/Meshは対象外・NOT_TESTED。

## native Windowsの操作確認

本来のcreate_window、packaged default、Impeller、明示R0.1 mm、Blade+Hubを使用した。
仮ディスクprocessから実CAD準備/生成、私有case公開、表示、CAD Full切替、視点/resize、
closeまでを実行した。開始呼出し0.063 s、全346.438 s中の最大heartbeat gap0.328 s。
前段で受入れたjobと**最終設計snapshotのhashが一致**し、算出後の寸法/設計値の保持を確認した。
Mechanical PASS、公開STEP 1件のhash一致、GUI/job snapshot一致、最新frame採用、render errorなし。
原本JSON不変、destroyのqueue取消/閉鎖、close0.016 sも確認した。
記録はartifacts/quality-native-provisional-disk/35c0393658034d42bcca6ecefb2528ee/。

これは仮ディスクを含む同じ入力による各1回の操作計測で、一定FPSや全入力/全PCの応答保証ではない。
前段の9.859 sは失敗/停止の履歴として保持し、異なる計測範囲のview単体94 msやprofile13.359 sと
混ぜて速度改善率を計算しない。全計算の所要時間短縮を主張する変更でもない。
CAD Fullの59,684可視polygonは単翼meshの周期配置で、全周一体solid表示の証拠ではない。
仮寸法のoverall WARNINGと、既定の所属範囲がLE/TEを含まないdomain_errorを保持する。
流体CADやANSYS成功へ昇格させない。

別のnative試験で開始100 ms後にcloseした。close呼出し0.016 s、全0.594 s、最大gap0.078 s。
ProvisionalDiskWorkerの所有treeがPROCESS_TREE_STOPPEDとなり、設計/原本不変、case未作成を確認した。
ここでworker reportのFAIL/cancelledは意図した取消結果で、外側の取消検証はPASSである。
記録はartifacts/quality-native-provisional-cancel/のresult.json。

人によるF5/マウス操作、全scope/全入力、長時間反復、複数monitorは未検証。
通常のupdate_geometry/全翼列/Flow Area、通常描画、fillet当たり判定の同期箇所は別課題として残る。
