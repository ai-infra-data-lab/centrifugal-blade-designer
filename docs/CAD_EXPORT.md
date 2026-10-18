# CAD / Fillet（v0.4）

既存の設計座標からOpen CASCADEのBREPを生成する任意機能です。通常の設計・CSV・従来のTurboGrid Profile PointsにはCAD環境は不要です。対象はImpellerです。Diffuser/RCの従来出力は維持します。

オープンインペラの正のTip clearanceを指定した場合、Mechanicalは短縮した実翼masterを使用します。Blade Onlyの一定隙間厚翼／可変隙間薄翼の試験は成功していますが、厚翼の可変隙間例は自己交差で拒否され未解決です。TurboGrid CADとExport Bothは隙間対応前のためjob作成前に拒否します。[翼端クリアランスの定義・制約](TIP_CLEARANCE.md)を参照してください。

## 環境

このPCではWindows / Python 3.12.14で分離環境を確認しています。既存の`.venv`へOCP/VTKを混在させません。

```powershell
.\.venv\Scripts\python.exe -m venv .venv-cad
.\.venv-cad\Scripts\python.exe -m pip install -r requirements-cad.txt
.\.venv-cad\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe main.py
```

実バックエンドは`cadquery-ocp==8.0.1.1.0`のOpen CASCADE APIで、CadQueryの高水準ラッパーは使用しません。NumPy/SciPyも独立環境へ導入します。`requirements-cad-windows-py312.lock.txt`はこのPCの全依存の記録で、別PCでの再現試験は未実施です。CAD環境のPython 3.11・Linux・macOSは未検証です。

## 操作

1. 左の編集対象からImpellerを選び、右の`CAD / Fillet`を開きます。
2. `根元フィレットR / Root R [mm]`へ任意の正の半径を入力します。Enterまたはフォーカス移動で確定し、`Generate CAD`で再生成します。初期値8 mmは固定値ではありません。Shroud無効、mm、Z軸は維持します。Blade Onlyでは根元フィレットを生成しません。
3. `仮ディスクを作成・表示 / Create Provisional Disk`で、仮寸法とディスク単体の実CADを作成します。元の翼ワイヤーフレームを残し、`No CAD Blade / No Root Fillet`を表示します。これは翼と結合したフィレット付きモデルの成功を意味しません。ディスク単体STEPは表示中のReportに対応するjobの`outputs/mechanical/provisional_disk_NO_FILLET.step`です。
4. Hub付きCAD生成でディスクが完全に未入力なら仮寸法を自動設定します。入力済みの手動寸法は上書きしません。実際の寸法を使う場合はBore radiusとDisk backside JSONを指定して`Apply Backside`を押します。仮寸法は画面・Project・CADレポートで`PROVISIONAL`と明示します。旧Project読込時に原本やアプリ既定JSONを自動更新しません。
5. `Validate CAD`または`Generate CAD`で計算・検証・CAD表示を実行します。両方とも現在のScopeに従って形状を計算し、通常出力先には保存しません。計算記録は`artifacts/cad-runs/<job>/`です。
6. `Export Mechanical`、`Export TurboGrid`、`Export Both`ではケースフォルダを選びます。各成果物の検証結果を分け、合格したものだけを保存します。

### 仮寸法の規則

ユーザーが仮寸法の作成を指定した場合に使うテンプレートです。実機のディスク寸法と扱いません。

- 内径は通常20 mm。小さいモデルではBore radiusを`min(10 mm, Hub最小R×0.25)`へ制限します。
- 表示中の主翼・スプリッターのHub側根元R/Zを壁面へ投影し、その最大距離より10 mm外側までを仮前面とします。元のHub終端を超えて延長しません。旧サンプリングの距離メタデータは使用しません。
- 裏面はShroudと反対側のHub Z範囲から20 mm離した平面です。TEでHub/Tip Zが同じなら流路のZ進行方向を使用します。保存済み既定モデルでは裏面Z=75 mm、内径20 mm、外径約251.86 mmです。20 mmは裏面のオフセットで、一様な板厚ではありません。
- 仮前面は構造CAD専用の範囲です。子午面の所属翼列やTurboGridの出力範囲は変更しません。TurboGridの所属範囲が無効なら、Mechanicalが成功してもTurboGridは拒否します。
- 半径と仮寸法はUndo/Redo・翼列別保存へ接続します。仮寸法を編集しても仮表示を保持します。Hub形状を大きく変えた場合は仮ディスクを再作成してください。

