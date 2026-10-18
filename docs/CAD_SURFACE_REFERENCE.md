# CAD参照面の表示（Stage 3A-2c・参照表示部分）

## 操作

Impellerを選択して`View → CAD Surface Reference`を開く。現在の設計を読取り専用で取得し、CADと同じmaster対応座標・端部接線・tensor splineから翼面の参照線を表示する。通常の中央3Dと既存の`3D Preview`は従来方式のまま。

- `Refresh`: 現在の選択翼列と設計snapshotを取り直す。
- `Main / Splitter`: 主翼または存在するSplitterを選ぶ。
- `補間格子`: 33/65/129/257/513を明示して参照面を作る。初期値65は表示設定であり、設計JSONへ保存しない。
- `実CADの採用格子を使用`: 同じsnapshotの直近CAD結果からrole別の格子を取得する。[照合条件と検証](CAD_ADOPTED_SURFACES.md)。
- `Full Annulus`: 選択した翼集合を、その翼列の枚数でZ軸回転して表示する。主翼とSplitterを混ぜて合否判定する機能ではない。
- Camera・正面/上面/側面/等角・Fit・Profiles/Spanwiseを使える。同じ表示中の格子・翼集合・Refresh変更でCameraを保持する。翼集合や全周へ切替えて表示範囲を調整したい場合は「全体」を押す。初回表示や無効化後の再取得は従来Previewの初回Fitを使う。

表示は取得時点のsnapshot。設計/対象が変わったら結果を無効にして参照画面を隠す。再取得するまで古い図を現在形状と表示しない。Hub/Shroud壁面がFit範囲を支配しないよう、この画面は翼のLE/PS/TE/SSだけを表示する。元の壁面、camber、端面、根元filletをこの参照面へ混ぜない。

静翼/RC、派生Shroud/外径カット、子午面だけの選択、不正入力は明示的に拒否する。派生形状は円筒補間を使う別契約であり、CADの高次面として黙って再生成しない。既存の出力ガードはそのまま。[派生元面](DERIVED_SOURCE_CONTRACT.md)。

## 共通化した処理

`geometry/cad_surface_reference.py::join_surface_tangents`へ、既存OCCT backendの端部接線計算を演算順を変えずに移した。`OcctBackend._join_tangents`はこの数値関数を呼ぶ。role別の導関数、方向平均、中央値の大きさ、SSの逆向き、cutoff端部の例外を維持する。Qt/OCPや外部ファイル形式をこの層へimportしない。

`reference_surfaces`は実masterのm_normをrole内で0〜1へ局所化し、metadataのない端部はindexを使う。これはCAD clientの既存入力契約と同じ。共通接線と`surface_evaluation.fit_surface_spline`から、各roleの数値面を作る。CAD clientのNPZ書式やparameters snapshotは変更していない。

`reference_lines`は数値面を直接評価する。Spanは31点、role内xiは101点で、xiの5点ごとにSpan方向の等パラメータ線を描く。各元断面Spanの輪郭線も同じ面から評価する。従来Previewの表示点番号を結ぶ直線へ置き換えてから表示する処理は使わない。ただし、画面へ描く各曲線自体は有限点のpolylineである。

`gui/cad_surface_reference_widget.py`が表示設定・取得snapshot・失効を管理し、MainWindowにはメニュー入口だけを追加する。`Preview3D.update_surface_reference`は別widgetの描画データを受け取り、通常の生成器・2D画面・設計値・履歴・既存Cameraには触れない。

## 一致の範囲と誤差予算

| 比較対象 | 今回の契約 | 成功としない項目 |
|---|---|---|
| 固定密度の数値参照面とOCCT面 | 同じmaster、xi、Span、接線、密度を入力したときの同じtensor spline | 全面偏差、物理対応、正常solid、STEP再読込み |
| 変更前後のCAD | 接線計算と係数・knot・degree・評価点を保持 | 公差緩和や、既存失敗形状の成立 |
| 実CAD出力 | 従来どおりrole別に33→65→129→257→513からmaster点の偏差条件で密度を選ぶ | 参照画面の65格子と、出力で選ばれた全roleの面が自動で同一という保証 |
| 参照表示のpolyline | 上記数値面上の31×101標本と等パラメータ線 | 描画線の標本間偏差上限、法線反転、自己交差・翼間干渉 |
| 従来Preview/trim | 互換方式を維持し、参照画面と明示的に分離 | 全経路を単一正本へ切り替えたという主張 |

実出力の`surface_grid_counts`と参照画面の補間格子が同じ場合に限って、同じ入力・roleの面を比較できる。自動密度はroleごとに異なることがある。初期実装は単一固定密度だったが、追加した採用格子モードでは同じsnapshotの実CAD結果からrole別の密度を取得できる。root topology・capは引き続き対象外。[採用格子の契約](CAD_ADOPTED_SURFACES.md)。

実CADのmaster点の偏差条件・cap/sewing/BREP/fillet/STEP公差は変更しない。新しい面全域の誤差予算やPASS閾値は設けていない。標本上の浮動小数点一致を設計精度や全面保証へ換算しない。表示設定は設計JSONやUndoへ追加しない。

## 検証記録

