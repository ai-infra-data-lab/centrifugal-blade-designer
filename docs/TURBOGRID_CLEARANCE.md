# クリアランス付きImpellerのTurboGrid Profile Points

## 出力内容と使い方

正のTipクリアランスがあるImpellerも、従来のTurboGrid Profile Pointsから出力できます。画面・設計値・JSONの翼は実Tipまでのまま、出力用にShroudへ届く断面を追加します。ケーシングのHub／Shroud子午線は移動しません。

`profile.curve`（名前を変更した場合はそのファイル）には、次の順で閉輪郭を保存します。

| 順番 | 内容 |
| --- | --- |
| 1 | 従来のHub断面 |
| 2〜N−1 | 設計済みの中間Span断面があればその断面 |
| N | `Tip_clearance`: 画面と同じ実Tip断面 |
| N+1 | `Shroud_extension`: 出力用のShroud到達断面 |

Nは設計断面数です。Hub／Tipだけなら実Tipは2、延長断面は3です。中間Spanが1つなら実Tipは3、延長断面は4です。実Tipを0〜1へ再変換したり、隙間をなくした設計で再計算したりしません。すべての元断面の輪郭・LE／TEマーカーを保持し、同じファイルに加えます。

`hub.curve`、`shroud.curve`、`profile.curve`、`BladeGen.inf`の4ファイル構成は維持します。実Tipの番号は出力後のステータスと`BladeGen.inf`のコメントに記録します。コメントは操作案内であり、TurboGridのクリアランスを自動設定する命令ではありません。

TurboGridで読込み後、**Shroud Tip → Clearance Type → Tip Option = Profile Number**にし、上記Nを指定してください。指定しない場合は、Shroudまで届く翼として扱われます。`CAD From Profile Points`を使う場合の`Include Tip Clearance in CAD File`など、入力モード別の設定は実機で確認してください。

