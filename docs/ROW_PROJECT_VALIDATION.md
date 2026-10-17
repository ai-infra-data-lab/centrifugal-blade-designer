# 翼列プロジェクトのLoad／Save検証（Stage 2B-2）

## 保存ポリシー

従来の全snapshotに対する「Impeller 3Dと放射状2Dを両方生成する」検証を、保存データの整合性と宣言翼種の幾何検証へ分離した。未使用の設定を仮の値へ置き換えず、そのまま保存・復元する。schemaの項目・バージョン選択・有効桁・単位・既存writerは変更しない。

| 対象 | 必要な検証 |
|---|---|
| `blade_rows`なしの旧JSON／API | 従来どおり旧半径の外向き順序、Impeller、旧2D、双方LE/TE等を検証する。自動でrow一覧を作らない |
| row一覧ありのroot編集snapshot | 保存する全値の整合性と、active rowの宣言翼種による実3D生成 |
| 各row snapshot | 保存する全値の整合性と、そのrowの宣言翼種による実3D生成。非選択rowも省略しない |
| shared Hub／Shroud／flow_path／resolution | 各rowの実3D生成にはrootの共通値を適用。保存されるsnapshot内の共通値も個別の入力整合性は検査する |

Impellerは`generate_impeller`、DiffuserとRCは`generate_diffuser_3d`を使う。rootとrowの設計値が異なる場合も、片方を黙って上書きせず、両方をそれぞれの宣言contextで検証する。row ID・name・kind・active ID・所属参照・非入れ子の従来検査は維持する。

## 未使用値を保存する条件

`validate_stored_settings`は、旧`validate_parameters`から**旧半径の外向き順序だけを外した**保存用の値検証である。旧半径は両方とも有限・正を要求する。例えば旧r_le=145、r_te=105は宣言rowの子午面3Dに使われなければ保存できるが、負半径、NaN、Infinityは保存できない。

全snapshotについて回転方向・翼数・出力点数／桁数・mapping・角度／厚さの入力範囲・端部type／比率・Span順・diffuser_profile・Splitter／Rake／clearance／trimの値域・CAD／TurboGrid設定を検査する。子午面の各曲線とresolution／component stationの入力整合性も検査する。両翼種のLE/TE端点は有限な0〜1とし、対応knotsとsampling flagも検査する。

一方、非使用翼種のTE > LE、壁面との交差、一定径cutoffへの到達、厚さを持つ翼面の壁面内への収まり等の**幾何成立性**は、その翼種が宣言rowとして存在する場合に検証する。静翼しかないプロジェクトの参考Impellerが不成立でも、値域と実静翼が正しければ保存できる。宣言されたImpellerが不成立なら、非選択でも保存・読込みを拒否する。

旧2D CSV／旧最適化は、実行時に従来の`validate_parameters`を使い、不成立な旧半径等を引き続き拒否する。新たに保存可能となったプロジェクトが、旧2Dでも成立するとは報告しない。

## 互換性と拒否の境界

旧schema 0.1／0.2の移行、0.3／0.4の項目、Hub alias一致、flow_path alias一致、enum、非入れ子rowのデコードは維持する。row snapshotのデコード時には型／項目を復元し、幾何検証はrootのrow kindと共有壁面が分かってから実行する。保存前・公開前に検証を終えるため、検証失敗や`os.replace`失敗で既存JSONを書き換えない。

row一覧なしの旧受入れは維持する。row一覧ありでは、従来は旧2Dのみの成立で通っていた静翼にも実3D成立を要求するため、未成立な静翼を含むファイルは明示的に拒否する。これは検証強化であり、旧2Dの成功を実静翼の成功と見なさないための変更である。新しく保存できる「未使用の旧2Dが不成立なrowプロジェクト」は、旧版アプリでは拒否される場合がある。

## GUIの対応

row一覧のあるLoadでは選択実3Dを先に検証し、不正入力で設計・履歴・project path・現在モデルを置換しない。旧2Dと参考Impellerは選択翼に不要なら任意生成とし、失敗理由を既存のlegacy／referenceメッセージで示す。Saveにあった無条件の参考Impeller生成も、row一覧ありの場合に限って外す。

