# READY_FOR_CODEX
# Centrifugal Compressor Blade Designer
## v0.4 — CAD Export / Blade Root Fillet / ANSYS Integration

### 0. 実装目的

既存のPython製「Centrifugal Compressor Blade Designer」へ、3D CAD形状生成・Fillet・ANSYS向けExport機能を追加する。

対象は遠心圧縮機のインペラとする。

**今回の固定設定**

| Parameter | Value |
|---|---|
| Hub Fillet Enabled | True |
| Shroud Fillet Enabled | False |
| Hub Fillet Radius | 8.0 mm |
| Fillet Geometry | True CAD Fillet |
| Export Target | Mechanical + TurboGrid |
| CAD Length Unit | mm |
| Rotation Axis | Z |
| Initial Blade Type | Open Impeller |

すでに実装したGeometry Engine、Meridional、Blade Angle、Thickness、Stacking、Rake、LE/TE、Span Layer、3D Preview、Undo/Redo、Project Save/Load、TurboGrid Profile Exportを維持する。

既存機能が未実装の場合は、現状を調査し、依存する機能を実装した上でCADへ進むこと。

既存コードを全面的に再作成しないこと。

---

# 1. 実装の基本方針

Geometry処理を以下の3階層に分ける。

### Layer 1：Blade Geometry Engine

既存機能を使用する。

- Hub/Shroud Meridional
- LE/TE Edge Curves
- Span Layers
- β distribution
- Thickness distribution
- Stacking
- Lean/Rake
- PS/SS
- LE/TE
- XYZ coordinate generation

この層ではCADライブラリに依存しない。

### Layer 2：CAD Geometry Engine

新しく追加する。

- B-spline/NURBS surface
- Blade Solid
- Hub Disk Solid
- Boolean Union
- Root Fillet
- CAD Geometry Validation

### Layer 3：Export Engine

以下に分ける。

- Mechanical STEP Export
- TurboGrid CAD Export
- TurboGrid Profile Points Export
- CAD Validation Report

CAD生成とファイル出力を同じ関数へまとめないこと。

---

# 2. CADライブラリ

第一候補はCadQuery + Open CASCADE（OCP）とする。

必要な機能：

- 曲線生成
- 曲面Loft
- Surface sewing
- Solid生成
- Boolean Union
- 3D Fillet
- STEP書込み
- STEP再読込み
- BREP妥当性検査

CadQueryで対応が難しい曲面構築はOpen CASCADEの低レベルAPIを使用してよい。

候補：

- BRepOffsetAPI_ThruSections
- BRepBuilderAPI_Sewing
- BRepAlgoAPI_Fuse
- BRepFilletAPI_MakeFillet
- BRepCheck_Analyzer
- STEPControl_Writer
- STEPControl_Reader

APIは実際にインストールしたバージョンに合わせて確認すること。

CadQueryが既存Python環境と競合する場合は、CAD計算を独立プロセスに分ける。

FreeCAD Pythonを代替Backendとして採用してもよい。

ただし、CadQuery/FreeCADの両方を最初から完全実装する必要はない。

最初に実際に動作するCAD Backendを1種類確定すること。

---

# 3. CAD Backendの独立化

抽象Interfaceを設計する。

例：

```python
class CadBackend(Protocol):
    def create_surface(self, ...): ...
    def create_blade_solid(self, ...): ...
    def create_hub_solid(self, ...): ...
    def boolean_union(self, ...): ...
    def apply_fillet(self, ...): ...
    def validate_solid(self, ...): ...
    def export_step(self, ...): ...
    def read_step(self, ...): ...
```

CADライブラリ固有のShapeオブジェクトを既存のGeometry Engineへ渡さないこと。

CADライブラリをインストールできない環境でも、既存の翼座標編集機能は正常に動作すること。

---

# 4. CAD Parameter Model

以下のデータモデルを追加する。

