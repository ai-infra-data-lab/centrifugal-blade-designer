# 現行機能・出力の対応表

更新日：2026-10-26。対象は`centrifugal_blade_designer`のみ。
計算コードの基準はローカル`af2ddba`／GitHubアプリ専用履歴`660e20f`。
これは対応状況の整理であり、新しいリリースタグや実機認定ではない。

**現在の判断は本表を入口とし、過去の監査・段階別テスト件数は開発履歴として読む。**
旧READMEのv0.3、CAD仕様のv0.4、GitHubのv0.3.0タグは同じ意味の版番号ではない。
タグは変更しない。新しい出力経路の条件は各仕様書と検証記録で確認する。

## 判定と検証の区別

- **実装済み**：記載した条件で処理経路がある。任意入力での成立やANSYS成功を意味しない。
- **条件付き**：対応する構成・出力形式・形状成立条件に制限がある。
- **未対応**：実行経路がない、または書込み前に拒否する。
- **自動試験／実CAD／Windowsプログラム操作／人手／ANSYS**は別の検証軸。
  `PASS_SAMPLED`は有限標本の合格であり、全面の精度・非干渉の証明ではない。

## 設計・表示・評価

| 機能 | 現行対応 | 残る条件・対象外 | 根拠・試験例 |
| --- | --- | --- | --- |
| 子午面Hub/Shroud | 直線/円弧、G1接続、型変更、R/Z表示、所属翼列、LE/TE位置編集 | 翼列距離の整数区間表示と、内部の全壁fraction・翼LE–TE座標を区別する | [子午面座標](MERIDIONAL_COORDINATES.md)、[翼列距離](MERIDIONAL_ROW_COORDINATES.md)、`tests/test_meridional_gui.py` |
| Impeller | Hub/TipとSpan方向の形状生成、回転方向、2D/3D、全周表示 | 任意の強いねじれや高翼数で常に成立する保証はない | `geometry/geometry_3d.py`、`tests/test_blade_edge_span_interpolation.py` |
| Diffuser/RC | 所属Hub/Shroud上の2断面をSpan方向に結ぶ。RCは外径側LE→内径側TE | 静翼中間Spanの独立設計は対象外。旧radial 2D Metrics/CSVと実3D座標は別経路 | [RC表示](RETURN_CHANNEL_DISPLAY.md)、`tests/test_return_channel.py`、`tests/test_stator_turbogrid_export.py` |
| 角度・厚さ・Splitter | PCHIP、共有編集グラフ、主翼連動/専用Splitter分布、開始位置・周方向配置 | 1主翼ピッチにSplitter1枚。専用分布は表示LE–TE内で補間 | [共有グラフ](SHARED_GRAPHS.md)、[Splitter補間](SPLITTER_INTERPOLATION.md)、`tests/test_splitter_local_interpolation.py` |
| LE/TE・Rake | 円/楕円の接線接続、端部先端を指定位置へ配置、Cutoff、Impeller TE Rake目標とMapper | 独立LE Sweep/Rake目標・任意Stacking曲線は未対応。全域G1/G2保証ではない | [端部位置](EDGE_END_POSITION.md)、`tests/test_edge_end_position.py`、`tests/test_impeller_te_rake.py` |
| Tip Clearance/解析用Shroud | 図面ケーシングから翼Tipを生成し、翼Tipを固定した別の解析用Shroudも作成 | LE/TE mm指定の幾何学的隙間。熱/回転変形・漏れ流量は評価しない | [翼端隙間](TIP_CLEARANCE.md)、[解析用Shroud](ANALYSIS_SHROUD.md)、`tests/test_analysis_shroud.py` |
| Shroud/外径カット | 元分布を保持し、面積率/指定D/切削率で派生形状を作る。後流側の扱いと滑らかな接続を選択 | 面積率は幾何量であり流量率ではない。派生TurboGrid/CADは未対応 | [派生カット](IMPELLER_TRIM_SPEC.md)、`tests/test_impeller_trim.py` |
| 流路面積/スロート | Gross/Net、Main–Main、Main–Splitter、Splitter–Main | Splitterが全Spanにある区間だけ両通路面積を表示。展開幅・3D弦の下限推定・Hub–Tip積分近似を区別する。CAD fillet込みの厳密3DスロートやCFD性能ではない | [流路解析](PASSAGE_ANALYSIS.md)、`geometry/flow_area.py`、`geometry/throat.py`、`tests/test_passage.py` |
| 座標最適化 | β/厚さ/共有子午面の基準保持型パラメータ移行、複数翼列・変数連動、LHS、外部CSV、RBF提案、2目的Pareto | solver/mesh/結果抽出adapter・無人反復・3目的以上は未対応。3D面/CADを探索へ含めない | [座標最適化](COORDINATE_OPTIMIZATION.md)、`optimization/coordinate_parameters.py`、`optimization/surrogate_proposals.py`、`optimization/pareto.py`、`tests/test_multiobjective.py` |
| GUI・保護 | 対象別編集、履歴、Camera保持、通常再計算/CAD準備の非同期化、取消、古い結果の不採用 | 全操作の人手確認・任意負荷での応答保証ではない | [通常再計算](ASYNC_PREVIEW_COMPUTATION.md)、[CAD準備](CAD_ASYNC_PREPARATION.md)、`tests/test_cad_async_worker.py` |

省略したPythonソースは`blade_designer/`配下。各行の試験は代表例であり、全試験一覧ではない。
座標最適化のWindows確認は模擬外部評価によるもので、実CFDによる性能改善は未検証。
予測と外部実評価を分け、候補生成の成功を全3D非干渉や性能の保証へ読み替えない。
Splitter付きのMain–Mainスロートは参考値で、Main–Splitter／Splitter–Mainと区別する。

