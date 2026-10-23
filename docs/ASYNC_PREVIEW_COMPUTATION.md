# 通常の形状再計算を別プロセスで実行する

## 操作と維持する範囲

数値入力のdebounce、翼列/子午面/Span切替、角度/厚さ/端点のドラッグ確定、
GUIのUndo/Redo、回転切替、指標の再計算、翼列追加/改名/削除/並べ替えからの
通常再計算を、選択済み`.venv`の所有processへ渡す。
Edit → Cancel Recalculationで待機/実行中の結果を破棄し、所有treeの停止を要求できる。
画面配置・既存メニュー入口・設計値・生成式・標本・JSON/CSV/TurboGrid/STEP形式は維持する。

公開済みの`update_geometry()`、直接の選択/Undo/Redo API、起動、New/Load/Save、
出力時の検証、最適化のlegacy評価は同期APIを維持する。
したがってアプリ内の全処理が非同期になったという意味ではない。
通常の3D面/線の描画とfilletマウス判定も別の処理であり、本変更の完了条件には混ぜない。

## 責務と結果の採用

- `geometry/preview_computation.py`は前回抽出した既存の数値生成を実行する。
  Qt/OCP/外部ファイル形式へ依存しない。
- `fileio/preview_job.py`は設計snapshot、対象翼種、全行生成の要否を固定し、子processで
  同じサービスを呼ぶ。snapshotを前後で照合し、完成payloadを書いてからresultを最後にpromoteする。
  このjobは私有`artifacts/preview-runs/`内だけを使い、ユーザーcaseを公開しない。
- `fileio/preview_payload.py`は内部専用の数値転送である。型は固定registry、配列はdtype/shapeと
  base64の生bytesを使い、float丸めや再標本化をしない。共有参照、enum、NumPy scalar、
  clearance/analysis Shroud、派生カットの由来を保つ。pickle/eval/入力由来のimportは使わない。
  payload/配列合計96 MiB、100,000 node、深さ128、snapshot4 MiBなどを上限として拒否する。
  これらは私有IPCの資源上限であり、形状公差や設計値の自動変更ではない。
- `gui/preview_worker.py`は実行中1件と最新待機1件だけを保持する。新入力は旧計算を取消し、
  旧workerと取消helperの終了前に次workerを開始しない。取消不能を停止済みと偽らない。
- MainWindowは入力世代・翼種/行/子午面選択・現在の設計値・未確定の入力文字を照合する。
  その後にだけ選択3D/Flow Area/全行を適用し、全行の数値計算をGUI側で繰り返さない。
  計算中は最終有効モデルを残し、現在の指標/Passage/Flow Areaを有効と扱わない。
  legacy/参考Impeller/選択3Dの独立した成功・失敗の契約を維持する。

プロセスのPASSは「数値準備が完了した」という意味である。`selected_error`があれば
形状は不成立であり、最終有効表示とエラーへ切り替える。digest一致だけで不完全な結果を採用しない。

## 終了と入力欄の寿命

通常closeは取消完了までイベント処理を継続してから閉じる。DeferredDeleteも同じ待機を行う。
QtのdeleteLater latchを消費した場合は、所有処理終了後の別イベントで破棄する。
直接のQObject破棄ではcontrollerをQApplication側に残して所有treeを取消し、
破棄済みwidgetをworkerが参照しない。CAD workerとの同時終了も同じcloseへ合流する。

確定済みAdd/Renameのmodal dialogは入力監視から外す。表の再構築で削除された旧editorも
保留入力にしない。存続する入力欄の文字変更や新たな入力欄は引き続き照合し、
設計値が未確定でも古い結果を採用しない。

## 検証

数値往復・共有参照・clearance/trim/Splitter・実processのQt/OCP非依存、破損/不完全/
stale snapshot拒否、最新待機だけの採用、未確定文字、表の破棄、Undo/Redo/JSON、
close/DeferredDelete/強制破棄、実process取消/起動失敗/timeoutを試験する。

旧GUI試験の400 ms固定待機を完了状態の待機へ変更した。数値期待値や歴史的fixtureは変更しない。
初回試験で転送node上限、DeferredDelete、信号引数の欠落、旧editorの削除による誤破棄を検出し、
NumPy scalarの小さい転送表現と、寿命・信号・入力監視を修正した。失敗したrunは成功件数へ含めない。
最終全回帰は2,428一意ID成功（通常2,331・実CAD97）。既存2,375を保持し、新規53。
失敗/error/skip/漏れ/重複0、固定381入力不変。旧数値期待値・fixture・原本JSONは変更しない。
private集計は`artifacts/quality-preview-async/final-test-coverage.json`、実行記録は次の3件。

- 通常1,272：`20261023T140211Z-0226d23d`
- 通常1,059：`20261023T142100Z-0ae6c886`
- 実CAD97：`20261023T131844Z-dceb882c`

quick63・関連試験・変更Pythonの限定Ruffも成功。途中の失敗runは保持し、最終件数へ含めない。
Windows/Fusionの製品MainWindowを実際に表示し、UI信号で子午面→Impeller→Diffuser→RC→子午面を切り替えた。
最終native記録は`artifacts/quality-preview-async/native-final/`。Camera/原本/既定JSON/履歴は不変、
全行の数値をGUI側で繰り返さず、終了後の所有worker残り0。切替呼出0.093〜0.500 s、
結果反映まで2.171〜3.797 s、最大heartbeat gap1.360 sを観測した。同時に通常回帰も動作しており、
一般的な応答時間保証ではない。通常の面描画が同期で残るため、次段階で改善する。
表示画像2枚も確認した。Cameraを維持した画像なので、全形状を自動fitした状態とは異なる。

最終の取消/closeでは所有tree停止を確認し、停止呼出0〜0.015 s、最大gap0.047〜0.062 s。
仮ディスク数値準備と通常再計算の同時closeでも両treeの停止を確認（最大gap0.094 s）。
`native-final-cancel/`、`native-final-close/`、`native-final-both/`に記録。
これは自動操作によるnative確認であり、F5の人手操作、全GUI操作、最終CAD kernel実行中との同時終了、
長時間設計の保証ではない。ANSYS Import/Meshは対象外のまま。