```python
from dataclasses import dataclass
from enum import Enum


class FilletMode(Enum):
    TRUE_CAD = "true_cad"
    NONE = "none"


class MechanicalExportScope(Enum):
    BLADE_ONLY = "blade_only"
    BLADE_HUB = "blade_hub"
    PERIODIC_SECTOR = "periodic_sector"
    FULL_IMPELLER = "full_impeller"


@dataclass
class FilletParameters:
    hub_enabled: bool = True
    shroud_enabled: bool = False
    hub_radius_mm: float = 8.0
    mode: FilletMode = FilletMode.TRUE_CAD


@dataclass
class CadExportParameters:
    mechanical_enabled: bool = True
    turbogrid_enabled: bool = True
    step_enabled: bool = True
    length_unit: str = "mm"
    rotation_axis: str = "Z"
    fillet: FilletParameters | None = None
```

`fillet` の実際のDefault Factoryは安全なDataclass方式で実装すること。

既存Project保存との互換性を維持する。

---

# 5. CAD出力対象

3つのモデルを区別する。

### A. Blade Only Solid

1枚の翼単体のソリッド。

構成：

- Pressure Surface
- Suction Surface
- Leading Edge
- Trailing Edge
- Hub側端面
- Tip側端面

主に形状検査用。

### B. Blade + Hub Disk Solid

翼とHubディスクを一体化したソリッド。

Hub Root Filletを付ける対象。

今回のMechanical用基本モデル。

### C. Full Impeller Solid

全周の翼とHubディスクを含むソリッド。

翼枚数に応じて周方向へ配置する。

周期セクタモデルも生成可能とする。

処理順：

Blade Only → Blade + Hub → Fillet → Sector / Full Impeller

---

# 6. Hubディスクの構造形状

現在のMeridional Hub Curveは、流体が接する面である。

これだけではMechanical用の閉じたディスクソリッドを生成できない。

CADモデルには追加で以下が必要。

- Hub流路面
- Disk backside profile
- Bore内径
- Diskの軸方向端面
- その他必要な接続面

`DiskGeometryParameters` を追加する。

構造ディスク形状は、R-Z平面で閉じた断面として定義し、Z軸回転でソリッド生成すること。

既存のLine/Arc Segment ChainをDisk Backsideにも再利用できる構造が望ましい。

**重要：ディスク裏面形状、板厚、内径を根拠なく推定してはならない。**

ユーザー入力が不足している場合：

- Blade Onlyの生成は許可
- Hub Disk + Filletの生成は実行しない
- 必須入力が不足していることをGUIに表示
- Mechanical完成モデルとして出力成功扱いにしない

Unit Test用には独立したサンプルディスク形状を用意してよい。

---

# 7. Blade CAD Surface生成

既存のSpan Layerと対応座標を利用する。

基本パラメータ：

\[
\mathbf X(\xi,s)
\]

- \(\xi=0\)：LE
- \(\xi=1\)：TE
- \(s=0\)：Hub
- \(s=1\)：Tip

生成する曲面：

- PS Surface
- SS Surface
- LE Surface
- TE Surface

内部では対応するSegment別座標を保持する。

異なるSpan断面で同じSegment/同じNormalized位置が対応するようにする。

---

# 8. B-spline Surface

各Span Layerの対応点を用いて曲面を生成する。

入力データ例：

```python
ps_points[span_index, streamwise_index, xyz]
ss_points[span_index, streamwise_index, xyz]
```

既存の高密度形状データをCAD曲面の基準とする。

出力Point数21/101/21/101に依存したCAD曲面生成は避ける。

必要な補間方式：

- B-spline曲線
- Span方向Loft
- 必要に応じてNURBS近似

元の点列からの最大形状偏差を評価する。

CAD曲面の滑らかさと、元の設計座標への忠実度を両立すること。

CAD用の曲面公差を独立設定にする。

初期値はCAD Backendの挙動を確認して決定すること。

---

# 9. LE/TE曲面

LE/TEについて既存の形状定義を維持する。

- Circular
- Elliptical
- Cutoff

ただし、True CAD FilletとLE/TEの組合せによってはCAD処理が失敗する可能性がある。

LE/TE曲面はPS/SSと正しい向きで接続する。

滑らかな接続が設計上必要な場合は、法線・接線の連続性を評価する。

単純に開いたPS/SSの端を平面で閉じて、正常なLE/TE曲面ができたと扱わないこと。

---

# 10. Blade Solid生成

次の順番で行う。

