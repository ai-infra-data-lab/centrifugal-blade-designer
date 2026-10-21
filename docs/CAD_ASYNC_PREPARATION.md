# CAD数値準備と取消の非同期化

GUIからCADを開始すると、まず`cad/pending_job.py::queue_job`で設計snapshotと要求を固定する。
この時点では翼生成を行わない。専用QProcessで既存の`prepare_job`を呼び、
私有子directoryに座標を生成する。snapshotのcanonical hash・原文・要求が不変であることを
照合し、numeric NPZを移した後に、完成したrequestを最後に置き換える。
途中失敗や取消でrequestがpendingのままならCAD工程へ進まない。
既存の同期`prepare_job` API、JSON、幾何計算、既存出力形式は維持する。

`gui/cad_export_worker.py`は数値準備とOCCTの2段階を順に起動する。
準備後と公開前にsnapshot実ファイルもhash検査し、改変ファイルを正本名で公開しない。
ユーザーがGUIを編集しても固定済みjobは変わらず、古いCAD previewは従来のsnapshot照合で非表示となる。

Windowsの取消は、所有するQProcessのPIDだけを対象に、別の非同期QProcessで`taskkill /T /F`を実行する。
GUIスレッドで`subprocess.run`や`waitForFinished`を呼ばない。
計算開始直後の取消もstarted signalで再確認する。終了helperと計算processの両方が
終了するまでcompletedを出さず、helper失敗時は確認済みと偽らない。
helperが失敗してworkerが生きている場合は親launcherだけをkillして子を残さず、
再取消またはworker終了を待つ状態を明示する。
終了commandの戻り値が不確かな場合は`termination_status=NOT_CONFIRMED`を維持する。

閉じる操作は一度保留し、取消完了signalの後でwindowを閉じる。
取消・数値準備失敗・pending jobはGUIでも直接`publish_job` APIでも既存caseへ公開しない。
CAD工程の部分成功を通常公開する従来契約とは区別する。

## 検証範囲

`test_cad_pending_job.py`は従来APIと全配列・snapshot・requestの一致、原設定不変、
改変・途中I/O故障・不完全job・直接公開拒否を検査する。
`test_cad_async_worker.py`は実子processとQtイベントを使い、工程順、不正report、異常終了、
開始中取消を検査する。模擬CADのreportはLIFECYCLE_ONLYとし、形状検証とは数えない。
Windows tree取消は実際の子process handleの終了と、helper待機中のイベント配送を確認する。
commandの戻り値だけを子の終了証拠にしない。
`test_cad_gui.py`は既存caseのbytes保持、非同期close、従来の履歴・snapshot・Camera契約を検査する。

Windows native Qtの専用一時windowでも計測した。CAD開始の呼出し0.0423 s、close呼出し0.00850 s、
20 ms heartbeatの最大間隔0.0630 s。実数値準備の後は取消用の模擬CAD待機processであり、
実カーネルの形状成功ではない。原本`blade_v03.json`は不変。
根拠は`artifacts/stage6-native-integrated-02/result.json`。
公開直前のsnapshot検査を追加した最終ソースの再測定は、開始0.0564 s、close 0.0137 s、
heartbeat最大0.532 s（`artifacts/stage6-native-integrated-03/result.json`）。
CAD開始/closeの呼出し改善と、描画等を含む全UIの無停止を区別する。良い回だけを代表値にしない。
最初の計測scriptは閉じたQObjectへの参照順を誤り、検査script側で例外が出たため採用せず、
計測scriptを直して別directoryへ再実行した。

一般の`update_geometry`、全行preview、初回仮ディスク寸法作成、描画/preview JSON読込みは
まだ同期箇所を持つ。Stage 6全体完了や人の全操作確認とはしない。
ANSYS Import/Meshは今回対象外・NOT_TESTED。全2,259一意件成功（通常2,206・実CAD53、新規32、既存2,227 ID保持、失敗/error/skip/漏れ/重複0・固定359入力不変）。
関連47件・短縮63件・Ruff成功。根拠は`artifacts/quality-cad-async-final/final-test-coverage.json`と各JUnit/raw log。公開I/Oの合成fixtureは幾何検証と区別する。
