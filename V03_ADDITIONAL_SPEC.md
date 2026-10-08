# v0.3 ADDITIONAL REQUIREMENTS

既存のv0.3仕様へ以下を追加して実装すること。

---

# 1. Rotation Direction

回転方向をユーザーが変更可能にする。

Parameter：

```python
from enum import Enum


class RotationDirection(Enum):
    CCW = "ccw"
    CW = "cw"
```

GUI表示：

```text
Rotation Direction

○ CCW
○ CW
```

回転方向の基準は、

```text
Viewed from +Z axis
```

とGUIおよびREADMEへ明記すること。

---

# 2. Rotation Direction Sign

内部数学座標系の正のtheta方向をCCWとする。

```python
rotation_sign = +1.0  # CCW
rotation_sign = -1.0  # CW
```

Blade Camber計算：

```math
dtheta/dm =
rotation_sign * tan(beta_m) / r
```

とする。

Rotation Directionを変更した場合、Blade Angle control point値そのものを書き換えないこと。

例えば、

```text
CCW
↓
CW
```

へ変更した場合は同じβ分布を使用してBladeのhandednessだけを反転させる。

これにより形状はLEを基準としてcircumferential方向へmirrorされる。

---

# 3. Rotation Direction適用範囲

Rotation Direction変更を以下すべてへ適用する。

```text
2D Blade Geometry

Hub Profile

Tip Profile

Intermediate Span Profiles

Full Annulus

3D Preview

PS / SS mapping

TurboGrid Export
```

表示だけをmirrorして内部座標が変わらない実装は禁止。

Export座標にも正しく反映すること。

---

# 4. Reverse Rotation command

ToolbarまたはGeometry Editorへ、

```text
Reverse Rotation
```

を追加してよい。

操作すると、

```text
CCW ↔ CW
```

を切り替える。

この操作もUndo対象とする。

---

# 5. Undo / Redo

アプリ全体へUndo / Redoを実装する。

PySide6の、

```python
QUndoStack
QUndoCommand
```

を基本として使用する。

MainWindowに、

```python
self.undo_stack = QUndoStack(self)
```

を持たせる。

---

# 6. Undo対象

最低限以下をUndo / Redo可能にする。

```text
Blade Angle control point変更

Blade Angle point追加

Blade Angle point削除

Thickness control point変更

Thickness point追加

Thickness point削除

LE parameter変更

TE parameter変更

Hub Meridional segment変更

Shroud Meridional segment変更

Meridional segment追加

Meridional segment削除

Meridional segment並べ替え

Impeller LE位置変更

Impeller TE位置変更

Diffuser LE位置変更

Diffuser TE位置変更

Rotation Direction変更

Hub/Tip Section copy

Span Section追加

Span Section削除
```

---

# 7. Undo GUI

以下を実装。

```text
Edit
 ├ Undo
 └ Redo
```

Shortcut：

```text
Undo
Ctrl+Z

Redo
Ctrl+Y
```

可能なら、

```text
Ctrl+Shift+Z
```

もRedoとして使用可能にする。

Toolbarにも、

```text
Undo
Redo
```

buttonを配置する。

---

# 8. Continuous DragのUndo

非常に重要。

Control Pointをマウスドラッグする場合、マウス移動1回ごとにUndo commandを作成してはならない。

以下とする。

```text
mouse press
↓
initial value保存
↓
drag中
real-time geometry update
↓
mouse release
↓
final value保存
↓
1個のUndoCommandとして登録
```

例えばβ Control Pointを、

```text
58
→57.9
→57.2
→56.4
→55
```

とドラッグしても、Ctrl+Zを1回押せば、

```text
55 → 58
```

へ戻ること。

---

# 9. Numeric input Undo

SpinBox等も1クリックごとではなく、原則として、

```text
editingFinished
```

時点で1操作として登録する。

リアルタイム表示は維持してよい。

---

# 10. Undo History

Projectを、

```text
New
Open
```

した場合はUndo historyをclearする。

Project Saveではhistoryをclearしない。

Undo stackの最大数は適切な値を設定する。

例：

```text
200 commands
```

---

# 11. 3D Preview Wireframe

3D PreviewではBlade profileだけをSpan方向に並べるのではなく、

**HubからTipまで同じ座標順番の点を接続するSpanwise lineを表示する。**

---

# 12. Coordinate topology

すべてのBlade Sectionで同じSegment topologyを使用する。

```text
LE
PS
TE
SS
```

Point数も同じ設定を使用する。