根拠: [Ansys 2026 R1 User's Guide 10.3.6.4](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i016457045820452615547.html)。Profile NumberはHubから1始まりです。公式資料は、実Tipを最後から2番目に置く際、最終断面がSpan方向の延長と整合している必要があるとも説明しています。

## 延長方法と検証

`geometry/span_extension.py`はQt・ファイル形式に依存しません。最後の2つの設計Spanの対応点を使い、円筒座標のZ・R・連続したthetaをそのままSpan方向へ線形延長します。Z/Rの延長半直線と解析的なShroudのLine／Arcとの最初の交点を求めます。TE Rake反映後の実断面を参照するため、ゼロ隙間へ設定を戻してβ積分をやり直す方法とは異なります。

TE Cutoffで内部のPS／SSの点数が違う場合だけ、区間内の正規化弧長で前のSpanを対応付けます。実Tipの点は変更しません。一定外径TEの半径は保ちます。曲線のゼロ隙間端では、既存サンプルの弦と解析円弧の差があるため、サンプル最大間隔と最小円弧半径から求めた微小誤差範囲内だけ、解析Shroudへ位置を合わせます。実Tip配列やユーザーのクリアランス値は修正しません。

到達不能・つぶれたSpan・逆行するキャンバー・輪郭の非接続・自己交差・非有限座標を拒否します。出力時は丸め後の重複点／LE・TEマーカー／断面間の点数も検査します。所属Hub／Shroudの連続性とLE／TE・最外輪郭の包含を従来どおり検査し、無効な現在値・不完全な所属設定では既存ケースを更新しません。保存済みJSONで現在のImpellerとその翼列snapshotのクリアランスが不一致なら再選択を求め、古い無隙間の値を出力しません。

すべての計算・検証・文字列化を出力先作成前に済ませます。I/O障害時は従来のファイル単位`os.replace`です。ケース全体の書込みトランザクションは追加していません。

## 互換性と対象範囲

- 隙間未指定／両端0 mmは従来経路で、3ケース12ファイルの歴史的ASCIIハッシュとゼロ隙間のバイト一致を検査します。参照fixtureは変更しません。
- 静翼Diffuser／RCの出力、設計・表示・保存・既定値・CSVは変更しません。出力軸X／Y／Zと単位MM／CM／Mは、実Tipと延長断面にも同じ変換を適用します。
- 今回は**Profile Points**です。正の隙間のTurboGrid CAD出力と、Splitter付きTurboGrid出力は引き続き書込み前に拒否します。主翼だけを不完全に出力しません。
- 実機での読込み・Profile Numberによる実Tip認識・LE／TE位置・壁面交差・メッシュ品質は未確認です。ファイルの自動検査をANSYS成功とは扱いません。

## 変更箇所と確認記録

- `geometry/span_extension.py`: 出力用のShroud断面を作る数値処理。
- `fileio/turbogrid_export.py`: 実Tipの次に延長断面を保存、追加検証、実Tip番号のコメント。
- `gui/main_window.py`: 実Tipの番号を出力完了時に表示。
- `tests/test_turbogrid_clearance.py`、`test_turbogrid_clearance_gui.py`: 新規23件。直線／円錐の解析解、曲線Shroud、片端ゼロ、一定外径TE、Rake、CW／CCW、軸／単位、既存配列不変、GUI、無効出力保護。
- `tests/test_tip_clearance.py`: 正の隙間は出力可能に変更し、幅超過の無効出力保護とCADの拒否を維持。
- README／FEATURES／ARCHITECTURE／TIP_CLEARANCE／本書: 現在の操作と対応範囲。

関連83件成功、63.69秒（`20261016T230012Z-8c113c80`）。最終全回帰703件が成功しました。非CADは235件（484.270秒、`20261016T230133Z-c2536223`）、228件（545.986秒、`20261016T230135Z-5abc9a4a`）、205件（447.958秒、`20261016T230135Z-b5b8b51b`）の3分割、CADは35件（692.134秒、`20261016T230135Z-3a2610b8`）です。時間はJUnitの記録です。単一実行の703 passedという意味ではありません。

収集した全703テストIDとJUnitを照合し、実行漏れ・予期しないID・失敗・error・skipは0件。最終試験開始時に固定したPythonソース207ファイルも一致しました。照合記録は`artifacts/turbogrid-clearance-review/final-test-coverage.json`。前回作業からの既存ソース変更はTurboGrid出力・MainWindowの完了表示・Tip clearance試験の3ファイル、追加は延長計算と新規試験の3ファイルです。以前の未コミット変更は保持しています。

`git diff --check -- .`成功、stage対象は空です。既定JSONのSHA-256は変更前と同じ`6511ea9186e18acad72ef055f0dbc1de4ac0700c27dc75627abad065a9121bce`です。

既定モデルの選択Impellerのコピーを使い、LE 0.5／TE 1.0 mm、15有効桁の例を`artifacts/turbogrid-clearance-review/example`へ作成しました。例示用コピーだけ全壁面を当該翼列へ割り当てています。Hub・実Tip・延長の3断面が各241点、すべてLE／TEマーカーを持ち、実Tip輪郭の最大出力誤差は4.974e−14 mm、延長輪郭の解析Shroudからの最大距離は1.465e−14 mmでした。元の設計パラメータと実形状配列は不変。記録は`smoke.json`、再現処理は`smoke.py`。これはANSYS読込みの確認ではありません。

開発途中の試験でTE Cutoff後の内部点数不一致を検出し、区間内対応を追加しました。ゼロ隙間端のサンプル弦誤差も検出し、解析交点への微小補正を追加。最初の関連実行は64成功／10失敗（`20261016T225644Z-bc3afda2`）、補正前の22件実行では21成功／1失敗（`20261016T225831Z-41ec8129`）でした。試験用の既定モデルコピーには、全輪郭を含む所属壁面を明示しており、ユーザー原本の所属・端位置は変更していません。GUIの追加コードの字下げミスによる3件の収集エラー（`20261016T225952Z-8fb9b5fc`）は修正後に再実行しています。環境エラーではなく開発中の修正記録です。

実ディスプレイ／F5／DPI／別PC／Python 3.11での今回変更後再確認・ANSYS Import／Meshは未確認。以前の未コミット作業を保持し、stage・commit・pushは行いません。
