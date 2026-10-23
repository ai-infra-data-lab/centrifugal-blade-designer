# CAD数値準備と本体の時間予算

## 確認した問題

CadExportWorkerは開始時の20分timerを準備とCAD本体で共用し、準備完了後のCAD開始時にも
再設定していなかった。既定形状に明示R0.1 mmと仮ディスクを用いる全周Mechanical試験は、
2,033.968 sと2,122.242 sを記録しており、正常に成立する計算でもGUI側の20分を超える。
数値準備が期限近くまでかかると、CADへ移った直後に旧期限で取消される問題もある。
これを不正形状やカーネル失敗として扱わない。

## 最小修正と維持する契約

- 数値準備は従来どおり20分。CAD backendが利用できることを確認した後、CAD本体の開始時に
  別の60分予算を開始する。60分は既存の実全周CAD回帰の上限3,600 sに合わせた。
- 準備失敗/不完全/取消からCADへ進めない既存の検査、終了後のtimer停止、手動取消、
  所有process treeだけの取消とclose待機は維持する。
- 通常PreviewWorkerとProvisionalDiskWorkerは従来の20分を維持する。
- 計算式、指定R、幾何公差、標本、設計値、既定JSON、保存/出力形式は変更しない。
  不正形状の成功化、Rの自動縮小、無期限の計算許可は行わない。

変更は`gui/cad_export_worker.py`の定数とCAD開始時のtimer再設定に限定する。
準備に使った時間をCAD本体の時間から差し引かない。60分で全形状・全PCの計算完了を
保証するという意味ではなく、現在の実形状を20分で不必要に取消していた問題の修正である。

## 検証

変更前の独立再現は4成功/2失敗（`20261023T154319Z-611cc577`）。
直接CAD開始が20分に制限されることと、準備の失効timerがCAD段階を取消すことを再現した。
元の失敗logは`artifacts/quality-cad-time-budgets/before-fix-reproducer.log`とrunに保存。
新しい6caseを製品テストへ追加し、同じ契約を使って変更後に成功した。
段階移行の一部はLIFECYCLE_ONLYの模擬request/launchであり、実CAD形状の成功とはしない。

関連60件成功：`20261023T160709Z-f3ab8e10`。実childの取消/完了/起動失敗、
CAD GUI、通常再計算、仮ディスクの既存契約を含む。quick63件：
`20261023T160811Z-e6f62ab7`。変更2 Pythonの限定Ruff・差分検査も成功。

Windowsの製品CadExportWorkerを実際に起動し、過去に検証したfull-scope入力3fileを
新規の私有UUID jobへ複製して使った。CAD本体開始時に有効timer3,600,000 ms、
残り3,599,890 msを確認し、その後に意図的に取消した。所有tree停止、元入力不変、
実行process残り0、STEP出力なし、最大heartbeat gap0.032 sを確認した。
`artifacts/quality-cad-time-budgets/native/latest.json`が実行先を指す。
これはnativeの開始/期限/取消確認（PASS_LIFECYCLE）であり、GUIで全周CADを最後まで
完了した確認ではない。ANSYS Import/MeshはNOT_TESTEDのまま。

最終Python・テストを固定した全回帰は2,472件成功（既存2,466件＋追加6件）。
一意IDの欠落・重複・予定外・失敗・error・skipはいずれも0、固定入力387件は不変。
通常1,227件：`20261023T164640Z-273929cb`、通常1,148件：
`20261023T170010Z-1332f0a6`、実CAD97件：`20261023T161017Z-e7edf8ec`。
集計は`artifacts/quality-cad-time-budgets/final-test-coverage.json`。
ユーザーJSONと同梱既定JSONは元々別の内容であり、両者を同一と扱わずそれぞれの不変を確認した。