1. PS Surface生成
2. SS Surface生成
3. LE Surface生成
4. TE Surface生成
5. Hub側端面生成
6. Tip側端面生成
7. Surface Sewing
8. Closed Shell生成
9. Solid生成

完成後、以下をValidationする。

- Closed shell
- Valid BREP
- Watertight
- Nonzero volume
- No self-intersection
- No inverted faces

失敗した場合は該当Surfaceを報告する。

---

# 11. Hub Solid生成

Hubの流体接触面とDisk Backsideを用いて閉じた回転体ソリッドを生成する。

既存のHub Meridional Curveと一致する領域が、翼根元の接続面になる。

HubとBladeの接続には、Boolean演算が成立するようにモデルを構成すること。

必要であれば、翼をHub内部へ微小に延長して交差を確保してよいが、延長量はCAD公差とモデル寸法に基づいて決め、元の設計面の位置を変えないこと。

使用した延長量をValidation Reportへ記録すること。

---

# 12. Blade + Hub Boolean Union

Blade SolidとHub Solidを結合する。

結合後：

- 単一の連続したSolidであること
- 不要な内部面がないこと
- 接続位置に隙間がないこと
- 異常な自己交差がないこと

を検査する。

Boolean Unionに失敗した場合、Root Fillet処理へ進まない。

CAD Kernelの例外内容を記録すること。

---

# 13. Hub Root Fillet

今回の最重要機能。

設定：

```text
Hub Fillet Enabled = True
Hub Fillet Radius = 8.0 mm
Fillet Mode = True CAD
```

翼とHubが接続するRoot Edgeにフィレットを生成する。

対象は基本的に：

- PSとHubの接続部
- SSとHubの接続部
- LE付近の接続部
- TE付近の接続部

とする。

全周のRoot Edgeを一貫して処理すること。

---

# 14. Filletアルゴリズム

Open CASCADEの3D Fillet処理を使用する。

候補：

```python
BRepFilletAPI_MakeFillet
```

またはCadQueryの3D Fillet API。

**単純な描画上の丸みや三角形メッシュの平滑化ではなく、実際のCAD BREP上にフィレット曲面を生成すること。**

True CAD Filletは、Mechanical用STEPを再読込みしたときにもフィレット面として認識できることが必要。

フィレット半径は8.0 mmである。

---

# 15. Root Edgeの自動識別

CAD Edgeを配列番号だけで選択してはならない。

Boolean後のEdge番号は形状変更で変わることがある。

Root Edge判定には：

- Hub接触面
- Blade接触面
- Edgeの幾何位置
- 隣接Faceの属性
- 必要に応じてCAD KernelのShape History

を使用する。

可能ならCAD Surface生成時から以下のSemantic IDを保持する。

```text
BLADE_PRESSURE
BLADE_SUCTION
BLADE_LE
BLADE_TE
HUB_FLOW_SURFACE
ROOT_PS
ROOT_SS
```

これらを利用してフィレット対象を識別する。

複数候補があって一意に判断できない場合、任意のEdgeへフィレットを適用しない。

---

# 16. 8 mm Filletの成立性検査

以下を検査する。

- Hub周辺の局所曲率
- 翼厚
- LE/TE近傍の曲率
- 隣接翼との干渉
- Root Filletの自己交差
- フィレット曲面の異常縮退
- Hubとの接続状態

**フィレット半径8 mmが幾何学的に成立しない可能性を必ず考慮すること。**

8 mmの指定が成立しない場合：

- 勝手に6 mmや4 mmへ変更しない
- フィレットなし形状を正常な8 mmモデルとして出力しない
- CAD処理失敗の原因を表示する
- Fillet失敗位置を可能な限り特定する
- ユーザーが再設計できる情報を提供する

小さな半径での試行は、診断目的に限って許可する。

---

# 17. Fillet失敗時の処理

例外を以下に分類する。

```python
class CadGeometryError(Exception):
    pass


class SurfaceConstructionError(CadGeometryError):
    pass


class BooleanUnionError(CadGeometryError):
    pass


class FilletGenerationError(CadGeometryError):
    pass


class InvalidSolidError(CadGeometryError):
    pass


class CadExportError(CadGeometryError):
    pass
```

