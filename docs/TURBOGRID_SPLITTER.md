# Impellerのスプリッター付きProfile Points出力

## 操作

編集対象でImpellerを選び、`File → Export → TurboGrid Export`から専用ケースフォルダへ出力する。既存の4ファイル構成（Hub、Shroud、profile、BladeGen.inf）を使う。主翼連動と専用角度/厚さ分布の両方に対応する。

profileファイル内は`## Main`と`## Splitter`で翼を区切り、その中にHubからTipへの各`#`断面を並べる。1ピッチの主翼1枚とスプリッター1枚を保存し、全周分の複製は出力しない。BladeGen.infのBlade Setsは主翼枚数、Blades Per Setは2。Blade 0/1それぞれのLE/TE指定も記録する。主翼のみのときは従来の形式とファイル内容を保持する。

3D表示に使う`generate_impeller`のsections / splitter_sectionsをそのまま出力する。Hub/Tip開始位置・ピッチ割合・TE Rake・厚さ倍率・専用分布は既存generatorが計算済みで、出力側ではもう一度回転/切出ししない。X/Y/Z軸とMM/CM/M単位には両翼へ同じ変換を適用する。元のJSON、設計値、表示設定を変更しない。

## クリアランスとTheta方向

クリアランス付きでは各翼の物理Tipを保持し、それぞれの直前Spanからケーシングへ延長したShroud断面を末尾に追加する。たとえばHub/中間/Tipの3断面なら、各翼はHub・中間・Tip_clearance・Shroud_extensionの4断面となる。

TurboGrid読込み後、**MainとSplitterの両方**に対しShroud TipのTip OptionをProfile Numberとし、出力後の表示およびBladeGen.infコメントにある物理Tip番号を指定する。番号は翼ごとのHub始まり1-basedで、`##`の翼名行を数えない。延長断面は翼面の継続用であり実際の翼端ではない。

ATMのSplitter配置では、指定したTheta方向で主翼が低Theta、Splitterが高Thetaとなる必要がある。アプリのCCW配置ではMachine DataのTheta DirectionをRight Handed、CW配置ではLeft Handedとして確認する。座標自体を反転させて合わせない。推奨方向をBladeGen.infのコメントと出力完了表示へ案内する。コメントは自動設定コマンドではないため、TurboGrid側の設定を確認する。

## 公式形式の根拠

