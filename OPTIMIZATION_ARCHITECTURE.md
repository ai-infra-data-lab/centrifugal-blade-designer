> v0.3でもこの層はDiffuser 2Dの候補変換・形状判定です。Angle/Thicknessは共通PCHIPを使用します。最新検証とImpeller仕様はREADME.md / V03_IMPLEMENTATION_REPORT.mdを参照してください。

# Design Parameter / Optimization Parameter Architecture

## 今回の変更

設計パラメータ、最適化変数、生成座標を分離しました。
現在のGeometry Engineは引き続き任意Control PointのBladeParametersのみを受け取ります。
最適化層からGeometry Engineの内部を変更する処理はありません。

```text
GUI Control Points ──────────────────────────┐
                                           ▼
Optimization Variables → ParameterMapper → BladeParameters
                                           ↓
                                      BladeDesigner
                                           ↓
                                      BladeGeometry
                                           ↓
                                 Geometry feasibility
                                           ↓
                             feasible の候補のみ外部CFDへ
```

最短スロートがLEに位置することは許容します。
LEの位置だけを理由とする警告・Rejectは行いません。TEには従来の注意表示を残しますが、位置だけでRejectにはしません。
スロート幅、接触、自己交差などの検査は継続します。

## GUIの操作

1. 通常の6タブでBaselineにしたい形状を作ります。
2. Optimizationタブの **Capture Current Design as Baseline** を押します。
3. Geometry／Architectureモード、9-variable／7-variableセットを選択します。
4. 各グループのUseで有効・無効を設定し、Type、Mode、Min、Initial、Max、Scaleを編集します。
5. Geometry Constraintsで使用する制約と閾値を設定します。表はスクロールできます。
6. **Generate / Check Initial Candidate** を押すと、Initialベクトルから候補を生成して判定します。
7. FEASIBLEなら **Apply Feasible Candidate to Design** で通常の設計画面へ反映できます。

REJECTEDでも生成できた候補形状は確認できますが、Applyは無効です。
パラメータや制約を編集すると前の判定・候補表示は無効になります。

Baselineはコピーとして保持します。通常のGUI編集や候補の適用ではBaselineを変更しません。
再Capture、New、Open ProjectではBaselineを更新し、変数セットを初期化します。
Mode／Preset切替も変数設定を初期化します。

**現在のOptimization設定・制約はセッション内の設定です。**
Save Projectは適用後の設計パラメータをschema 0.3で保存します（旧0.1/0.2の移行も維持）。
Baseline、最適化変数の範囲、制約設定の永続化は今回追加していません。
APIからはdataclassを使用して外部側で管理できます。

## 変数セット

標準9項目:

| 変数 | 初期Mode | 初期値 | 役割 |
| --- | --- | --- | --- |
| beta_le | Delta | 0° | LE翼角 |
| beta_25 | Delta | 0° | Mnorm=0.25の翼角 |
| beta_50 | Delta | 0° | Mnorm=0.50の翼角 |
| beta_75 | Delta | 0° | Mnorm=0.75の翼角 |
| beta_te | Delta | 0° | TE翼角 |
| thickness_scale | Absolute | 1 | 基準翼厚倍率 |
| m_tmax_shift | Delta | 0 | 厚さ最大位置の移動量 |
| le_ellipse_ratio | Absolute | Baseline値 | LE楕円比 |
| te_thickness | Absolute | Baseline値 | TE厚さ |

7項目セットでは5翼角変数をbeta_le／beta_bow／beta_teの3変数へ減らします。

LE Typeは最適化中に変更しません。
Circular／CutoffのBaselineでは楕円比は形状に効かないため、le_ellipse_ratioのUseを初期OFFにします。
したがって既定のCircular翼では9項目セットの有効ベクトルは8次元、7項目セットは6次元です。
LEをEllipticalに変更してCaptureすると、それぞれ9／7次元になります。
Circularのまま楕円比を有効化すると設定エラーを表示します。