失敗した場合は：

1. GUIへエラー表示
2. ログへ詳細記録
3. 可能ならフィレット直前のCAD形状をDebug保存
4. Projectデータは変更しない
5. 既存の有効なExportファイルを不正なファイルで上書きしない

Debug用モデルには `NO_FILLET` 等の名称を付け、完成モデルと明確に区別すること。

---

# 18. Mechanical用STEP Export

Mechanical用出力では、真の3D CAD Solidを使用する。

対象モデル：

```text
Blade + Hub Disk + Root Fillet
```

出力形式：

```text
STEP
```

ファイル例：

```text
impeller_mechanical_R8.step
```

出力前にSolid Validationが成功していること。

今回の8 mmフィレットが生成されなかった場合は、この完成ファイルを作成しない。

---

# 19. Mechanical用モデル範囲

以下の3種類を設計上サポートする。

### Blade + Hub

単翼とHubディスクのモデル。

### Periodic Sector

翼1ピッチ分とHubセクタを持つモデル。

翼枚数Nの場合：

\[
\Delta\theta=\frac{360^\circ}{N}
\]

### Full Impeller

N枚の翼を周方向へ複製した一体モデル。

最初にBlade + Hubを完成させ、その後Periodic SectorとFull Impellerに進むこと。

Periodic Sectorでは周期境界面を正しく作成する。

Sector切断面の幾何学形状とフィレットの干渉にも注意する。

---

# 20. STEP Export Verification

STEP書込み後に、同じCAD Backendで再読込みする。

確認：

- ファイル存在
- ファイル非空
- 読込み成功
- Solid数
- Volume
- Bounding Box
- BREP Validity
- Units

Export前後の体積・寸法を比較する。

許容差はモデル寸法とCAD公差に応じて設定し、レポートする。

STEP Exportに成功しただけでValidation PASSとしてはならない。

---

# 21. TurboGrid出力方式

TurboGrid用は2種類の出力経路を用意する。

**経路A：Profile Points方式**

既存形式を使用する。

```text
BladeGen.inf
hub.curve
shroud.curve
profile.curve
```

**経路B：CAD方式**

生成したCAD曲面・フィレット付き翼形状から、TurboGridが読み込めるCADモデルを作成する。

TurboGridへの直接CAD読込みは対応ファイル形式を検証すること。

Parasolid等への変換が必要な場合、外部CADソフトを利用する独立した変換処理を用意する。

---

# 22. TurboGrid Profile Points Export

既存のProfile Export機能を維持する。

最低限：

```text
hub.curve
shroud.curve
profile.curve
BladeGen.inf
```

を出力する。

各ProfileはHubからShroudへの順序を維持する。

LE/TEには必要に応じてTurboGrid形式のタグを付ける。

LE/PS/TE/SSの点数：

```text
LE = 21
PS = 101
TE = 21
SS = 101
```

出力有効数字：

```text
6
```

ただしCAD曲面は、このExport用点数とは独立して生成する。

---

# 23. Profile PointsとFilletの区別

**Profile Pointsファイルだけでは、今回Pythonで生成した8 mmのRoot Fillet曲面を完全には表現できない。**

従来の`.curve`出力には、原則としてフィレット前の翼形状を保存する。

TurboGridでフィレットを必要とする場合は、以下のいずれかを使用する。

A. TurboGrid側でCAD From Profile Points + Blade Blendを実行する。

B. Python側で生成したフィレット付きCADをTurboGridへ取り込む。

Aの場合、ANSYSが生成するBlade BlendとPythonのCAD Filletが幾何学的に完全一致する保証はない。

MechanicalとCFDで同一フィレット形状を使用したい場合は、可能な限りBを優先する。

---

# 24. TurboGrid True Blend

TurboGrid側でBlade Blendを生成する経路も残す。

設定例：

```text
Hub Blend = Enabled
Rolling Ball Radius = 8 mm
Shroud Blend = Disabled
Blend Style = True Blend
```

ただしこれはTurboGridで実行する設定であり、PythonのCAD Fillet APIと同一のアルゴリズム・結果を意味しない。

True Blendのメッシュ生成にはANSYS側の対応トポロジーが必要となる。