既定モデルの翼＋仮ディスクに対するR8は、根元に4面共有のエッジが残りOCCTで拒否されています。半径を自動縮小したり、ディスク単体の成功をフィレット成功と表示したりしません。任意Rの実CAD反映は別の検証モデルでR2.5とSTEP再読込後の半径を確認しています。詳細は[仮ディスク追加報告](PROVISIONAL_DISK_REPORT.md)を参照してください。

裏面入力の形式（以下はキーの説明で、実機寸法の推奨値ではありません）:

```text
{
  "start_z": 数値mm,
  "start_r": 数値mm,
  "start_angle_deg": 数値deg,
  "segments": [{"length": 数値mm},
               {"radius": 数値mm, "sweep_deg": 数値deg, "clockwise": trueまたはfalse}],
  "export_points": 正の整数
}
```

裏面は外周側から内径側へ定義し、最終RをBore radiusへ一致させます。Hub流路出口→裏面開始、裏面末端→Hub入口Zの内径点→Hub入口を直線端面で閉じてZ軸回転します。この端面構成が意図したディスクか確認してください。自己交差・非閉鎖・結合不能・所属壁面が翼を含まない場合は拒否します。軸孔R=0は明示指定時だけ許容します。

ScopeはBlade Only、単翼＋Hub、周期セクタ、全周インペラです。単翼＋HubのHubは全周ディスクです。周期セクタは全周実体を1ピッチで切断します。Hub付きモデルは主翼と有効なスプリッターを処理し、根元フィレットと主翼／スプリッター間・ピッチ間干渉を検査します。Blade Onlyは個々の翼solidだけを検証し、アセンブリの干渉はNOT_TESTEDです。個々の設計でR8が成立する保証はありません。成立しない半径を自動縮小しません。

計算はQProcess内で実行し、開始時の深いコピーとSHA256を保存します。途中の編集はジョブに混入しません。Cancelはこのジョブのプロセスツリーだけを停止します。計算後に設計が変わっていれば古いCADメッシュを隠します。Undoで元のパラメータへ戻れば再表示できます。ジョブの出力は開始時のsnapshotに対応します。

## CAD表示

生成したBREPを三角形化し、既存の3D画面へ渡します。設計曲線を太く描いた擬似フィレットではありません。CAD Blade、Hub Disk、Root Fillet、Full、Surface Edgesを切り替えられ、根元は別色です。根元の面をクリックすると指定半径を表示します。表示用メッシュはSTEPの代用ではありません。既存の自由回転・平行移動・ズーム・視点ボタンとカメラを維持します。

## 生成・検証

- PS/SS/LE/TEのmaster座標を共通パラメータで対応付け、SciPyの補間制御点・ノットからOCCTのB-spline曲面を作ります。出力点数設定には依存しません。
- 各master点に対応する曲面点の偏差を測定し、既定0.01 mm以下へ適応分割します。入力Span間全域の解析的誤差保証ではありません。
- 平面のHub/Tip端面は厳密な平面、非平面の場合は充填面で閉じ、sewing、閉shell、solid化を行います。BREPと自己交差、閉鎖、正体積を検査します。
- Hub流路面と翼面の隣接関係、生成履歴からRoot Edgeを選択します。LE/TE/PS/SSが揃わない・曖昧な場合は停止します。固定エッジ番号には依存しません。
- OCCTの実フィレットへ指定半径を渡し、生成面を記録します。半径の局所主曲率をSTEP前後でサンプルします。面全域の厳密半径保証は`NOT_TESTED`です。
- STEPはMMで書出し、再読込後のBREP・自己交差・閉鎖・solid数・体積・bbox・edge toleranceを比較します。比較許容差と実測差をJSONへ記録します。

## 出力と保護

```text
case/
  mechanical/*.step
  mechanical/import_instructions.md
  turbogrid/profile_points/{BladeGen.inf,hub.curve,shroud.curve,profile.curve}
  turbogrid/cad/turbogrid_cad.step
  turbogrid/cad/cad_import_instructions.md
  turbogrid/blade_blend_settings.md
  parameters/geometry_snapshot*.json
  validation/cad_validation*.{json,txt}
  validation/*_surface_roles.json
```

