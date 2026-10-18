# 実CADの採用格子による参照（Stage 3A-2c 続き）

## 操作と適用範囲

`View → CAD Surface Reference`へ「実CADの採用格子を使用」を追加した。従来の固定格子モードは初期状態のまま残す。

1. 現在のImpellerの設計でCADを生成する。
2. 参照画面で現在の設計を取得し、「実CADの採用格子を使用」を有効にする。
3. Main/Splitterごとに、LE/PS/TE/SSの実採用値を確認する。固定格子の入力欄は無効になる。

結果はこのアプリセッションで最後に完了したCAD jobから取得する。保存済みcaseのresult.jsonを任意に開く機能ではない。アプリ再起動後は結果を再生成する必要がある。CAD結果がない状態で有効にして拒否された場合、CAD完了後にRefreshする。固定モードへ戻す場合も、参照が無効になっていたらRefreshする。

新しいCAD結果が届いたとき、採用格子モードで有効な取得snapshotがあれば再照合して表示する。設計/翼列が変わった場合は、従来どおり参照を失効させる。結果を推定したり、欠けたSplitter情報に主翼の値を使ったり、エラー時に65格子へ黙って戻したりしない。

## 照合契約

`cad/reference_report.py::adopted_surface_counts`はファイルを読み書きせず、既存のCAD reportと参照snapshotを照合する。

- canonical design snapshotのSHA-256が完全一致すること。row ID/選択・設計値・CAD設定もsnapshotに含まれる。
- Impeller、mm、Z軸で、overallがPASSまたはWARNING、cad_surface_status/blade_solid_statusがPASSであること。
- 選択集合のBREP有効・自己交差検査・閉鎖がTrue、solid_countが整数1であること。これは既存CAD検証結果の確認であり、参照画面が新しくkernel検査をする意味ではない。
- `checks.blade_solids.main/splitter.surface_grid_counts`の4 roleが揃い、33/65/129/257/513の整数であること。bool、float、欠損/余分なrole、不正値は拒否する。

返す格子mapはコピー。レポートや設計値を変更しない。FAIL job、ディスクだけのjob、snapshot不一致、古い/不完全なレポートは適用しない。Blade OnlyのWARNINGは基準翼面の参照として許可するが、根元フィレット・ディスクとの結合・ANSYSの成立を意味しない。

MainWindowは既存のCAD完了処理で、公開処理後の結果をメモリ内にコピーする。公開失敗もFAILとして扱う。以前の成功結果を新しい失敗結果の代わりに使わない。参照widgetはその結果を読取り専用で取得し、選択集合に応じた格子を使う。既存のCAD生成・publish・STEP・preview.jsonの形式は変更しない。

## 数値面への適用

`geometry/cad_surface_reference.py::reference_surfaces`は従来の単一整数に加え、4 roleの格子mapを受け取れるようにした。report固有の検査はCAD層に残し、幾何層はQt/JSON/CADファイルへ依存しない。

同じsnapshotのmaster、m_normからの局所xi、Span、共通接線条件、実採用格子を入力して、各roleのtensor splineを再構成する。例えば実CADがLE/TE=33、PS/SS=129を採用していれば、その組合せで4面を評価する。固定65の全roleへ揃えない。元のmasterやβ/厚さを変更しない。

これは`blade_solids`に記録された**Hub結合・fillet前の基準翼面**である。Hub/Tipのcap、根元filletで置換された領域、加工TE、STEP再読込み後の面、最終流体/構造solid全体との一致は別問題。参照の線も有限点の描画標本であり、全面偏差・法線反転・干渉のPASS判定ではない。

## 検証記録

新規31件（レポート/数値24、Qt offscreen 6、実OCCT 1）。集合別コピー、role別格子での係数一致、snapshot/kind/軸/単位、失敗/不足report、BREP flags、非整数/不正密度、完全なrole map、Camera/設計値保持、報告到着/失敗による更新、固定モードへの復帰を検証する。書込みとCAD jobの呼出しを禁止したGUI試験を含む。

新旧参照関連50件成功（13.03秒、`20261018T024130Z-1d0115c7`）。実OCCT関連3件成功（9.78秒、`20261018T024217Z-9f4fbc2b`）。新しい実OCCT試験は、実workerが生成したBlade Only fixtureのreport、NPZ、snapshotを使い、採用された各roleの格子で13×23点を照合する。実採用値はLE=33、PS=129、TE=33、SS=129だった。比較は数値面と同じ入力で作るOCCT基準面の標本比較であり、STEP後の全面保証ではない。Splitterは集合別のレポート/数値/GUI試験で扱い、今回新規の実worker fixtureは主翼である。

同じ実worker fixtureを使ったoffscreen画像を900×700で確認し、採用値の表示・固定格子入力の無効化・曲線全体の表示を確認した。画像用にSegoe UI/Meiryoを明示読込みし、アプリのフォントは変更しない。根拠は`artifacts/quality-adopted-cad/render.py`、`adopted-native.png`、`native-job.txt`。これは実設計の既定形状やnative Windows操作の確認ではない。

既存の数値fixture・期待値・原本/既定JSON・出力ファイルは変更しない。確定結果は次節に記録する。

## 残る課題

保存済みCAD caseの取込み、cap/fillet/STEP後の参照、全面の距離/法線/Jacobian、周期翼/主翼-Splitter干渉、物理対応と表示/CAD/trimの全面統一は未完了。参照取得や多数翼の応答性はStage 6の対象。native GUI・高DPI・ANSYS Import/Meshは未検証。現既定形状の根元フィレット未成立も、この参照対応で解決したとは扱わない。


## 最終全回帰

**1,132一意件成功**（通常1,092・実CAD40）。既存1,101 IDを全て維持し、新規31 IDを追加した。failure/error/skip/実行漏れ/重複/想定外IDは0。固定256入力（package/test Python、main、既定JSON、原本JSON）は開始から終了・commit前の再照合までhash不変。原本と同梱デフォルトの一致も確認した。既存の数値fixture・期待値は変更していない。

通常6群・CAD1群のJUnitと収集IDを照合した。根拠は`artifacts/quality-adopted-cad/final-test-coverage.json`、`source-hashes.json`、`groups.json`。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 399.029 | 20261018T024446Z-65293a6e |
| 通常1 | 143 | 360.392 | 20261018T024446Z-2b2680d2 |
| 通常2 | 122 | 416.539 | 20261018T024446Z-dfc255c5 |
| 通常3 | 191 | 294.461 | 20261018T024446Z-3ae5ada3 |
| 通常4 | 146 | 385.007 | 20261018T024446Z-ef08c1a1 |
| 通常5 | 374 | 470.768 | 20261018T024446Z-8f6be1c2 |
| 実CAD | 40 | 828.417 | 20261018T024446Z-250a6ad6 |

この成功を、根元fillet後/STEP後の面全域の一致、native GUI、高DPI、ANSYS Import/Meshの成功とは扱わない。Stage 3Aの全面統一は未完了。