- [Ansys 2026 R1：BladeGen.inf](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i998527.html)：1組の翼数と各BladeのLE/TE指定。
- [Radial Compressor公式チュートリアル](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_tutr/i1131098.html)：主翼とSplitter、クリアランス、ATM Single Splitterの設定。
- 同ページから配布する[radcomp.zip](https://ansyshelp.ansys.com/public/Views/Secured/Doc_Assets/v261/TurboGrid/radcomp.zip)の`profile.crv`で、翼区切りが`##`、断面区切りが`#`であることを実ファイル確認。ZIP SHA256は`b648d46141d3bb0d71dbce6112d5b2d74fead57060bbec1be062ff02763f9d17`。ZIPはローカル検証資料としてartifacts内に保持し、リポジトリへ転載しない。
- [User Guide 10.4.4](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/pdf/Ansys_TurboGrid_Users_Guide.pdf)：ATMの対応端部形状、子午面位置、Theta配置の条件。これらと実機でのTopology/mesh成立は、ファイルの自動検査だけでは保証しない。

## 検証と既存出力の保護

生成・所属確認・単位変換・丸め後の輪郭/LE・TEマーカー/Span間点数の検査を両翼に行い、すべての内容をメモリ上で完成してから既存のケース単位publishへ渡す。片方だけを出力しない。点数一致は翼ごとに検査し、翼同士の点数は無理に合わせない。

選択Impellerとそのrow snapshotでSplitter設定が違うときは再選択を求める。Splitterの欠落/Span不一致、所属壁面の範囲外、無効な設定、低精度でつぶれる断面、延長失敗なら既存ケースを保持し、新規出力先も作成しない。既存の未対応な派生Shroud/外径カットや正の隙間のTurboGrid CAD制限は解除しない。所属壁面が主翼とSplitterの全輪郭を含む必要があり、既定モデルでも所属不足は自動修正しない。

`tests/test_splitter_turbogrid.py`はCW/CCW×Cutoff/楕円TE×連動/専用分布×隙間有無×3軸/単位の48組、開始位置とピッチ、実Tip/延長断面、丸め/閉鎖/マーカー、保存/読込、出力切替・ユーザーファイル保持、不正値/欠落/Span/所属/つぶれ/延長失敗の保護を検査する。主翼のみの4ケースは修正前commit `3734406`のexporterから取った新しい専用fixtureと16ファイルのhashを完全比較する。以前の半円の歴史参照を置換したものではなく、同じ現行形状で本変更前後の出力を比較するもの。

`tests/test_splitter_turbogrid_gui.py`はQt offscreenのメニュー出力、クリアランス付き実Tip番号、設計不変とReadinessの非書込み整形検査を確認する。実ディスプレイ、高DPI、ANSYSのImport/各翼のTip指定/Theta方向/ATM生成/mesh品質は未検証。

### 現在の原本/同梱既定の所属条件

読取り専用の追加確認では、両JSONともImpellerのHub/Shroud所属終端はR80 mm、TE基準はR81 mmだった。このままでは所属チェックで止まる。出力用の所属区間は丸めた端部を含む全輪郭まで含める必要がある。Splitterの削除やLE/TE移動で黙って回避せず、子午面の所属区間を設計者が確認する。原本/既定JSONは変更していない。証跡は`artifacts/quality-splitter-turbogrid/user-input-probe.json`。

## 検証記録（2026-10-19）

quick 63件、関連137件（既存関連76、新規出力58、新規GUI2＋既存clearance GUI1）が成功。限定Ruffの変更Python9ファイルと`git diff --check`も成功。

最終全回帰は**1,593一意件成功**（通常1,548・実CAD45）。既存1,533 IDをすべて維持し、新規60 IDを追加した。failure/error/skip/漏れ/重複/想定外IDは0。通常6群と実CAD1群のIDを収集一覧へ照合し、実装・テスト・設定・全fixture・原本/同梱既定JSONを含む固定308入力は全回帰中不変。既存参照fixtureの値は変更していない。

証跡は`artifacts/quality-splitter-turbogrid/final-test-coverage.json`、`source-hashes.json`、`collected-tests.txt`とgroup log。JUnit/完全ログは各`artifacts/test-runs/<run ID>/`に残す。

| 群 | 件数 | 秒 | run ID |
|---|---:|---:|---|
| 通常0 | 116 | 479.224 | 20261018T233653Z-0dfb699d |
| 通常1 | 147 | 436.478 | 20261018T233653Z-91b59245 |
| 通常2 | 125 | 504.448 | 20261018T233653Z-daecfd40 |
| 通常3 | 211 | 368.934 | 20261018T233653Z-d96f924c |
| 通常4 | 153 | 489.383 | 20261018T233653Z-6fee7b53 |
| 通常5 | 796 | 879.662 | 20261018T233653Z-c18d83fa |
| 実CAD | 45 | 644.740 | 20261018T233653Z-c7ff2ad6 |

実CAD45件は既存CAD経路の回帰であり、ASCIIをANSYSへImport/Meshした検証ではない。

追加の読取り検証では、修正前exporterと主翼のみ16出力の生バイト列・ファイル順が完全一致した（`main-only-raw-byte-check.txt`）。Hub/Tipの2断面＋gapでは両翼とも物理Tip番号2・Shroud延長3を確認した（`probe_two_spans.py`と検証用`two-span-example`）。曲がった既定壁面は、コピー上の所属ラベルだけを解除して全壁面の検証用範囲とし、gap 0.5/1 mmで両翼の物理Tip/延長断面を整形できた（`curved-default-probe.json`）。このコピー上の範囲変更を原本/既定へ反映していない。

製品変更は`fileio/turbogrid_export.py`（2翼セット・各延長/所属/整形検査）、`fileio/export_readiness.py`（対応状況）、`gui/main_window.py`（翼区切りを除いた正しいTip番号と案内）。数値形状generator、設計値、保存schemaは変更しない。新規試験2ファイル・主翼のみの新fixture、旧拒否を扱った関連試験4ファイル、機能一覧/操作資料/監査/ロードマップを更新した。
