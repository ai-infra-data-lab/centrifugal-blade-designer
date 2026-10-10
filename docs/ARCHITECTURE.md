# アプリ構造（2026-10-08 調査）

対象は遠心圧縮機アプリ。親フォルダの家計簿は今回の対象外です。
初回コミット時はPython package内65ファイル、test_*.pyは54ファイルです。2026-10-10のデフォルト・翼枚数変更後はPythonファイル68、テスト61ファイルです。

| 場所 | 役割・依存 |
|---|---|
| main.py | argparseでdesign/optimizationとProjectを選び、QApplication・MainWindowを起動 |
| blade_designer/models/ | dataclass/Enum、入力・結果・Validation。数値配列はNumPy |
| blade_designer/geometry/ | PCHIP分布、子午面Line/Arc、G1接続、2D/3D断面、面積・曲率・スロート・全周投影。NumPy/SciPyとmodels |
| blade_designer/fileio/ | JSON保存・旧schema移行、CSV、TurboGrid固有形式。models/geometryに依存 |
| blade_designer/gui/ | PySide6 Widgets、PyQtGraph 2D、QPainterの3D wireframe、Undo。上記層を呼ぶ |
| blade_designer/optimization/ | パラメータ写像・制約・候補判定。models/geometryに依存。探索ソルバーを実行しない |
| tests/ | 解析解・幾何不変条件・旧座標fixture・Qt offscreen・入出力検証 |
| tools/ | GUI画像生成、開発用テスト実行。製品起動経路とは別 |
| docs/ / .vscode/ | 開発手順・調査結果・IDE設定 |

流れ: main → gui → models / geometry / fileio / optimization。
geometryからQtを呼ぶ構成ではありません。3Dはソフトウェアwireframeで、PyVista/VTK/OpenGLの依存はありません。

## 複数翼列（2026-10-09）

`gui/design_navigator.py`は左の子午面・翼列選択と追加/削除/順番変更を提供します。
追加ボタンは名前とインペラ/静翼の種類を指定するモーダルダイアログを開き、確定時だけMainWindowへ種類・名前を通知します。空白名では確定できず、キャンセルでは設計を変更しません。
`models/blade_rows.py`はQtに依存しない翼列snapshot・共通壁面適用・構造検証です。
`BladeParameters.blade_rows`は任意の`BladeRow(identifier, name, kind, parameters)`リスト、`active_blade_row`は現在の翼列IDです。
各snapshotは従来のBladeParametersを保持し、入れ子の翼列リストは禁止します。Hub/Shroud・Flow Path・resolutionは最上位プロジェクトを正本として適用します。
GUIは選択翼列の設定を既存EditorとGeometry Engineに渡します。並べ替えは翼列リストの順序だけに作用し、数値計算・翼端位置を変更しません。
JSONの追加フィールドは任意です。旧Projectは従来のAPI・保存形式を維持し、翼列管理を開始するとsnapshotを初期化します。
保存時は非選択翼列も検証し、無効な翼列がある場合は書込み前に拒否します。CSV/TurboGridは対象種類に合う選択翼列のみを出力します。
別ウィンドウの最適化は選択中のDiffuser、または最初のDiffuserを対象にします。Diffuserがない場合は別ウィンドウ側に追加します。元の設計へ候補を自動適用しません。

## 対象別レイアウト

`main.create_window`はユーザー指定のblade_v03.jsonをコピーした`blade_designer/defaults/default_project.json`を既存Project loaderで読み、MainWindowのdefault_parametersへ渡します。MainWindowは独立したsnapshotを保持し、起動・New・別の最適化ウィンドウで再利用します。`--project`は起動値を上書きします。プログラムからdefault_parametersを省略して作るMainWindowと数値モデルBladeParametersの既定値は、既存API・歴史的回帰ケースの互換性のため従来値を維持します。数値計算層からJSONへ依存しません。
翼枚数は既存ParameterPanel.controls["vane_count"]を右側上部へ移して使い、既存の更新・保存・Undo経路を維持します。所属する翼列の設定に追従し、子午面選択時は隠します。

