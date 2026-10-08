# READY_FOR_CODEX

# Centrifugal Compressor Blade Designer v0.3
## Flow Path / Meridional / Flow Area / 3D Blade / TurboGrid Export

---

# 0. 実装方針

既存の `Centrifugal Compressor Blade Designer` v0.1 / v0.2コードをベースに、v0.3へ拡張すること。

既存コードを全面的に作り直さないこと。

まず既存コード、データモデル、テスト、GUI構造を確認し、既存機能を可能な限り維持しながら段階的に拡張すること。

各Stage終了時に、

```bash
pytest -q
```

を実行し、既存テストを含めて0 failureであることを確認してから次Stageへ進むこと。

Geometry EngineとGUIを分離する。

Geometry Engineから以下をimportしてはならない。

```text
PySide6
PyQtGraph
PyVista
```

外部ソフト固有の処理、特にTurboGrid形式への変換はGeometry Engineへ含めず、Exporterへ分離すること。

---

# 1. v0.3の完成目標

v0.3では以下を完成させる。

```text
1. Blade Viewを常時表示

2. Geometry変更時にZoom/Pan/Viewを保持

3. Blade AngleとThicknessの編集画面を切替式にする

4. Blade Angle / ThicknessをPCHIPへ統一

5. Hub / Shroud Meridional Curveを設計可能にする

6. Hub / ShroudをLine + Circular Arcで構成

7. Line-Arc / Arc-Line / Arc-ArcをG1接線連続にする

8. Meridional上へ
   Inlet
   Impeller LE
   Impeller TE
   Diffuser LE
   Diffuser TE
   Outlet
   を配置

9. Meridional上で
   Inlet
   Impeller
   Vaneless Diffuser
   Vaned Diffuser
   Outlet
   の対応範囲を表示

10. Gross Flow AreaをMeridional位置に対して計算

11. Flow Area graphを表示

12. Meridional ViewとFlow Area graphを連動

13. Hub Blade Profile生成

14. Tip Blade Profile生成

15. 任意Intermediate Spanへ拡張可能な構造

16. 3D Preview

17. TurboGrid用
    hub.curve
    shroud.curve
    profile.curve
    をExport

18. LE / PS / TE / SS point数を独立指定

19. Default point数
    LE = 21
    PS = 101
    TE = 21
    SS = 101

20. Export Significant Digitsを指定

21. Default Significant Digits = 6

22. v0.1 / v0.2 ProjectをMigration可能

23. pytest 0 failure
```

---

# 2. v0.3では実装しないもの

以下は今回実装しない。

```text
Splitter Blade

Tip Clearance

Lean専用parameter

Sweep専用parameter

Rake専用parameter

Effective Area including blade blockage

TurboGrid automatic meshing

CFX automatic execution

Optimization execution

Optuna integration

BoTorch integration

OptiSLang integration

STEP

IGES

Solid CAD
```

ただし将来追加できる構造にすること。

---

# 3. Main Windowの再構成

Blade Viewは常時表示する。

Blade AngleやThicknessを編集するためにBlade View自体を切り替えて消してはならない。

基本レイアウト：

```text
┌──────────────────────────────────────────────────────────────┐
│ Toolbar                                                      │
├───────────────────────────────┬──────────────────────────────┤
│                               │ Editor                       │
│                               │                              │
│                               │ [Blade Angle]                │
│        BLADE VIEW             │ [Thickness]                  │
│        常時表示               │ [LE / TE]                    │
│                               │ [Meridional]                 │
│                               │ [Output]                     │
│                               │                              │
│                               │ selected editor contents     │
│                               │                              │
├───────────────────────────────┴──────────────────────────────┤
│ Context View                                                 │
│ Meridional / Flow Area / Metrics / 3D Preview               │
├──────────────────────────────────────────────────────────────┤
│ Validation / Status                                          │
└──────────────────────────────────────────────────────────────┘
```

Blade ViewをMain geometry displayとする。

Editor側のみ内容を切り替える。

---

# 4. View Preservation

非常に重要。

Geometry Parameterを変更しても、ユーザーが現在見ているZoom/Pan位置をリセットしてはならない。

対象：

```text
Blade Angle

Thickness

LE / TE

Hub / Shroud

Span Section

Meridional Segment

Point Count
```

