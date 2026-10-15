# アプリ構造（2026-10-08 調査）

対象は遠心圧縮機アプリ。親フォルダの家計簿は今回の対象外です。
初回コミット時はPython package内65ファイル、test_*.pyは54ファイルです。2026-10-11の翼端R/Z入力追加後はPythonファイル70、テスト65ファイルです。

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

## インペラTE RakeのParameter Mapper（2026-10-15）

BladeParameters.impeller_te_rake_degは任意の目標角（Noneで従来処理）です。generate_impellerは既存β積分と端部/外径処理後、geometry/impeller_parameter_mapper.ImpellerParameterMapperへ生成形状を渡します。MapperはHub固定、β・R/Z・厚さを保持して各断面を軸まわりに剛体回転します。既存の静翼最適化用optimization/parameter_mapperとは役割を分離し、Qt/ファイル形式へ依存しません。

角度の基準はHub/Tip TEキャンバー端点の中点と軸を通る子午面です。chord=v、面法線=nθとしてgamma=atan2(v・nθ, |v-(v・nθ)nθ|)です。半径と軸方向距離から最大到達角を求め、小さいねじれ側の解をbrentqで求めます。正符号は絶対座標+θ（CCW）です。θTE(s)=θTE(Hub)+s*Δθ、θLE(s)=θTE(s)-積分巻き角とし、曲線配列の共有を考慮して一度だけ回転します。Hub/Tip全体の目標であり、Span毎の局所Rake一定や端部キャップ頂点基準ではありません。

JSONはNoneの項目をsnapshotも含めて省略し、旧schema 0.3を維持します。新規項目なしの旧JSON・デフォルト・数値参照を変更しません。GUIはLE/TEタブのチェック付き入力と実測表示を追加し、読み込んだ未編集値は画面丸めで上書きしません。_bind_history_inputsへRake入力を含めてCtrl+Zを維持し、翼列別snapshot・Undo/Redo・New・保存読込へ既存経路で接続します。静翼3D生成はマッピングしません。

tests/test_impeller_te_rake.pyは一定R=120 mm・Hub/Tip軸間隔20 mmの解析式Δθ=2 asin(20 tan(gamma)/(2*120))、β積分、R/Z不変、3D弦からの独立測定、JSON/出力一致、到達不能時の既存ファイル保護を検証します。GUIテストは独立翼列、Undo、入力確定、表示/保存、精度、無効時の表示保持を確認します。3D面全体の交差や空力/応力評価は追加しません。
geometryからQtを呼ぶ構成ではありません。3DはQPainterによる回転面と翼wireframeで、PyVista/VTK/OpenGLの依存はありません。

MainWindowの上部メニューはFile/Edit/View/Toolsの順で1つずつ作り、ツールバーは作りません。ExportはFile、最適化別ウィンドウはTools、回転方向/反転はEdit、投影面はViewへ配置します。回転方向は排他的QActionGroupから非表示の既存radio状態へ渡し、radio変更をメニューへ同期します。投影面も非表示の既存comboへ渡し、_sync_projection_menuで選択値と対象別の有効状態を同期します。非表示Widgetは既存の計算/保存/Undo経路との接続を維持するための内部状態です。ファイル操作や各解析ウィンドウのcallback・ショートカットを変更せず、入口と順序だけを整理します。

Preview3Dのカメラは従来のazimuth/elevation/scale/center/panに自由回転行列rotationを追加します。仮想球上のドラッグ位置の対応から回転を合成し、SVDで直交性を維持します。従来の角度APIは基底方向として残し、投影・面の奥行き/陰影・Fit Viewは同じ回転基底を使用します。正面/上面/側面/等角/リセットでは自由回転を初期化して全体を収め、Fitは回転を保持します。画面操作はパラメータ・Undo履歴・ファイル形式へ保存せず、形状計算と出力処理は変更しません。中央/別ウィンドウの両Previewで同じ操作を提供します。

## 複数翼列（2026-10-09）

