# 通常プレビューの描画と処理資源

## 変更範囲

大きい通常Hub/Shroud、Tip包絡面、Analysis Shroudにも、既存CADのQImage workerを適用する。
4,096 polygon以下は従来の同期描画を使い、それを超える場合は1実行/最新1待機とする。
待機中の輪郭だけを簡略化し、完成画像の面、色、透過、照明、描画順は変えない。
通常面の世代、CAD表示の有無、Camera、可視設定、size、DPIを照合する。
通常面の更新時に同一geometry objectを使っても古い画像を再利用しない。
CAD controlsの遅延生成を維持し、CADを一度も表示していなくても動作する。
数値の生成式・標本・設計値・既定JSON・保存/出力形式は維持する。

根元filletのクリックは画面上のbounding boxで候補を絞り、その候補へ従来と同じ
Qt OddEvenFill polygon判定を行う。Camera/sceneごとの1frameだけを保持し、
可視設定・CAD差替え・通常面の更新で古い候補を採用しない。
ToolTipとtrackballの既存動作を維持する。描画面の計算やfillet半径は変えない。

入力取得が失敗した場合は旧previewを取消してpendingを解除し、次の入力で再開できるようにする。
子processの起動/実行や結果転送の失敗は、設計値の誤りとは別の実行エラーとして表示する。
実数値計算での形状不成立は既存の形状エラー方針を維持する。

## 一時ジョブの所有と保持

`fileio/preview_retention.py`はQtを読まず、controllerが新しく作成・登録した私有jobだけを扱う。
登録前から存在するjobを列挙/削除しない。完了後は通常5件を保持し、controller破棄時には
整理可能な完了jobを削除する。実行中/待機中のjobは整理対象にしない。
診断用の`keep_jobs=True`はcontroller内の一時設定であり、設計JSONへ保存しない。

実際の削除前に、絶対pathの親とUUID、directory identity、全親directoryと各fileの
reparse/symlink、file type、既知file名だけであることを確認する。
既知fileだけをunlinkし、空のdirectoryだけをrmdirする。再帰削除は使わない。
未知file、置換directory、link、OS削除エラー、停止未確認の取消jobは保存し、
整理の失敗を表示する。例外的に保存したjobまで5件に切り詰めるという意味ではない。
作業前の診断記録、CAD job、ユーザーの出力ファイルは整理しない。

## 検証と制限

関連78件、quick63件、変更8 Pythonの限定Ruff成功。通常画像のbytes一致、
同一objectでの再生成、全行/可視設定/Camera/resize/hide/close、遅延CAD追加、
旧クリック判定との一致、2,000面での候補絞り込み、保持5件/診断保持、未知file・
置換directory・reparse・削除失敗の保護、入力失敗からの回復を検査した。
関連runは`20261023T143919Z-f6391b09`、quickは`20261023T143844Z-f9d228ff`。

Windowsの実倍率1.75で、Impeller/静翼の4,608面とclearance付き9,216面の完成widget画像を
同期描画と比較し、全3caseでbytes一致を確認。記録は
`artifacts/quality-preview-resources/native-pixels/`。これは指定caseの一致であり、
任意の描画backend/DPI/サイズや全設計の保証ではない。

製品MainWindowのUI信号で子午面/Impeller/Diffuser/RCを切替え、Camera保持、
現在の形状/測定元、履歴、原本/既定JSONの不変、所有worker残り0を確認した。
初回`artifacts/quality-preview-resources/native-final/`は数値準備完了の確認であり、
撮影されたRC画像は面描画待機中だった。切替呼出0.047〜0.219 s、数値反映1.578〜2.000 s、
最大heartbeat gap0.640 sだが、完成画像までの時間としては扱わない。

画像を確認して診断手順へ明示的なframe照合を追加し、別の`native-final-v2/`で
全5切替の完成frame、render errorなし、撮影後のframe一致も確認した。
この実行は重い実CAD回帰と同時で、切替呼出0.172〜1.031 s、完成11.593〜16.204 s、
最大gap1.812 sだった。初回値との負荷条件/完了条件が異なるため、一般的な改善率へ換算しない。
2D plotや既存同期API等も残り、全操作の応答性PASSにはしない。

別の実CAD由来meshで、可視55,076面/fillet47,322面を表示し、6点のクリック結果が旧方式と一致。
6点合計は新方式0.047 s、旧方式5.406 sで、原記録の対象fileは不変。
`artifacts/quality-preview-resources/native-fillet-hit-v2/`に記録。初回は診断scriptが
テスト用offscreen設定をimportしたためnativeの前提確認で停止した。初回logは
`native-fillet-hit/process.log`へ保存し、製品不具合や成功件数へ混ぜない。

通常取消/close、仮ディスク数値準備との同時closeでは所有tree停止を確認した。
同時closeの最大gap0.156 s。実Windows junctionの私有fixtureでも登録を拒否し、
リンク先のmarkerを保持した（`native-retention/result.json`）。
これらは自動操作によるnative確認であり、人手によるF5/全機能/長時間の確認ではない。
ANSYS Import/Meshは対象外、数学的な全面精度や性能成立の保証とは区別する。

最終全回帰は2,466一意ID成功（通常2,369・実CAD97）。既存2,428を保持し、新規38。
失敗/error/skip/漏れ/重複0、固定386入力不変。数値期待値・fixture・原本JSONは変更しない。
集計は`artifacts/quality-preview-resources/final-test-coverage.json`。全reportと監査driverはexit0。

- 通常1,229：`20261023T152711Z-70f2fdc6`
- 通常1,140：`20261023T154344Z-f8fd9dea`
- 実CAD97：`20261023T144255Z-8d8d78ef`

全回帰後、他の検証を同時に動かさず`native-final-v3/`を別記録先として再実行。
全5切替の完成frame、Camera/設計元/履歴/原本の保持、render errorなし、worker残り0を確認。
切替呼出0.047〜0.265 s、完成1.843〜2.516 s、最大gap0.406 s、close/destroy0.032 s。
子午面とRCの完成画像も確認した。初回と高負荷実行の記録は上記のとおり保持する。
この限定計測を全GUI操作・人の操作・全scopeの性能保証にはしない。

## 後続の独立修正で扱うCAD期限

実CAD回帰中に、既存CadExportWorkerの20分が数値準備とCAD本体で共用され、
CAD開始時に再設定されない問題も確認した。既定全周R0.1の実測は前回2,033.968 s、
今回2,122.242 sで20分を超える。変更前の独立再現試験は4成功/2失敗
（`20261023T154319Z-611cc577`）。CAD本体が20分に制限されることと、
準備期限を消費したままCADへ移ることを再現した。本描画変更ではworkerのCAD期限は
変更せず、続く[独立修正](CAD_TIME_BUDGETS.md)で数値準備20分/CAD本体60分へ分ける。
開始/期限/取消の確認だけで、全scopeのGUI出力が検証済みとは報告しない。