Default：

```text
LE = 21
PS = 101
TE = 21
SS = 101
```

各Sectionで同じSegment内の同じindexは対応点として扱う。

例：

```text
Hub PS point 30
↓
Span 25% PS point 30
↓
Span 50% PS point 30
↓
Span 75% PS point 30
↓
Tip PS point 30
```

を線で接続する。

---

# 13. Spanwise Wireframe

3D Previewでは最低限2種類のlineを表示する。

### Profile lines

各Span断面のBlade contour：

```text
Hub profile

Intermediate profiles

Tip profile
```

### Spanwise lines

同じsegment / same indexをSpan方向へ接続：

```text
Hub
 ↓
Intermediate
 ↓
Tip
```

これによりBlade surface shapeがWireframeとして視認できるようにする。

---

# 14. 3D Wireframe example

概念：

```text
             Tip profile
       ┌─────────────────┐
      /│ / / / / / / / /│
     / │/ / / / / / / / │
    /  / / / / / / / /  │
   /  / / / / / / / /   │
  └───────────────────────┘
       Hub profile
```

Profile方向とSpan方向の両方のgrid lineを表示する。

---

# 15. Intermediate Sections

HubとTipしかない場合、

```text
Hub point i
────────────
Tip point i
```

を直線で接続してよい。

Intermediate Span Sectionが存在する場合、

```text
Hub
↓
Span section 1
↓
Span section 2
↓
Tip
```

をPolylineで接続する。

---

# 16. Spanwise correspondence

単純なclosed-contour global indexだけに依存しないこと。

内部では、

```text
segment = LE / PS / TE / SS

segment_fraction

segment_index
```

を保持する。

例えば、

```text
PS index 40
```

はすべてのSpan Sectionで同じNormalized PS位置を意味すること。

これによりSpan方向接続が安定する。

---

# 17. 3D Preview Controls

最低限以下を表示切替可能にする。

```text
Show Profiles        ON

Show Spanwise Lines  ON

Show Surface         optional

Show Hub Curve       ON

Show Shroud Curve    ON
```

Default：

```text
Profiles       ON
Spanwise       ON
Hub/Shroud     ON
Surface        OFFまたはON
```

どちらでもよいがWireframeは常に確認可能にする。

---

# 18. 3D Camera Preservation

既存要求どおり、Geometry変更時にCamera位置をリセットしない。

特にβ、Thickness、LE/TE Stationを編集しながら同じ視点で形状変化を確認できること。

---

# 19. Blade Edge Station Architecture

Impeller LE / TEを単一のFlow Path station値だけで定義しない。

Impeller Blade EdgeはHub側とShroud側で別々のMeridional位置を持つ。

Data model例：

```python
@dataclass
class BladeEdgePosition:
    hub_m_flow_norm: float
    shroud_m_flow_norm: float


@dataclass
class BladeRowEdgeParameters:
    leading_edge: BladeEdgePosition
    trailing_edge: BladeEdgePosition
```

Impeller：

```python
impeller_edges: BladeRowEdgeParameters
```

Diffuserについても同じ構造を使用可能にする。

---

# 20. Impeller LE

Leading Edgeは、

```text
LE Hub Point
LE Shroud Point
```

を持つ。

両点はそれぞれ、

```text
Hub Meridional Curve
Shroud Meridional Curve
```

上に拘束する。

ユーザーが自由なR-Z空間へ移動できないようにする。

---

# 21. Impeller TE

Trailing Edgeも同じ。

```text
TE Hub Point
TE Shroud Point
```

を独立指定可能とする。

---

# 22. Meridional GUI Blade Edge

Meridional View上に、

```text
Impeller LE

Impeller TE

Diffuser LE

Diffuser TE
```

をBlade Edge Lineとして表示する。

概念：

```text
Shroud
────────●────────────●────────────────
        ╲            ╲
         ╲ LE         ╲ TE
          ╲            ╲
───────────●────────────●──────────────
Hub
```

---

# 23. Edge endpoint drag

Blade EdgeのHub/Shroud endpointをマウスドラッグできるようにする。

Drag中は、

**対応するHubまたはShroud Meridional Curve上のみ移動可能**

とする。

Nearest point / curve parameterを求めてCurveへprojectする。

---

# 24. Edge numeric editor

ドラッグ操作以外に数値入力も用意する。

例：

```text
Impeller Blade Edge

Leading Edge

Hub Mflow       0.180000
Shroud Mflow    0.125000

Trailing Edge

Hub Mflow       0.510000
Shroud Mflow    0.545000
```