Geometry更新時に、

```text
autoRange()
fitInView()
setRange()
```

などを自動実行しないこと。

Graphic Item自体を毎回破棄して再作成するのではなく、可能な限り、

```python
plot_item.setData(...)
```

等で既存Itemのデータだけを変更する。

---

# 5. Fit View

Toolbarへ、

```text
Fit View
```

を追加する。

ViewのAuto Fitを行うのは原則、

```text
Application start

New Project

Open Project

Fit View clicked
```

の場合だけとする。

Geometry Parameter変更時には行わない。

---

# 6. 3D ViewのCamera Preservation

3D Previewも同様。

Geometry更新前にcamera stateを保持し、

```text
geometry update
↓
mesh update
↓
camera restore
```

とする。

Geometry変更のたびにdefault cameraへ戻してはならない。

---

# 7. Blade AngleとThicknessの補間方法

Blade AngleとThicknessは同一の補間関数を使用する。

標準補間：

```python
scipy.interpolate.PchipInterpolator
```

PCHIP：

```text
Piecewise Cubic Hermite Interpolating Polynomial
```

である。

共通関数：

```python
def interpolate_distribution(
    m_norm: FloatArray,
    control_m_norm: FloatArray,
    control_values: FloatArray,
) -> FloatArray:
    ...
```

を作成すること。

Blade Angle用とThickness用に同じアルゴリズムを別々に重複実装しないこと。

---

# 8. Control Point

Blade AngleとThicknessは任意数Control Pointとする。

最低2点。

必ず、

```text
m_norm = 0
m_norm = 1
```

を持つ。

内部Control Pointについては、

```text
0 < m_norm < 1
```

とする。

同一m_normは禁止。

単調増加であること。

GUI操作：

```text
Add Point

Delete Point

Drag Point
```

をBlade AngleとThickness両方へ実装する。

---

# 9. Normalized Meridionalを2種類に分ける

Meridional方向座標を曖昧にしない。

内部では物理的累積Meridional Distance：

```text
m
```

を持つ。

さらにFlow Path全体には、

```text
m_flow_norm
```

を持つ。

定義：

```math
m_flow_norm =
(m - m_inlet) /
(m_outlet - m_inlet)
```

範囲：

```text
Inlet  = 0
Outlet = 1
```

---

# 10. Blade用Normalized Meridional

各Blade Rowについて、

```text
m_blade_norm
```

を使用する。

定義：

```math
m_blade_norm =
(m - m_LE) /
(m_TE - m_LE)
```

範囲：

```text
Blade LE = 0
Blade TE = 1
```

Blade AngleとThicknessの横軸は、

```text
Normalized Meridional
```

と表示する。

内部変数名は、

```python
m_blade_norm
```

とする。

---

# 11. Blade Angle βm

v0.1のalpha名称は廃止し、

```text
Blade Angle βm
```

へ統一する。

内部変数：

```python
beta_m_deg
beta_m_rad
```

βmの定義：

**局所Meridional方向とBlade Camber Line局所接線の間の角度**

とする。

基本式：

```math
tan(beta_m) =
r * dtheta/dm
```

したがって、

```math
dtheta/dm =
tan(beta_m) / r
```

とする。

Hub / Tip / Intermediate Sectionで同じ定義を使用する。

---

# 12. Flow Path Topology

Meridional GeometryはHub / Shroud curveだけでなく、Component Station情報を持つ。

最低限以下を実装する。

```text
INLET

IMP_LE

IMP_TE

DIF_LE

DIF_TE

OUTLET
```

意味：

```text
INLET
Flow Path開始

IMP_LE
Impeller Blade Leading Edge

IMP_TE
Impeller Blade Trailing Edge

DIF_LE
Diffuser Vane Leading Edge

DIF_TE
Diffuser Vane Trailing Edge

OUTLET
Flow Path終了
```

---

# 13. Component Region

Stationから以下の領域を生成する。

```text
INLET → IMP_LE
Inlet Region

IMP_LE → IMP_TE
Impeller

IMP_TE → DIF_LE
Vaneless Diffuser / Gap

DIF_LE → DIF_TE
Vaned Diffuser

DIF_TE → OUTLET
Outlet Region
```

Meridional View上に背景、ラベル、境界線等で分かるように表示する。

