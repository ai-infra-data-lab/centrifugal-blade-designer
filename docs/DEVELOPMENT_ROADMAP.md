# 品質改善ロードマップ

2026-10-17。対象`6b8d3be`の実装監査に基づく計画。
[現行機能](CURRENT_FUNCTION_AUDIT.md)と[品質指摘](GEOMETRY_QUALITY_REVIEW.md)を根拠にする。
本書は一括実装指示ではなく、段階ごとの変更範囲・依存・完成条件を定める。今回の変更は監査資料のみ。

根元フィレットの受入れ条件は、その後の利用者指示により**対象形状で成立する半径で実フィレットを生成できること**とする。R8は必須ではない。R8未満の明示的な試行を認め、成功した半径でBREP・結合・STEP再読込み・半径測定を確認する。試行値を記録し、既定値やユーザー入力を黙って小さくしない。過去のR8失敗記録と独立fixture R8試験は履歴・回帰として保持する。

実装進捗: **Stage 1A完了**（全832一意件成功、既存出力参照不変）。**Stage 1B完了**（全860一意件成功、保持バックアップ・中断復旧、既存16出力bytes不変）。**Stage 1C完了**（全872一意件成功。入力診断とCAD／ANSYS未実施を区別）。**Stage 2A完了**（実断面指標・XYZ CSV・正本識別。全906一意件成功、原本・既定・数値fixture不変）。Stage 2B（共通入力／Load・Save検証契約の分離）以降は未完了。監査時の不具合記録と現在の対応状況を区別する。[変更・検証記録](EXPORT_QUALITY_IMPROVEMENTS.md)。

## 優先順位

1. **既存出力の安全性と出力可否の明示**: E01の丸め後検査、E02のcase一括公開、D01の非破壊Readiness診断。
2. **同じ形状を見て評価すること**: G01の表示／指標／CSV／最適化正本の区別と統一。旧形式と数値参照は維持する。
3. **3D設計の成立性**: G02/G05のSpan面・周期翼・Splitter干渉、G03/G04/G06/G07の定義と検査。
4. **実モデルCADを成立させて精度を示すこと**: 対象形状に合わせて小さいRも試し、成立した指定Rで検証する。半径を小さくしても失敗する場合はC01の根元位相を診断・修復する。C02のSTEP面偏差、C03の構造／流体共通境界も確認する。公差緩和や指定と異なる半径で成功を装わない。
5. **GUIの応答性・保守性と実機連携**: U01/U02のsnapshot・worker・履歴契約、ANSYS Import/Meshの実環境検証。
6. **検証後の機能拡張**: 派生カット／Splitter／静翼CAD等の未対応出力、面積・スロート精度向上、実解析との連携。品質基盤ができる前に性能最適化へ進めない。

現時点で実用上の障害となるのは、現既定ImpellerからのProfile PointsがSplitterと所属で拒否されること、現既定形状で成立する根元フィレットが未確認であること、旧指標と実3Dが異なること。表示成立・出力成立・設計性能成立を別の状態として扱う。

## Stageと依存関係

