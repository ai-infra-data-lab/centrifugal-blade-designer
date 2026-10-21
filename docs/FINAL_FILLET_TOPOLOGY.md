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

## 残る条件

製品の全周組立ては依然としてfillet済み単一passageからHubを差し引いて複製する方式。
診断の全周一体化後fillet方式を採用するには、全instanceの根元対応・cap内包・干渉、
STEP再読込みと半径・公差・偏差、周期sectorと流体CAD、出力保護の検証が必要。
ANSYS Import/Meshは今回対象外のまま。