`gui/design_navigator.py`は左の子午面・翼列選択と追加/削除/順番変更を提供します。
追加ボタンは名前とインペラ/静翼の種類を指定するモーダルダイアログを開き、確定時だけMainWindowへ種類・名前を通知します。空白名では確定できず、キャンセルでは設計を変更しません。
名前変更ボタンは選択翼列のIDと新しい名前をMainWindowへ通知します。rename_blade_rowはnameだけを変更し、既存のsnapshot履歴で1 Undoとして保存します。空白名・同名・キャンセルは変更しません。Navigator・子午面区間の所属名・Blade EdgesのRow名と形状タイトルを更新します。Blade Edgesは各種類の先頭翼列を表示名の基準とし、同種類の翼列を選択中はその翼列名を優先します。ID・数値・JSON schemaは変更しません。
`models/blade_rows.py`はQtに依存しない翼列snapshot・共通壁面適用・構造検証です。
`BladeParameters.blade_rows`は任意の`BladeRow(identifier, name, kind, parameters)`リスト、`active_blade_row`は現在の翼列IDです。
各snapshotは従来のBladeParametersを保持し、入れ子の翼列リストは禁止します。Hub/Shroud・Flow Path・resolutionは最上位プロジェクトを正本として適用します。
visible_edge_rowsは旧impeller_edges/diffuser_edges APIの互換参照先を、選択中の同種類翼列または最初の同種類翼列として求めます。画面では全翼列IDを管理し、get_parametersのapply_to_rowsで各欄の編集を所有snapshotへ保存します。起動・JSON読込時だけreconcile_visible_row_edgesでトップレベルの表示値を対応snapshotへ引き継ぎ、旧GUIで控えが古く残った場合の選択時の値変更を防ぎます。他の同種類翼列は更新しません。JSON loader/serializer・元のユーザーJSONは変更せず、Undo復元・通常の翼列切替には読込補正を適用しません。
GUIは選択翼列の設定を既存EditorとGeometry Engineに渡します。並べ替えは翼列リストの順序だけに作用し、数値計算・翼端位置を変更しません。
JSONの追加フィールドは任意です。旧Projectは従来のAPI・保存形式を維持し、翼列管理を開始するとsnapshotを初期化します。
保存時は非選択翼列も検証し、無効な翼列がある場合は書込み前に拒否します。CSV/TurboGridは対象種類に合う選択翼列のみを出力します。
別ウィンドウの最適化は選択中のDiffuser、または最初のDiffuserを対象にします。Diffuserがない場合は別ウィンドウ側に追加します。元の設計へ候補を自動適用しません。

## 対象別レイアウト

### 全翼列のLE/TE欄（2026-10-12）

BladeEdgeEditor.row_edgesは全翼列のIDを正本にし、row_controls/all_coordinate_controlsで各翼列の4端点を管理します。表は4×翼列数の行を持ち、名前と順序はNavigatorに追従します。get_parametersはapply_to_rowsで各所有snapshotへ独立した値を保存します。従来のedges/controls/coordinate_controlsはimpeller_edges/diffuser_edgesの互換参照として選択中または最初の同種類翼列を指します。visible_edge_rowsはこの旧APIとトップレベルJSONの互換参照にだけ使用し、画面の翼列数を2組に制限しません。
ContextMeridional.update_edge_groupsは翼列IDごとにLE/TEのBladeEdgeHandlesを作り、キーを同じIDにしてドラッグを正しい翼列へ届けます。名前変更はラベル・凡例へ反映し、削除された翼列のグラフィックスを除去します。既存Component Stationsの個数・Flow Areaデータは変更しません。子午面区間の追加・編集時は全翼列の端点と未適用R/Z入力を処理します。新しいJSONフィールドは追加せず、旧schemaと数値処理を維持します。
この節は従来の「各種類の先頭/選択翼列だけを画面に表示する」説明を置き換えます。再開後の拡張関連108件と最終全回帰457件が成功しました。Git status・差分チェックも実行できています。

`main.create_window`はユーザー指定のblade_v03.jsonをコピーした`blade_designer/defaults/default_project.json`を既存Project loaderで読み、MainWindowのdefault_parametersへ渡します。MainWindowは独立したsnapshotを保持し、起動・New・別の最適化ウィンドウで再利用します。`--project`は起動値を上書きします。プログラムからdefault_parametersを省略して作るMainWindowと数値モデルBladeParametersの既定値は、既存API・歴史的回帰ケースの互換性のため従来値を維持します。数値計算層からJSONへ依存しません。
翼枚数は既存ParameterPanel.controls["vane_count"]を右側上部へ移して使い、既存の更新・保存・Undo経路を維持します。所属する翼列の設定に追従し、子午面選択時は隠します。