| Stage | 対応指摘・実装単位 | 依存 | 完成条件・必要証拠 |
|---|---|---|---|
| 0: 基準固定 | 現状のcommit、source hash、試験ID、監査資料を固定 | なし | 今回実施。既存768一意試験の記録照合、追加81件成功、再現プローブ、現既定R8 FAILを保存。外部ANSYSはNOT_TESTED |
| 1A: 出力前検査 | E01。通常Impellerにも丸め後の重複・閉輪郭・LE/TE・断面対応検査 | 0 | 有効桁1〜15、軸X/Y/Z、単位MM/CM/M、全端部、gap有無で成功／拒否を確認。低精度無効例で既存case不変。既存通常精度のbytes fixture不変 |
| 1B: 安全な公開 | E02。生成・検証・公開を分離し世代別case／manifestで一括参照 | 0。1Aの検証器を利用 | 各replace、権限不足、ディスクエラー、Windowsロック、取消／プロセス異常の故障注入。旧一式か検証済み新一式のみ有効。既存成功report、STEP、curve、manifestのhashを保護。クラッシュ復旧手順も検証 |
| 1C: Readiness | D01、C01。選択row、所属範囲、Splitter、trim、gap、CAD backend／ディスク／根元の可否を分離 | 0 | 現既定でProfile PointsのSplitter制限と所属エラー、CADの未成立を別理由として表示。診断だけで設計値・原本・出力を変更しない。Blade Only PASSをR8 PASSにしない |
| 2: 形状正本と指標 | G01。row ID・snapshot・geometry種別を付け、実3D指標を新経路にする | 1C | RC R130→90と旧100→160を混同しない。中央2D/3D、Passage、CSV、新指標が同じmasterに対応。旧CSVは明示legacyで互換保持。失敗した旧2Dが無関係な3D更新を遮断しない |
| 2B: 検証契約の分離 | G01。共通validate_parameters、3D generator、JSON全体チェックに残る旧2D／未選択Impeller依存を分離 | 2Aの正本識別・互換fixture | 無関係な旧半径・未選択行の値を仮の既定値へ置換しない。各対象が使う値を検査し、保存時の設計成立性ポリシーと旧JSONの受入れを明示。正当な既存拒否・精度を維持する |
| 3A: Surface契約 | G05。streamwise／Span対応と共通surface評価器 | 2 | 正本が線形／高次のどちらか明示。Hub/Tip・中間Span、強ねじれ、Rake、gap、Splitter、trimの密な対応点でpreview/CAD/trimを比較。密度収束と誤差予算を保存 |
| 3B: 3D品質ゲート | G02/G07。Span面自己交差・隣接周期翼・主翼/Splitter干渉 | 3A。高速検査は2後に先行可能 | 高翼数1000、極端pitch_fraction、強Spanねじれで意図的FAIL。断面上だけ正常な不成立面を独立fixtureで検出。正常旧fixture不変。出力前に全経路で実行し、未検査は未検査と返す |
| 3C: 定義と局所精度 | G03/G04/G06。端部接線、実肉厚、クリアランス | 3A。定義の説明は0後から可能 | 厚み勾配ありでG0/G1/曲率を別測定。既存定義を保持した実最小肉厚・gap測定。Line/Arc解析解、曲率限界とadaptive収束を照合。形状方式の変更には互換選択が必要 |
| 4A: 根元フィレット試行・位相 | C01。小さい指定Rで試行し、必要ならBoolean前後の履歴・隣接・cap接続を診断・局所修復 | 1C。3Aの境界評価を利用、他の全Stage完了待ちは不要 | 現既定＋仮ディスクを固定fixture化。試行半径と結果を保存。失敗時は根元各edgeのdistinct隣接face数・role・ループ・内部面を記録。主翼＋HubおよびSplitter＋Hubを1solid化し、対象形状で成立する指定Rを確認する。成立しなければ位相上の問題と半径の幾何限界を区別する |
| 4B: 実モデルCAD完了 | C01/C03。成立する指定R、周期／全周、主翼/Splitterの成立性 | 4A、3B | 有効BREP、閉鎖、正体積、単一連結実体、周期／全周干渉なし、生成fillet roleとSTEP前後の指定半径測定。R8成功は必須ではない。実機寸法がない仮ディスクはPROVISIONALのまま。Blade Onlyやフィレットなしの成功を代用しない |
| 5: CAD/STEP精度 | C02/C03。双方向面距離・法線・境界role、再読込み検査強化 | 3A。実モデル確認は4B後、独立fixtureは先行可 | master→CAD→STEP→再読込みを別予算で測定。同bbox/体積だが局所面変形の独立negative fixtureで拒否。要求公差以下、法線反転なし、共通構造／流体境界一致。現行の過大edge/bbox/volume拒否を維持 |
| 6A: GUI応答性 | U01。同期箇所の計測、immutable snapshot worker、取消・世代統一 | 2。計測は0後から可能 | native WindowsでUI heartbeat・計算時間・メモリを記録。編集中のstale結果不採用、取消後に部分出力なし、閉じる操作で終了。遅いCAD本体だけでなくprepare_job／全行生成／Flow Areaも対象 |
| 6B: 履歴と保守性 | U02。DesignSnapshot/SelectionState/ViewState、責務分割 | 2、6Aの境界 | 設計全項目に入力確定・Undo・Redo・JSON・別画面同期の契約試験。通常更新でCamera保持、意図したFitのみ変更。GUI構築を全面再生成せず、再生成service、履歴、出力controllerを順に抽出 |
| 7: ANSYS実機検証 | 対応済みProfile Points／Mechanical／流体CADの受入れ | 1、5。Profile Pointsは必要部分の完成後に先行可 | 下記受入れ表のImport/Mesh記録、対象ANSYSリリース・ライセンス・ファイルhash・設定・画像・メッシュ品質を保存。変換待ち／Import失敗／Mesh失敗を分ける |
| 8: 未対応出力拡張 | Splitter Profile Points、静翼CAD、gap付きTurboGrid CAD、派生カット出力を各1機能ずつ | 3、5、7の既存経路確認 | 仕様を先に固定し、表示・解析・出力の同一正本と、LE/TE・gap・周期・filletの意味を検証。各機能で拒否ガードを外すのは新しい回帰と実機確認条件が揃ってから |
| 9: 設計評価・最適化 | G08。面積／スロート収束、実3D制約、外部解析連携 | 2、3、5。実解析最適化は7/8と境界条件仕様後 | 幾何近似とCFD値を分離。円筒／円錐解析解、曲線壁の上限／下限または収束を示す。3Dスロート面・CAD閉塞を別機能として実装。流量／圧力比／効率は実solver・境界条件・モデル検証がある場合だけ評価 |