新規22件（非Qt数値13、Qt offscreen 7、実OCCT 2）。独立した正方形の接線方向とcutoff例外、3次曲面の中間Spanと直線chordの差、格子33/65/129/257/513、Rake/gap/専用Splitter、入力不変、不正格子・断面数差、GUIメニュー、Camera・Undo・選択、stale結果の失効、書込み/CAD job非実行、未対応入力拒否を確認する。実OCCTは独立backend processで33/129格子の4 roleを13×23内部点で照合する。backend未導入時は既存と同じoptional skipであり、成功件数へ含めない。

初回関連35件成功（37.74秒、`20261017T232238Z-ded48769`）。取得し直しでもCameraを維持する検査を追加してGUI 6件成功（2.26秒、`20261017T232401Z-6be72ba6`）。参照画面を翼面だけに整理してwireframeを含む10件成功（2.15秒、`20261017T232516Z-6c4ee6fd`）。captionを参照表示と明示した最終関連35件成功（36.52秒、`20261017T232600Z-f375d74f`）。既存数値fixture・期待値は変更していない。

変更前commit `fe228599d1e47ce4c2c8bd55f9b6a8178bb87856`のCAD/trimを独立moduleとして読込み、既定Impeller/Diffuser/RC、半径方向3断面、強ねじれ、Rake/gap/Splitter、派生カットの7条件・40patchで旧/新接線とOCCT全pole/knot/degree/評価点が一致した。派生30曲線の従来配列も一致し、原本JSONのhashを維持した。共通数値評価と実OCCTの最大標本差6.07105e-14 mmは演算評価の比較であり、物理精度ではない。根拠は`artifacts/quality-stage3a2c/probe_surfaces.py`、`surface-probe.json`。未対応の静翼/派生CADを出力した結果ではない。

offscreen画像を900×700で生成し、主翼・Splitter・Full Annulusで線全体が表示範囲へ収まり、操作欄とsnapshot表示が読めることを確認した。最初はoffscreenの空フォントDBで文字が四角になったため、画像確認スクリプトだけでWindowsのSegoe UI/Meiryoを明示読込みした。アプリのフォントや設定は変更していない。`render_reference.py`、`reference-main-verified.png`、`reference-splitter-verified.png`、`reference-annulus-verified.png`を同じartifact領域へ保存した。これはnative Windows、高DPI、実マウス操作の検証ではない。

翼列一覧のない旧形式JSONでは、選択種別がGUI内にだけ存在する。そのためMainWindowの取得入口で静翼選択を拒否する検査を追加し、現在の対象と異なるImpellerを表示しないようにした。最終GUI関連17件成功（29.27秒、`20261017T232906Z-a0719466`）。

この旧形式の追加検査のため、初回全回帰は専用orchestratorのcommand line/生成時刻/親子関係を確認したprocess treeだけを停止し、部分結果は採用していない。終了済みprocessへの停止通知の競合はあったが、同じPID/生成時刻の残存processがないことを確認した。最終全回帰は別領域`artifacts/quality-stage3a2c-final/`から固定入力で再実行した。試験失敗とは別の停止処理の記録である。

確定結果は次節に記録する。

## 残る改善

実CADのrole別採用密度の適用は[追加対応](CAD_ADOPTED_SURFACES.md)で実施した。加工TE/cap/STEP後の参照、面全域の偏差・法線・Jacobian、周期翼/主翼-Splitter干渉、物理対応を含む単一正本への移行・互換条件は残る。参照取得は同期処理で、大規模設計・多数翼の応答性とworker化はStage 6で扱う。Stage 3A全体は未完了。実モデル根元フィレット成立とANSYS Import/MeshはNOT_TESTED/未成立の既存記録を維持する。


## 最終全回帰

**1,101一意件成功**（通常1,062・実CAD39）。既存1,079 IDを全て維持し、新規22 IDを追加した。failure/error/skip/実行漏れ/重複/想定外IDは0。固定253入力（package/test Python、main、既定JSON、原本JSON）は回帰開始から終了までhash不変で、原本と同梱デフォルトの一致も確認した。既存数値fixture・期待値は変更していない。

通常6群・CAD1群のJUnitと収集IDを照合した。根拠は`artifacts/quality-stage3a2c-final/final-test-coverage.json`、`source-hashes.json`、`groups.json`。停止した初回の部分結果は含めない。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 407.243 | 20261017T233004Z-cc31237b |
| 通常1 | 143 | 363.487 | 20261017T233004Z-f958a409 |
| 通常2 | 122 | 421.653 | 20261017T233004Z-798e8908 |
| 通常3 | 191 | 296.586 | 20261017T233004Z-4bf2d747 |
| 通常4 | 146 | 388.613 | 20261017T233004Z-94aab8c0 |
| 通常5 | 344 | 481.287 | 20261017T233004Z-c5b568ad |
| 実CAD | 39 | 814.827 | 20261017T233004Z-e10d3a68 |

最終回帰の実行中、ログ確認用の追加シェル操作が利用上限による自動承認レビュー失敗で実行されなかった。テストprocessは継続して完了しており、再開後にJUnit/試験IDと現時点の253入力hashを照合して不変を再確認した。この承認処理の失敗をテスト失敗やskipへ算入しない。

実OCCT試験の成功をnative Windows操作、高DPI、実モデル根元フィレット成立、STEP/ANSYS Import/Meshの全面保証とは扱わない。参照表示部分の完了であり、Stage 3A全体の完了ではない。