中央の縦Splitter（model_splitter）上段のQStackedWidget（central_views）は、子午面選択時に既存meridional_editor.context、翼列選択時に単翼形状または全周形状を表示します。子午面グラフを中央へ移し、右Editorには数値・区間・所属翼列の表を残します。グラフとドラッグ信号・Undo・所属オーバーレイは同じインスタンスを使用します。角度・厚さのグラフは右Editorに置き、これらのタブ切り替えでは中央の翼形状を維持します。下段のmodel_preview_3dは子午面選択時に全翼列、翼列選択時にその翼と所属壁面区間を表示します。Full Annulusのチェックは保持し、子午面選択中の2Dチェック変更で子午面グラフを隠しません。翼列へ戻ると選択に従って単翼/全周を復元し、設計値・JSON・カメラを変更しません。
Preview3Dはbase_linesを保持し、全周表示時だけ選択翼列の翼枚数でZ軸回転して描画します。全周の各線は描画用に最大151点へ間引き、元の計算・出力座標は保持します。Impellerは既存3D計算、Diffuserはgenerate_diffuser_3dで子午面上の断面を生成します。Viewのpreview_3dも選択翼列の同じ3D形状を表示します。数値計算とドラッグ/Undo処理は共通です。点のクリックも選択として処理し、右側の狭いグラフでドラッグ開始距離に達しない操作を扱います。
右Editorは子午面選択時にMeridionalだけ、翼列選択時にBlade Angle / Thickness / LE / TE / Full Annulus（LE / TEは1タブ）を表示します。最適化専用モードではOptimizationも表示します。
Component Stationsの編集表を可視レイアウトから外し、子午面のStation値一覧を非表示にしました。旧station_table APIとFlowPathParametersは保存互換性・Flow Area計算のため維持します。Blade Edgesは引き続き独立して編集できます。
下部Contextは表示レイアウトから除去しました。解析Widgetと内部APIは保持し、Viewメニューからスクロール可能な別ダイアログで開きます。Outputも同じ仕組みです。
中央表示/右Editorは横方向Splitterで幅を調整できます。スクロールとサイズポリシーで編集内容の最小高さがメインウィンドウへ伝播することを防ぎ、起動時は利用可能画面サイズに合わせます。

## 中央下部の対象別3D（2026-10-12）

MainWindow._update_central_previewは子午面選択時に全翼列のrow_parametersを既存3Dエンジンへ渡し、Preview3D.update_rowsで名前・ID付きの翼線とSpanwise線を合成します。Full Annulusには線ごとの所有翼列の枚数を使い、共通壁面の回転面は1組だけ表示します。無効な翼列は名前付きエラーで除外し、他の有効な翼列と2D編集を維持します。
翼列選択時は既存の選択翼形状を維持し、geometry/row_domain.preview_wall_chunksでその翼列に所属するHub/Shroudの連続区間を解析的な端点を含めて描画用にサンプリングします。全未割当なら全壁面、割当がある場合は未所属の壁面は描かず、離れた区間同士を面で結びません。出力時の連続区間・翼包含検証とは独立し、保存データと計算は変更しません。
設計snapshotと表示対象をキャッシュし、タブ・全周表示だけの変更では翼を再計算しません。形状更新時にキャッシュを無効化し、Project復元中の入力再構築からは更新せず、完成した幾何形状で中央3Dを更新します。カメラ・表示チェックを保持します。Viewの別3D Previewは従来どおり選択翼列を表示します。

## Hub/Shroud回転面（2026-10-11）

回転面描画: geometry/revolved_surface.pyはHub/ShroudのZ/RからZ軸回りの閉じた全周quadを返します。描画用に子午面最大49点・周方向48区間を使用し、元の計算・壁面サンプリング・出力は変更しません。Preview3Dは面をカメラ奥行き順に半透明で描き、その上へ従来の翼wireframeを描きます。Hub/Shroudの元の線配列は内部API用に保持し、線としては描画しません。既存の表示チェックは面に作用します。全周翼表示で壁面を重複生成せず、常に1組の回転面を保持します。Fit Viewは回転面の全頂点を含めます。中央とViewの別3D Previewへ同じ描画を適用します。