Geometry OptimizationではR LE／R TE／Vane Countは固定です。
Architecture Optimizationではr_le、r_teと離散vane_countを追加します。
翼枚数の既定候補はBaseline±3枚（下限1）です。Choices欄で昇順・重複なしの整数候補を指定できます。

## 型・正規化・Scale

- CONTINUOUS: 連続変数。
- INTEGER: 整数変数。正規化入力は最近傍整数へ量子化します。中間値は大きい整数側です。
- DISCRETE: Choices内の値。正規化値は候補インデックスへ対応付けます。
- FIXED: 有効ならInitialを固定値として適用し、ベクトルの次元には含めません。
- UseがOFFなら、その変数による変更を適用しません。

連続変数の変換:

```text
physical = lower + normalized × (upper - lower)
normalized = (physical - lower) / (upper - lower)
```

範囲外、非有限値、ベクトル次元不一致を拒否します。
物理値入力では整数の小数丸めを行わず、不正な値を拒否します。
Vane CountのCONTINUOUS指定も拒否します。

Scaleは外部アルゴリズム用の正の特性スケール情報です。
上記の0〜1正規化へ重ねて乗算しません。Geometry Engineへは物理値だけを渡します。

Absolute／Deltaは各変数の入力の解釈です。
例: beta_teのAbsolute=48°と、Baseline=50°に対するDelta=-2°は同じ候補になります。
GUIでModeを切り替えてもMin／Initial／Maxを自動換算しません。新しい解釈に合わせて設定してください。

## マッピング規約

### 翼角

BaselineのPCHIP分布を基準とし、指定した位置の目標値とBaselineとの差をPCHIP補間して加えます。
beta_30／beta_60もAPIで指定可能です。未指定のLE／TEは維持します。
修正がある場合は約101点と元のControl Point・変数位置で設計用Control Pointを生成します。
全ゼロの変更では元のControl Pointをそのまま維持します。

```text
beta(M) = beta_baseline(M) + delta_beta(M)
          + beta_bow × 4M(1-M) + beta_offset
```

beta_bowは端点を変えず、中央を指定量だけ変えます。beta_offsetは全域の加算量です。
いずれも基準値0で、値の単位はdegreeです。

### 翼厚

thickness_scaleはBaselineの全厚さを倍率変更します。
Deltaモードなら倍率は1+Deltaです。

m_tmax_shiftはDeltaモードではBaselineの最大厚さ位置からの移動量、
Absoluteでは目標の最大厚さ位置です。
元の最大点から新しい最大点へ、前後区間のMnormをそれぞれ線形写像して端点を固定します。
最大値が複数ある場合は最初の最大点を基準にします。
ピークが端点にあるBaselineは、ゼロでないピーク移動を拒否します。

APIのthickness_front／thickness_rearは前半／後半の局所倍率です:

```text
t(M) = thickness_scale × t_baseline(warped M)
       × [1 + thickness_front × f_front(M) + thickness_rear × f_rear(M)]

f_front = sin²(2πM)  (0 <= M <= 0.5)、それ以外0
f_rear  = sin²(2πM)  (0.5 <= M <= 1)、それ以外0
```

局所係数は-1以上です。
le_thickness／te_thicknessを明示すると、倍率変更後の端点をその値で上書きします。
Deltaは倍率変更前のBaseline端点値に対する差です。
標準セットではTE厚さを独立指定するため、thickness_scaleだけを動かしてもTEはInitial値に保たれます。
TEも倍率で変えたい場合はte_thicknessのUseをOFFにしてください。

LE／TE Type、PS mapping、出力点数、CSV精度はBaselineから引き継ぎます。
te_ellipse_ratio、le_thickness、beta_offset、局所厚さ係数はAPIから追加設定できます。
任意の全Control Pointを独立変数にする高自由度セットは今回の初期セットには含めていません。

## 形状制約

標準の形状検証後、次を判定します。

