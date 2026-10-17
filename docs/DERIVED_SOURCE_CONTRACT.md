# 派生元面の参照適用（Stage 3A-2b）

Shroud/外径カットで失われていた元曲面上の位置を、内部の結果データとして保持する。共通の区分線形数値層から派生点を再構成できるようにした。既存の表示・翼形状生成・CAD spline・出力形式を別方式へ切り替える変更ではない。

## 今回の実装

`models/geometry_3d.py::CurveSourceMap`を追加し、`Curve3D.source_map`へ任意で付加する。設計パラメータではなく、生成のたびに再作成する内部の由来情報である。プロジェクトJSON、CSV、TurboGrid、CAD NPZの項目は増やさない。無カット時のsource_mapはNoneのまま。

| フィールド | 意味 |
|---|---|
| source_set | 元geometry内の`sections`または`splitter_sections`。主翼/Splitterを区別する |
| role | 元のcamber/master_ps/master_ss/master_le/master_te |
| law | `source_row_index`（元断面の各自index）または`trim_common_index`（既存Shroudカットの共通最大点数格子） |
| coordinates | 各結果点の元位置を表す(N,K,2)配列。末尾の2成分は元Spanと元index |
| weights | 各元位置の非負の重み(N,K)。各行の和は1 |

ShroudカットのHubは従来どおり元Hub曲線を直接コピーする。この場合は`source_row_index`とする。断面間で点数が異なると、共通格子への再サンプリングが元Hubのknotsを全て通るとは限らないためである。Hub以外のカット曲線は従来の共通index格子と、探索した各点の元Spanを保存する。

外径カットは、元頂点を保持し末尾の交点だけを補間する。その交点では元位置そのものを平均せず、両端点の元位置と補間比を保持する。表示用`resample_curve`でも、同じXYZ長と重複点フィルターを使って由来の重みを伝える。未変更の表示曲線へ後付けで形状を再計算しないため、外径カットで再サンプリングされないLE等の既存表示曲線にはsource_mapがない場合がある。そのときに由来を推定するfallbackは行わない。

## なぜ単一の元位置では足りないか

例えば元面が`r(s,t)=10+10s+20t+20st`の場合、(s,t)=(0.2,0.2)と(0.8,0.8)の半分で作る点の半径は31.8。一方、平均座標(0.5,0.5)で元面を評価すると30になる。交差項のために1.8 mmの差が生じる。単一の補間済みsource_span/source_indexだけでは、この点を正確に再構成できない。

そのため、`geometry/curve_source.py::blend_source_map`は元位置と重みを連結して保存する。座標平均や最寄点投影で差を隠さない。由来点はShroudカット後にK=1、外径切断後にK=2、その後の表示再サンプリングでK=4となる。これは精度のための内部データであり、翼の制御点を追加する操作ではない。

## 参照面の評価と適用範囲

`evaluate_source_curve(curve, geometry.source_geometry)`は対応する元の翼集合・roleを取り出し、共通の`SectionSurface`検証とSpan列補間を利用する。元位置でr/theta/Zを評価してから重みで合成し、最後にXYZへ変換する。XYZを平均する別の面とは混同しない。呼出し例:

```python
from blade_designer.geometry.curve_source import evaluate_source_curve

section = geometry.sections[-1]
reconstructed_xyz = evaluate_source_curve(section.master_ps, geometry.source_geometry)
```

元geometryはcallerが対応する生成結果から渡す。source_mapはrow IDやsnapshot hashの代替ではなく、別の設計結果との同一性を自動証明しない。Stage 2のrow/snapshot識別は引き続き必要である。

新しく機械加工で作るTE capは元TEの一部ではないためsource_map=Noneとし、再構成要求は明示的に拒否する。既存のsource_spanが残っていても、それだけで元TE面上の点と判定しない。新TEを含む完全な加工境界モデルや、そのCAD化は別の実装単位である。

不正なrole/集合/方式、配列shape、範囲外・非有限の元座標、負の重み、和が1でない重みは拒否する。重みの和の判定は機械epsilonの32倍以内で行い、自動で正規化しない。この浮動小数点の整合確認をCAD/fillet/STEP公差の緩和に使わない。

## 保護した互換性

- 形状の計算式・補間順、42回の境界探索、外径交点、既存beta/厚さ/source_spanは維持する。
- 元geometryは変更せず、派生結果のコピーへ由来を付加する。無カットの生成結果は従来どおり返す。
- 新しいTEには旧TEの由来を誤って転用しない。派生カットのCAD/TurboGrid未対応ガードを解除しない。
- 設計JSONには保存せず、Load後の生成で同じ由来を再作成する。原本・同梱デフォルトJSONを変更しない。
- Qt、外部ファイル形式、OCPに依存しない数値層として実装する。GUIの操作やCamera、メニューは変更しない。

## 検証

