# Centrifugal Compressor Blade Designer v0.3

起動・Newの既定モデルを指定の`blade_v03.json`（Impeller／Diffuser／RC、RC選択）へ更新しました。静翼の中央2Dは、3Dで生成したHub断面のXY投影を単翼／全周で表示します。RCは子午面に沿って外径側LEから内径側TEへ進みます。元の入力・JSON形式・3D計算は保持します。旧2D Metrics／CSVは別の計算経路のため、子午面ベースのRC形状と区別してください。[原因・操作と確認範囲](docs/RETURN_CHANNEL_DISPLAY.md)。

アプリ名・バージョン・角度定義は`About → About Blade Designer`で確認できます。画面内の大きなヘッダーを除き、編集に使える領域を広げました。詳細は[Aboutメニュー](docs/ABOUT.md)。

Impellerの`LE / TE → 派生設計 / Shroud・外径カット`で、元の基準Gross面積に対する一定削減率と、指定外径[mm]／元外径からの切削率[%]を設定できます。角度・厚さ・子午面の元データを保持し、元の翼面から主翼とSplitterを切り出します。翼Tipとケーシングを変更し、既存の絶対クリアランスを維持します。中央の形状と流路解析は派生形状、編集グラフは元設計です。派生形状のTurboGrid／CAD出力は未対応で、書き込み前に拒否します。操作・定義・制限は[派生カット](docs/IMPELLER_TRIM_SPEC.md)を参照してください。

専用スプリッターの角度・厚さは、表示中のLE〜TEの点だけで主翼と同じPCHIP補間を行います。2点なら直線です。既存の専用分布・コピー直後にも適用するため、以前の形状から変わる場合があります。主翼連動モードは従来どおりです。詳細は[専用分布の補間](docs/SPLITTER_INTERPOLATION.md)。

