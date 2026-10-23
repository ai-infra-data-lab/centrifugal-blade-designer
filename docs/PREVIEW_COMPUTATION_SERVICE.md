# 画面用数値準備の分離

Stage 6Bの小さな責務分離として、選択翼列の3D/参考Impeller/legacy 2D/Flow Areaと、
子午面選択時の全翼列生成を`geometry/preview_computation.py`へ移す。
Qt、OCP、保存/出力形式に依存しない同期サービスであり、一般再計算の非同期化はまだ行わない。

## 維持する契約

- `BladeDesigner`、`calculate_flow_area`、`preview_wall_chunks`を既存の順序・引数・標本数で使用する。
  生成式、表示XYZ/円筒カット/CAD splineの方式、元の角度/厚さ/設計JSONを変更しない。
- 入力を独立コピーし、結果は呼出し側が所有する。これは内部結果型であり永続形式ではない。
- legacyの失敗、静翼選択時の参考Impellerの失敗、選択3D/面積の失敗を分ける。
  有効な静翼を参考計算の失敗で隠さず、選択失敗時には有効なlegacy結果と診断をcontrollerへ返す。
  想定する数値例外はValueError/ArithmeticErrorだけとし、プログラム例外を隠さない。
- MainWindowの同期API、注入したdesigner、Load/最適化が渡す既計算Impellerを維持する。
  GUI側が表示・履歴・current source・last valid・メニュー・Cameraを管理する。

選択3Dとlegacyの区別は[形状正本の契約](GEOMETRY_SOURCE_CONTRACT.md)、
Load/Saveの検証境界は[保存検証](ROW_PROJECT_VALIDATION.md)を維持する。
このサービスによって参考計算の結果を選択形状へ代入したり、保存前検証を弱めたりしない。

## 修正する不整合

従来の全翼列表示は、3D生成の直後に翼列を登録し、その後の所属解析壁面の生成に失敗すると
「row omitted」と表示しても翼列自体が残る順序だった。新サービスは壁面準備まで成功した
翼列だけを登録し、失敗した翼列とその壁面を一緒に省く。他の有効な翼列は残す。

選択形状とFlow Areaは数値準備が完了してからGUIへ適用する。面積準備が失敗した際に
`_wall_geometry`だけ新結果へ切り替わる中間状態を作らない。最終有効表示は保持するが、
現在の選択測定/current source/Passageは従来通り無効化し、有効と誤認させない。

## 検証範囲

新規のサービス比較試験は、保存済み既定のImpeller/Diffuser/内向きRCについて、既存生成器の
全dataclass/配列とFlow Area、全行の順序・翼枚数・解析壁面の厳密一致を確認する。
これは抽出前後の同等性検査であり、歴史的数値fixtureや独立解析解を置き換えない。
独立processでの実数値生成にQt/OCPが読み込まれないこと、入力コピー、既計算結果の再利用、
独立障害、想定外例外の伝播、翼列/壁面の一括省略、GUIのlast valid/Cameraを検査する。

関連42件、quick 63件、変更Pythonの限定Ruffが成功。最終コードの全回帰は
**2,375一意ID成功**（通常2,278・実CAD97、既存2,358保持・新規17）。
失敗/error/skip/漏れ/重複/想定外IDはいずれも0、固定375入力は不変、全runner終了コード0。
歴史的fixture・原本`blade_v03.json`・既定JSONを変更していない。
原本と既定JSONは独立のファイルであり、互いのbytes一致を要求する検査ではない。

集計は`artifacts/quality-preview-computation/final-test-coverage.json`、個別記録は以下。

- 通常1,142件: `artifacts/test-runs/20261023T042739Z-6e4c5ad2/`。
- 通常1,136件: `artifacts/test-runs/20261023T044126Z-e54aa7bb/`。
- 実CAD97件: `artifacts/test-runs/20261023T034732Z-6170fbfc/`。
- 関連42件: `artifacts/test-runs/20261023T034539Z-190cc0bf/`。
- quick 63件: `artifacts/test-runs/20261023T034323Z-66140396/`。

数値試験・Qt offscreen・実CADと下記native操作は別の確認であり、ANSYS検証へ読み替えない。

native Windows/Fusionの製品起動経路でも、子午面→Impeller→Diffuser→RC→子午面を確認した。
各Cameraを保持し、選択PSとcurrent source/Passageが同期、全3行が存在し、履歴追加0、
CAD jobなし、原本/既定JSON不変、close/destroy 0.047 s。
起動3.265 s、選択呼出し0.953–1.907 s、最大heartbeat gap 1.922 sで、通常再計算は依然同期。
これは実CAD回帰と並行した1回の観測であり、性能の改善量や他PCの応答保証ではない。
`artifacts/quality-preview-computation/native/result.json`と同フォルダの2画像を確認した。
全行の存在確認とCamera保持は、あらゆるCameraで全形状が収まることの保証ではない。

一般再計算workerの取消/最新入力のみ採用/close、およびANSYS Import/Meshは未検証。

## 次の段階

このサービスを境界に、通常編集・全行生成・Flow Areaの固定入力を所有processへ渡す。
1実行＋最新待機、入力世代/選択/未確定テキストの照合、取消/closeでのtree終了、同期APIとの
互換性を別ワーク単位で実装・測定する。CADの非同期化成功を一般再計算の成功とは扱わない。