## 編集Widgetの整理（2026-10-11）

ProfileDistributionEditorは共通PlotWidgetをControlPointEditorのshared_plot引数へ渡します。断面ごとの一時PlotWidgetを作成・破棄せず、曲線・ハンドルだけを共有グラフへ追加します。グラフの所有者はProfileDistributionEditorのままです。ControlPointEditorの単独利用、表編集・ドラッグ・既存転送APIは維持します。Impeller表示では直後に上書きされるDiffuser曲線の更新を省き、選択断面を直接表示します。数値計算・既定値・ファイル形式は変更しません。

## インペラTEの円筒Cutoff（2026-10-11）

geometry_3d.generate_impellerは解析的なHub壁面上の指定TE位置から共通半径Rを取得します。Cutoffの断面だけへ渡し、blade_section.generate_sectionは各Span壁面のR交点のうち指定TEに最も近いものを選びます。断面の正規化座標はLEから実際の円筒切断位置までの0～1へ対応します。PS/SSの長い側を交点で切り、短い側は終端角度・厚さを一定として交点まで延ばします。延長に必要な仮想camberが有限壁面を越える場合は終端の壁面接線を継続して角度だけを求め、実際の翼座標は有限壁面上に置きます。TEはR一定・Span内Z一定でPS/SS端点をつなぎます。円形・楕円TE、LE、2D Diffuserの処理は維持します。

cylindrical_cutoff.pyはサンプリング済み子午面の交点・展開面上の切断と延長を扱い、Qtや出力形式に依存しません。到達不能、LE以前の切断、外径を越える輪郭は拒否します。表示・TurboGrid出力は同じ3D形状を使用します。新しい設定フィールドはなく、元JSON・デフォルト用JSONは変更しません。従来のCutoffを含むJSONは読込後に新しい円筒Cutoffで再計算します。

## 子午面区間の所属と出力

MeridionalEditorのType列はLine/ArcのQComboBoxです。geometry/meridional_segments.convert_segment_typeで経路長とblade_row IDを保持したパラメータを生成し、選択区間だけを置換します。Line→Arcは既定Sweep=35°と長さからRadiusを求め、Arc→LineはR×|Sweep(rad)|をLengthへ渡します。数値処理はQtに依存せず、非正・非finiteの長さは拒否します。表の種類別入力欄と中央プレビューを更新し、既存editFinishedで1 Undoになります。JSON schemaは変更しません。

翼端R/Z入力: gui/blade_edge_editor.pyは全8端点のR/Zを表示し、Applyで編集された座標ペアだけをgeometry/blade_edge.project_to_wallの解析的なLine/Arc最近点へ投影します。結果の壁面距離を既存BladeEdgePositionへ保存し、表示を実座標へ戻します。座標入力中は設計を変更せず、ApplyのparametersChanged/editFinishedで一括更新・1 Undoとなります。MeridionalEditorの有効な壁面更新と翼端ドラッグで表示座標を再取得します。既存normalized controls APIは非表示で保持し、JSONフィールド・計算・出力は変更しません。
末尾への区間追加では、geometry/blade_edge.rescale_extended_wall_edgesが追加側のLE/TE正規化距離に旧全長/新全長を掛け、既存壁面上の物理距離とR/Zを維持します。MeridionalEditorは現在の端点を換算し、wallExtendedでMainWindowの非選択翼列snapshotも換算します。追加と換算は既存editFinishedで1 Undoとなり、未適用座標入力は表示更新後に復元します。JSON形式は維持し、削除・移動とProject読込には換算を適用しません。
子午面の開始条件と区間数値のCompactDoubleSpinBoxはsetKeyboardTracking(False)でキー入力中のvalueChangedを保留し、フォーカス移動・Enterの確定時だけ既存の計算経路へ渡します。setValue・スピン操作・種類/方向選択の既存経路は維持し、editingFinishedによるUndo記録も維持します。
寸法・開始条件・種類変更はMeridionalEditor._edit_wallで候補壁面を生成し、既存の流路検証を行います。geometry/blade_edge.adapt_wall_edge_coordinatesは旧端点を新壁面へ解析的に最近点投影し、壁面上に残る位置は維持、外れる位置は投影座標へ更新します。現在の2組とMainWindow._other_row_edgesで取得した非選択snapshotの全端点を計算してから、曲線と端点距離をまとめて反映します。壁面自体が無効な場合だけ入力欄とモデルを元へ戻して理由を表示します。翼端が壁面出口へ重なって生成翼が無効になる場合も壁面編集を優先し、既存の形状・保存検証を維持します。未適用のR/Z入力を保持し、壁面変更と翼端調整を既存Undo経路で1操作として記録します。新しいJSONフィールドはありません。