保存先: [アプリ専用のGitHubリポジトリ](https://github.com/ai-infra-data-lab/centrifugal-blade-designer)。最新の静翼TurboGrid出力対応は全回帰490件成功。v0.3.0タグの記録は318件成功で、タグは維持します。実ディスプレイの変更後操作とTurboGrid実機Importは未確認です。

2026-10-11のローカル整理では、角度・厚さEditorの不要な一時グラフ、重複する表示更新、未使用importを削除しました。操作・数値計算・既定値・保存形式は維持します。検証記録は[FEATURES.md](FEATURES.md)を参照。GitHubのv0.3.0タグは変更していません。

インペラのTEをCutoffにすると、子午面上のHub側TE位置の半径をRとして、全Spanを同じ円筒面（外径D=2R）で切ります。PS/SSを切断位置で止め、TEを円筒面上で閉じます。Tip側TE位置はSpan壁面の対応・複数交点の選択基準に使用し、Cutoffの外径はHub側で決まります。切断面に届かないSpanやLEより手前に切断面がある形状はエラーになります。円形・楕円TEと静翼のCutoffは従来処理を維持します。

## 継続開発環境（2026-10-08）

既存GUI・計算コードは変更せず、Windows版VS Codeから開発・検証する設定を追加しました。

1. このフォルダの **blade-designer.code-workspace** をVS Codeで開く。
2. Python: Select Interpreterで **.venv/Scripts/python.exe** を選択。
3. **F5 → Blade Designer: Design** で起動・デバッグ。最適化は別のlaunch設定。
4. Testing画面、または `.\.venv\Scripts\python.exe tools/run_tests.py` で既存回帰テストを実行。
5. Codex拡張で本人がサインインし、AGENTS.mdのルールに従って1機能ずつ変更。
6. Source Controlでこのアプリの差分を確認し、検証後にGitへ記録。親Gitリポジトリには別の家計簿もあるので、Stage Allは使用しない。

- [既存機能と確認状態](FEATURES.md)
- [インストール・デバッグ・Git・WSL・手動確認手順](docs/DEVELOPMENT.md)
- [モジュール構造・依存・入出力](docs/ARCHITECTURE.md)
- [今回の環境調査・検証報告](DEVELOPMENT_SETUP_REPORT.md)
- [Codex開発ルール](AGENTS.md)

新規Windows環境ではPython 3.12で.venvを作り、`requirements-windows-py312.lock.txt`から導入します。現在の.venvはそのまま使用します。固定依存は環境の記録で、新規インストール・Linux実行は未検証です。詳細は開発手順を参照。


Hub/ShroudのLine・Circular Arc子午面、Hub/Tip・中間Spanの翼断面、Component Stations・Gross Flow Area、3D Wireframe、TurboGrid座標ファイルを生成するPythonアプリです。既存の2D Vaned Diffuser、CSV、設計指標、最適化パラメータ層も維持しています。

正本仕様: [V03_FLOW_PATH_SPEC.md](V03_FLOW_PATH_SPEC.md)、追加要件: [V03_ADDITIONAL_SPEC.md](V03_ADDITIONAL_SPEC.md)。

子午面の区間一覧で円弧（Arc）の行を選ぶと、一覧の下に中心・始点・終点のR/Z座標[mm]を表示します。Hub／Shroudの切替、編集、Undo／Redoに追従する読み取り専用の表示です。直線は始点・終点のみ表示します。[座標表示の詳細](docs/MERIDIONAL_COORDINATES.md)。

角度・厚さは`Blade Angle`／`Thickness`で主翼とスプリッターを同じグラフに表示します。下の`主翼 / Main`・`スプリッター / Splitter`で編集対象を選びます。Splitterタブは開始位置・コピー等の設定用です。タブや解析グラフを開いた際は線全体が見える範囲に合わせ、編集中のズームは維持します。[共有グラフと全体表示](docs/SHARED_GRAPHS.md)。

## CAD / Fillet（v0.4）

オープンインペラは`LE / TE → オープンインペラ / Tip Clearance`でLE・TEの隙間[mm]を指定します。Shroudを固定ケーシングとし、Hub側法線方向へ翼Tipを移し、間はケーシング沿いの距離で線形補間します。入力はEnter／フォーカス移動で確定。子午面と3DにTipとケーシングを分けて表示し、翼列別保存・Undoに対応します。TurboGrid Profile Pointsは実Tip断面に加え、ShroudまでSpan方向に延長した断面を同じprofileファイルへ出力します。読込み後はShroud TipのProfile Numberに出力後表示の実Tip番号を指定してください。Splitter付きProfile Pointsにも対応し、主翼とSplitterの各Tip/延長断面を出力します。両翼の実Tip番号とTheta方向をTurboGrid側で確認してください。正の隙間のTurboGrid CADは未対応です。[スプリッター出力](docs/TURBOGRID_SPLITTER.md)。操作と検証は[クリアランス付きTurboGrid](docs/TURBOGRID_CLEARANCE.md)、CADの成立範囲・面積の扱いは[翼端クリアランス](docs/TIP_CLEARANCE.md)を参照してください。

Impellerの`CAD / Fillet`タブで、master座標から実BREPの翼・Hub・根元フィレットを生成し、Mechanical用STEPとTurboGrid用流路CADを検証付きで出力できます。`根元フィレットR`へ正の半径を入力し、Enter/フォーカス移動で確定して再生成します。初期値は8 mmです。Shroud無効、mm、Z軸は維持します。

`仮ディスクを作成・表示`で仮寸法のディスク単体を表示できます。既定モデルでは内径20 mm、外径約251.86 mm、裏面Z=75 mmです。画面・JSON・レポートへPROVISIONALと記録します。手動の入力済み寸法は保持します。ディスク単体には根元フィレットは含まれず、現在の既定翼と結合したR8は根元位相の制約で未成立です。[仮ディスク追加報告](docs/PROVISIONAL_DISK_REPORT.md)を参照してください。

CADは別環境`.venv-cad`のOpen CASCADEで処理します。TurboGrid CADはSTEP中間形式で、対応形式への変換は`CONVERSION_REQUIRED`、ANSYS Import/Meshは`NOT_TESTED`です。既存のProfile Pointsにフィレットは含みません。

環境構築、裏面入力、各Scope、MechanicalのWorkbench Import/Mesh手順、TurboGridのProfile Points/CADの2経路は[CAD操作手順](docs/CAD_EXPORT.md)を参照してください。[実装・検証報告](docs/CAD_IMPLEMENTATION_REPORT.md)に確認範囲と制約を記載しています。

## 起動・検証

インペラの「LE / TE」タブにある「TE Rake target / β保持」を有効にすると、TE Rake目標角を入力できます。無効（既定値）は従来の形状、有効で0°はTE Rakeを0°へ合わせる指定です。各翼列で独立して保存し、Undo/Redoに対応します。入力はEnter/フォーカス移動で確定します。

本アプリのTE Rakeは、Hub/TipのTEキャンバー端点を結ぶ線と、その中点と回転軸を通る子午面との角度です。正は+Zから見て反時計回り（+θ）で、回転方向CW/CCWとは独立した幾何学的符号です。子午面R–Z内の傾きやHub/Tipのθ差そのものとは異なります。Hub断面・β分布・厚さ・子午面・TE半径を維持し、ImpellerParameterMapperで各Spanの開始θを決めます。TEのθはHubを基準にSpan方向へ線形に配置し、LEのθはTE目標位置からβの積分巻き角を引いて求めます。中間Spanそれぞれの局所Rake角を一定にする指定ではありません。丸い端部の頂点ではなくキャンバー終端を基準にします。

TE Rakeの実測角とHub/TipのLE θを表示します。Rake有効時の「Hub Theta LE」はHubの配置基準で、TipのLE位置は独立入力ではありません。βは自動変更せず、表示・TurboGridは同じマッピング済み3Dを使用します。固定したTE半径とR/Zでは実現できない角度は拒否し、入力を修正するかUndoで戻します。未指定の旧JSONは同じ形状・形式を維持し、新しい任意項目impeller_te_rake_degは指定時だけ保存します。Rake指定JSONは対応版で開いてください。ユーザー原本と既定値ファイルは変更しません。

既存の断面検証とRakeの到達性を確認します。Span間の面全体の交差・隣接翼との3D衝突・応力/CFD検証は今回追加していません。βを保持しても翼のSpan方向配置が変わるため、性能や強度が同じになるとは限りません。設計概念の参考: [CFturboのRake/Stacking](https://manual.cfturbo.com/en/sl.html)。本アプリの角度定義は上記のとおり明示しています。

インペラの「Splitter」タブで「スプリッターを追加 / Enable Splitter」を有効にすると、各主翼間へ1枚ずつ追加します。主翼枚数Nに対してスプリッターN枚、合計2N枚です。既定値は無効で、既存の主翼・静翼・デフォルトJSONは変更しません。

Hub/Tip開始位置は各主翼の物理的な子午面距離でLE=0%、TE=100%とした値です。50%なら後半を使用し、中間Spanの開始割合はHub/Tip間で線形補間します。「主翼間の位置」は回転方向へ1ピッチの割合で、50%は中間です。「厚さ倍率」は元の主翼分布へ掛けます。初期の連動状態ではβと厚さの分布を主翼上の元の位置から切り出し、短い翼の0〜100%へ元分布全体を引き伸ばしません。端部タイプは主翼を継承し、新しいLEを再生成します。TEは主翼の位置・外径Cutoff・TE Rakeに追従します。

中央2D・3DとFull Annulusではスプリッターを緑色で表示します。右側に実際のHub/Tip LEのR/Zと枚数を表示します。翼列ごとに独立保存し、Undo/Redo・New・JSON往復に対応します。数値入力はEnter/フォーカス移動で確定します。初期状態は主翼連動です。「主翼からコピーして角度・厚さを独立編集」を選ぶと、その時点の主翼制御点をコピーし、共通のBlade Angle / Thicknessグラフ・表で調整できます。専用分布も横軸は元の主翼LE=0、TE=1で、各SpanのスプリッターLE〜TEだけを表・ドラッグ点で編集します。可視点だけのPCHIP補間をコピー直後にも適用するため、連動時と形状が変わる場合があります。上流点は保存データとして保持しますが、専用区間の点間の傾きには使いません。[編集範囲の詳細](docs/SPLITTER_EDIT_RANGE.md)と[補間の詳細](docs/SPLITTER_INTERPOLATION.md)。厚さグラフは倍率適用前の値です。独立編集後は主翼β・厚さの変更に追従しません。「現在の主翼から再コピー」で初期化でき、連動へ戻す操作もUndo可能です。主翼の中間Spanを後から追加した場合は、保存済み専用Span間で分布を補間します。独立モードでも端部・TE位置・Rakeは主翼に追従します。複数種類のスプリッターと翼間の3D干渉評価は今回含みません。

**スプリッター付きインペラのTurboGrid出力は現在未対応です。** 主翼だけを誤って出力しないよう、書込み前に明示的なエラーにして既存ケースを保護します。スプリッター無効時の既存Impeller出力と静翼出力は維持します。スプリッター形状の保存には対応版のProject JSONを使用してください。

3D画面は左ドラッグでトラックボール自由回転、右ドラッグで平行移動、ホイールで拡大・縮小できます。真上/真下を越えて回転でき、画面の縁では視線方向の傾きも変えられます。中央下部と別ウィンドウの両方に「正面（+X/YZ）・上面（+Z/XY）・側面（+Y/XZ）・等角・全体・リセット」ボタンがあります。「全体」は現在の向きを維持し、「リセット」は初期の斜め方向へ戻して全体を表示します。形状編集、Undo、翼列切替、Full Annulusで自由回転した向きを保持します。これは表示操作だけで、設計座標・JSON・CSV・TurboGrid出力は変更しません。

このPCの専用環境はPython 3.12です。別環境ではPython 3.11以上とrequirements.txtの依存を使用してください。

Python 3.11のWindows環境を再現する場合は、`requirements-windows-py311.lock.txt`を使用します。2026-10-12に別のPython 3.11.9環境で新規インストール・pip check・全回帰457件成功・通常設計/最適化のQt offscreen起動を確認しました。別PCと実画面操作は今回未確認です。手順と検証結果は[開発手順](docs/DEVELOPMENT.md)・[検証記録](FEATURES.md)を参照してください。既存の3.12環境は上書きしません。

```powershell
cd 'C:\Codex\pythonのGUI作成\centrifugal_blade_designer'
.\.venv\Scripts\python.exe main.py
# Separate optimization startup mode
.\.venv\Scripts\python.exe main.py --mode optimization
# Optional existing project
.\.venv\Scripts\python.exe main.py --mode optimization --project blade.json
.\.venv\Scripts\python.exe tools/run_tests.py
.\.venv\Scripts\python.exe tools\v03_additional_smoke.py
```

新規環境:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

PyVista/VTK/OpenGLは不要です。Geometry EngineはQtへ依存しません。
起動・Newのデフォルトは2026-10-11指定のblade_v03.jsonをアプリ内へコピーした値です。保存時の編集対象Diffuserも復元します。元のJSONは変更せず、起動時にユーザーファイルへ依存しません。
最新の共通LE/TE・全周表示は [SHARED_EDGE_ANNULUS_REPORT.md](SHARED_EDGE_ANNULUS_REPORT.md)、同時編集・モード分離は [SIMULTANEOUS_EDITOR_REPORT.md](SIMULTANEOUS_EDITOR_REPORT.md)、編集対象・投影表示の変更は [TARGET_EDITOR_REPORT.md](TARGET_EDITOR_REPORT.md)、v0.3追加要件の実装報告は [V03_ADDITIONAL_REPORT.md](V03_ADDITIONAL_REPORT.md) を参照してください。前回の記録は [V03_FLOW_PATH_REPORT.md](V03_FLOW_PATH_REPORT.md) と [V03_IMPLEMENTATION_REPORT.md](V03_IMPLEMENTATION_REPORT.md) に保存しています。

## GUI

### 左側の編集対象・複数翼列（2026-10-10）

左の縦パネルで「子午面 / Meridional」または「翼 / Blade Rows」配下の翼列を選択します。
左に選択パネル、中央上段に2D表示、中央下段に3D表示、右にEditorを配置しています。中央の上下境界をドラッグして表示高さを調整できます。下部Contextのタブパネルはありません。
中央上段は編集対象に合わせ、子午面選択時にHub/Shroudの子午面グラフ、翼列選択時に翼形状を表示します。角度・厚さタブの切り替えでは翼形状を維持します。子午面の数値・区間・所属翼列・翼端は右のMeridionalで編集し、中央グラフ上の翼端ドラッグも使用できます。中央下段の3D翼表示は維持します。
翼列のタブはBlade Angle / Thickness / LE / TE / Full Annulusです（LE / TEは1タブ）。角度・厚さの分布グラフと入力表は右側で操作します。
Full Annulusタブの「2D Full Annulus」「3D Full Annulus」で、中央上段・下段をそれぞれ単翼／全周表示へ切り替えます。上部Viewグループにも同じ切り替えがあります。翼枚数は選択翼列の設定に追従し、切り替えだけでは設計値やカメラを変更しません。全体を収める場合はView → Fit Viewを使用します。表示設定はJSONの設計値には保存しません。
3DのHub・Shroudは子午面をZ軸回りに360度回転した半透明の面で表示します。Hub / Shroudチェックで各面を隠せます。壁面は単翼・Full Annulusのどちらでも全周を表示し、翼は従来の線表示を維持します。Fit Viewは回転面全体を含めて収めます。面の分割は描画用で、形状計算や出力座標は変更しません。
中央表示と右Editorの境界をドラッグして幅を調整できます。編集欄はスクロールし、対象切替でウィンドウの高さは変更しません。起動サイズは利用可能な画面サイズ内に収めます。
Component Stationsの編集表と子午面上部のStation値一覧は表示しません。Blade Edgesの翼端編集は使用できます。既存JSONのStation値は保存・読込とFlow Area計算の互換性のため保持します。
Blade EdgesではIMP/DIFのHub・ShroudそれぞれのLE/TEをR・Z［mm］で指定します。両座標を入力して「R/Zを適用 / Apply R/Z」を押すと、編集した端点をまとめて反映します。入力点は対応壁面上の最近点へ投影し、確定座標を入力欄へ戻します。適用前の入力は設計値へ反映されません。ドラッグや子午面変更後も座標表示が追従します。JSONは従来の正規化壁面距離を維持し、LE/TE順序の検証とUndo/Redoを使用します。インペラTE Cutoffの外径は引き続きHub側TEのRで決まります。
「Add Line」「Add Arc」は壁面の末尾へ区間を追加します。この追加では、確定済みLE/TEのR・Z位置を全翼列で維持し、未適用のR・Z入力も保持します。内部の正規化距離だけを新しい壁面全長に合わせて換算し、区間追加とまとめて1回のUndoで戻せます。区間の削除・並べ替えは従来の動作を維持します。
区間表の「Type」で、追加済み・読込済みの区間もLine（直線）／Arc（円弧）へ変更できます。区間の順番・所属翼列・経路長を保持し、LineではLength、ArcではRadius・Sweep・Directionの入力欄へ切り替わります。Line→Arcは初期Sweep=35°・CCWで、経路長に合うRadiusを設定します。Arc→Lineは円弧の経路長をLengthに使います。確定した種類変更は1回のUndoで戻せ、JSONにも保存できます。
子午面の長さ・半径・Sweep、および開始Z/R・開始角度の数値入力は、入力欄からフォーカスが外れた時、またはEnterで確定した時に反映します。数字の入力途中は再計算しません。スピンボタンや方向・種類の選択は従来どおり即時反映します。

既存区間の長さ・半径・角度・方向・種類、および開始位置・角度の編集は壁面形状を優先します。全翼列のLE/TEについて、元のR・Z点が新壁面上に残れば位置を保持し、外れる場合は対応する新壁面の最近点へ移して座標を更新します。壁面変更と翼端調整はまとめて1回のUndoで戻せます。未適用のR・Z入力も保持します。壁面自体が交差・負の半径などの無効形状になる編集は取り消します。投影先でLE/TEが重なるなど翼形状が無効になる場合は壁面編集を保持し、既存の形状・保存検証でエラーを表示するため、翼端位置を調整してください。
上部はFile → Edit → View → Toolsのメニューバーだけです。Fileには新規・開く・保存・Export（CSV/TurboGrid）・終了、EditにはUndo/Redo・Rotation Direction (+Z)（CCW/CW）・Reverse Rotation、ViewにはFull Annulus・Fit View・Projection（XY/XZ/YZ）・出力設定・解析/3D別ウィンドウ、Toolsには別ウィンドウの最適化モードをまとめています。投影面はImpeller選択時だけ変更でき、静翼ではXY固定です。回転方向と投影面のメニュー選択はUndo・読み込み・翼列切替に追従します。ツールバーはなくし、Ctrl+N/O/S/Z、Ctrl+Y・Ctrl+Shift+Zの既存ショートカットは維持します。Copy Hub→Tip / Tip→Hubボタンはありません。
中央下段の3Dは、子午面選択時に全翼列と共通のHub/Shroud回転面を表示します。翼列選択時にはその翼だけと、その翼列へ所属を割り当てた子午面区間のHub/Shroud回転面を表示します。所属を全く設定していない旧プロジェクトでは全壁面を表示します。所属設定を使っている場合、割り当てのない壁面は表示せず、離れた所属区間は別々の面として描きます。翼の計算・JSON/CSV/TurboGridの出力範囲は変更しません。全翼列の3D Full Annulusは各翼列の独立した翼枚数を使います。生成できない翼列は全翼列表示から除外し、名前と理由を表示します。左ドラッグで回転、右ドラッグで移動、ホイールで拡大縮小できます。Diffuserも子午面のHub・ShroudとDIFのLE/TE位置を使い、Hub（Span=0）・Tip（1）の2断面を作成します。同じ角度・厚さ・LE/TE形状設定を各断面へ適用し、対応するLE/PS/TE/SS点をSpanwise線でつないで3D表示します。子午面・翼端・角度・厚さの編集に追従し、3D Full Annulusは翼枚数で各断面と接続線をZ軸回転します。View → 3D Previewも選択翼列に追従します。Impellerの計算は維持します。Diffuserの上段2D輪郭・指標・CSVは従来の半径指定による2D計算を維持し、3Dは子午面上のLE/TE位置を使用します。JSONに新しい設定項目は追加しません。 子午面上で翼が自己交差する、端部が壁面範囲を越えるなど3D形状が無効な場合は、理由を表示して3Dだけ前回の有効形状を保持します。2Dとして有効な設定の編集・表示・CSVは継続できます。

#### 子午面区間の所属と翼列別出力範囲

子午面のBlade Edges表は、翼列ごとにHub LE・Shroud LE・Hub TE・Shroud TEの4行を表示します。翼列を追加すると独立した欄とLE/TE線・ドラッグ点が追加され、既存のDiffuserの欄や値は置き換わりません。新しい翼列の初期値は同種類の設定からコピーされるため、初めは同じ位置になることがあります。R/Z入力を適用するか、その翼列名のドラッグ点を動かして独立した位置へ変更できます。名前変更・順番変更・削除・Undo、JSON保存・再読込に対応します。表の高さは従来の上限を保持し、翼列が増えた分は表内でスクロールします。
この修正は拡張した関連108件と最終全回帰457件が成功しています。詳細はFEATURES.mdの検証記録を参照してください。

子午面を選び、Hub / Shroudそれぞれの直線・円弧の表で「所属翼列 / Blade Row」を選びます。1区間につき1翼列を割り当てます。曲線上にも翼列ごとの色と名前・区間番号を表示します。壁面形状は共有のまま、所属だけを指定します。区間の追加・削除・順番変更に所属も追従し、Undo/RedoとJSON保存に対応します。翼列削除ではその所属を解除し、Undoで復元します。

TurboGrid出力は選択Impellerの所属区間にHub/Shroudの出力範囲を限定します。Hub・Shroud両方で連続した区間を割り当て、LE/TEと翼輪郭全体を含めてください。飛び飛びの所属、片側だけの割り当て、翼が範囲外の場合は出力前にエラーを表示し、既存出力を変更しません。点数・単位・座標系・翼輪郭ファイル形式は従来と同じです。

割り当てを一切使っていない旧プロジェクトは従来どおり全流路を出力します。JSONの直線・円弧に任意の`blade_row`を保存し、未割り当ての旧データには追加キーを出しません。Diffuserの所属も保存できますが、既存Diffuser CSVは翼輪郭用で壁面を含まないため、この割り当てではCSV輪郭を切り詰めません。区間途中での境界指定・同一区間の複数翼列への割り当ては今回の実装に含みません。

手動確認: Hub/Shroudで翼列を割り当て、色・名前を確認し、翼列切替と下段3D操作、Undo/Redo、JSON再読込、選択Impellerの壁面出力端点を確認してください。実画面での操作とTurboGrid実機Importは未確認です。

- 「追加 / Add Row」を押し、画面で名前と「インペラ / Impeller」または「静翼 / Diffuser」を指定して「追加 / Add」を押します。名前の前後の空白は除去し、空白だけの名前では追加できません。キャンセルでは設計を変更しません。同じ種類の既存翼列をコピーして作成し、追加後の編集は元の翼列に反映しません。
- 各翼列の角度・厚さ・LE/TE形状・翼枚数・翼端位置・回転方向・出力設定を独立して編集・保存できます。ImpellerはHub/Tip・中間Span、Diffuserの3DはHub/Shroudの2断面を使用します。Diffuserの上段2Dは従来のXY形状です。
- 左の翼列を選択して「名前変更 / Rename」を押すと、登録後も名前を変更できます。前後の空白は除去し、空白名は確定できません。キャンセル・同名での確定は変更を作りません。名前変更はUndo/Redo・JSON保存に対応し、翼列ID・形状・区間の所属は維持します。
- 子午面右下のBlade Edges表のRow欄も左の翼列名を表示します。同種類が複数ある場合は、選択した翼列の名前へ切り替わります。名前変更は所属翼列の選択肢・子午面区間のラベル・形状表示の名前へ反映します。
- 「Delete Row」で選択翼列を削除します。少なくとも1翼列を残します。「Move Up / Down」は一覧・保存順序だけを変更し、翼端位置やComponent Stationは自動変更しません。
- 追加・削除・並べ替えと数値編集はUndo/Redoに対応します。翼列の選択だけでは履歴を追加しません。
- 子午面のLE/TE欄は全翼列を名前付きで表示し、それぞれの翼列へ編集を保存します。追加した同種類の翼列も既存欄を置き換えません。旧JSONのトップレベルIMP/DIF値と翼列内の古い控えが異なる場合は、読み込み直後の値を対応する選択中/最初の同種類翼列へ引き継ぎます。他の翼列の独立した値は保持し、原本JSONは読み込みで上書きしません。
- Hub/Shroud壁面、Component Stations、内部計算解像度はプロジェクト共通です。翼列を切り替えても壁面編集を保持します。
- CSVは選択中のDiffuser、TurboGridは選択中のImpellerを書き出します。複数翼列を一括で書き出す機能はありません。
- 初期表示・旧JSONでは従来のImpeller/Diffuserを表示します。左パネルで翼列を選択するか翼列管理ボタンを使うと複数翼列管理に移ります。対象切替のプログラムAPIは保持しています。
- JSON schema 0.3に任意の`blade_rows`と`active_blade_row`を追加します。旧0.1/0.2/0.3は引き続き読み込めます。翼列管理を使わない従来プロジェクトは追加フィールドなしで保存します。複数翼列の情報を保持するには、この機能に対応した版で編集してください。

手動確認: 追加画面で名前・インペラ/静翼を指定して追加、空白名とキャンセル、右の入力欄・グラフ操作、中央上段が子午面と翼形状を選択に応じて切り替えること、2D/3Dの独立したFull Annulus切り替え、Station表がないこと、子午面→翼列切替、別々の角度・翼枚数・翼端位置の編集、順番変更、削除とUndo、別名JSON保存・再読込、選択翼列の書き出しを確認してください。実画面での追加操作は未確認です。変更前のF5起動はユーザー確認済みです。

中央上段に選択対象の子午面または翼形状、右側にSection SelectorとEditorを配置しています。右側上部の「翼枚数 / Blade Count」で選択翼列の枚数を変更できます。各翼列で独立し、2D/3Dの全周表示・隣接翼・設計指標へ反映します。Undo/Redo・JSON保存に対応し、子午面選択時は隠れます。

F5・`main.py`の起動とProject → Newは、ユーザー指定の`blade_v03.json`からコピーした`blade_designer/defaults/default_project.json`を使用します。元のユーザーJSONは変更しません。New・起動直後は未保存の新規プロジェクトとして扱い、Saveで保存先を選びます。`--project`で指定したJSONは起動時のデフォルトより優先します。通常の編集・保存でデフォルト用JSONは書き換えません。

- Editor: 子午面選択時はMeridional、翼列選択時はBlade Angle / Thickness / LE・TE / Full Annulus。
- 下部Context Viewは削除しました。解析表示と出力設定は上部Viewメニューから開きます。
- 通常EditorにDiffuser GeometryとOptimizationのタブはありません。Full Annulusは選択したImpeller/Diffuserを表示し、ImpellerではHub/Tip断面とXY/XZ/YZ投影にも追従します。Diffuser CurvatureはViewメニューから開きます。ディフューザのR LE / R TEはDiffuser選択時のOutput Settingsに表示します。
- 最適化は `main.py --mode optimization` またはModeメニューのOpen Optimization Mode in Separate Windowで別ウィンドウとして起動します。Modeメニューでは現在の設計をコピーします。候補の適用・Undo・保存はそのウィンドウだけへ反映されます。通常Editorの設計へ自動適用しません。
- 左の翼列一覧で表示と編集対象を切り替えます。角度・厚さ・LE/TE設定は対象ごとに独立しています。右側のEditingラベルで現在の対象を確認できます。
- ImpellerではSection SelectorでHub/Tip/中間Spanを選び、ProjectionでXY / XZ / YZを切り替えます。Diffuserは従来の2D XY表示で、Section Selectorを隠し、ProjectionはXY固定です。インペラへ戻るとその投影方向を復元します。
- 形状更新は既存Plot ItemのsetDataで行います。起動・New・Open・Fit View以外では自動Fitしません。
- 3Dは左ドラッグで回転、右ドラッグでPan、ホイールでZoom。形状変更でcamera_positionを維持します。
- 角度・厚さはHub/Tipを同じグラフへ常時表示し、それぞれの表・Add/Delete・操作点から切り替えずに直接編集します。Hubは水色の中心点、Tipはオレンジ色の外側の輪です。同一座標でも両方を個別にドラッグできます。中間Spanも同じグラフへ追加します。Section SelectorはBlade ViewとFull Annulusの断面選択に使用します。ImpellerのLE/TE形状タイプ・楕円比は全断面で共通です。Add Spanで任意の内部断面を追加できます。Hub/Tipは削除できません。
- Hub → Tip / Tip → HubのGUIボタンは削除しました。従来のプログラムAPIは互換性のため保持します。
- AngleとThicknessは同一ControlPointEditorです。表編集、Add/Delete、マーカーのDragができます。端点位置は0/1固定、端点の削除は禁止です。
- 通常は編集から150ms後に再計算します。Drag中は50ms間隔を目安に更新し、リリース時にも再計算します。無効入力では最後の有効形状を残して理由を表示します。
- MeridionalではHub/Shroudを同時表示し、Start Z/R/angle、Line Length、Arc Radius/Sweep/CW・CCWを編集します。Add Line/Add Arc/Delete/Move Up/Move Downを使用できます。
- View → Output SettingsでLE/PS/TE/SS点数、有効桁、Component IMP_LE/TE、TurboGrid単位・回転軸・ファイル名・端部設定を編集します。翼端の壁面位置はMeridionalのBlade Edges表で編集します。
- Blade Countは右側上部の「翼枚数 / Blade Count」で設定し、出力に使う枚数と共有します。
- ExportメニューのDiffuser CSVは従来の2D座標形式です。Impellerの3D座標はTurboGrid Exportで出力します。
- 画面下にValidation/Statusを表示します。Throat/Curvature/SolidityとOptimizationの形状判定は既存Diffuser 2Dの値です。

## 子午面・座標定義

長さの内部単位はmm、内部数値はfloat64、角度入力はdegreeです。R-Z平面では水平軸Z、垂直軸Rです。
Start angleは+Zから+Rへ向かう角を正とします。ArcのCCWは正回転、CWは負回転です。

LineはLength、ArcはRadiusと正のSweep Angle（0 < sweep < 360）を入力します。
各Segmentは前の終点・単位接線を継承するため、Line–Arc、Arc–Line、Arc–ArcともG1接続です。
解析円弧長はRadius × |sweep_rad|です。結果にはSegmentの始点/終点/接線とArc中心・半径を保持します。

一般のサンプル列・平均流路のMeridional distanceは累積hypot(dR,dZ)です。
Line/Arcの結果に保持するmは解析弧長の累積値です。総長はLine長とRadius × |sweep_rad|の総和と一致し、表示点数に依存しません。

BladeのLEからTEまで:

```text
m_blade_norm = (m - m_LE) / (m_TE - m_LE)
dtheta/dm = rotation_sign * tan(beta_m) / R
X = R*cos(theta)
Y = R*sin(theta)
Z = Z
```

βm=0は局所Meridional方向です。Diffuserの半径方向曲線ではradial vaneに相当します。
Angle/Thicknessはgeometry/distributions.pyの共通PCHIPを通ります。
v0.2の厚さ端点ゼロ勾配Hermiteは、正本仕様に従いPCHIPへ変更しました。

HubはHub壁面、TipはShroud壁面を使用します。翼LE/TEは各壁面の独立した弧長fractionで指定し、その4つの翼端を含む壁面対応をSpanで線形補間します。
各断面自身の累積Meridional distanceを用いてm_blade_normを定義します。
IMP_LE/IMP_TEの既定m_flow_normは0.15/0.85で、上流・下流の余白を確保します。
厚さは局所Meridional–周方向の法線方向へ配置し、壁面上のMeridional位置・θへ変換します。3D CAD面ではありません。

PS mappingは推定です。Impeller Autoは正の平均βmで負法線をPSとし、負の場合は正法線をPSとします。
+Normal/-Normalの明示選択も可能です。実際の流れによるPS/SSの確定は行いません。

## 計算精度・Validation

Camber/PS/SS masterの既定値は2001点、端部401点、Span壁面8001点、平均流路4001点、Area501点です。
Projectのresolutionで内部解像度を独立設定できます。Output点数とは分離しています。
出力点数を変更してもmaster形状と既存DiffuserのMetrics/Curvature/Throatは変わりません。

検証対象: 非正Length/Radius、ゼロ/360度以上Sweep、NaN/Infinity、非正R、子午面自己交差、Hub/Shroud交差・接触、
断面Span重複/逆順、制御点不正、端部設定不正、流路外へ出る翼、翼輪郭自己交差/内部厚さ縮退。
子午面交差はLine/Circleの解析判定、翼輪郭はmaster点の子午面–周方向chartで判定します。
LE/TEの厚さ0による鋭い端部は使用できます。

Throat最小位置がLE上にあっても拒否・警告理由にしません。既存の連続Throat計算を保持しています。

## Flow PathとGross Flow Area

選択翼列の翼厚差引き面積とスロートは、`View → Passage Area / Throat → Calculate`で確認します。Impellerでは主翼間の参考値、主翼→スプリッター、スプリッター→次の主翼を分け、断面面積とSpan別の最小幅、Hub–Tip積分による近似スロート面積を表示します。形状編集後は再計算してください。曲線壁の幅は3D直線距離の下限推定で、厳密な壁面拘束付きスロートではありません。[定義と制限・操作手順](docs/PASSAGE_ANALYSIS.md)を参照してください。従来の`View → Flow Area`の総面積表示は維持します。

INLET < IMP_LE < IMP_TE < DIF_LE < DIF_TE < OUTLETを保存します。
領域はInlet / Impeller / Vaneless Diffuser・Gap / Vaned Diffuser / Outletです。
Component Stationsは既存JSONとの互換性およびFlow Area計算用に保持します。Meridional EditorのStation TableとStation値一覧は画面から撤去しました。翼端の位置はBlade Edgesで編集します。
IMP_LE/TEと従来のblade_le_fraction/blade_te_fractionは同じ値を参照する互換aliasです。

流路全体の平均流路距離:
m_flow_norm = (m - m_inlet) / (m_outlet - m_inlet)。
Blade Row内のm_blade_normとは区別します。

共通の壁面弧長fractionへHub/Shroudを再サンプリングし、独立関数で平均流路を生成します。
局所単位接線に直交する法線と、有限長のLine/Arc壁面との交点Ph/Psを解析的に求めます。
L_hs=|Ps-Ph|、Rc=(Rh+Rs)/2、A_gross=2π Rc L_hs。
軸流はπ(Rs²-Rh²)、半径流は2πRbへ一致することをテストしています。
Blade blockageやEffective Areaは計算しません。

Area PlotはNormalized Flow Meridional対Gross Flow Area [mm²]です。
Station面積表とA/A_IMP_LE、m、領域、Hub/Shroud R、Passage Lengthを表示します。
面積プロット上のマウス移動、Station表選択、Meridionalクリックが相互に連動します。
壁面交点がない位置はN/Aと明示し、曲線もその箇所で切ります。外挿で面積を捏造しません。
新規既定流路の出口は両壁R=135 mmへ揃えています。読込済み流路を自動で延長・変更しません。

## Output・TurboGrid

既定点数はLE=21、PS=101、TE=21、SS=101、有効桁数6（設定範囲1～15）です。
JSONはfull precisionです。Export時だけformat(value, ".6g")相当に丸めます。

TurboGrid Exportで指定したcase directoryに以下を書きます。

編集対象でImpeller・Diffuser・RCなどの翼列を選択してから出力します。子午面を選択中は翼列選択を要求します。静翼は選択翼列の独立設定から、中央3Dと同じ`generate_diffuser_3d`でHub/Tipの2断面を生成し、中間Spanは追加しません。上段2Dと従来のDiffuser CSVは変更しません。

静翼の壁面は、その翼列に所属するHub/Shroudの連続区間を出力します。両壁面への割り当てとLE/TE・全輪郭の包含を確認し、未割り当て・飛び飛び・範囲外なら出力を拒否します。全区間が未割り当ての旧プロジェクトは全壁面を出力します。表示は欠落/分離区間も描画できるため、表示できても出力できるとは限りません。

静翼の翼枚数・回転方向・端部タイプ・軸/単位は選択翼列の設定を使います。Full AnnulusのON/OFFでは出力を変えず、1翼分と翼枚数を記録します。出力時は現在の値を再生成し、無効編集後に画面へ残った前回の有効3Dを代わりに出力しません。丸めで静翼輪郭の点が重なる場合は、有効桁数を増やしてください。

表示輪郭は高密度のmaster、出力は指定点数の再サンプリングです。元の形状と所属範囲を共通化し、座標丸めとサンプリング差を区別します。TurboGridでのLofting・曲線補間・LE/TE認識・壁面への接続・入口/出口の余裕は実機で確認してください。4ファイルは検証後に一時ファイルから個別置換するため、無効形状は既存出力を変更しませんが、置換途中のI/O障害に対する4ファイル一括の原子性は保証しません。

```text
hub.curve
shroud.curve
profile.curve
BladeGen.inf
```

- 内部Z回転軸のXYZを、指定X/Y/Z回転軸へ右手系の巡回置換で変換します。MM/CM/Mへ自動単位変換します。
- 壁面ファイルはラベルなしのX Y Z列、上流→下流順です。各壁面の既定Export点数は501、Projectモデルで独立指定できます。
- profile.curveはHub→内部Span→Tip順。各断面を#行で区切り、LE→PS→TE→SS reverse→LEの閉輪郭とします。
- Segment接続頂点は1回のみ出力し、最後に先頭頂点を1回繰り返します。非縮退の既定輪郭は241行です。
- 鋭い端部などの幾何学的に重複する連続頂点は除去します。独立Segmentの指定点数と、重複除去後の閉輪郭点数は区別します。
- 第4フィールドのle/teマーカーで端部位置を指定します。
- .infはBlade Count、単位、軸、3ファイル名、Number of Blades Per Set=1、確認済みLE/TE設定を出力します。
- TurboGrid端部設定autoはRoundedをEllipseEnd、全断面CutoffをCutOffEndへ対応します。SpanでRounded/Cutoffが混在する場合は該当.inf設定を省略し、profile markersとTurboGridの判定を使用します。
- 既存case directoryへのExportでは同名の生成ファイルを更新します。無効Geometry/設定はファイル書込み前に拒否します。
- TurboGrid固有処理はfileioにあります。Geometry Engineに座標ファイルの構文は含めません。

確認資料（Ansys 2026 R1）:

- [User's Guide 2.1: .infの構文・単位・端部Enum](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i998527.html)
- [User's Guide 10.3.6: 壁面/翼座標と端部マーカー](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i016457045820452615547.html)
- [公式Steam Stator tutorial](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_tutr/i1138740.html)
- [公式stator.zip](https://ansyshelp.ansys.com/public/Views/Secured/Doc_Assets/v261/TurboGrid/stator.zip)内のBladeGen.infを実際に取得して照合しました。

TurboGrid実機Importは未検証です。このPCでANSYS/TurboGridのインストールを確認できませんでした。
使用環境ではLoad TurboGrid Init FileでBladeGen.infを読み込み、軸/単位/Hub-Tip/LE-TE/輪郭方向/Geometry Errorを確認してください。
壁面のCurve TypeはPiece-wise Linearを使用してください。公式資料は多数点の壁面Bsplineを推奨していません。

## Save/LoadとAPI

Schema 0.3を保存し、0.1/0.2およびFlow Path拡張前の0.3も読めます。Migrationはfileio/project_migration.pyに分離しました。
0.1/0.2のβm/厚さ/LE/TEを独立したHub/Tipへコピーし、Default Hub/Shroudを割り当てます。元ファイルを変更しません。
旧0.3は元の壁面・Span対応・翼座標を維持します。初期0.3の翼位置は旧壁面弧長fraction、Flow Path拡張済み0.3は旧法線断面と壁面との交点から独立翼端を初期化します。元のサンプリング格子も保持します。Component Station編集が新しい翼端へ自動伝播することはありません。追加Migrationはfileio/blade_edge_migration.pyに分離しています。
Control Pointの保存名はm_blade_normです。旧API/旧JSONのm_normは互換aliasとして読み込めます。

```python
from blade_designer.models.parameters import BladeParameters
from blade_designer.geometry.designer import BladeDesigner
from blade_designer.fileio.turbogrid_export import export_turbogrid

parameters = BladeParameters()
parameters.sections[1].blade_angle.points[1].value = 40
impeller = BladeDesigner().generate_3d(parameters)
parameters.diffuser_profile.blade_angle.points[1].value = 35
diffuser = BladeDesigner().generate_diffuser(parameters)  # 独立したDiffuser 2D
export_turbogrid("my_case", parameters)
```

旧blade_angle/thickness/edges属性はHubのデータを参照します。Tipは独立しています。Diffuserはdiffuser_profileのblade_angle/thickness/edge_parametersを使用します。従来のgenerate(parameters) APIは互換性のため旧Hub aliasを読み、独立Diffuserにはgenerate_diffuser(parameters)を使用します。
Optimization層は従来のDiffuser用で、ソルバー実行はしません。[設計書](OPTIMIZATION_ARCHITECTURE.md)を参照してください。

## 検証結果と手動チェック

2026-10-04: 追加前は189 passed。最新の全回帰テスト結果は [追加実装報告](V03_ADDITIONAL_REPORT.md) とartifacts/v0.3-additional/stage_results.jsonを参照してください。前回Flow Path拡張の結果はartifacts/v0.3-flow-path/stage_results.jsonに保存しています。

Qtの実際のMouse EventによるDrag、表編集、Section切替、Save/Load、CSV、TurboGridダイアログ接続を自動検証しました。
v03_additional_smoke.pyは画面画像・Default/5-SpanのCCW/CW case・検証JSONをartifacts/v0.3-additionalへ出力します。旧Projectの座標一致と、ユーザーのblade.json/blade.csvが不変なことも検査します。
OS標準ファイルダイアログの人による操作とTurboGrid実機Importは未検証です。

手動チェック手順:

1. 起動し、右Editorをすべて切り替えてもBlade Viewが表示されることを確認。
2. Blade ViewをZoom/Panし、角度/厚さ/LE・TE/子午面を変更。Viewが維持されることを確認。
3. Fit View、New、OpenではViewがFitされることを確認。
4. Hub/Tipを別々に編集して保存・再読込。コピー、中間Span追加/削除も確認。
5. 3D Previewを回転/Zoom/Panし、編集後もカメラが維持されることを確認。
6. 無効Radius/Length/Sweepと交差を入力し、最後の有効形状とErrorを確認。
7. Flow Areaを選択してマウスを動かし、MeridionalのCross-flow lineと情報を確認。MeridionalのStation選択でArea Markerが連動することを確認。
8. MeridionalのComponent Stations編集表が表示されないこと、Blade Edgesを編集しても保存・再読込で既存Station値が保持されることを確認。
9. TurboGrid Exportし、実機で4ファイルをImportして上述の方向とGeometry Errorを確認。

## 既知の制限・次版

- 3DはWireframeです。CAD-quality面、3Dの流れ・性能判定は提供しません。Throat/曲率の既存指標はDiffuser用です。
- PS/SS Autoは幾何学的推定です。実際の流れ条件に応じて明示mappingを使用してください。
- 極端な制御点間隔、大きい厚さ/楕円比、非常に少ない出力点数・有効桁では形状精度が低下します。出力の丸めで異なる点が同じ文字列表記になる場合があります。
- PCHIPはC1連続で、制御点で2階微分に段差がありえます。翼輪郭自己交差検査は有限master点に基づきます。
- 線形Span補間は初期方式です。複雑なHub/Shroudの対応関係、Span方向の面/隣接翼の3D交差保証は将来課題です。
- GUIのNew/Open/Exitは未保存変更を保持しません。必要な設計は先に保存してください。
- 複雑に折り返す流路では複数の法線交点が生じます。対応する壁面seedの近傍から局所枝を選び、同距離の曖昧な枝や交点欠損はErrorとします。高度な全流路枝追跡は将来課題です。
- Gross Areaの法線断面と独立した翼LE/TE接続線は別のGeometryです。旧0.3は互換サンプリング格子で保持します。
- Flow PathのDIF_LE/TEは流路の領域境界です。従来Diffuser 2Dの半径設定や指標は独立して保持します。今回のTurboGrid出力はImpeller断面です。
- 次版候補: Fillet編集コマンド、B-spline Span補間、PyVistaのSurface Preview、TurboGrid実機検証。
- 今回の対象外: 複数種類のSplitter、Splitter付きTurboGrid出力、Tip clearance、専用Lean/Sweep/LE Rake、CFX・自動Meshing・Optimization実行、STEP/IGES/Solid CAD。TE Rake目標のスタッキングは対応しています。

## Rotation / Undo / Spanwise / Blade Edge 追加機能

- 回転方向の基準は **Viewed from +Z axis**。+Z側から原点を見る視点でCCWが正のθ、CWが負です。ToolbarでCCW/CWを選ぶかReverse Rotationを使用します。
- βm Control Pointをそのまま保ち、θ_LEを基準に周方向の変位だけを反転します。R/Zは保持し、PS/SS・LE/TE・中間Span・Full Annulus・CSV/TurboGridの実座標へ適用します。
- +Normal/−Normalの名称はCCW基準から運ばれる法線です。CWではその法線とPS/SSを鏡映し、入力のβmや明示Mapping設定を保存したまま形状を反転します。
- Edit → Undo/RedoとToolbarのUndo/Redoを使用できます。Undo: Ctrl+Z、Redo: Ctrl+Y / Ctrl+Shift+Z。数値Editor内でもProjectの履歴へ作用します。
- 数値編集はeditingFinishedで1操作、Point/Segment追加削除・移動・コピー・Rotation変更は1操作、継続Drag全体も1操作です。無効入力もUndoできます。選択Sectionを復元し、表示範囲と3D Cameraを維持します。
- 最大200操作。New/Openで履歴を消去し、Saveでは保持します。履歴は実行中のメモリにありProject JSONへ保存しません。
- 3D PreviewはProfiles / Spanwise Lines / Hub Curve / Shroud Curveを独立表示できます。初期値はすべてONです。Surfaceは生成しません。
- Spanwiseは同じLE/PS/TE/SS Segment内の同じ点番号をHub→中間Span→Tipへ結びます。Segment名・segment_fraction・segment_indexを保持します。segment_fractionは各Segmentの3D弧長で再サンプリングした0～1の位置です。点数不一致はErrorです。
- 既定の244本（LE21、PS101、TE21、SS101）のSpanwise lineを描画します。接続端点の重複する線もSegment対応として保持します。Export輪郭の重複除去とは別処理です。

### 独立した翼端とComponent Station

Meridional → Blade EdgesにはIMP/DIFごとにHub LE / Shroud LE / Hub TE / Shroud TEがあります。
hub_m_flow_norm/shroud_m_flow_normは、それぞれの壁面の入口から出口までの**物理弧長を0～1にした値**です。
Flow PathのComponentStation.m_flow_normは平均流路の物理弧長であり、別のデータとして保存します。
互換APIのblade_le_fraction/blade_te_fractionはComponent IMP_LE/TEを参照します。新しい翼端はimpeller_edges/diffuser_edgesを使用してください。

Meridionalに4本の色付きBlade Edge Lineと壁面上のDrag handleを表示します。端点は対応壁面のLine/Arcへ解析的に最近点投影します。
翼端が傾いた場合、可視のIMP/DIF領域境界も翼端の線に合わせます。Area計算とComponent Station値は独立して保持します。
数値表示は12小数桁、内部保存はfloat64のまま、Export有効桁とは分離しています。

各Spanの翼位置は、独立したHub/Shroudの壁面対応を線形補間した流路上で生成します。
各断面自身のm_LE/m_TEからm_blade_norm=(m−m_LE)/(m_TE−m_LE)を計算し、角度・厚さの端点は常に0/1です。
0～1範囲、finite、両壁面と各生成SpanのTE>LE、LE/TE Lineの交差・接触を検査します。

追加Manual Test手順（実機操作は未実施）:

1. Reverse Rotationで鏡映を確認し、Ctrl+Zで元へ、Ctrl+Y/Ctrl+Shift+Zで再反転。
2. βmと厚さのPointを複数回動かしながらDragし、それぞれ1回のUndoで元へ戻ることを確認。
3. MeridionalでIMP LEのHub端点をDragし、Hub壁面に拘束されることと1回のUndoを確認。Shroud、TE、DIFも確認。
4. Hub/TipでLE/TE位置を異なる値へ変更し、中間Spanの位置と各分布の0/1が追従することを確認。
5. 3D PreviewでProfilesとSpanwise Linesを切り替え、同じSegmentの対応点が接続されることを確認。
6. Cameraを回転/Zoom/Panしたまま翼端を変更し、Undo/Redo後も同じCameraと2D Viewであることを確認。
7. 数値を複数回変更して編集完了し、1回のUndoを確認。New/Openで履歴が消え、Saveで残ることを確認。

追加の次版候補: 曲がったLE/TE・Intermediate edge control、Span対応の高度化、3D Surface、履歴のディスク永続化。

## 編集対象・投影方向（2026-10-05）

1. ToolbarでImpellerを選びます。Blade AngleとThicknessにHub/Tip/中間Spanが同時に表示され、各断面の表・操作点を直接編集できます。Section SelectorはBlade ViewとFull Annulusの断面を選択します。
2. ProjectionをXY / XZ / YZから選びます。CamberとLE/PS/TE/SSを実際のXYZ座標から投影し、軸名も切り替えます。
3. ToolbarでDiffuserを選ぶと、専用の角度・厚さ・LE/TEへ切り替えます。インペラの断面設定は保持されます。
4. 対象を戻すと入力値を復元します。Project JSONへ両者を保存します。旧Projectは従来のHubと同じ値を独立Diffuser設定へコピーして初期化します。
5. 投影・対象変更でもZoom/Panと3D Cameraを維持します。形状が範囲外ならFit Viewを使用してください。
6. Undo/Redoは編集した対象と値を復元します。対象・投影だけの切替は設計変更として履歴へ追加しません。
7. 通常EditorにDiffuser Geometry / Optimizationタブはありません。ToolbarのDiffuser選択で角度・厚さ・LE/TEを編集し、OutputでR LE / R TEを編集します。Modeメニューから独立した最適化ウィンドウを開けます。Diffuserの候補、Metrics、CSVは専用Diffuser設定を使用します。Full Annulusは現在の編集対象へ追従します。

Project保存はschema 0.3を維持し、diffuser_profileを追加しました。Projectionと編集対象の選択は表示状態でありJSONへ保存しません。
専用の検証はtools/target_editor_smoke.pyで再現できます。画面画像・独立設定Project・Diffuser CSV・検証JSONはartifacts/target-editorsへ出力します。
人によるNative GUI操作は未実施です。自動Qt検証と画像の目視確認は [検証報告](TARGET_EDITOR_REPORT.md) を参照してください。

## 同時編集の確認

`python tools/simultaneous_editor_smoke.py` でHub/Tip同時入力、JSON往復、最適化別ウィンドウの分離を確認し、artifacts/simultaneous-editorsへ画像を保存します。手動確認では同値のHub/Tipを中心点・外輪から各々ドラッグし、Undo/Redo、Impeller/Diffuser切替、Zoom/Pan保持、最適化モードで候補を適用して通常設計が変化しないことを確認してください。自動GUI検証はQt offscreenです。

## 共通LE/TE・コピー・全周表示

ImpellerのLE/TE画面ではCircular / Elliptical / Cutoffおよび楕円比をHub/Tip・中間Spanで共通編集します。旧Projectで形状設定が異なる場合は、GUI読込時にHubの設定へ統一します。元のJSONを読込だけで上書きしません。各断面の角度・厚さやMeridionalの翼端位置は保持します。DiffuserのLE/TE設定は独立しています。

`Copy Hub → Tip` はHubの角度・厚さのControl PointをTipへコピーし、Tipの既存値を上書きします。`Copy Tip → Hub` は逆方向です。LE/TE形状・壁面・翼端位置はコピーしません。Undoで元の値へ戻せます。

Full Annulusは選択したImpeller/Diffuserと翼枚数を使用します。Impellerでは選択中のHub/Tip/中間SpanのXYZをZ軸周りに配置してからXY/XZ/YZへ投影します。更新によるZoom/Panのリセットはありません。Diffuser CurvatureタブはImpeller選択時に非表示です。

`python tools/shared_edges_annulus_smoke.py` で画面をartifacts/shared-edges-annulusへ生成します。手動確認ではTip選択中のLE/TE変更がHubへも反映されること、Full Annulusの対象・断面・投影と翼枚数、Curvatureの対象別表示、コピー後のUndoを確認してください。