新規30件。独立した双線形面の交差項、外径交点・表示の重み継承、断面間の点数差、1個だけ残る微小曲線のarclength knot、末尾の微小区間が除去された場合の端点clamp、不正由来拒否、CW/CCW、主翼/専用Splitter、Rake12°、gap0.4/0.8、Shroud/外径/結合カット、原本を変更しないJSON再生成を検証する。

関連101件成功（50.50秒、`20261017T224245Z-4b8820a1`）。回転方向の6ケース追加後、新規28件成功（29.40秒、`20261017T224424Z-d7d24d9b`）。微小曲線の1件を追加し、wireframeを含む最終関連33件成功（26.02秒、`20261017T224520Z-4d4c5d2c`）。既存数値fixtureと期待値は変更していない。

変更前commit `0164f1cb3d34be98885534dacf2d1cafe7e2399b`のtrimを独立moduleとして読み込み、CW/CCW×主翼連動/専用Splitter×Shroud/外径/結合カットの12条件・648曲線でr/theta/Z/m_norm/距離/source_spanが完全一致した。m/beta/厚さとHub/Shroud配列も一致した。由来がある曲線の再構成最大距離は2.93099e-14 mm。これは標本点の数値再構成であり、全面偏差・物理精度の保証ではない。原本と同梱デフォルトのSHA256は両方とも`aa724c8253463289caec919960d7d486d698765cee35202c13e4efd17a603dd6`のまま。再現コードと結果は`artifacts/quality-stage3a2b/probe.py`、`probe.json`。

別途`BladeParameters`標準の曲線流路へShroud面積10%カットを適用し、18曲線の再構成最大距離5.85929e-14 mmを確認した（`curved-probe.json`）。これはpackaged default JSONの形状とは別の標準パラメータ例である。

追加調査で、末尾の微小区間が重複点フィルターから除かれる場合、新しい由来補間だけが約1.78e-15の負の重みを作ることを再現した。既存np.interpと同じ端点clampを由来補間へ適用した。追加した厳密比較は内部点の1 ULP差で1件失敗・33件成功（27.05秒、`20261017T225030Z-f9d6286c`）。新テストでは端点の厳密一致と非負重みを維持し、内部点を1 ULP以内で確認する。修正後の最終関連34件成功（26.31秒、`20261017T225113Z-dec69ec6`）。既存の数値期待値やCAD公差は変更しない。

初回全回帰はこの境界ケースを追加するため停止し、結果を採用していない。専用orchestratorのcommand line・生成時刻・親子関係を確認したprocess treeだけを停止した。終了済み子processへの停止通知が競合して停止コマンドは非0となったが、対象processの残存なしを確認した。テスト失敗とは別の停止処理の結果である。最終全回帰は別領域`artifacts/quality-stage3a2b-final/`で固定入力から再実行した。CADの重いBoolean試験を他のCAD試験と別群に分けるが、全IDを一度ずつ照合する。

最終回帰は通常6群とCAD2群で実行する。CADのsession fixtureは各群で別々に構築されるため、群の時間を単一processの所要時間とはみなさない。試験IDの重複や漏れは別途JUnitと収集結果で検査する。確定結果は次節に記録する。

## 残る課題

今回の参照適用は派生元の円筒座標補間面に限定する。PreviewのXYZ直線、CADの高次splineを同じ面へ変更したわけではない。全面の単一正本適用、表示/CAD互換モード、加工TEの完全な由来、全体の誤差予算、Jacobian/法線反転/3D干渉は残る。現実モデルの根元フィレット成立、native GUI、高DPI、ANSYS Import/Meshは今回の成功としない。


## 最終全回帰

**1,079一意件成功**（通常1,042・実CAD37）。既存1,049 IDを全て維持し、新規30 IDを追加した。failure/error/skip/実行漏れ/重複/想定外IDは0。固定した248入力（package/test Python、main、既定JSON、原本JSON）は開始から終了までhash不変。原本と同梱デフォルトの一致も確認した。既存数値fixture・期待値は変更していない。

通常6群・CAD2群のJUnitと収集IDを照合した結果である。根拠は`artifacts/quality-stage3a2b-final/final-test-coverage.json`、`source-hashes.json`、`groups.json`。停止した初回の部分結果は含めない。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 458.128 | 20261017T225156Z-6b9c4507 |
| 通常1 | 143 | 409.797 | 20261017T225156Z-779957df |
| 通常2 | 122 | 478.621 | 20261017T225156Z-b7244b62 |
| 通常3 | 191 | 338.725 | 20261017T225156Z-c9c63c08 |
| 通常4 | 146 | 441.480 | 20261017T225156Z-75dd2b16 |
| 通常5 | 324 | 522.254 | 20261017T225156Z-2f285b48 |
| 実CAD0 | 1 | 650.966 | 20261017T225156Z-2d3ee011 |
| 実CAD1 | 36 | 931.196 | 20261017T225156Z-e43c3316 |

これらの成功を、表示とCADの全面一致、実モデル根元filletの成立、native Windows操作やANSYS Import/Meshの成功とは扱わない。
