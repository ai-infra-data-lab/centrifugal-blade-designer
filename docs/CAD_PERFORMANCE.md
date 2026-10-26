# CAD処理時間の基準と改善順序

2026-10-26。CAD改善の第1段階として、既存Windows GUI検証の通知時刻を分解する。
**今回は計測・比較の開発補助を追加した。CAD計算の高速化自体は未実施で、短縮率は報告しない。**
形状、指定R、公差、自己交差/体積/STEP等の検査、既存JSON・CAD出力形式は変更しない。

## 読取り専用の解析ツール

```powershell
.\.venv\Scripts\python.exe -X utf8 tools/analyze_cad_timing.py `
  artifacts/quality-status-and-gui/attempt-2/events.jsonl

# 複数の独立した記録を比較し、新しいJSONレポートへ保存
.\.venv\Scripts\python.exe -X utf8 tools/analyze_cad_timing.py `
  artifacts/quality-status-and-gui/events.jsonl `
  artifacts/quality-status-and-gui/attempt-2/events.jsonl `
  --json-output artifacts/quality-cad-timing/new-report.json
```

保存先の親フォルダはあらかじめ用意する。既存ファイルを上書きせず、同名出力は終了2で拒否する。
入力・CAD job・検証済みSTEPは書き換えない。アプリ/CAD環境へのライブラリ追加も不要。
時刻のない通常の`process.log`から時間を推測する機能ではない。
上記ログはローカル検証資料であり、clone先に同梱されるサンプルではない。

入力はGUI検証ハーネスのUTF-8 JSONL（BOMありも可）。
`worker`、`stage`、`completed`、`cancellation_verified`、`fresh_gui_export_verified`を読む。
CAD/仮ディスクのworkerを区別し、CAD jobごとに完了・取消・GUI照合通知の有無を出す。
未完了jobは総時間を`null`、開いた工程を明示し、取消状態も未観測なら`null`にする。
同じjobの二重入力、worker重複、不正/非有限値、時刻逆行、未対応イベントを拒否する。
入力バイト列のSHA-256を保存し、後からログの版を照合できる。

最小の入力形式例（人工の時刻であり、実CADを生成した記録ではない）：

```jsonl
{"time": 10, "kind": "worker", "type": "CadExportWorker", "job": "example"}
{"time": 11, "kind": "stage", "stage": "FULL IMPELLER"}
{"time": 20, "kind": "completed", "overall": "WARNING", "cancelled": null}
```

この例では観測総時間10秒、最初の通知まで1秒、FULL IMPELLER通知後9秒となる。
GUI照合通知はなく、形状の妥当性は解析しない。

## 測定の意味

- `observed_job_seconds`はGUI側でworkerを観測してから完了通知を観測するまでの壁時計時間。
- 各工程は通知〜次の通知までの間隔。内側の複数処理・process起動・GUI側完了処理も入り得る。
- STEP進捗通知の最後には後処理/preview/公開が含まれるため、STEP単体のCPU時間と呼ばない。
- ハーネスの単調時計による`gui_reported_seconds`は別欄。二つの時計を同じ値へ補正しない。
- 時刻逆行は拒否するが、前向きの時計補正はログだけで検出できない。CPU時間・全負荷での性能保証ではない。
- ログ中の`PASS/WARNING`やGUI照合通知は観測値。解析ツールの`geometry_validation`は常に`NOT_ASSESSED`。
  形状の合否は元のCAD/受入れレポートで確認する。

## 実測基準

基準は[GUI受入れ](GUI_FOLLOWING_SECTOR_ACCEPTANCE.md)の修正後の成功ケース。
既定の主翼11枚＋Splitter11枚、自動仮ディスク、明示R0.1 mm、
`periodic_sector / blade_following`、CAD公差0.01 mm、Mechanical STEP。
GUI通知からの観測総時間は2708.567秒、単調時計のボタン→結果照合は2708.968秒。
以下の比率は前者を分母とする。

| 通知区間 | 秒 | およその時間 | 構成比 |
| --- | ---: | --- | ---: |
| FULL IMPELLER | 692.934 | 11分33秒 | 25.6% |
| RECONSTRUCTED VALIDITY | 588.872 | 9分49秒 | 21.7% |
| RECONSTRUCT FULL WHEEL | 487.474 | 8分7秒 | 18.0% |
| PRIVATE FULL VALIDITY | 391.431 | 6分31秒 | 14.5% |
| RECONSTRUCTED BOUNDARY SAMPLES | 168.823 | 2分49秒 | 6.2% |
| INTER-BLADE INTERFERENCE | 115.545 | 1分56秒 | 4.3% |

上位4区間で約79.8%。再構成の結合と妥当性検査だけで約39.7%。
`FULL IMPELLER`には全周結合・fillet・その検査などが含まれ、fillet単体25.6%という意味ではない。
妥当性検査にもBREP/自己交差/体積/面積/bbox等があり、この通知だけでは個別の時間は分からない。

補助比較として初回のCAD完了記録では、上位4区間がそれぞれ687.024、585.617、488.639、389.800秒だった。
この初回はCAD/公開の完了後にハーネスの誤期待でFAILとなり、GUI照合通知がない。
完全なGUI通し成功の件数へ加えない。取消jobも短縮後の成功生成として混ぜない。
両記録の差は無変更での観測差であり、速度改善の証拠ではない。

ローカル結果：`artifacts/quality-cad-timing/baseline-with-provenance.json`。

## 次に改善する順序

1. 上位2つの妥当性検査で、BREP、自己交差、体積積分、面積/bbox等の内訳を計測する。
   現時点では自己交差が最大の原因と断定しない。
2. 全周再構成のBoolean結合と、元全周生成の内訳を比較する。
   ネイティブ処理には既に並列実行指定があるため、未計測のthread設定変更を速度改善と呼ばない。
3. 具体的な候補を1件ずつ比較し、同じ入力・指定R・公差・検査・出力品質を維持したことを確認する。
   通知時間だけで幾何学的同等性を判定しない。

コピーの検査へ元objectの結果を流用したり、再構成・自己交差検査を省いたりして短縮しない。
[既存の検査再利用条件](CAD_VALIDATION_REUSE.md)を維持する。
代表構成の追加受入れ、実ANSYS、3D CAD最適化の組込みはこの作業では実施していない。

## 検査

新規30件（`tests/test_cad_timing_analysis.py`）成功。
解析解の時間配分、入力不変、取消/未完了、誤帰属/重複、非有限/逆行、UTF-8 BOM、
実CLI、新規出力と既存ファイル保護、時刻のない入力の拒否を確認した。
短時間63件と変更2 Pythonの限定Ruffも成功。
今回の変更は独立した開発ツール・試験・文書だけで、アプリの計算・GUI・設計JSON/出力経路には接続しない。
そのため既存全回帰は再実行せず、既存入力/試験IDの不変と全件収集を照合する。
今回の全件収集は実行PASS件数ではない。
全2,691 IDの収集で既存2,661を保持し、新規30は本ツールの試験だけだった。
既存413入力は不変。新規30件は`20261026T090824Z-f0a34bd2`、quick63件は
`20261026T090313Z-b63bef49`、収集は`20261026T090942Z-90466a4b`。
監査結果はローカル`artifacts/quality-cad-timing/audit.json`。
