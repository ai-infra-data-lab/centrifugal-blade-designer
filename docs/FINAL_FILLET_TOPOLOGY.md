# フィレット履歴と完成形状の面分類

## 問題と修正

OCCTの`BRepFilletAPI_MakeFillet.NewFaces`と`Generated(edge)`には、後続のcorner
処理で置換された構築途中の面が残ることがある。履歴に存在するだけでは、完成BREPの
面とは限らない。従来はこの中間面をrolling面として半径検査へ渡していた。

`OcctBackend.apply_fillet`は、完成`builder.Shape()`のfaceとの`IsSame`一致を
先に確認する。完成形状にない履歴面はroleと半径測定へ含めず、
`excluded_intermediate_fillet_faces`に記録する。支持面の除外、生成元edge/vertexによる
rolling/corner分類、group所有者の検査は維持する。

これは完成形状の削除、半径の縮小、公差の緩和ではない。完成形状に生成面が残らない
場合はエラーとする。完成形状にある面の半径不一致・欠測・非有限は従来どおり拒否する。

## 再現と検証範囲

現既定Impeller＋Splitter、仮ディスク、明示R0.1 mmについて、診断専用に
生の全周翼とHubを先に一体化し、その後一括filletを試行した。
完成331面のBREP・閉鎖・正体積・1solid・自己交差検査は成立したが、旧分類による
半径検査で出力受入れを拒否した。保存された完成形状のrolling 158面は同じ基準で成立し、
履歴にだけ残る面の混入を再構築で確認した。

診断記録は`artifacts/quality-root-interface/full-fillet/`、
`radius-live/`、`full-fillet-final-topology/`。診断用の構築経路は製品の全周経路へ
まだ採用していない。診断では自己交差検査の実行をparallel化したが、検査対象や閾値は
変えていない。途中の失敗・timeoutも保存し、成功へ読み替えない。

`tests/cad/test_final_fillet_topology.py`は実カーネルのbox filletへ
中間面を含む履歴を注入し、完成面だけを測定すること、完成生成面がない場合の拒否を検査する。
これは既定全周のSTEP出力成功を代替する試験ではない。

修正後の同じ診断経路は約863秒で完了。完成面は331、filletは202面
（rolling 158・corner 44）、中間面31面を除外した。BREP・閉鎖・正体積・1solid・
自己交差検査が成立し、rolling 158面の半径標本も成功した。
最大edge公差は約0.0008701 mmで、指定0.01 mm以内。corner全面G1と全面の厳密な
半径保証は未検査。STEP再読込みは別検査であり、この結果に含めない。

## 回帰結果

関連18件、短縮63件、変更PythonのRuffが成功。全2,261 ID（通常2,206・実CAD55、
既存2,259保持、新規2）を実行し、固定360入力に変更はなかった。
初回全回帰では通常テスト1件が新規出力directoryの`os.replace`でWindowsの
`PermissionError / WinError 5`となった。無効Splitterを検査する前の正常ケース作成時の
環境エラーであり、初回全回帰を全件成功とは記録しない。

同じソースで単独1件、続いて該当`tests/test_splitter_turbogrid.py`全58件を再実行し成功。
最終の採用結果はこの58件を置き換え、他の全回帰結果と合わせて2,261一意ID、
漏れ・重複・未期待ID・残る失敗/error/skipは0。初回ログと失敗は削除していない。
根拠は`artifacts/quality-final-fillet-topology/final-test-coverage.json`と
`artifacts/quality-final-fillet-topology-verified-02/final-test-coverage.json`、各JUnit/raw log。
最初の監査読取りはUTF-8ログをcp932で開いて失敗し、UTF-8で再監査した。
これはテスト失敗や計算値変更とは別のツールエラーである。

全周STEP追加診断の最初の再試行は全回帰とのメモリ競合を避けるため中断し、
`full-step-final-topology/interruption.json`に未完了として記録した。
全回帰終了後の別作業領域`full-step-final-topology-retry/`で検証を継続する。

## 全周STEPの追加診断結果

ソース`c61887a`で診断用全周形状をSTEPへ書き出し、再読込みを完了した。
元形状と再読込み形状のBREP・自己交差・閉鎖・正体積・1solidが成立。
単位mm、体積差約0.08280 mm³（既存上限11.38325 mm³）、bbox最大差約1.42e-14 mm、
再読込み後の最大edge公差約0.0007876 mm（指定0.01 mm以内）を確認。
STEP前後ともrolling 158面の半径標本が成立し、再読込み後の最大半径誤差は
約0.0002487 mmだった。全体約1,381秒で、受入れ基準の変更はない。

根拠は`artifacts/quality-root-interface/full-step-final-topology-retry/model/result.json`、
`loaded-source-manifest.json`、`process.log`、`watchdog.json`。
これは既存`step_roundtrip`の検査範囲の成功であり、全面の双方向偏差・法線一致や
corner全面G1、ANSYS Import/Meshを検証した結果ではない。

別途、単一passageとHubの実体積から求めた11回配置の期待体積との差は
約0.05016 mm³だった（`full-volume-consistency.json`）。体積比較だけで同一形状と判定しない。
製品の全周構築経路はまだ変更しておらず、上記の組込み条件と回帰を引き続き必要とする。

STEP writer単体についても同じ全周形状の書出し前後でバイナリBREPの指紋が一致した
（`writer-constness/result.json`）。元形状を変更せずに書き出していることの診断であり、
新しい妥当性検査の代用ではない。

さらに11配置×主翼/Splitterの全22部品に別々のgroupを付け、各capのHub内包、
各groupのLE/TE/PS/SS根元対応を確認した。全158根元edgeの対応が揃い、fillet後も
22 groupの所有者が一意、半径標本も成立した。後者は分類のみの診断で、妥当性検査は
省略して`UNVALIDATED_CONSTRUCTION_DIAGNOSTIC`と記録している。
その完成BREPとSTEPまで検証済みの完成BREPのバイナリ指紋は一致した。
根拠は`instance-coverage/result.json`、`per-instance-fillet-roles/result.json`、
`per-instance-binary-comparison.json`。別形状や別Rへ結果を一般化しない。

## 残る条件

2026-10-22、製品の全周組立てへ全周一体化後fillet方式を追加した。
全instanceの根元対応・cap内包・配置間距離、現既定R0.1全周STEPと半径・公差を確認し、
既存R8周期sector・流体CADと出力保護を含むCAD全66件が成功した。
全2,272一意IDの監査も完了した。現既定の周期sector/流体CAD、全面偏差・法線は別に追跡する。
[製品経路と検証範囲](FULL_FILLET_ASSEMBLY.md)。
ANSYS Import/Meshは今回対象外のまま。