対象ANSYSバージョンとBlade CAD生成ライセンスを検証すること。

Pythonアプリ単体でANSYS CAD生成を実行したと偽ってはならない。

---

# 25. TurboGrid CAD Geometry

TurboGrid CADモードへ取り込むために、以下を区別する。

- Blade CAD surfaces
- Hub flow surface
- Shroud flow surface
- Hub root fillet surface
- Inlet/Outlet boundaries
- 必要な周期境界

Mechanical用のディスクソリッドを、そのままTurboGrid用の流体境界として使用しないこと。

TurboGridでは流体流路の境界面が必要になる。

必要に応じて、同じCAD BREPから流路側の面を抽出する。

---

# 26. CAD Surface Classification

CAD GeometryにSemantic Labelを保持する。

例：

```text
HUB
SHROUD
BLADE_PS
BLADE_SS
BLADE_LE
BLADE_TE
HUB_FILLET_PS
HUB_FILLET_SS
INLET
OUTLET
PERIODIC_LOW
PERIODIC_HIGH
```

ANSYS側への受け渡しでNamed Selectionが利用可能なら、対応付ける。

ただしSTEPにNamed Selectionが確実に保持されるとは限らない。

GUIまたはドキュメントからANSYS側で確認できるようにする。

---

# 27. TurboGrid CAD Export Validation

CAD Exportが成功した場合でも、TurboGrid Importが必ず成功するとは限らない。

最低限以下を分けて検証する。

### Python側

- Valid CAD Geometry
- Required surfaces存在
- Root Fillet存在
- No missing surfaces
- No surface intersections
- Unit consistency

### ANSYS側

- CAD Import成功
- Hub/Shroud認識
- Blade認識
- Complex Blade End認識
- Fillet geometry認識
- Mesh generation成功
- Mesh quality確認

ANSYSを実行できない環境では、ANSYS側を `NOT_TESTED` とする。

---

# 28. CAD Export GUI

既存アプリに以下のEditorを追加する。

```text
CAD / Fillet
```

表示項目：

```text
CAD Backend
[ CadQuery / Open CASCADE ]

Hub Fillet
[x] Enabled

Hub Fillet Radius
[ 8.0 ] mm

Shroud Fillet
[ ] Enabled

Fillet Mode
[ True CAD ]

Mechanical Export
[x] Enabled

TurboGrid Export
[x] Enabled

Mechanical Model Scope
[ Blade + Hub ]

Export Format
[ STEP ]

[ Validate CAD ]

[ Generate CAD ]

[ Export Mechanical ]

[ Export TurboGrid ]

[ Export Both ]
```

---

# 29. GUIの実行順序

GUI操作は以下を想定する。

```text
Geometry Parameters
        ↓
Generate 3D Blade
        ↓
Generate CAD Surfaces
        ↓
Generate Solids
        ↓
Generate Fillet R8
        ↓
Validate CAD
        ↓
Export Mechanical / TurboGrid
```

CADモデル生成中にGUIがフリーズしないよう、Worker Threadまたは別プロセスを使用する。

CAD計算中にユーザーが設計条件を変更した場合でも、出力には開始時点のパラメータSnapshotを使用すること。

中途半端に異なる形状パラメータが混在したファイルを作らないこと。

---

# 30. CAD Preview

既存の3D Previewを拡張する。

表示切替：

```text
[ ] Wireframe
[x] CAD Blade Surfaces
[x] Hub Disk
[x] Root Fillet
[ ] Full Impeller
[ ] Surface Edges
```

CAD Geometryと元の設計Wireframeを重ねて比較可能にする。

Fillet R8の部分を選択すると半径情報を表示できる構造とする。

既存要求どおり、Geometry変更時にCamera位置を自動リセットしない。

---

# 31. CAD Geometry Validation

新規モジュール：

```text
cad_validation.py
```

を追加する。

検査項目：

- Surface construction validity
- Face orientation
- Surface gaps
- Shell closure
- Solid validity
- Boolean result
- Fillet validity
- Positive volume
- Self-intersection
- Inter-blade interference
- Units
- STEP round-trip

検査結果はPASS / WARNING / FAILに分類する。