最低限ラベルを表示する。

---

# 14. Meridional View

Meridional EditorではHubとShroudを同時表示する。

概念：

```text
R
↑

          Shroud
              ╭────────────────────────
            ╭─╯
          ╭─╯
        ╭─╯
Hub ────╯───────────────────────────────

   │         │        │        │        │
 INLET     IMP_LE    IMP_TE   DIF_LE   DIF_TE   OUTLET

   Inlet      Impeller       Vaneless     Diffuser
```

Station labelは常に読み取れるようにする。

---

# 15. Meridional Geometry Primitive

Hub / Shroud Curveの基本Primitiveは、

```text
Line

Circular Arc
```

とする。

自由SplineをMeridional Geometryの基本表現にはしない。

---

# 16. Segment Chain方式

Meridional Curveは複数Segmentを順番につなぐ。

例：

```text
Line
↓
Arc R20
↓
Arc R40
↓
Arc R80
↓
Line
```

以下すべてを扱うこと。

```text
Line → Line

Line → Arc

Arc → Line

Arc → Arc
```

特にShroud Curveで複数Arcを連続使用できること。

---

# 17. G1 Tangency

標準ではSegment同士をG1連続とする。

接続点：

```math
P_previous_end =
P_next_start
```

接線：

```math
T_previous_end =
T_next_start
```

数値的には単位接線のdot product：

```math
dot(T1, T2) ≈ 1
```

となること。

---

# 18. Meridional Curve Initial Condition

各Curveは、

```python
start_z
start_r
start_angle_deg
```

を持つ。

そこから各Segmentを順番に生成する。

---

# 19. Line Segment

Line Segmentの基本Parameter：

```python
@dataclass
class LineSegmentParameters:
    length: float
```

Start PointとStart Tangentは前SegmentまたはCurve Initial Conditionから継承する。

End Pointは、

```math
P_end =
P_start + length * T_start
```

として生成する。

---

# 20. Circular Arc Segment

基本Parameter：

```python
@dataclass
class ArcSegmentParameters:
    radius: float
    sweep_deg: float
    clockwise: bool
```

Start PointとStart Tangentは前Segmentから継承する。

ユーザーは主に、

```text
Radius

Sweep Angle

CW / CCW
```

を入力する。

この方式で、

```text
Arc R1
↓
Arc R2
↓
Arc R3
```

をG1接続可能とする。

---

# 21. Meridional Parameter Model

概念：

```python
class SegmentType(Enum):
    LINE = "line"
    ARC = "arc"


@dataclass
class LineSegmentParameters:
    length: float


@dataclass
class ArcSegmentParameters:
    radius: float
    sweep_deg: float
    clockwise: bool


@dataclass
class MeridionalCurveParameters:
    start_z: float
    start_r: float
    start_angle_deg: float

    segments: list[
        LineSegmentParameters |
        ArcSegmentParameters
    ]
```

---

# 22. Meridional Geometry Result

```python
@dataclass
class Point2D:
    z: float
    r: float


@dataclass
class LineSegmentGeometry:
    start: Point2D
    end: Point2D


@dataclass
class ArcSegmentGeometry:
    start: Point2D
    end: Point2D

    center: Point2D

    radius: float
    sweep_rad: float

    clockwise: bool


@dataclass
class MeridionalGeometry:
    segments: list[
        LineSegmentGeometry |
        ArcSegmentGeometry
    ]

    z: FloatArray
    r: FloatArray

    m: FloatArray
```

---

# 23. Meridional Editor GUI

右Editorへ、

```text
Meridional
```

を追加。

Curve選択：

```text
Hub
Shroud
```

Segment Table：

```text
No.  Type   Length   Radius   Sweep   Direction

0    Line    25.0
1    Arc              20.0     35.0     CCW
2    Arc              45.0     20.0     CCW
3    Arc              80.0     15.0     CCW
4    Line    40.0
```

操作：

```text
Add Line

Add Arc

Delete Segment

Move Up

Move Down
```

---

# 24. Meridional Invalid Geometry

最低限以下をValidationする。

```text
Line length <= 0

Arc radius <= 0

Arc sweep = 0

NaN

Infinity

r <= 0

Curve self intersection

Hub / Shroud intersection
```

無効Geometryでアプリをクラッシュさせない。

