# LE/TEの単一接線円弧（Tangent arc / G1）

## 現行仕様（2026-10-18）

利用者の指定により、既存の **Circular / Ellipticalも常にPS/SSへ接線接続**する。
右側LE/TEのTypeはCircular (G1)、Elliptical (G1)と表示する。保存値`circular`、`elliptical`と楕円比は変更しない。
既存の`Tangent arc (G1)` / `tangent_circular`は互換用の円弧選択肢として同じ計算を使う。
旧JSONを開いても切替操作は不要で、既存の円/楕円が新しい接線形状になる。
旧半円/半楕円の出力座標の完全再現は今回の明示的な仕様変更により終了する。
原本JSON・同梱既定JSON・歴史数値fixtureは書き換えない。

円は必ず単一円弧、楕円は指定軸比を持つ単一楕円弧。PS/SS上の端部近傍で接点を移動して両側に接する。
LE/TEを別々に指定でき、Impellerの全Span・Splitter、Diffuser/RCでも共通の生成経路を使う。
元の角度/厚さ/camber/Stacking/Rake入力、子午面LE/TE基準は保持する。
PS/SSを局所的に切り詰め、残る区間を同じmaster点数で再標本化するため、側面の標本位置も変わる。
不成立は明示エラーで、半円・biarcへの自動退避や公差緩和はしない。
Cutoffは従来の直線/一定径カットを保持し、接線連続を要求しない。

## 一般的な構築との対応