LineSegmentParameters / ArcSegmentParametersに任意のblade_row IDを保持します。Hub/Shroudはプロジェクト共有で、区間定義と所属を一緒に移動・削除します。MeridionalEditorは所属列と色・名前のオーバーレイを提供します。保存時は翼列IDとの整合性を検証し、未割り当ての旧JSONには新キーを出しません。翼列削除時は共有壁面と残るsnapshotの所属を解除します。
Qt・ファイル形式に依存しないgeometry/row_domain.pyが解析的な区間長から物理距離の連続範囲を返します。TurboGridの壁面サンプリングだけへ適用し、元の翼形状計算・プロファイル座標は変更しません。両壁面の連続性、LE/TEと輪郭の包含をファイル書込み前に検証します。全区間未割り当てなら旧来の全壁面出力です。Diffuser CSVは元々壁面を含まないため、所属では輪郭を切り詰めません。

## 依存環境

Windows 11 build 26300、Python 3.12.14の既存.venvを確認。
直接依存: NumPy 2.5.3 / SciPy 1.18.1 / PySide6 6.11.2 / PyQtGraph 0.14.0 / pytest 9.1.1。
pip checkは成功。標準ライブラリはdataclasses、enum、json、csv、pathlib、copy等。
requirements.txtは既存の非固定指定を維持。requirements-windows-py312.lock.txtは現在の全依存の記録で、新規環境への再インストール結果ではありません。

## Diffuserの子午面3D

geometry/geometry_3d.pyのgenerate_diffuser_3dはdiffuser_profileをSpan 0・1へ独立コピーし、diffuser_edgesのHub/Shroud LE/TEで壁面対応を作ります。共通の_generate_rowとgenerate_sectionを使い、子午面の実座標から各Spanの角度積分・厚さ・翼端を計算します。Impeller専用の一定外径TE Cutoffは適用せず、静翼Cutoffは従来の局所端部処理です。戻り値は既存のHub/Shroud/sectionsを持つ3D geometry型を共有し、Qtには依存しません。Preview3Dは既存の区間別Spanwise接続・回転面・全周描画を再利用します。上段2D・曲率・指標・CSVは既存generate_diffuserを維持し、JSON schema・保存検証・旧データ移行を変更しません。 MainWindow._display_geometryは追加3D計算のエラーを独立して捕捉し、2Dを更新しながら3Dのみ前回の有効形状を保持して理由を表示します。従来の2Dとして有効な編集を新しい3D検証で阻止しません。

## リソース・入出力

