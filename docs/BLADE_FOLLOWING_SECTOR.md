# 翼追従のMechanical周期セクター

## 操作・対応範囲

Impellerの主翼・Splitter・根元フィレットを切らずに、1組を含む周期セクターを
Mechanical STEPへ出力する追加方式。従来の固定平面方式は既定のまま維持する。

![翼追従の周期境界設定](images/user-manual/following-sector-settings.png)

Windows実画面。境界設定を選んだ例であり、画面のR8で生成できたという意味ではない。

1. Impellerを選び、`CAD / Fillet`を開く。
2. `Mechanical Model Scope`を`periodic_sector`にする。
3. `周期境界 / Sector boundary`を`翼追従曲面 / Blade-following`にする。
4. `Hub Fillet`を有効、`Fillet Mode`を`true_cad`にし、根元Rを設定する。
5. ディスクを設定し、`Generate CAD`または`Export Mechanical`を実行する。
6. レポートの`checks.following_sector`、Mechanical artifact、STEP roundtripを確認する。

主翼3枚以上に対応。1ピッチは360°/主翼枚数で、Splitter数は分母へ加えない。
現対応は、全周フィレット生成時の翼別face識別を持つモデルである。
フィレット無しの旧全周経路には同じ識別がないため、翼追従の出力検査で拒否する。
固定平面方式のフィレット無し出力は従来どおり。
別Scopeを選択中は境界選択欄を無効にするが設定を保持する。
フィレット不成立時にRを自動縮小する処理は追加しない。

新方式はMechanical専用。`Export Both`と`Export TurboGrid`はジョブ作成前に拒否する。
Mechanicalだけ曲面、流体領域だけ平面という組合せを暗黙に出力しない。
従来方式のTurboGrid経路は変更しない。全周結合・全配置フィレット生成を維持するため、
計算時間の短縮は保証しない。

## 方式と出力ゲート

`geometry/sector_boundary.py`はQt/OCP/出力形式を参照しない数値提案。
主翼の対応PS/SS点から中心位相を取り、物理R/Z上で線形kernelのRBF補間を作る。
Hub/Tipの別々の0〜1座標を同じ位置と扱わない。同一R/Zに矛盾する位相がある場合は拒否する。
主翼とSplitterのLE/PS/TE/SSを含む位相幅から、1ピッチに収まるオフセットを選ぶ。
翼領域外へ位相を継続し、`cad/following_sector.py`で滑らかなB-spline工具面を作る。
反対面はZ軸回り1ピッチの回転コピー。数値提案の標本余裕を、CAD非干渉の証拠にはしない。

既存の全周結合→フィレット生成→検査を維持し、最後の切断だけを変更する。
切断はkernelの幾何コピー上で行い、コピーも別objectとして実CAD検査する。
通常のコピーはバイナリ表現の一致を保証しないため、別objectへ検査結果を使い回さない。
元モデルは処理前後のバイナリfingerprintで不変を要求する。
新方式の合格には、以下を全て要求する。

- 工具のBREP・自己交差・閉鎖・正体積・1solid・既存CAD公差。
- 両工具面と全配置の完成翼/フィレット面のkernel最短距離がCAD公差を超える。
- 主翼@0と有効なSplitter@0だけを保持し、作業用コピーの完成面・全フィレット面を同じtopologyで残す。
- 別配置のフィレット面を混入させず、切断後も1つの閉じた有効solidである。
- 周期面をBoolean履歴で分類する。平面法線や固定face番号で識別しない。
- Lowを1ピッチ回転し、外向き法線を反転したHighと双方向の面標本を比較する。
- 全周体積とN倍セクター体積を、既存STEP検査と同じ体積予算式で比較する。
- N個を回転・結合し、再構成体の実CAD妥当性・1solid・公差を確認する。
- 元全周との全face双方向の距離・法線標本を比較し、体積重複を同じ予算以内に収める。
- 既存のSTEP再読込み、全境界の双方向標本、フィレット半径標本のゲートを維持する。

再構成の合格は`PASS_SAMPLED_VOLUME_BUDGET`。面比較は有限標本であり、
`global_material_coverage=NOT_CONFIRMED`をレポートと警告に残す。
ほぼ一致する全周体同士のBoolean差分は数値的に不安定で非常に遅いため、出力ゲートには使わない。
これは既存公差の緩和ではなく、実CAD妥当性・体積・境界標本それぞれの検証範囲を明示したもの。
corner全域G1・全点半径・全面の材料一致・ANSYS周期mesh成功へ昇格しない。

## 保存・失敗時の保護