表示桁数はGUI用として適切に設定してよい。

Export significant digits設定とは分離する。

---

# 25. Blade Edge interpolation across span

Hub / Shroud edge位置から、各SpanでのLE / TE Meridional位置を求める。

v0.3では初期方式として、

```math
m_edge(span) =
(1-span) * m_edge_hub
+
span * m_edge_shroud
```

相当の補間を使用してよい。

ただし物理m距離または適切なMeridional parameter上で補間し、実装を独立関数にする。

将来的に、

```text
Intermediate edge control

Curved LE

Curved TE
```

へ拡張可能にする。

---

# 26. Each-section Normalized Meridional

各Span Sectionでは、そのSection固有の、

```text
m_LE(span)

m_TE(span)
```

を持つ。

Blade normalized meridional：

```math
m_blade_norm =
(m - m_LE(span))
/
(m_TE(span) - m_LE(span))
```

とする。

したがって全Sectionで、

```text
LE = 0
TE = 1
```

になる。

---

# 27. β / Thicknessとの関係

Blade AngleおよびThicknessは、

```text
m_flow_norm
```

ではなく、

```text
m_blade_norm
```

に対して定義する。

したがってLE/TE Station位置を変更しても、

```text
β control point M=0
β control point M=1
```

は常に新しいLE/TEへ追従する。

Thicknessも同様。

---

# 28. Blade Edge validation

最低限以下を検査する。

```text
0 <= LE hub <= 1

0 <= LE shroud <= 1

0 <= TE hub <= 1

0 <= TE shroud <= 1
```

各Spanについて、

```text
m_TE(span) > m_LE(span)
```

でなければERROR。

LE/TE Lineが不自然に交差する場合もERROR。

---

# 29. Component stationとの区別

以下を区別すること。

```text
Blade Edge Position
```

と、

```text
Flow Path Component Boundary
```

を完全に同じデータとして持たない。

例えばImpeller Regionは、

```text
Impeller LE edge
Impeller TE edge
```

を基準に表示してよいが、内部的にはBlade Edge geometryとして管理する。

LE/TEが傾いている場合、Component Region boundaryも傾いたBlade Edge Lineとして表示する。

---

# 30. Diffuser Edge

Vaned Diffuserについても同じBladeEdgePositionモデルを使用する。

Radial diffuserでは通常Hub/Shroudで近い位置になるが、

```text
hub position
shroud position
```

を独立保持可能とする。

---

# 31. Undo対象追加

以下もUndo対象とする。

```text
LE Hub endpoint drag

LE Shroud endpoint drag

TE Hub endpoint drag

TE Shroud endpoint drag

Rotation reversal
```

Drag操作全体を1 Undo Commandとして扱う。

---

# 32. Required tests

以下を追加する。

```text
test_rotation_direction.py

test_undo_commands.py

test_spanwise_wireframe.py

test_blade_edge_position.py

test_blade_edge_span_interpolation.py

test_blade_normalized_meridional.py
```

---

# 33. Rotation test

同一Blade Parameterについて、

```text
CCW geometry
CW geometry
```

を生成。

LE基準のcircumferential displacementについて、

```math
delta_theta_CW
≈
-delta_theta_CCW
```

となること。

---

# 34. Blade Edge test

Known Hub / Shroud edge positionsから、

```text
span = 0
→ Hub position

span = 1
→ Shroud position
```

になること。

中間Spanが期待する補間値になること。

---

# 35. Blade Normalized Meridional test

各Spanで、

```text
LE → 0

TE → 1
```

になること。

HubとTipでLE/TE physical positionが異なっていても成立すること。

---

# 36. Spanwise Wireframe test

全Sectionで、

```text
LE points

PS points

TE points

SS points
```

のtopologyが一致すること。

同一Segment / same indexをSpan方向へ接続できること。

Index mismatchを黙って無視しない。

---

# 37. Manual test additions

以下をManual Testへ追加。

```text
Reverse rotation and observe immediate mirror

Undo rotation

Redo rotation

Drag beta point and undo once

Drag thickness point and undo once

Drag Impeller LE Hub endpoint

Undo LE drag

Hub/Tip LE positions different

Hub/Tip TE positions different

3D wireframe shows profile lines

3D wireframe shows hub-to-tip corresponding point lines

3D camera remains fixed while LE/TE changes
```

以上を既存v0.3仕様へ追加して実装すること。