| 制約 | 初期値 |
| --- | --- |
| No self intersection | 有効 |
| Minimum thickness | 0.1 mm |
| Maximum PS/SS curvature | 1 /mm |
| Minimum PS/SS curvature radius | 0.1 mm |
| Minimum throat | 0 mm |
| Maximum throat | 無効 |
| Minimum TE thickness | 0.1 mm |
| Maximum local turning gradient | 200 deg / Mnorm |
| Maximum second derivative | 無効 |

表の閾値は初期の試用値です。対象翼・設計条件に合わせて設定してください。
曲率制約の対象はPS／SSです。丸いLE／TE自体の曲率は含めません。
表面cusp／オフセット反転と、隣接翼の接触（Throat <= 1e-7 mm）は別途拒否します。
1枚翼でThroatが定義できない場合、有効なThroat制約は不成立になります。

厚さの最小値は補間多項式の極値まで調べます。
翼角勾配と2階微分の最大値はPCHIPの区間多項式を直接調べるため、
Master Geometryのサンプル点間にある急変も検出します。
曲率と自己交差の検査は既存の高密度Master Geometryを使います。

## API例

以下はプロジェクトディレクトリで実行できます。最適化・CFDソルバーの追加依存はありません。

```python
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.optimization import (
    ParameterMapper, default_parameters, GeometryConstraints, evaluate_candidate,
)

baseline = BladeParameters()
mapper = ParameterMapper(default_parameters(baseline), baseline)

# 標準の境界: 正規化ベクトル → 物理設計パラメータ → 共通Geometry Engine
vector = mapper.initial_vector()
design = mapper.create_design(vector)
geometry = BladeDesigner().generate(design)

# CFDに渡す前の判定。feasible=FalseならCFDへ送らない。
candidate = evaluate_candidate(mapper, vector, GeometryConstraints())
if candidate.feasible:
    accepted_geometry = candidate.geometry
    # 外部側でメッシュ生成・CFD・目的関数評価を接続する
else:
    reasons = [c for c in candidate.feasibility.checks if not c.passed]

# 外部が物理値を直接持つ場合
physical_vector = mapper.initial_vector(normalized=False)
design = mapper.create_design(physical_vector, normalized=False)
```

名前付き変数を直接設計へ変換することもできます。
この低レベル関数は設計妥当性を検査しますが、探索範囲の管理にはParameterMapperを使用してください。

```python
from blade_designer.optimization import OptimizationVariables, ValueMode, optimization_to_design

variables = OptimizationVariables(
    values={"beta_te": -2.0, "beta_bow": 1.0, "thickness_scale": 1.05},
    value_modes={"beta_te": ValueMode.DELTA},
)
candidate_design = optimization_to_design(variables, baseline)
```

## 実装ファイル・検証

- optimization/models.py: 変数・型・モード・制約・候補結果のdataclass。
- optimization/presets.py: 9／7項目セット、Architectureの離散翼枚数。
- optimization/parameter_mapper.py: Baselineコピー、正規化、Absolute／Delta変換。
- optimization/feasibility.py: 共通Geometry Engineを呼ぶ候補生成・制約判定。
- gui/optimization_widget.py: グループ別設定、候補表示、適用。
- geometry/designer.py: LE位置だけを理由とするThroat警告を削除。
- tests/test_optimization_mapper.py、test_optimization_constraints.py、test_optimization_gui.py: 追加検証。
- artifacts/optimization/: 現行画面の画像。
- artifacts/v0.2-before-optimization.zip: 修正前ソースの退避。

2026-10-03: 全体の `pytest -q -W error` は **109 passed、0 failure、0 warning**。
既存78件と追加31件が成功しています。
Baselineの独立性、正規化、離散／整数、端点維持、変数無効化、形状制約、
LEスロートの許容、GUIの候補適用・Reject・失効を検証しました。

今回実装したのは最適化の設定・マッピング・Geometry feasibilityまでです。
Optuna／BoTorch／GPyTorch／optiSLang、DOEの自動実行、CFD、目的関数評価は接続していません。