CAD設定に`sector_boundary`を追加。旧JSONは`fixed`として読み込み、保存時も省略する。
明示した`blade_following`だけを保存する。同梱既定値・ユーザーJSON・翼設計座標は変更しない。
Undo/Redoへは通常のCAD設定として含める。
CAD/通常preview/座標Studyのsnapshotも、既定の`fixed`を共通の非破壊処理で省略し、
追加前の候補hashを維持する。旧StudyやCADジョブの整合性ガードを緩める処理ではない。
正規化は設定dictと翼列の経路だけを処理し、大きな座標/三角形配列をコピーしない。

不正点/対応座標、隙間不足、翼/フィレット交差、部分切断、複数solid、周期面不一致、
再構成失敗をエラーにする。小実体の削除・架橋・翼の移動/縮小・公差緩和・平面への
無通知fallbackは行わない。既存の私有ジョブ・検証済みartifact公開機構で既存出力を保護する。

## 検証

数値：±π跨ぎ、主翼+Splitter、R/Z位相変化、入力不変、不正値/隙間不足の拒否、JSON往復、
TurboGridの事前拒否。GUI：選択欄の有効/無効、Undo/Redo、保存・再読込み。
Windowsプログラム操作で別翼列へ切替えて戻ったときの設定保持も確認する。
既定設定の旧snapshot文字列との一致、非既定設定がhashへ入ること、入力dict不変も検査する。

実kernel：1ピッチより大きく巻いた人工翼の全周モデルを曲面で切断し、元翼面保持、
1solid、周期面標本、全周再構成、STEP再読込みを検査。意図的な翼交差も拒否する。
体積は等しいが別配置の翼を径方向へ移動した非周期形状も、再構成境界の不一致で拒否する。
人工翼は実機性能検証ではない。

### 2026-10-26の完了結果

全2,661一意ID成功。通常2,563件、実CAD98件、既存2,647件を保持し新規14件。
失敗/error/skip/漏れ/重複0。通常回帰後の変更はCAD専用2ファイルとworkerの新方式の警告1行で、
実CAD全件を最終ソースで再実行した。各組の固定413入力を照合し、ユーザーJSON・同梱既定値・
既存数値fixtureは変更していない。変更13 Pythonの限定Ruffも成功。

通常の結果は`20261025T130542Z-b6a36f55`、`20261025T132917Z-3db7d1bf`、
実CADは`20261025T141453Z-1aaa3fc0`。一意IDの集計と組ごとのソース境界は
`artifacts/quality-following-sector/final-regression/final-test-coverage.json`へ保存した（ローカル検証資料）。

既定形状の主翼11枚＋Splitter11枚、仮ディスク、明示R0.1 mmで実CADを検証した。
今回の既存全周回帰も成功し、その32座標配列と保存済みの実CAD checkpointの元入力が完全一致することを確認した。
requestの差はScope・境界方式・snapshot hashのみ。
保存済み全周BREPのSHA-256とface識別を照合して読み戻し、現在の製品関数でコピーの実CAD検査から
切断・再構成・STEP再読込み・境界/半径検査を再実行した。コピーへ過去の検査結果を使い回していない。
これはcheckpoint再開検証であり、GUIから全周生成を含めて一括実行した証拠ではない。

| 項目 | 実測・結果 |
| --- | --- |
| 保持翼 | `main@0`、`splitter@0`のみ、完成面・フィレットを保持 |
| 元全周BREP | 処理前後のバイナリfingerprint不変 |
| 周期面と翼/フィレットの最短距離 | 両面とも約2.534 mm（指定CAD公差0.01 mm超） |
| 周期面の双方向距離標本 | 最大約8.0×10⁻¹⁵ mm |
| 全周体積と11倍sector体積の差 | 0.273 mm³（既存式による予算11.269 mm³以内） |
| 切断・STEP再読込み | ともに閉じた有効な1solid、自己交差・公差検査成功 |
| STEP双方向距離標本 | 最大約1.20×10⁻⁹ mm |
| rolling半径標本 | STEP前12面・後12面成功、corner全域の半径/G1保証は別問題 |
| 全周再構成 | 実CAD妥当性・体積・双方向境界標本成功、全面材料一致は`NOT_CONFIRMED` |

再開検証は約29分で、先行する全周生成時間を含まない。元入力、再開範囲、警告、各測定値は
`artifacts/quality-following-sector/default-resumed/result.json`に保持した。
初期のほぼ一致する全周Boolean差分の試行は途中中止として残し、成功件数へ含めない。

Windowsの別processで設定欄・翼列切替・Undo/Redo・保存/再読込みをプログラム操作し、元JSON不変を確認した。
GUIからの新方式の通し生成と時間上限内完了、人手/F5、ANSYS Import/Mesh・周期拘束・周期meshは未検証。
STEPのface名によるNamed Selection保持も保証しない。実機性能・強度の検証ではない。