---

# 25. Fillet

Filletは基本Geometry Primitiveにはしない。

将来的な補助編集コマンドとする。

優先順位：

```text
Line / Arc Segment Chain
>
Fillet Tool
```

v0.3ではFilletは必須ではない。

---

# 26. Flow Area Engine

新規モジュールを作る。

例：

```text
blade_designer/geometry/flow_area.py
```

目的：

Hub / Shroud Meridional GeometryからGross Flow Areaを計算する。

Blade blockageはまだ考慮しない。

---

# 27. Mean Meridional Line

Hub / Shroud間の代表的なMean Meridional Lineを生成する。

単純な同一index平均だけに依存しないよう、共通のFlow ParameterへHub / Shroudを再サンプリングしてから求める。

代表点：

```math
Z_mean =
(Z_hub + Z_shroud) / 2

R_mean =
(R_hub + R_shroud) / 2
```

を初期方式として使用してよい。

ただし処理を独立関数にし、将来別アルゴリズムへ変更できるようにする。

---

# 28. Local Cross-flow Direction

Mean Meridional Lineの局所単位接線を、

```math
T_m
```

とする。

R-Z plane内でこれに垂直な単位ベクトルを、

```math
N_m
```

とする。

各Meridional stationで、Mean Pointを通り `N_m` 方向に伸びるCross-flow lineを定義する。

このLineとHub CurveおよびShroud Curveとの交点を求める。

---

# 29. Hub-Shroud Passage Length

Cross-flow lineと、

```text
Hub

Shroud
```

との交点を、

```text
P_h
P_s
```

とする。

距離：

```math
L_hs =
|P_s - P_h|
```

を計算する。

---

# 30. Gross Flow Area

Cross-flow line上の回転半径について、代表半径を、

```math
R_c =
(R_h + R_s) / 2
```

とする。

Gross Flow Area：

```math
A_gross =
2 * pi * R_c * L_hs
```

とする。

この定義により、軸流と半径流を統一して扱えること。

---

# 31. Axial Passage Validation

Cross-flow lineが半径方向の場合、

```math
L_hs =
R_s - R_h
```

なので、

```math
A =
2*pi*((R_s+R_h)/2)*(R_s-R_h)
```

となる。

これは、

```math
A =
pi*(R_s^2-R_h^2)
```

に一致する。

必ずUnit Testする。

---

# 32. Radial Passage Validation

Cross-flow lineが軸方向で流路高さを、

```math
b
```

とすると、

```math
L_hs = b
```

なので、

```math
A =
2*pi*R*b
```

となる。

これもUnit Testする。

---

# 33. Flow Area Data Model

```python
@dataclass
class FlowAreaStation:
    m_flow_norm: float
    m: float

    z_mean: float
    r_mean: float

    hub_z: float
    hub_r: float

    shroud_z: float
    shroud_r: float

    passage_length: float

    gross_area: float

    component_region: str
```

Result：

```python
@dataclass
class FlowAreaResult:
    stations: list[FlowAreaStation]
```

必要ならNumPy配列形式へ最適化してよい。

---

# 34. Flow Area Plot

Context Viewへ、

```text
Flow Area
```

を追加する。

横軸：

```text
Normalized Flow Meridional
```

縦軸：

```text
Gross Flow Area [mm²]
```

表示：

```text
A_gross vs m_flow_norm
```

Station位置も表示する。

```text
IMP LE

IMP TE

DIF LE

DIF TE
```

---

# 35. Area Ratio

最低限以下を計算する。

```text
A / A_IMP_LE
```

さらにStation tableに、

```text
Station
Area
Area / A_IMP_LE
```

を表示する。

---

# 36. Meridional / Area Link

Meridional ViewとArea Plotを連動させる。

Area Plot上でマウスを動かした場合、

```text
nearest m_flow_norm
```

を取得。

Meridional View上に対応するCross-flow lineを表示する。

逆にMeridional Viewでstationを選択した場合もArea Plot上へMarkerを表示する。

---

# 37. Cursor Information

選択中Stationについて最低限以下を表示する。

```text
m_flow_norm

Physical meridional distance

Component Region

Gross Area

Hub R

Shroud R

Passage Length
```

---

# 38. Component Station Table

Meridional EditorへStation設定画面を追加する。

