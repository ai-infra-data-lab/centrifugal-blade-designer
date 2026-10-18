# LE/TEの単一接線円弧（Tangent arc / G1）

## 操作と互換性

右側のLE/TE設定のTypeで **Tangent arc (G1)** を選ぶ。
Impellerでは全SpanとSplitterの共通端部設定、Diffuser/RCではその翼列の独立設定となる。
LE/TEを別々に選べる。Undo/Redo・保存/読込に対応する。

新方式は**必ず単一円弧**。端部近傍のPS/SS上で接点を移動して両側に接する円を求める。
2円弧へ切り替えない。円弧角は厚さの増減や実側面の方向に従い、180度に固定しない。
元の角度・厚さ分布、camber、LE/TEの子午面基準位置、Stacking/Rakeの入力は変えない。
PS/SSの生成済み補間曲線の端を局所的に切り詰め、残る部分を同じmaster点数で再標本化する。
接点は旧端点から移動するため、端部の形状と出力座標は意図的に変わる。

**Circular (legacy)** は旧半円、Ellipse/Cutoffも従来形状のまま。
既存JSONの`circular`を自動置換しない。New/同梱既定の設計値も変えない。
既定形状へ適用する場合も利用者が新しい種類を選ぶ。
保存する新しい値は`"tangent_circular"`。旧JSONは従来どおり読み込めるが、
新しい種類を保存したJSONはそれを実装した版で開く必要がある。
原本`blade_v03.json`、同梱JSON、旧数値fixtureは書き換えない。

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

## 2D/3Dと出力

2Dは実XY側面の3次補間曲線から接点と接線を評価する。
3Dは元側面の(m,theta)補間曲線と既存壁面の写像を共有する。
各端部の局所座標は`y=rotation_sign*(theta_side−theta_camber_edge)*r_side`。
その微分には厚さ勾配・半径変化を含め、接点探索と切詰め後の出力に同じ評価関数を使う。
残ったPS/SSの`m_blade_norm`は元の流れ方向座標を保持する。

円弧であるのはXYまたはこの局所(m,y)内。曲がった壁面へ写像したXYZ曲線は一般に真円ではない。
標本と壁面の離散写像には誤差があり、任意の粗い分解能で厳密なXYZ G1を保証しない。
CutoffのTEは従来の一定径カットを保持する。

表示・ASCII/XYZ出力・CAD snapshotは同じ生成済みmasterを使う。
CADの既存接線拘束・適応近似・0.01 mm公差・失敗時保護を維持する。
出力点数はmaster形状を変えない。出力点を直線で結ぶ表示の角度は分解能に依存する。
TurboGridの輪郭順・単位・回転軸・中間indexのLE/TEマーカー規約は維持する。
非対称な接点配置でマーカーが厳密な幾何学的先端になることは保証しない。
Splitter ASCII・静翼CAD・派生cut・clearance CAD等の従来の未対応ガードは解除しない。

## 検証

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
