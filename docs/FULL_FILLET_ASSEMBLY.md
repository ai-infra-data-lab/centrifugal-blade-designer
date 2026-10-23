# 全周一体化後の根元フィレット

既定形状の周期sectorを製品workerで追加確認。明示R0.1 mm・仮ディスクで約22分37秒、全周1実体/22配置924比較と、切断後2実体/STEP全56面・fillet19面の半径標本が成立。周期面回転対応も別診断で確認。単一連結sector条件はFAIL、仮ディスクはWARNING、全面品質/GUI人手操作/ANSYSは未検証。設計値/公差/ガードは維持。[根拠・範囲](DEFAULT_PERIODIC_SECTOR_CHECK.md)。

## 対象と構築順

`cad/worker.py`は、真のHub filletを要求し、全周・周期sectorまたはTurboGrid CADを
生成するとき、`cad/full_assembly.py`を呼ぶ。翼のみ、Blade+Hubのみ、filletなしの
従来経路は維持する。入力Rを自動的に縮小せず、設計値・JSON・Profile Pointsを変更しない。

旧経路はfillet済み単一passageからHubを差し引き、その差分を回転していた。
既定形状では、この差分が接線接続部に自己交差を含む閉立体となる。
差分のBREP analyzer成功や正体積だけを根拠に、複製可能な有効形状として扱わない。

新経路は元面のHub内延長を持つ主翼・Splitterを各pitchに配置し、ひとつのHubと
非破壊Booleanで一括結合した後、全根元に一度だけ指定Rのfilletを生成する。
単一passageのプレビュー・従来の根元reportは別途維持する。

## 検査と失敗時の扱い

- 各配置のconstruction capが実際の翼topologyに属し、Hubからはみ出さないことを
  非破壊Cutで確認する。延長ありなのにcapがない、古いcapを参照する場合も拒否する。
- 全周結合の中間体はBREP・閉鎖・1solid・正体積・積分収束と、内部cap消失を検査する。
  この段階の自己交差は`NOT_TESTED_INTERMEDIATE`であり、成功と報告しない。
- 各`main@pitch`／`splitter@pitch`についてLE/TE/PS/SS根元を全て要求し、
  fillet後も全所有者が残ることを要求する。
- 完成立体は自己交差を含む実カーネル検査、閉鎖・1solid・正体積・edge公差を検査する。
  自己交差checkerは従来と同じsmall-edge=False/self-intersection=Trueで並列実行する。
- fillet前の有効な翼差分で周期コピーの重なり体積を測定する。完成後は全配置対について
  blend同士、blendと他翼の元面（双方向）、元面同士の4比較を行う。元面にはTip capも含む。
  距離が要求公差以下、未取得、非有限、対象面欠落の場合は拒否する。
- 離れた面群は、保存公差を含み三角形を使わないBREP boundsから、軸方向gapの最大値を
  距離の下限として使う。差の丸めを負方向へ一段補正し、下限が要求公差を超えた場合だけ
  分離とする。それ以外は実面間距離を評価する。下限を実測最小距離と表記しない。
- rolling faceの半径標本、STEP再読込み後のBREP・自己交差・単位・体積・bbox・edge公差・
  半径標本を既存基準で検査する。corner全面G1や全面の双方向偏差を検証したとはしない。
- 失敗は従来のstaged出力・検証済みartifactのみの公開契約へ返す。
  無効な全周STEPを既存の有効なケースへ置換しない。

## 検証記録

入力・cap・接触・checkerに関する新規nativeテスト4件、既存R8周期sectorと流体CADの
関連2件、quick 63件、変更PythonのRuffが成功した。
結合済みmetadataの修正後、既定Blade+Hub・cap・干渉・R8周期sector・流体CADを含む
関連14件も成功した（`20261022T104932Z-a1a1d974`、590.10秒）。
最初の関連試行ではOCP 8の`Bnd_Box.Get`戻り型がPythonへ公開されておらず失敗したため、
既存backendでも使用している`CornerMin/CornerMax`で取得するよう修正した。
失敗した試行を成功結果に含めない。

既定モデルの主翼11枚＋Splitter11枚、明示R0.1 mmの製品経路はSTEPまで成功した。
22 groupの158根元edge、202 fillet面（rolling 158／corner 44）が成立。
全配置対の4比較924件は、保存公差込みboundsによる分離774件、実面距離150件で成立した。
実面距離を計算した150件の最小は約5.45174 mm、bounds下限の最小は約0.11848 mm。
後者は実測最小距離ではなく、全体の最小距離を5.45174 mmと断定しない。
いずれも要求0.01 mmを超える。