- パッケージ内の常設画像リソースは見つかりません。グラフ・wireframeは座標から描画。
- blade.json / blade.csv: ユーザーの作業データ。変更せずGit対象から除外。
- tests/fixtures/*.json / *.npz: 旧プロジェクト・既存実装座標の回帰資料。Git対象。
- artifacts/: 過去の画像・検証結果・zip・ANSYS形式資料・今回のログ。Git対象から除外。
- 読込: Project JSON schema 0.1/0.2/0.3、起動時--project。
- 書出: Project JSON（内部精度）、Diffuser segments/contour CSV（有効桁）、選択Impeller/静翼のTurboGrid hub.curve/shroud.curve/profile.curve/BladeGen.inf。
- TurboGridで実際にImportする確認とCAD/CFD連携は今回実行していません。

### 静翼TurboGrid出力（2026-10-13）

fileio/turbogrid_export.pyは従来のImpeller計算経路を維持し、選択行のkindがdiffuserならrow_parametersで独立snapshotへ共有壁面等を組み合わせ、generate_diffuser_3dを呼びます。RCは名前であり同じdiffuser種類です。静翼のauto端部判定はdiffuser_profile.edge_parametersを参照します。geometry/row_domain.export_wall_intervalsへ対象edgesを渡し、所属IDは元プロジェクトから取得して両壁面の連続性と静翼LE/TE・全輪郭の包含を検証します。edges省略時のImpeller互換APIは維持します。

MainWindowは子午面選択中の出力を拒否し、翼列選択時は保留編集をcommit_editで確定して現在値を出力関数へ渡します。3D生成・JSON schema・CSV・Preview3Dは変更しません。静翼の丸め後の輪郭縮退/対応点数の不一致をファイル作成前に拒否します。書込みの個別os.replaceによるI/O障害時の原子性は従来どおりで、ケース全体のトランザクションは追加しません。

tests/fixtures/turbogrid_impeller_sha256.jsonは実装変更前のb751f27で生成した3ケース/12ファイルのLF正規化ASCIIハッシュです。歴史的な出力互換性の基準であり解析解ではありません。静翼は別途、円錐壁面の解析座標・回転/単位・所属端点・独立設定・GUI出力と現在3Dの一致を検証します。

既存の詳細仕様・変更報告はプロジェクト直下のV03_*.md、各EDITOR_REPORT.md等を維持しています。最新のユーザー要求を優先し、旧仕様から動作を勝手に戻さないでください。

## スプリッター（主翼連動/専用分布、2026-10-15）

BladeParameters.splitterは任意のSplitterParameters（Hub/Tip開始割合、ピッチ割合、厚さ倍率、任意の専用sections）です。Noneは無効で、JSONの追加キーをsnapshot内も含めて省略します。旧schema 0.3・既定値は維持し、任意フィールドのあるJSONは対応版で開きます。

generate_impellerは主翼とTE Rakeの生成を完了した後、geometry/splitter.pyへ渡します。主翼配列は変更せず、ImpellerGeometry.splitter_sectionsに別の断面リストを保持します。生成はQt/ファイル形式に依存しません。各Spanで主翼の実効m_LE/m_TE（Cutoff後）を使い、m_start=m_LE+f(s)*(m_TE-m_LE)、f(s)=(1-s)*fHub+s*fTipとします。generate_sectionの任意引数で開始位置・厚さ倍率・TE周方向目標を指定し、β・厚さの評価座標はf+(1-f)*m_splitterです。各断面のTE θを主翼TE θ + rotation_sign*2π/N*pitch_fractionへ配置し、主翼TE Rakeを継承します。新しいLE端部を生成し、既存の断面検証と一定外径Cutoffを再利用します。

GUIはImpeller専用のSplitterタブ内にSplitterEditorを配置します。未編集値の精度、入力確定、Undo、独立翼列snapshot、New/JSON読込へ接続します。2D・Full Annulus・中央/別3D・子午面選択時の全翼列3Dは同じsplitter_sectionsを描画し、各翼列の主翼数Nで複製します。初期はsections=Noneで主翼連動、独立チェック時に主翼の各Spanの制御点を深いコピーで取得します。専用β・厚さの座標軸も元の主翼の0〜1とし、開始位置で切り出すことでコピー時の形状を完全維持します。専用ProfileDistributionEditorは初回使用時に生成し、追加・削除・ドラッグ・表入力・Undoへ接続します。厚さの曲線は倍率適用前です。主翼に新しいSpanが増えた場合、splitter.independent_profileで保存済み専用Spanの間を補間します。専用分布と主翼分布は保存/復元後も別オブジェクトです。複数種類・3D翼間干渉は追加していません。

TurboGridの複数翼セットに対応する出力形式はこの実装の範囲外です。export_turbogridはスプリッター付きImpellerをファイル作成前に拒否し、主翼だけの不完全な出力を防ぎます。静翼と無効時の既存出力は変更しません。tests/test_splitter.pyは解析β巻き角・分布切出し・主翼不変・Rake/Cutoff/CW/CCW・JSON精度・出力保護を、tests/test_splitter_gui.pyは編集確定・Undo・独立翼列・同一表示座標・全周枚数・保存読込を検証します。