最低限：

```text
INLET

IMP_LE

IMP_TE

DIF_LE

DIF_TE

OUTLET
```

各StationはMeridional Curve上の位置として保存する。

できればPhysical `m` ではなくNormalized Flow Coordinateを保存し、Geometry変更時にも位置関係を維持しやすくする。

ただしBlade LE/TEとのGeometry consistencyをValidationする。

---

# 39. Blade Section Architecture

v0.3からSpan方向へ一般化する。

```python
@dataclass
class BladeSection:
    span: float

    blade_angle: BladeAngleParameters

    thickness: ThicknessParameters

    edge_parameters: EdgeParameters
```

Blade row側：

```python
sections: list[BladeSection]
```

とする。

---

# 40. Default Blade Sections

最低限、

```text
span = 0.0
Hub

span = 1.0
Tip
```

を作る。

Hub SectionはHub Meridional Curveへ配置。

Tip SectionはShroud Meridional Curveへ配置。

---

# 41. Intermediate Span

内部データ構造は任意Span Sectionを扱えるようにする。

例：

```text
0.000 Hub

0.250

0.500

0.750

1.000 Tip
```

可能ならGUIへ、

```text
Add Span Section

Delete Span Section
```

を追加する。

Hub / Tipは削除禁止。

---

# 42. Blade Section Selector

Blade Angle / Thickness / LE-TE Editorへ、

```text
Section:
[ Hub ▼ ]
```

を追加する。

最低限：

```text
Hub

Tip
```

を選択可能にする。

Intermediate Sectionが存在すれば自動的に追加する。

---

# 43. Copy Section

最低限、

```text
Copy Hub → Tip

Copy Tip → Hub
```

を追加する。

コピー後は独立編集可能とする。

---

# 44. Blade Angle Distribution

Blade Angle：

```text
beta_m(m_blade_norm)
```

をPCHIPで生成する。

Camber Lineは、

```math
dtheta/dm =
tan(beta_m) / r
```

を数値積分して生成する。

各Span Sectionごとに独立したβm Control Pointを持てること。

---

# 45. Thickness Distribution

Thickness：

```text
t(m_blade_norm)
```

もPCHIPとする。

各Span Sectionごとに独立設定可能。

---

# 46. LE / TE

既存仕様を維持。

最低限：

```text
Circular

Elliptical

Cutoff
```

を扱う。

Hub / Tipごとに独立設定可能。

---

# 47. Output Point Counts

出力点数はSegmentごとに指定。

```python
@dataclass
class OutputPointParameters:
    le_points: int = 21
    ps_points: int = 101
    te_points: int = 21
    ss_points: int = 101
```

Default：

```text
LE  = 21

PS  = 101

TE  = 21

SS  = 101
```

---

# 48. Internal Geometry Resolution

Output Pointsと内部計算精度を分離する。

Geometry EngineではHigh Resolution Master Geometryを生成。

推奨初期値：

```text
master profile resolution ≈ 2001
```

ただしHard-coded dependencyにしない。

流れ：

```text
Design Parameters
↓
High Resolution Geometry
↓
Validation / Metrics
↓
Output Resampling
↓
LE / PS / TE / SS points
```

---

# 49. Export Significant Digits

Export設定：

```python
@dataclass
class ExportParameters:
    significant_digits: int = 6
```

Default：

```text
6
```

範囲：

```text
1～15
```

Exportのみ適用。

内部計算：

```text
float64
```

Project JSON：

```text
full precision
```

---

# 50. 3D Coordinate

各Blade Sectionについて、

```text
R

Theta

Z
```

を保持。

Cartesian：

```math
X = R*cos(theta)

Y = R*sin(theta)

Z = Z
```

を生成する。

---

# 51. 3D Preview

可能ならPyVistaを使用する。

最低限：

```text
Hub Curve

Shroud Curve

Hub Blade Profile

Tip Blade Profile

Intermediate Blade Profiles
```

を表示。

Surface生成できる場合は簡易Surfaceも表示してよい。

CAD-quality surfaceは不要。

Camera positionはGeometry変更後も維持する。

---

# 52. TurboGrid Export

新規モジュール例：

```text
blade_designer/fileio/turbogrid_export.py
```

ユーザーがExportすると、