元／再読込みの最大edge公差は約0.00087007／0.00078762 mm。
体積差は約0.08280 mm³（既存上限11.38325 mm³）、bbox差は約1.42e-14 mm。
STEP前後ともrolling 158面の半径標本が成立し、再読込み後の最大半径誤差は約0.00024867 mm。
結果は仮ディスクのため全体`WARNING`、Mechanical artifactとroundtripは`PASS`。
ANSYS Import/Mesh、現既定のTurboGrid所属範囲の成立を意味しない。
根拠は`artifacts/quality-full-fillet-product-verified/product-full-summary.json`と
`20261022T105140Z-5c0c5353`の実worker report。

全回帰は2,272一意IDで成功した。通常2,206件、実CAD66件、既存2,267件を保持し新規5件。
失敗・error・skip・漏れ・予期しないID・重複は0、固定363入力はすべて不変だった。
初回の全回帰候補で、単体翼の延長metadataを結合済みbodyへ持ち越すと、既に埋没・消失した
capを再要求してしまう問題を検出した。結合済みbodyを再結合するときは単体翼の構築metadataを
渡さず、形状・labelsを引き継ぐよう修正した。元の翼のcap検査は省略しない。
初回はこの失敗後に所有する3つの試験プロセスツリーを停止し、中断として保存した。
根拠は`artifacts/quality-full-fillet-product/interruption.json`。
修正後の全回帰は別の`artifacts/quality-full-fillet-product-verified/`で開始した。
全周自己交差の重い工程でCAD private memory約4 GB、空き約320 MBとなったため、
通常2組だけを所有PID確認のうえ中断した。CADは続行し、通常2組は同じ固定ソースで再実行した。
`normal-partitions-interruption.json`と停止ログを保持し、中断組を成功件数へ含めない。
通常再実行と全ID監査は`artifacts/quality-full-fillet-product-normal-retry/final-test-coverage.json`
へ保存した。受入れは通常1,131件＋1,075件と実CAD66件の3つの完成JUnitを照合した結果。
元の不具合候補や中断runが全件成功したという意味ではない。

仮ディスクは`PROVISIONAL`のまま。ANSYS Import/Meshは対象外・`NOT_TESTED`。
R0.1の成立を他の入力Rや他形状への成立保証に一般化しない。

pytest件数とは別に、既存の独立sampleへSplitterを加え、主翼2枚＋Splitter2枚、
明示R1 mm・周期sector・Mechanical/流体CAD同時出力も実行した。
4 groupの16根元edgeと24比較が成立し、Mechanical STEPと流体STEPのroundtripが成功。
専用の新しい一時caseへのpublishも完了し、Profile Pointsは`PASS`、流体CADは
`CONVERSION_REQUIRED`、ANSYS Import/Meshは`NOT_TESTED`だった。
これは現既定JSONではなく独立fixtureの追加検証である。
根拠は`artifacts/quality-full-fillet-splitter-flow/published-summary.json`、worker report、
watchdogと専用caseのmanifest。

## 次の検証へ引き継ぐ観測

現在の全周STEPと過去の検証済み診断BREPを、全331面・各方向2,913点で比較した。
最大の実境界距離は順方向約2.244e-9 mm、逆方向約2.877e-9 mm、法線角度は
両方向で最大約1.479e-6 deg。元の製品worker内の比較ではなく、診断BREPとの追加比較である。
有限標本であり、標本間を含む全面保証ではない。結果と入力hashは
`artifacts/quality-step-local-deviation/full-product-samples/`に保持した。
体積/bboxを保った内部面移動の独立不正例は現行roundtripを通るため、C02は未完了。

生成済みの実CAD previewを独立したWindows Qt部品へ読み込むnative計測も行った。
ファイル約51.3 MB、全周57,956三角形、JSON読込み約1.531 s、最大paint約1.765 s、
20 ms heartbeatの最大間隔約1.766 s。設置時のcamera保持を確認し、画像を確認した。
これは表示部品の計測で、export GUI全経路や人のマウス操作の検証ではない。
応答性は未改善としてStage 6へ引き継ぐ。根拠は
`artifacts/quality-native-full-preview/result.json`、`window.png`、`watchdog.json`。