CAD Kernelの妥当性検査だけでなく、設計座標との差分も検査すること。

---

# 32. Fillet Validation

フィレット付きSolidに対し、以下を追加確認する。

- Root Fillet Surface存在
- Root FilletがHubへ接続
- Root FilletがBladeへ接続
- 接続部に隙間がない
- 不正な縮退面がない
- 隣接翼と交差しない
- R8指定が処理に使用されている

フィレットの全箇所で所定の円弧半径を厳密に検証できない場合は、CAD KernelによるFillet成功判定と追加の断面計測結果を記録し、未確認項目を明記する。

---

# 33. CAD Validation Report

JSON形式のレポートを出力する。

例：

```json
{
  "geometry_type": "impeller",
  "export_target": "both",
  "cad_unit": "mm",
  "hub_fillet_enabled": true,
  "hub_fillet_radius_mm": 8.0,
  "shroud_fillet_enabled": false,
  "cad_surface_status": "PASS",
  "boolean_status": "PASS",
  "fillet_status": "PASS",
  "solid_validity": "PASS",
  "step_roundtrip": "PASS",
  "mechanical_import": "NOT_TESTED",
  "turbogrid_import": "NOT_TESTED",
  "turbogrid_mesh": "NOT_TESTED"
}
```

これはレポートSchemaの例であり、未実行の検査を自動的にPASSへ設定してはならない。

レポートには可能な限り以下も記録する。

- CAD Backendとバージョン
- Geometry Parameter SnapshotのHash
- Volume
- Surface Area
- Bounding Box
- Fillet生成条件
- エラー内容
- 処理日時
- 実行した検査一覧

---

# 34. 出力ディレクトリ構造

Export例：

```text
case_name/
│
├ mechanical/
│   ├ impeller_mechanical_R8.step
│   └ import_instructions.md
│
├ turbogrid/
│   ├ profile_points/
│   │   ├ BladeGen.inf
│   │   ├ hub.curve
│   │   ├ shroud.curve
│   │   └ profile.curve
│   │
│   ├ cad/
│   │   ├ turbogrid_cad.step
│   │   └ cad_import_instructions.md
│   │
│   └ blade_blend_settings.md
│
├ validation/
│   ├ cad_validation.json
│   └ cad_validation.txt
│
└ parameters/
    └ geometry_snapshot.json
```

CADファイル名は実際に生成できた形式に合わせて調整する。

TurboGrid向けParasolidが生成可能なBackendまたは外部変換環境が確認できた場合のみ`.x_t`/`.x_b`を出力する。

STEPを単純に拡張子変更してParasolidとして扱わないこと。

TurboGrid用CADは流路境界として必要な幾何要素を含むことがValidation条件であり、単にSTEPが生成されたことをもってTurboGrid対応完了とはしない。

---

# 35. Export Status

各成果物の生成状況を個別に管理する。

例：

```text
Mechanical STEP
PASS

TurboGrid Profile Points
PASS

TurboGrid CAD STEP
PASS

TurboGrid Parasolid
UNAVAILABLE

TurboGrid CAD Import
NOT_TESTED
```

一部の出力に失敗した場合でも、他の正常な出力を失わないようにする。

ただし `Export Both` の全体ステータスは、要求した成果物のすべてが揃っていない場合、完全成功としない。

---

# 36. Undo / Redo

今回の追加パラメータもUndo/Redoの対象とする。

- Fillet Enabled変更
- Fillet Radius変更
- CAD Model Scope変更
- Disk Geometry変更
- CAD Output Parameters変更

既存のQUndoStackを再利用する。

CAD計算の実行結果そのものをUndoする必要はないが、設計パラメータはUndo可能とする。

---

# 37. Project Save / Load

CAD設定を既存Project Schemaへ追加する。

既存v0.1～v0.3 Projectを読み込んだ場合でもエラーにしない。

新しいCAD設定にはDefault値を適用する。

```text
Hub Fillet Enabled = true
Shroud Fillet Enabled = false
Hub Radius = 8.0 mm
Export Target = both
```

ただしDisk Geometryの未設定状態を、勝手に完成形状として補完しない。

---

# 38. 推奨モジュール構成

既存構造に合わせて調整可能。