```text
<case_name>/
│
├ hub.curve
├ shroud.curve
├ profile.curve
└ BladeGen.inf
```

を生成する構造にする。

---

# 53. hub.curve

Hub Meridional Curveを、

```text
upstream
↓
downstream
```

の順で出力する。

Blade LEより上流、TEより下流まで含める。

---

# 54. shroud.curve

Shroudも同様に、

```text
upstream
↓
downstream
```

の順で出力。

---

# 55. profile.curve

Blade Profilesは、

```text
Hub
↓
Intermediate Span
↓
Tip
```

の順で出力。

各Profileはclosed contourとする。

輪郭順：

```text
LE
↓
PS
↓
TE
↓
SS reverse
↓
LE
```

既定point数：

```text
LE 21

PS 101

TE 21

SS 101
```

---

# 56. Closed Contour Point Duplication

Segment接続点の重複は一貫して処理する。

Segment別データでは各Segmentが指定point数を維持。

Closed contourでは接続点重複を削除する。

必要な場合のみ最後に最初のpointを再度追加する。

Export Option：

```text
Repeat first point at end
```

を用意してもよい。

Default：

```text
OFF
```

---

# 57. TurboGrid固有Format

TurboGrid固有のFile FormatはExporter内だけで扱う。

Geometry Engine側のデータ構造をTurboGrid形式に依存させない。

---

# 58. BladeGen.inf

`.inf` は正確な形式が確認できた場合だけ生成する。

現在インストールされているANSYS sample、既存TurboGrid sample、公式仕様等を確認できる場合、その形式に従う。

Formatを推測して作らないこと。

確認できない場合：

```text
hub.curve

shroud.curve

profile.curve
```

を確実にExportし、

`.inf` は、

```text
Not generated: exact format not verified.
```

と最終報告する。

---

# 59. TurboGrid Export Validation

Export前に以下をValidationする。

```text
No NaN

No Infinity

Hub/Shroud valid

Profile closed

Section order valid

Hub → Tip order valid

LE / TE valid

All coordinate arrays non-empty
```

---

# 60. Project Schema

Project schema：

```text
0.3
```

へ更新。

v0.1 / v0.2もロード可能とする。

Migration functionsを分離する。

例：

```python
migrate_v01_to_v02(...)

migrate_v02_to_v03(...)
```

---

# 61. v0.2 → v0.3 Migration

旧単一Blade Profileは、

```text
Hub

Tip
```

の両方へコピーして初期化してよい。

ただし既存、

```text
Blade Angle

Thickness

LE / TE

Output points

Significant digits
```

を失わないこと。

Meridional GeometryはDefault Flow Pathを与える。

---

# 62. 推奨新規Module

必要に応じて以下を追加。

```text
blade_designer/
│
├ geometry/
│  ├ meridional.py
│  ├ meridional_segments.py
│  ├ flow_path.py
│  ├ flow_area.py
│  ├ span.py
│  ├ blade_section.py
│  └ geometry_3d.py
│
├ fileio/
│  └ turbogrid_export.py
│
└ gui/
   ├ editor_stack.py
   ├ meridional_editor.py
   ├ flow_area_widget.py
   ├ section_selector.py
   └ preview_3d.py
```

既存構造との整合を優先し、必要なら名称を調整してよい。

---

# 63. 必須Unit Tests

追加：

```text
test_meridional_line.py

test_meridional_arc.py

test_meridional_arc_arc.py

test_meridional_tangent.py

test_meridional_length.py

test_flow_path.py

test_normalized_meridional.py

test_flow_area_axial.py

test_flow_area_radial.py

test_flow_area_general.py

test_component_stations.py

test_blade_sections.py

test_geometry_3d.py

test_turbogrid_export.py

test_project_migration_v03.py
```

---

# 64. Line Test

Known start point、angle、lengthから期待End Pointになること。

---

# 65. Arc Test

Known Radius / Sweepについて以下を検証。

```text
End Point

End Tangent

Arc Length
```

Arc Length：

```math
L =
R * abs(delta_phi)
```

---

# 66. Arc-to-Arc Tangency Test

例：

```text
Arc R20
↓
Arc R40
```

接続点：

```math
P1_end =
P2_start
```

接線：

```math
dot(T1_end, T2_start)
≈ 1
```