実際に生成できた出力だけを保存します。形状・STEP再読込が失敗したファイルは公開しません。検証後のSHA256を照合して一時ファイルから置換します。失敗レポートは別名で残し、既存の成功レポート・STEPを保護します。ファイル単位の置換であり、OS障害時のケース全体のロールバックはありません。デバッグ用`NO_FILLET_OR_INCOMPLETE.step`はジョブ内だけに残し、正常出力にはしません。

ProjectはCAD設定変更時にschema 0.4へ保存します。CAD設定が既定のままなら追加キーを省略して従来のschema 0.3を維持します。旧JSONには寸法未設定・R8の安全なCAD設定を補います。元のProject原本を自動更新しません。

## ANSYS Mechanical手動確認（NOT_TESTED）

1. WorkbenchでStatic Structural等を追加します。
2. GeometryセルへMechanical用STEPをImportします。
3. Mechanicalを開き、solid数、mm、Z軸、寸法・体積を検証レポートと照合します。
4. Hub根元のR8とShroud側にフィレットがないことを断面・測定で確認します。
5. 周期セクタの場合は軸と周期面を割り当て、切断面の位相・翼との交線が解析で意図した構成か確認します。現在の切断面はZ軸を通る放射状平面です。
6. メッシュを生成し、根元の品質を確認します。

Named SelectionsのSTEP経由の保持は保証しません。`*_surface_roles.json`の面積・重心・bboxは役割の照合資料です。ANSYSへの自動Named Selection割当ではありません。

## TurboGrid手動確認（NOT_TESTED）

### Profile Points経路

従来のProfile Pointsはフィレットを含まない翼座標です。通常のFile → Exportも維持します。Profile Pointsは保存済みの従来TurboGrid単位・軸設定を使い、CADの固定mm/Z設定とは独立しています。TurboGridでBladeGen.infを開き、Hub/Shroud/Profile、軸・単位・輪郭向き・LE/TEを確認します。必要ならBlade BlendをHub R8、Shroud無効として設定し、CAD From Profile Pointsへ切り替えて生成・メッシュを試します。この経路のBlendはANSYSが別に生成するもので、Python側フィレットと同一形状の保証はありません。

CAD From Profile Pointsのライセンス・スタンドアロン起動条件は対象リリースで確認してください。スプリッター付きProfile Pointsは[専用仕様](TURBOGRID_SPLITTER.md)で主翼とSplitterを出力できます。CAD流路が成功してもProfile Pointsの失敗を隠しません。

### CAD経路

機械用ディスクSTEPを流用せず、Hub/Shroudで閉じた流路回転体から全周の翼・根元材料を差し引き、1ピッチの流体領域を作成します。Hub、Shroud、Blade PS/SS/LE/TE、Root、Inlet/Outlet、Periodicの役割を検査します。

現在は有効な**流路STEP中間ファイル**を出力します。Parasolid writer/converterは未導入で、ステータスは`CONVERSION_REQUIRED`です。STEPを`.x_t`へ改名してはいけません。使用中リリースが対応するCAD形式を調べ、必要ならSpaceClaim等の実CADコンバータでParasolidへ変換します。対応環境のTurboGridスタンドアロンでGeometry InputをCADにし、Topological EntityとBlade/Hub/Shroud/Complex Blade Endを割り当て、根元を確認してメッシュを試します。変換による面分割・トポロジー変更も確認します。

対象ANSYSリリースが未指定のため、STEPの直接TurboGrid入力・変換・Import・Mesh成功は主張しません。特に放射状の周期切断面が翼を横切る設計では、必要な周期トポロジーを実機側で確認してください。CADのBREP妥当性検査だけではTurboGridでのメッシュ適合性を証明しません。

## 一次資料

- [TurboGrid CAD Input / 2025 R2](https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/tg_user/i4566510856516542556.html)
- [CAD From Profile Points / 2026 R1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i132455554122894.html)
- [Blade CAD Features / 2026 R1](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i016457045820452615547.html)
- [Mechanical Geometry Import / 2024 R2](https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/wb_sim/ds_Attach_Geometry_wb.html)
- [CadQuery documentation](https://cadquery.readthedocs.io/en/stable/)

リリースが異なる資料を同一環境の仕様として扱わず、導入先の公式仕様を優先してください。実装・検証記録は[CAD_IMPLEMENTATION_REPORT.md](CAD_IMPLEMENTATION_REPORT.md)です。