```text
blade_designer/
│
├ geometry/
│   ├ blade_geometry.py
│   ├ geometry_3d.py
│   └ meridional.py
│
├ cad/
│   ├ backend.py
│   ├ occt_backend.py
│   ├ surface_builder.py
│   ├ blade_solid.py
│   ├ hub_solid.py
│   ├ boolean_operations.py
│   ├ root_fillet.py
│   ├ edge_classification.py
│   └ cad_validation.py
│
├ fileio/
│   ├ mechanical_step_export.py
│   ├ turbogrid_export.py
│   ├ turbogrid_cad_export.py
│   └ cad_validation_report.py
│
└ gui/
    ├ cad_editor.py
    ├ cad_preview.py
    └ cad_export_worker.py
```

---

# 39. 必須Unit Test

最低限以下を追加する。

```text
test_cad_backend.py
test_blade_surface.py
test_blade_solid.py
test_hub_solid.py
test_boolean_union.py
test_root_fillet.py
test_fillet_failure.py
test_edge_classification.py
test_cad_validity.py
test_step_export.py
test_step_roundtrip.py
test_mechanical_export.py
test_turbogrid_export.py
test_cad_parameter_serialization.py
```

---

# 40. Test Fixtures

少なくとも以下のテスト形状を用意する。

### Fixture A：単純な直線翼

- 単純なHub形状
- 直線的な翼形状
- 十分な接続部寸法
- 小さなフィレット半径

目的：CAD Backendの基本機能を検証。

### Fixture B：曲がった遠心インペラ翼

- 複数Span Layer
- β分布あり
- Wrapあり
- 翼厚変化あり
- Hub Root Fillet

目的：実際の3D翼で曲面生成とフィレットを検証。

### Fixture C：R8失敗条件

- 翼根元の幾何制約を意図的に厳しくした形状
- Hub Fillet Radius = 8 mm

目的：異常終了しないことと、適切なエラー報告を確認。

### Fixture D：Full Impeller

- 主翼枚数N
- 周方向複製
- Hub一体化
- 翼間干渉判定

目的：全周CAD生成を検証。

---

# 41. CAD Fillet Test

単純Geometryに対し、既知のFilletが生成できること。

その後、曲がった翼でFilletを生成する。

R8に対して：

```text
Fillet Radius = 8 mm
```

の指定が実際のCAD Kernelへ渡されることを確認する。

CAD結果が妥当でない場合はTestをFAILにする。

---

# 42. STEP Round-trip Test

生成したSTEPを再読込みする。

比較：

```text
Original CAD Volume
Imported STEP Volume

Original Bounding Box
Imported Bounding Box

Original Solid Count
Imported Solid Count
```

対象ファイルの必要な幾何情報が維持されていること。

---

# 43. CAD Geometry Regression Test

β、Thickness、LE/TE、Rakeを変更して再生成する。

その際：

- CADモデルを再生成できる
- 形状が実際に変更される
- 旧形状のSurfaceが残らない
- View Cameraを維持する
- Project Parameterを維持する

こと。

---

# 44. 実装Stage

## Stage 1：既存コード確認

既存Projectを確認。

最初に以下を実施。

```bash
pytest -q
```

CADへの入力となる3D Geometryデータ構造を確認する。

## Stage 2：CAD Backend

CADライブラリの環境を整備。

- インストール確認
- 基本Solid作成
- Fillet作成
- STEP出力
- STEP再読込み

を単純形状で検証。

## Stage 3：Blade Surface

既存翼座標からPS/SS/LE/TEのCAD曲面を作成。

元のGeometryとの形状偏差を確認。

## Stage 4：Blade Solid

閉じた翼ソリッドを生成。

BREP妥当性を検査。

## Stage 5：Hub Disk

Disk Backside等の入力を追加。

Hub Solid生成。

## Stage 6：Boolean Union

翼とHubを結合。

## Stage 7：Root Fillet

Hub Fillet R8を適用。

失敗検出、Edge識別、CAD Validationを実装。

## Stage 8：Mechanical STEP Export

有効なフィレット付きSolidのSTEP出力。

再読込み検査。

## Stage 9：TurboGrid Export

既存Profile Points出力を維持。