最適化画面で旧2D不成立のprojectをLoadした場合は、前projectのbaseline／candidate／plot／sourceを解除し、生成・適用ボタンを無効化する。モード変更や直接呼出しでも旧baselineを再使用しない。新規projectや有効なbaselineの再取得で復帰する。通常編集で明示的に取得したbaselineを保持する既存動作は維持する。

## 変更ファイル

- `blade_designer/models/validation.py`: 旧APIを維持した保存用値検証。
- `blade_designer/fileio/project_io.py`: row contextでの検証とデコード後の検証順。
- `blade_designer/gui/main_window.py`: Load／Saveの不要な生成依存を分離。
- `blade_designer/gui/optimization_widget.py`: 読込み時の不成立な旧baselineを解除。
- `tests/test_row_project_validation.py`、`tests/test_row_project_gui.py`: 保存・復元、拒否、保護、GUI操作の追加試験。
- `FEATURES.md`、本書、`docs/ROW_VALIDATION_CONTRACT.md`、`docs/GEOMETRY_SOURCE_CONTRACT.md`、`docs/ARCHITECTURE.md`、`docs/CURRENT_FUNCTION_AUDIT.md`、`docs/GEOMETRY_QUALITY_REVIEW.md`、`docs/DEVELOPMENT_ROADMAP.md`: 現行契約と対応範囲を更新。

## 検証

新規46ケース（保存41・GUI 5）。root／row両方の保存値検査、不正な非選択宣言row、保存失敗とreplace失敗の既存ファイル保護、入力原本不変、roundtrip設計値・全master XYZの完全一致を確認する。GUIでは実engineを使い、読込み→編集→保存→再読込み、Undo履歴、無効読込みの状態保護、最適化の解除・復帰を確認する。既存テストや数値期待値は変更しない。

初期の既存関連123件成功（78.97秒、`20261017T213549Z-40453a7c`）。GUI／旧最適化／既存測定の関連21件成功（65.96秒、`20261017T213805Z-8ae7f7ef`）。最終コードの新規46件成功（21.79秒、`20261017T213945Z-8b61f59f`）。

最終全回帰は**1,002一意件成功**（通常967・実CAD35）。既存956 IDを全て維持し、新規46 IDを追加。failure／error／skip／未実行／重複／想定外IDは全て0。固定241入力は回帰開始からhash不変、原本と既定JSONの一致を確認した。単一pytestプロセスではなく、次の7群のJUnitと収集IDを照合した結果である。根拠は`artifacts/quality-stage2b2/final-test-coverage.json`、`source-hashes.json`。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 401.549 | 20261017T214026Z-a2bd10fd |
| 通常1 | 143 | 359.061 | 20261017T214026Z-0939c319 |
| 通常2 | 122 | 416.100 | 20261017T214026Z-c2d37c18 |
| 通常3 | 191 | 298.424 | 20261017T214026Z-7fee1151 |
| 通常4 | 146 | 386.444 | 20261017T214026Z-5bca96a9 |
| 通常5 | 249 | 417.388 | 20261017T214026Z-733ed919 |
| 実CAD | 35 | 823.205 | 20261017T214026Z-70b02d31 |

変更前のGitソースを独立moduleとして読み込み、正常な4条件（row一覧なし、Impeller選択、Diffuser選択＋CW、既定3翼列）で保存JSONのraw bytesと読込み結果が一致した。旧検証11条件はlevel／field／messageと順序が一致。追跡fixture／既定JSONの6ファイルと原本JSONのhash不変も確認した。根拠は`artifacts/quality-stage2b2/baseline-comparison.json`。新たに許可／拒否する境界は上述の保存ポリシーと区別する。

native画面・高DPI・ANSYS Import/Meshは未検証。3DのSpan面／周期翼／主翼-Splitter干渉、CAD共通surface、実モデルの根元fillet成立、実3D最適化は本変更に含まれない。