これは作業依存の整理であり、同時に全部変更する計画ではない。特に1A、1B、2、4Aは別commitとする。

## 主な変更対象の見通し

| 作業 | 想定ファイル | 保護する互換性 |
|---|---|---|
| 1A/1B | `fileio/turbogrid_export.py`, `mechanical_step_export.py`, `cad/client.py`、新しい公開／検証helperとテスト | 現行通常精度出力、path制約、無効形状ガード、既存成功report |
| 1C/2 | `geometry/designer.py`, `models`の結果型、`gui/main_window.py`, `metrics_widget.py`, `fileio/csv_export.py`、関連仕様・GUI試験 | legacy CSV、旧JSON、行別snapshot、既存数値fixture |
| 3 | `geometry/blade_section.py`, `span.py`, `splitter.py`, `tip_clearance.py`, `impeller_trim.py`、新surface/quality層、`cad/occt_backend.py` | β積分・回転符号・元制御点・端部・Hub TE円筒定義 |
| 4/5 | `cad/occt_backend.py`, `cad_validation.py`, `worker.py`, `tests/cad/` | 指定R、公差、実カーネル検査、出力失敗保護。参照数値の都合よい置換は禁止 |
| 6 | `gui/main_window.py`, `cad_export_worker.py`, `passage_widget.py`, `undo_commands.py`, `preview_3d.py` | メニュー入口、対象別Editor、Camera、保留入力、Undo、別画面 |
| 7/8/9 | 実機手順書、対象Exporter、geometry品質層、`optimization/` | 既存Impeller Profile Points、ANSYS未検証表示、既存出力形式 |

上記の省略パスは`blade_designer/`配下。実装着手時に該当コードと試験を再読込し、変更ファイルはその機能に必要な最小集合へ絞る。

## ANSYS受入れ表（現在はすべてNOT_TESTED）

| ケース | 必須確認 | PASSへ進めない条件 |
|---|---|---|
| 主翼のみ | X/Y/Z軸・単位・翼枚数、Hub/Shroud接続、LE/TE順、閉輪郭、周期メッシュ | Python出力のみ／ImportのみでMesh未実行 |
| Clearanceあり | 外側延長と実Tip Profile Number、指定gap、壁との接続、隙間メッシュ品質 | 延長Tipを物理Tipと誤認、gap未復元 |
| Diffuser／RC | 所属壁面、Hub/Tip対応、外向き／内向き流れのLE/TE、周期境界 | 旧2D形状からの推定だけ、RCを単に半径順へ並べ替える |
| Splitter | 対応形式・枚数・主翼との位置・両側通路、端部認識・局所メッシュ | 未対応Profile Pointsの拒否解除のみ |
| 派生カット | 指定D、削減率基準、切断TE、gap維持、出力境界と表示一致 | 元形状を代替出力、制御点の無断変更 |
| CAD＋Fillet | 対応形式への変換、境界role、根元R、流体／構造境界、mesh品質 | CONVERSION_REQUIREDのSTEP生成のみ |
| Mechanical | solid数・単位・軸・根元接続・指定フィレットR、周期／全周Mesh | Blade Onlyや仮ディスク単体をフィレット付きassembly扱い |

## 各ワーク単位の完了規約

1. 既存status・差分と該当仕様・試験を確認。変更対象は本アプリのみ。原本JSON・既存出力・家計簿を触らない。
2. 不具合再現と解析解／不変条件を先に定義。歴史的fixtureと解析解を区別し、期待値を実装都合で更新しない。
3. 最小変更と意味のある回帰を追加。geometry・GUI・serialization変更時は関連試験と`.venv\Scripts\python.exe tools/run_tests.py`による全回帰を実施し、失敗と環境エラーを分ける。
4. 数値・ファイル・GUI offscreen・native・ANSYSの確認を別記録する。未実行をPASSにしない。FEATURESと該当仕様へ制限・検証結果を反映する。
5. 差分と出力保護を確認後、明示した本アプリ内のファイルだけstageする。`git add .`／Stage Allは禁止。親リポジトリ全体のstage一覧を検査する。
6. **このチャットの利用者指示により、今後の機能修正は検証後にcommitまで行う。** 1機能／修正を1ワーク単位とし、実装・試験・資料を対応させる。未解決や未検証はcommitの報告にも残す。失敗を隠して完成扱いしない。
7. **push、リモート変更、公開範囲変更は別の明示指示があるときだけ。** 今回はpushしない。commit ID、対象数、残差分、未確認項目を報告する。

最初の実装候補はStage 1A。その後1B・1C、Stage 2と4Aへ進む。今回の監査ではこの順序を提示し、いずれの設計アルゴリズム変更も先行実装していない。