中央の縦Splitter（model_splitter）上段のQStackedWidget（central_views）は単翼形状と全周形状だけを切り替え、下段のmodel_preview_3dは選択翼列を常時表示します。子午面・角度・厚さのグラフは右Editorに置き、タブ切り替えでは中央を変更しません。Full Annulusタブと上部Viewグループの2D/3Dチェックは独立し、設計値・JSON・カメラを変更しません。
Preview3Dはbase_linesを保持し、全周表示時だけ選択翼列の翼枚数でZ軸回転して描画します。全周の各線は描画用に最大151点へ間引き、元の計算・出力座標は保持します。Impellerは既存3D計算、Diffuserは既存2D輪郭のZ=0表示です。Viewの旧preview_3dは別に保持します。数値計算とドラッグ/Undo処理は共通です。点のクリックも選択として処理し、右側の狭いグラフでドラッグ開始距離に達しない操作を扱います。
右Editorは子午面選択時にMeridionalだけ、翼列選択時にBlade Angle / Thickness / LE / TE / Full Annulus（LE / TEは1タブ）を表示します。最適化専用モードではOptimizationも表示します。
Component Stationsの編集表を可視レイアウトから外し、子午面のStation値一覧を非表示にしました。旧station_table APIとFlowPathParametersは保存互換性・Flow Area計算のため維持します。Blade Edgesは引き続き独立して編集できます。
下部Contextは表示レイアウトから除去しました。解析Widgetと内部APIは保持し、Viewメニューからスクロール可能な別ダイアログで開きます。Outputも同じ仕組みです。
中央表示/右Editorは横方向Splitterで幅を調整できます。スクロールとサイズポリシーで編集内容の最小高さがメインウィンドウへ伝播することを防ぎ、起動時は利用可能画面サイズに合わせます。

## 子午面区間の所属と出力

LineSegmentParameters / ArcSegmentParametersに任意のblade_row IDを保持します。Hub/Shroudはプロジェクト共有で、区間定義と所属を一緒に移動・削除します。MeridionalEditorは所属列と色・名前のオーバーレイを提供します。保存時は翼列IDとの整合性を検証し、未割り当ての旧JSONには新キーを出しません。翼列削除時は共有壁面と残るsnapshotの所属を解除します。
Qt・ファイル形式に依存しないgeometry/row_domain.pyが解析的な区間長から物理距離の連続範囲を返します。TurboGridの壁面サンプリングだけへ適用し、元の翼形状計算・プロファイル座標は変更しません。両壁面の連続性、LE/TEと輪郭の包含をファイル書込み前に検証します。全区間未割り当てなら旧来の全壁面出力です。Diffuser CSVは元々壁面を含まないため、所属では輪郭を切り詰めません。

## 依存環境

Windows 11 build 26300、Python 3.12.14の既存.venvを確認。
直接依存: NumPy 2.5.3 / SciPy 1.18.1 / PySide6 6.11.2 / PyQtGraph 0.14.0 / pytest 9.1.1。
pip checkは成功。標準ライブラリはdataclasses、enum、json、csv、pathlib、copy等。
requirements.txtは既存の非固定指定を維持。requirements-windows-py312.lock.txtは現在の全依存の記録で、新規環境への再インストール結果ではありません。

## リソース・入出力

- パッケージ内の常設画像リソースは見つかりません。グラフ・wireframeは座標から描画。
- blade.json / blade.csv: ユーザーの作業データ。変更せずGit対象から除外。
- tests/fixtures/*.json / *.npz: 旧プロジェクト・既存実装座標の回帰資料。Git対象。
- artifacts/: 過去の画像・検証結果・zip・ANSYS形式資料・今回のログ。Git対象から除外。
- 読込: Project JSON schema 0.1/0.2/0.3、起動時--project。
- 書出: Project JSON（内部精度）、Diffuser segments/contour CSV（有効桁）、Impeller TurboGrid hub.curve/shroud.curve/profile.curve/BladeGen.inf。
- TurboGridで実際にImportする確認とCAD/CFD連携は今回実行していません。

既存の詳細仕様・変更報告はプロジェクト直下のV03_*.md、各EDITOR_REPORT.md等を維持しています。最新のユーザー要求を優先し、旧仕様から動作を勝手に戻さないでください。