---

# 67. Line-Arc Tangency Test

以下について同じ検査。

```text
Line → Arc

Arc → Line
```

---

# 68. Meridional Length Test

Line / Arc混在Curveについて、

```text
m
```

が単調増加。

Total mが、

```text
sum(line lengths)
+
sum(arc lengths)
```

と一致すること。

---

# 69. Flow Coordinate Test

```text
INLET
m_flow_norm = 0
```

```text
OUTLET
m_flow_norm = 1
```

を確認。

各Blade Rowでは、

```text
LE
m_blade_norm = 0
```

```text
TE
m_blade_norm = 1
```

を確認。

---

# 70. Axial Flow Area Test

Known Hub radius：

```text
Rh
```

Known Shroud radius：

```text
Rs
```

について、

```math
A_reference =
pi*(Rs^2-Rh^2)
```

とFlow Area Engine結果を比較。

---

# 71. Radial Flow Area Test

Known radius：

```text
R
```

Known passage width：

```text
b
```

について、

```math
A_reference =
2*pi*R*b
```

と比較。

---

# 72. General Flow Area Test

斜めの単純Meridional passageを作成し、

```text
Area > 0

Area finite

m monotonic
```

を確認。

小さなGeometry perturbationでAreaが不連続にジャンプしないことも確認する。

---

# 73. Component Station Test

Station順序：

```text
INLET
<
IMP_LE
<
IMP_TE
<
DIF_LE
<
DIF_TE
<
OUTLET
```

を基本Validationとする。

特殊Geometryへ将来対応できるようValidation処理は独立関数にする。

---

# 74. PCHIP Test

Blade Angle / Thicknessの両方が共通Interpolatorを使用。

Control Pointを正確に通る。

単調Control Pointsで不要なovershootを作らない。

---

# 75. Output Point Test

Default：

```text
LE 21

PS 101

TE 21

SS 101
```

Segment exportで各point数が一致。

---

# 76. Significant Digits Test

Default：

```text
6
```

CSV / TurboGrid exportへ適用。

Export precision変更によって内部Geometry値が変わらないこと。

---

# 77. TurboGrid Export Test

Temporary directoryへ出力。

確認：

```text
hub.curve exists

shroud.curve exists

profile.curve exists

not empty

no NaN

no Inf

correct number of blade sections
```

---

# 78. GUI Manual Test

必ずManual Test ListをREADMEまたは別文書へ記載する。

確認項目：

```text
Blade View always visible

Blade Angle editor switching

Thickness editor switching

LE/TE editor switching

Meridional editor switching

Zoom retained after β modification

Zoom retained after thickness modification

Zoom retained after meridional modification

Fit View works

Hub/Shroud shown simultaneously

Component labels shown

Flow Area graph shown

Flow Area cursor linked to Meridional

Hub/Tip section switching

3D camera retained
```

---

# 79. 実装Stage 1

## Existing Project Inspection

最初に既存コードを確認。

確認内容：

```text
Data model

Geometry modules

GUI modules

Project schema

Existing tests

Existing export
```

その後、

```bash
pytest -q
```

を実行しInitial statusを記録。

---

# 80. Stage 2

## GUI Architecture

実装：

```text
Blade View always visible

Editor Stack

Context View

Fit View

View preservation
```

Geometry計算は変更しない。

---

# 81. Stage 3

## PCHIP統一

実装：

```text
Common Distribution Interpolator

Blade Angle → PCHIP

Thickness → PCHIP
```

既存Geometry Regression Testを通す。

---

# 82. Stage 4

## Meridional Segment Geometry

実装：

```text
Line

Circular Arc

Line-Line

Line-Arc

Arc-Line

Arc-Arc

G1 tangency

Meridional arc length
```

---

# 83. Stage 5

## Flow Path Topology

実装：

```text
INLET

IMP_LE

IMP_TE

DIF_LE

DIF_TE

OUTLET

Component Region
```

Meridional GUIへ表示。

---

# 84. Stage 6

## Flow Area Engine

実装：

```text
Mean Meridional Line

Local tangent

Cross-flow normal

Hub intersection

Shroud intersection

Passage length

Gross Area
```

Axial / Radial analytical testsを必ず通す。

---

# 85. Stage 7

## Flow Area GUI

実装：