旧実装はcamber方向を半円の接線としたため、厚さ勾配のあるPS/SSには正接しなかった。
[OCCT公式の2曲線への接円構築](https://occt3d.com/dev/doc/refman/html/class_geom2d_gcc___circ2d2_tan_rad.html)は
曲線への接線条件から円と接点を求める一般的な構築を説明する。
[CFturbo公式の端部設計](https://manual.cfturbo.com/en/le.html)でも、側面上の接点とその勾配を使って
滑らかな端部を設計する。CFturboのBezier方式を移植したものではない。
[Edge positionの公式説明](https://manual.cfturbo.com/en/edge_position.html)では側面と端部の遷移位置を扱う。

今回の円は指定Rの根元filletではなく、端部厚さと側面の接線条件からRを求める。
端点・接線をすべて固定すると一般に単一円では解けないため、利用者の指定どおり接点の移動を許す。
PS/SSの入力分布を変えて無理に円へ合わせたり、公差を緩めて成立扱いにしたりしない。

## 数値方式と探索範囲

`geometry/tangent_arcs.py`はQt/OCP/保存形式に依存しない。
元側面の補間曲線をP(u),Q(v)とし、Pの内向き単位法線をnとする。
一方の接点Pを候補位置に固定すると中心はC=P+r n。
もう一方の側面上のQについて以下を満たすrと接点を探す：

`r = |Q−P|² / (2 n·(Q−P))`

`(Q−C) · Q' = 0`

半径を翼厚で正規化した残差について、49点の標本で符号変化を探しBrent法で解く。
これは距離と接線の拘束を解くもので、CADの公差変更ではない。
まずPS/SSそれぞれの旧端点を固定して探索し、必要な場合だけ固定側も少し動かす。
固定側の試行位置は0/.002/.005/.01/.02/.04/.08/.12。
両側ともLE側の先頭15%またはTE側の末尾15%に制限し、外挿しない。
割合は元側面標本の正規化パラメータであり、任意曲面の厳密な物理弧長割合ではない。

各段階で得た有効候補から接点パラメータ移動量の和が小さいものを選ぶ。
有限の局所探索であり、全円の存在判定や大域的最小化の証明ではない。
正の半径（旧接点間幅の10倍以下）、両端の向き付き接線、外側へ張り出す円弧、
一周/反転しないことを検査する。見つからなければ明示的にValueErrorを返す。
半円や2円弧への自動退避、翼面のwelding、入力値の自動変更は行わない。

厚さ0の端部は従来どおり一点へ縮退し、有限Rや接線を保証しない。
接続はG1（方向連続）であり、PS/SSと円弧のG2（曲率連続）は保証しない。
対称な直線側面y=±(b+kx)のLEはR=b sqrt(1+k²)、円弧角pi−2 atan(k)となる。

## 楕円の接線拘束

`fit_elliptical_cap`は端部camberの流れ方向を軸e、指定比をqとし、
`T = I + (1/q - 1) e e^T`でPS/SSとその微分を変換する。
変換空間で同じ接円拘束を解き、`T^-1 = I + (q - 1) e e^T`で点と接線を戻す。
非特異な線形変換が接点と接線方向を保つことを使う。軸e方向の半軸/直交方向の半軸がqとなり、q=1で円と一致する。
[OCCTの公式パラメータ化資料](https://www.occt3d.com/dev/doc/refman/html/_convert___parameterisation_type_8hxx.html)も円と楕円を平面内のアフィン変換で対応づけている。
本実装の具体的な接点探索はそのAPIの移植ではなく、この変換と既存の接円ソルバを組み合わせたもの。
q<1も既存設定として保持し、0/負/非有限値は拒否する。局所15%の探索に解がなければエラーとなる。

## 2D/3Dと出力

2Dは実XY側面の3次補間曲線から接点と接線を評価する。
3Dは元側面の(m,theta)補間曲線と既存壁面の写像を共有する。
各端部の局所座標は`y=rotation_sign*(theta_side−theta_camber_edge)*r_side`。
その微分には厚さ勾配・半径変化を含め、接点探索と切詰め後の出力に同じ評価関数を使う。
残ったPS/SSの`m_blade_norm`は元の流れ方向座標を保持する。

円/楕円弧であるのはXYまたはこの局所(m,y)内。曲がった壁面へ写像したXYZ曲線は一般に真円/楕円ではない。
標本と壁面の離散写像には誤差があり、任意の粗い分解能で厳密なXYZ G1を保証しない。
CutoffのTEは従来の一定径カットを保持する。

表示・ASCII/XYZ出力・CAD snapshotは同じ生成済みmasterを使う。
CADの既存接線拘束・適応近似・0.01 mm公差・失敗時保護を維持する。
出力点数はmaster形状を変えない。出力点を直線で結ぶ表示の角度は分解能に依存する。
TurboGridの輪郭順・単位・回転軸・中間indexのLE/TEマーカー規約は維持する。
非対称な接点配置でマーカーが厳密な幾何学的先端になることは保証しない。
Splitter ASCIIは[スプリッター仕様](TURBOGRID_SPLITTER.md)で対応。静翼CAD・派生cut・clearance CADの未対応ガードは維持する。

## 常時接線接続版の検証

新規`tests/test_rounded_joins.py`の43件は、対称wedgeの解析楕円軸・両側接線、非対称接点移動、反転/回転、軸比1と円の一致、不正比、既定JSONの全翼列/主翼/SplitterとCW/CCW、2D実側面、保存/読込、出力失敗時保護を確認した。
`tests/test_rounded_joins_gui.py`の3件は、通常の円での起動、楕円への変更/軸比編集、Undo/Redo、全翼列の2D表示と3D master一致、保存/読込をoffscreenで確認した。
実CAD楕円の閉solid/STEP試験は`tests/cad/test_rounded_ellipse.py`で実行する。

既存の歴史試験は、今回意図的に変更する端部と維持する入力/基準を区別するために契約を更新する。旧NPZ/JSON/hash値を新結果で置換しない。

- `test_project_flow_path_migration.py`: camberは旧公差（3e-6または1e-12 mm）のまま比較。PS/SSは接点移動で標本位置が変わるため、凍結した旧側面の3次補間曲線上に残ることと、接点が端部15%以内であることを検査。新しい円/楕円の接線拘束は新規の解析/生成試験で検査する。旧capとの座標一致は要求しない。
- `test_stator_turbogrid_export.py`: 壁面/BladeGen設定の旧ASCII hashは完全一致を維持。profileは新形状を指定桁で丸めた座標と完全一致、単位/軸/LE・TEマーカーも照合する。旧profile hashは資料として保持し、新結果に置き換えない。
- `test_csv_export.py`: PS/SSのm_normを接点後も無理に0–1へ戻さず、元の分布座標がそのまま出ることを確認。segment_fractionの0–1と出力点数は維持する。

旧側面の補間比較の実測最大XYZ差は旧v03で3.83e-8 mm、normal-cut旧版で2.50e-8 mm。補間を伴う側面比較には歴史試験の幾何比較尺度3e-6 mmを用い、camberの厳密な1e-12 mm比較は緩めていない。CAD公差も変更していない。

### 既定JSONの実XYZ接合方向差

原本/同梱既定を変更せず、メモリ上で両端を円または軸比2の楕円に設定して計測した。Cutoffの接線を保証する表ではない。master曲線の3次補間の端点微分で評価し、全Span面や最終CADの連続性証明とは区別する。

| 翼列/翼 | 円の最大角 [deg] | 軸比2楕円の最大角 [deg] |
|---|---:|---:|
| Impeller / Main | 0.00315594 | 0.00279555 |
| Impeller / Splitter | 0.00707895 | 0.00090688 |
| Diffuser | 0.00000475 | 0.00000226 |
| RC | 0.00000372 | 0.00000191 |

根拠は`artifacts/quality-rounded-joins/default-probe.json`。同フォルダの`rc-circular.png`、`rc-elliptical.png`はRC TE拡大のoffscreen画像。Meiryoを検証プロセスだけに登録し、製品のフォント設定は変更しない。

### 全回帰と入力保護（2026-10-18）

最終有効結果は**1,533一意件成功**（通常1,488・実CAD45）。既存1,486 IDを維持し、新規47件（解析/生成43・GUI3・実CAD1）を追加した。failure/error/skip/漏れ/重複は0。アプリの`.venv`と`tools/run_tests.py`で通常6群と実CAD1群を実行した。

初回バッチでは旧CSV座標端点1件と旧ASCII profile hash3件の仕様差を検出した。実装は固定したまま、該当する2テストファイルの契約を更新し、その全30件を再実行した。最終ID照合は初回の該当30結果を再試験30結果で置き換えて行った。したがって初回バッチをそのまま全成功とは扱わない。移行試験の2件はバッチ前に上記契約へ変更して成功済み。

初回固定300入力のうち298は不変、差は再試験した`test_csv_export.py`と`test_stator_turbogrid_export.py`だけ。アプリ実装は初回固定後から不変。最終300入力のhashと、追跡済み参照fixture5ファイルのhashを記録した。NPZはHEADとバイト一致、テキストfixtureはGitの改行差を除いて一致し、値を置換していない。変更Python10ファイルの限定Ruffと`git diff --check`も成功。

ローカル証跡は`artifacts/quality-rounded-joins/final-test-coverage.json`、`initial-batch-coverage.json`、初回/最終source hashes、fixture hashes、収集IDと各群log。初回バッチのobsolete assertion4件を履歴に残し、採用したIDと再試験結果を明示する。

| 採用元run ID | 採用件数 | 注記 |
|---|---:|---|
| 20261018T134806Z-21190843 | 114 | CSV試験2件を再試験へ置換 |
| 20261018T134806Z-3e09f5a6 | 147 | 通常 |
| 20261018T134806Z-2d55795b | 125 | 通常 |
| 20261018T134806Z-5daa2b0b | 183 | stator出力試験28件を再試験へ置換 |
| 20261018T134806Z-110fcee7 | 153 | 通常 |
| 20261018T134806Z-a6b232b1 | 736 | 新規解析/GUIを含む |
| 20261018T134806Z-2d345596 | 45 | 実CAD・新規楕円/STEPを含む |
| 20261018T135535Z-35f37b8c | 30 | 契約更新後の2ファイル全件 |

検証開始時のユーザー`blade_v03.json`はSHA256 `60ba6c13a1b132b914f70657131298c2c01c6fbbab8ef2dfe8e72ebd681dd2e1`で、同梱既定（`aa724c...`）とは別内容だった。両方を個別にhash照合し、そのまま保持した。現在のユーザー原本も読取り専用で生成し、Impeller（Main/Splitter）の丸め接続最大0.007079°、Diffuser約0.00000475°、RC約0.00000391°を確認した。根拠は`user-project-probe.json`。

## 初期の単一円弧選択肢導入時の検証（過去版）

新規テストは`tests/test_tangent_arcs.py`、`tests/test_tangent_arcs_gui.py`、`tests/cad/test_tangent_arcs.py`。
対称wedgeの解析R/角度、非対称接点の移動と単一半径、両端の接線、回転/反転/尺度、
局所探索不成立、尖端、元の分布不変、元側面上の切詰め、CW/CCW・mapping、主翼/Splitter/RC、
clearance・Cutoff、JSON/ASCII一致・出力密度独立、出力失敗注入による既存ファイル保護を確認する。
GUIは選択・共通Span・静翼との独立性・Undo/Redo・保存/読込をoffscreenで検証する。
画像`artifacts/quality-circular-caps/offscreen-tangent.png`で1480×920の種類欄と配置も確認した。
画像取得プロセスのみMeiryoを登録し、製品のフォント/テーマ設定は変更しない。native操作の検証ではない。
既存の種類別テストにも新enumが加わるが、既存試験コード・fixtureは変更しない。

単一円弧版の関連49件成功、限定Ruff成功、実CAD1件で単一閉有効solidとSTEP再読込を確認。
**全1,451一意件成功**（通常1,407・実CAD44）。既存1,381 IDをすべて維持し、
新規70 ID（新ファイル36件と既存種類別試験の新enum34件）を追加した。
failure/error/skip/実行漏れ/重複/想定外IDは0。
開始時に固定した294入力は実行後もhash不変で、原本/同梱既定JSONも一致した。
既存試験のコードと数値fixtureは変更していない。限定Ruffも成功。

根拠は`artifacts/quality-circular-caps/final-test-coverage.json`、`source-hashes.json`、
`input-change-audit.json`、`collected-tests.txt`と各群のraw log/JUnit。
通常6群と実CAD1群の全IDを収集一覧と照合した。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 441.744 | 20261018T095135Z-ab375d07 |
| 通常1 | 147 | 397.131 | 20261018T095135Z-061a15d1 |
| 通常2 | 125 | 455.887 | 20261018T095135Z-b2449207 |
| 通常3 | 211 | 330.043 | 20261018T095135Z-18d5e3cf |
| 通常4 | 153 | 428.852 | 20261018T095135Z-87c33c7f |
| 通常5 | 655 | 561.798 | 20261018T095135Z-e282f2c7 |
| 実CAD | 44 | 871.918 | 20261018T095136Z-fb1374a1 |

実CADには新しい単一接線円弧の閉solid/STEP試験1件を含む。根元filletやANSYSの実機確認へ置き換えない。

利用者の方針確定前に開始したbiarc版の全回帰は中断した。
`artifacts/quality-tangent-arcs/INTERRUPTED.json`に記録し、最終検証には使用しない。
単一円弧版の最終証拠は`artifacts/quality-circular-caps/`へ分離する。
実装のimport整理時に一度インデントエラーをRuff/collectionで検出し、修正後に関連49件を再実行した。

### 現既定JSONの測定（単一円弧）

原本/同梱既定SHA256：`aa724c8253463289caec919960d7d486d698765cee35202c13e4efd17a603dd6`。
原本を書き換えず、非Cutoff端部だけをメモリ上で切り替えた。
実XYZ masterの3次補間曲線の接合点で方向差の最大を計測した。

| 翼列/翼 | 旧端部の最大角 [deg] | 単一接線円弧 [deg] | 最大接点変位 [mm] |
|---|---:|---:|---:|
| Impeller / Main | 3.54241748 | 0.00315551 | 0.00014531 |
| Impeller / Splitter | 3.09270532 | 0.00707887 | 0.00132798 |
| Diffuser / Main | 3.45330369 | 0.00000475 | 0.00040528 |
| RC / Main | 10.19430014 | 0.00000372 | 0.00878744 |

接点変位は旧端点からのXYZ直線距離。全組でcamber/β/厚さ配列は不変で、各端部が局所座標内の
単一円であることも確認した。全Span面や最終CADの連続性証明ではない。
根拠は`artifacts/quality-circular-caps/default-probe.json`。

## 未確認

実ディスプレイ/高DPI操作、ANSYS Import/Mesh、全Span面のG1/G2・全面干渉、
実既定の新端部での根元fillet/最終CAD精度保証は未完了。実CAD試験は独立fixtureによる。