## 出力対応

| 出力 | Impeller/主翼 | Splitter | Diffuser/RC | 隙間・派生・filletの条件 | 外部実機 |
| --- | --- | --- | --- | --- | --- |
| Selected Row CSV/TXT | 対応 | 対応 | 対応 | XYZ/円筒座標、列順、Span別、Hub/Shroud別・一括。実Tip/図面・解析Shroud/派生座標に対応 | 外部CAD/CFDでの一律受入れ保証ではない |
| 旧2D CSV | 維持 | 既存仕様どおり | radial 2D計算経路を維持 | 実3DのRC座標が必要ならSelected Row Coordinateを使う | 実3Dとの同一形状を保証しない |
| TurboGrid Profile Points | 対応 | 1枚/主翼ピッチに対応 | 選択行Hub/Tip＋所属壁面に対応 | 正の隙間はShroud延長断面＋実Tip番号の指定が必要。filletなし。派生カットは事前拒否 | Import/Mesh `NOT_TESTED` |
| TurboGrid CAD | 条件付き | 生成経路あり、成立確認が必要 | 未対応 | 流体STEP中間形式、`CONVERSION_REQUIRED`。正の隙間、解析用Shroud設定（0 mmも含む）、派生カット、翼追従境界は未対応 | 変換器未導入、Import/Mesh `NOT_TESTED` |
| Mechanical STEP | 条件付き | 主翼と併せて対応 | 未対応 | Blade Only、Blade+Hub、固定周期/翼追従周期、全周。Hub付きは成立するディスク/根元が必要 | Workbench/Mechanical Import/Mesh `NOT_TESTED` |

座標定義は[CSV/TXT仕様](COORDINATE_CSV.md)、Profile Pointsは
[Splitter](TURBOGRID_SPLITTER.md)・[クリアランス](TURBOGRID_CLEARANCE.md)、
CADは[CAD/Fillet](CAD_EXPORT.md)を参照。
対応していない構成で、元形状・固定境界・隙間なし形状を無通知で代替出力しない。

## Mechanical CADの成立条件

- 仮ディスクは`PROVISIONAL`。実機の寸法・応力・安全率を保証しない。
- 根元Rは指定値を使い、不成立時に自動縮小しない。R8成立は完成条件ではない。
- 既定の主翼11枚＋Splitter11枚では、仮ディスク・明示R0.1 mmの全周生成とSTEP検査が成立している。
- 旧固定平面の既定モデル検証では2solidとなった。これは旧方式の記録であり、
  [翼追従方式](BLADE_FOLLOWING_SECTOR.md)の1solid成立結果と混同しない。
- 翼追従方式は主翼3枚以上・真のHub fillet付き・Mechanical専用。
  翼面/fillet保持、切断距離、周期回転対応、体積、再構成、STEP検査が必要。
  全面材料一致は`NOT_CONFIRMED`、面比較は有限標本。
- 表示XYZ直線接続・派生カット円筒補間・CAD splineは既存方針で維持する。
  方式間の一致を同じsnapshotだけで保証しない。検査不足を公差緩和で隠さない。

## 検証記録

直近の全回帰は2,661一意ID成功（通常2,563・実CAD98、失敗/error/skip/漏れ/重複0）。
この件数は今回の文書変更で全回帰を再実行したという意味ではない。
通常回帰後のCAD限定差分は実CAD全件を最終コードで再検証し、組ごとの固定413入力を照合している。
今回も計算コード・数値fixture・同梱既定値・ユーザーJSONを変更しない。

今回の短時間63件・関連GUI/worker 23件・公開契約18件は成功。計算413入力は不変で、
文書/画面資料のみのため全回帰は再実行していない。

Windows GUIの新方式通し検証も成功（Export Mechanical、既定11主翼＋11Splitter、仮ディスク、R0.1 mm）。
取消時の旧case保護と再実行、1solidのSTEP公開、previewのhash、保存/再読込みを確認した。
ボタンから結果照合までは約45分9秒。初回ハーネスの誤期待によるFAILを残し、修正後に再生成した。
条件と数値は[受入れ記録](GUI_FOLLOWING_SECTOR_ACCEPTANCE.md)に分離する。
checkpointから再開した実CAD検証、GUIから最初から再生成した検証、人手/F5を別に記録する。
このPCのアプリ/CAD環境はPython 3.12.14。別PCでの同一再現は別の受入れ項目。
全ケースのANSYS取込み・Mesh・CFD・強度解析は未検証。

## 次の段階

最新対応表の整理と上記GUI通し検証は今回完了。次は代表構成と処理時間の受入れ範囲を広げる。

1. 本表とGUI通し検証の結果を起点として、完成した項目と残る受入れ項目を整理する。
2. 代表モデルの実操作・保存/再読込み・取消/再実行・出力を増やす。CAD処理時間は計測して改善候補を絞る。
3. ANSYSのあるPCでは主翼のみ→Splitter→隙間→Diffuser/RCの順に、Import/Mesh/solver/結果CSVを検証する。
4. 外部解析adapterの成立後、予算・停止・再開・重複防止を持つ反復へ接続する。
   角度/厚さ/子午面の座標最適化を維持し、3D CAD評価の組込みは別段階とする。
5. 派生TurboGrid/CAD・静翼CAD・正の隙間のTurboGrid CADは、仕様と受入れを定めて各1機能ずつ拡張する。

[ANSYS引継ぎ](ANSYS_EXTERNAL_ANALYSIS_HANDOFF.md)、[開発計画の履歴](DEVELOPMENT_ROADMAP.md)、
[初回監査と追記](CURRENT_FUNCTION_AUDIT.md)、[品質レビュー履歴](GEOMETRY_QUALITY_REVIEW.md)。