```text
Area vs Normalized Flow Meridional

Station markers

Area ratio

Meridional cursor link

Area cursor link
```

---

# 86. Stage 8

## Blade Section Architecture

実装：

```text
Hub Section

Tip Section

Optional Intermediate Sections

Section selector

Copy Hub → Tip

Copy Tip → Hub
```

---

# 87. Stage 9

## 3D Blade Geometry

実装：

```text
βm(M)

Thickness(M)

LE

PS

TE

SS

R / Theta / Z

X / Y / Z
```

---

# 88. Stage 10

## 3D Preview

最低限Wireframe profilesを表示。

Camera preservationを実装。

---

# 89. Stage 11

## TurboGrid Export

実装：

```text
hub.curve

shroud.curve

profile.curve
```

`.inf`は形式確認できる場合のみ。

---

# 90. Stage 12

## Migration / Regression

v0.1 / v0.2 Projectをload。

すべてのpytestを実行。

---

# 91. v0.3完成条件

以下すべてを満たすこと。

```text
[PASS] Blade View always visible

[PASS] Editor switching

[PASS] Zoom/Pan preservation

[PASS] Fit View

[PASS] Blade Angle PCHIP

[PASS] Thickness PCHIP

[PASS] m_flow_norm

[PASS] m_blade_norm

[PASS] βm definition

[PASS] Hub Line/Arc Geometry

[PASS] Shroud Line/Arc Geometry

[PASS] Arc-to-Arc

[PASS] G1 tangency

[PASS] INLET station

[PASS] IMP_LE station

[PASS] IMP_TE station

[PASS] DIF_LE station

[PASS] DIF_TE station

[PASS] OUTLET station

[PASS] Component regions displayed

[PASS] Gross Flow Area

[PASS] Axial area analytical test

[PASS] Radial area analytical test

[PASS] Area graph

[PASS] Area/Meridional cursor link

[PASS] Hub Blade Profile

[PASS] Tip Blade Profile

[PASS] Intermediate Span compatible architecture

[PASS] LE points default 21

[PASS] PS points default 101

[PASS] TE points default 21

[PASS] SS points default 101

[PASS] Significant Digits default 6

[PASS] 3D Preview

[PASS] 3D camera preservation

[PASS] hub.curve

[PASS] shroud.curve

[PASS] profile.curve

[PASS] v0.1 migration

[PASS] v0.2 migration

[PASS] pytest 0 failure
```

---

# 92. v0.4へ残す項目

v0.3完了後は以下を次Version候補とする。

```text
Splitter Blade

Tip Clearance

Blade Blockage

Effective Flow Area

Lean

Sweep

Rake

Advanced spanwise interpolation

TurboGrid automatic meshing

Mesh quality check
```

その後、

```text
CFX setup
↓
CFX solve
↓
Post processing
↓
DOE
↓
Surrogate Model
↓
Optimization
```

へ進む。

---

# 93. 最終Architecture

v0.3完成時の基本データフロー：

```text
Hub / Shroud Segment Chain
        ↓
Flow Path Geometry
        ↓
Component Stations
        ↓
Meridional Distance
        ↓
Gross Flow Area
        ↓
Blade LE / TE
        ↓
Blade Normalized Meridional
        ↓
βm(M)
+
Thickness(M)
        ↓
Hub / Tip Blade Profile
        ↓
3D Blade Geometry
        ↓
Preview
        ↓
TurboGrid Export
```

---

# 94. 最終報告形式

実装終了時は以下を必ず報告する。

```text
1. Existing code inspection result

2. Modified files

3. New files

4. GUI architecture changes

5. View preservation implementation

6. PCHIP common interpolator

7. Meridional Line/Arc implementation

8. Arc-to-Arc G1 implementation

9. Flow Path station implementation

10. Component region implementation

11. Gross Flow Area algorithm

12. Axial analytical test result

13. Radial analytical test result

14. Hub/Tip Blade Section implementation

15. 3D geometry implementation

16. TurboGrid export implementation

17. .inf format verification status

18. Project migration

19. pytest result

20. Manual test result

21. Known issues

22. Remaining v0.4 items
```

テスト未実施の場合は「完成」と報告しないこと。

以上をCentrifugal Compressor Blade Designer v0.3の正本仕様として実装すること。