CAD Geometry出力とANSYS向け手順書を追加。

## Stage 10：GUI

CAD/Fillet Editor。

CAD Preview。

Worker処理。

## Stage 11：Project Migration

既存Projectを読み込み可能にする。

## Stage 12：Regression / Final Validation

全Unit TestとManual Testを実施。

---

# 45. ANSYS Mechanical検証手順

READMEへ以下を記載する。

1. ANSYS Workbenchを起動
2. Static Structural等を追加
3. GeometryセルへSTEPをImport
4. Mechanicalを起動
5. Solid認識を確認
6. CAD単位を確認
7. Hub Fillet部分の形状を確認
8. Geometryに問題がないことを確認
9. Meshingを試行

周期セクタを使う場合は、周期境界面と軸の整合も確認する。

実機で確認していない場合はManual TestをNOT_TESTEDとする。

---

# 46. ANSYS TurboGrid検証手順

READMEへ2種類の手順を記載する。

### A. Profile Points

1. TurboGrid起動
2. BladeGen.inf読込み
3. Hub/Shroud/Profile読込み
4. 翼座標の向き確認
5. Geometry確認
6. 必要に応じてBlade Blendを設定
7. CAD From Profile Pointsへ切替
8. True Blend生成
9. 対応トポロジーでMesh試行

CAD From Profile Pointsは対応するANSYSライセンスとスタンドアロン実行条件を確認すること。

### B. CAD

1. TurboGridスタンドアロン起動
2. Geometry InputをCADに切替
3. 対応するCADファイルを指定
4. 必要なTopological Entityを割当
5. Blade、Hub、Shroud、Complex Blade End等を確認
6. Filletの形状確認
7. Meshを試行

Parasolid等のサポート形式は使用中のANSYS環境で確認すること。

---

# 47. 公式資料

以下のANSYS公式資料を参照する。

TurboGrid CAD Input:
https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/tg_user/i4566510856516542556.html

TurboGrid CAD From Profile Points:
https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i132455554122894.html

TurboGrid Blade CAD Features:
https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i016457045820452615547.html

TurboGrid User's Guide（.inf / .curve形式）:
https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/tg_user/i998527.html

Mechanical Geometry Import:
https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/wb_sim/ds_Attach_Geometry_wb.html

CadQuery:
https://cadquery.readthedocs.io/en/stable/

上記の機能はANSYSのリリースやCAD生成ツールによって制限が異なる。

必ず対象バージョンに合う仕様を優先すること。

---

# 48. 完成判定

以下を区別して報告する。

**Python側の完成条件**

- CAD Backend動作
- Blade CAD Surface生成
- Blade Solid生成
- Hub Disk Solid生成
- Boolean Union成功
- Hub Root Fillet R8生成
- Shroud Fillet無効
- CAD Validation PASS
- Mechanical STEP出力
- STEP再読込みPASS
- TurboGrid Profile Points出力
- TurboGrid CAD Geometry出力
- 既存アプリ機能維持
- pytest 0 failure

**ANSYS実機側の完成条件**

- Mechanical STEP読込み成功
- Mechanical Meshing成功
- TurboGrid Geometry読込み成功
- TurboGrid Fillet認識
- TurboGrid Meshing成功

ANSYSを利用できない環境では、実機検証項目を未実施として報告すること。

---

# 49. 最終報告

実装終了時に以下を報告する。

1. 変更ファイル一覧
2. 新規ファイル一覧
3. CAD Backendと使用バージョン
4. CAD Surface生成方式
5. Solid生成方式
6. Hub Disk生成方式
7. Boolean Union結果
8. Hub Fillet R8の実装方法
9. Fillet成功・失敗の検証結果
10. STEP Export結果
11. STEP再読込み結果
12. TurboGrid CAD Export方式
13. Profile Points Export結果
14. pytest実行結果
15. GUI Manual Test結果
16. Mechanical実機検証結果
17. TurboGrid実機検証結果
18. 既知の制約・未完了項目

未検証項目をPASSと記載しないこと。

既存機能の破壊やRegression Test失敗がある状態で、完成と報告しないこと。

以上をCAD Export / Fillet機能の実装仕様として使用すること。