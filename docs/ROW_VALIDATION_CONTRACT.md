# 翼種別の入力検証（Stage 2B-1）

## 変更ファイル

- `blade_designer/models/validation.py`: 旧APIを保持し、翼種別の設定検証入口を追加。
- `blade_designer/geometry/geometry_3d.py`: 選択翼種の設定とLE/TE成立性を検証。
- `blade_designer/geometry/blade_edge.py`: 既存の端点有限性・範囲検査を共通関数へ切り出す。
- `blade_designer/fileio/project_io.py`: 全体JSONの従来受入れを明示的に維持。
- `tests/test_row_validation.py`、`tests/test_row_measurements_gui.py`: 入力分離、従来拒否、座標／入力不変、GUI測定・出力の追加試験。
- `FEATURES.md`、本書、`docs/ARCHITECTURE.md`、`docs/CURRENT_FUNCTION_AUDIT.md`、`docs/GEOMETRY_QUALITY_REVIEW.md`、`docs/GEOMETRY_SOURCE_CONTRACT.md`、`docs/DEVELOPMENT_ROADMAP.md`: 挙動、検証、対応範囲と次段階を更新。

## 変更範囲

`geometry/geometry_3d.py`の生成時検証を、旧radial 2Dと選択3Dの入力に分けた。数値生成式、補間、既定値、JSON schema、出力書式は変更しない。不正値を既定値へ置換しない。

`models/validation.py`の既存`validate_parameters(params)`は旧APIと同じ検査・順序を保持する。新しい`validate_row_settings(params, kind)`は共通設定と翼種固有設定を検査するpreflightであり、単独で幾何成立を保証する関数ではない。実断面、壁面、Span、LE/TEは3D generatorが引き続き検査する。

| 入力 | Legacy 2D／全体JSON | Impeller 3D | Diffuser／RC 3D |
|---|---|---|---|
| 独立した旧r_le／r_te | 従来どおり有限・正・外向きを要求 | 不使用、検査しない | 不使用、検査しない |
| theta_le、翼数、回転方向、PS/SS mapping | 従来どおり | 検査する | 検査する |
| 出力点数、桁数、repeat_first_point | 従来どおり | 共通設定として検査を維持 | 共通設定として検査を維持 |
| 主翼Hub/Tip分布・端部 | 検査する | 全設計Spanを検査 | 不使用、検査しない |
| diffuser_profile | 旧2D生成で検査 | 不使用、検査しない | Hub/Tipへ使用する共通分布を検査 |
| impeller_edges | 検査する | 検査する | 全端点の有限性・0〜1範囲だけ検査 |
| diffuser_edges | 検査する | 全端点の有限性・0〜1範囲だけ検査 | 検査する |
| Rake／trim／clearance／Splitter | 従来どおり | 検査する | 不使用、検査しない |
| 共通Hub/Shroud、flow_path、resolution | 従来どおり | 検査する | 検査する |

旧半径が負値や逆順であっても、その半径を使わない子午面3Dの計算を妨げない。RCの内向きR130→90は、旧放射状2Dの外向きR100→160とは独立している。実際に使う断面、壁面、LE/TEの不成立は従来どおり拒否する。両翼種のLE/TE端点の有限性と0〜1範囲は、未選択でも従来の入力整合性契約として保持する。未選択翼種のTE > LEや壁面上の交差などの幾何成立性だけを選択3Dから分離する。3Dの有効化は、旧2Dの有効化やCFD性能の保証を意味しない。

## Load／Saveの互換境界

この作業単位では**全体JSONの受入れを緩和しない**。保存対象の全row snapshot、旧半径、旧2D、Impeller、双方のLE/TE等が従来契約を満たす必要がある。3D generatorから未選択の`diffuser_edges`検査を外した分は、`fileio/project_io.py::_check`で元のHub/Shroudに対して明示的に検査する。派生trim後の壁面を使って受入れ範囲を変えない。

したがって「静翼3Dは有効だが、使用していないImpeller／旧2Dが不正」という入力は表示・実断面測定・新XYZ CSVで扱えても、JSON保存は拒否する場合がある。保存失敗時の既存JSON保護も維持する。旧2D CSV／最適化の検査を緩和しない。

新しい形状識別metadataはsnapshot全体のJSON表現を使うため、NaN／Infinityや未定義Enumを含む非直列化可能なsnapshotまで新GUI／XYZ出力で保証するものではない。値の修復・省略でこの制約を隠さない。今回のGUI統合検証は有限な旧半径の不成立を対象とする。

## 残るStage 2B-2

row一覧がある場合の「宣言された翼種で成立すべき値」と「保存するだけの非使用値」を分け、旧schema／row一覧なしの受入れを含む保存ポリシーを定義して実装する。非使用の不正値を保存可能にする変更は、この今回の修正には含めない。G01全体、3D干渉検査、実3D最適化、CAD共通surface契約も未完了。

## 検証

新規50ケース。`tests/test_row_validation.py`の49件では、未使用値を変えたときの全master XYZの完全一致、入力不変、選択対象の不正値拒否、Impeller固有設定の拒否、JSONの従来拒否と既存ファイル保護、不明な翼種の拒否、未選択端点の入力整合性を確認する。`tests/test_row_measurements_gui.py`の追加1件では、geometry計算をmockせず有限な不正旧半径を入力し、RC実断面指標とXYZ出力・snapshotの整合を確認する。

初期実装の関連101件成功（61.92秒、`20261017T150830Z-8757fca2`）、新規46件成功（8.64秒、`20261017T150923Z-a7c15634`）。その後の全回帰で既存`test_invalid_endpoints[diffuser_edges-*]`の4件が失敗した。未選択端点のNaN／Inf／範囲外まで許容したことが原因。期待値を変更せず、従来の端点データ整合性検査を`validate_blade_edge_bounds`へ分離して両翼種に保持し、静翼側にも4件を追加した。初回CAD群は管理下の専用プロセスツリーだけを停止し、成功結果として再利用しない。修正後の全回帰は別領域`artifacts/quality-stage2b-final/`で実行した。

端点検査補強後の関連93件成功（52.54秒、`20261017T152008Z-e94b1f49`）。既存の基本検証・Blade Edge・JSON・GUI測定を含む。以前からある端点検査の期待値や数値fixtureは変更していない。

最終全回帰は**956一意件成功**（通常921件・実CAD35件）。既存906 IDをすべて維持し、新規50 IDを追加。failure／error／skip／未実行／重複／想定外IDはすべて0。固定239入力のhash不変、原本と既定JSONの一致を確認した。製品・試験ソースは最終回帰開始から不変。単一pytestプロセスではなく、次の7群のJUnitと収集IDを照合した結果である。根拠は`artifacts/quality-stage2b-final/final-test-coverage.json`、`source-hashes.json`。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 448.877 | 20261017T152119Z-22848336 |
| 通常1 | 143 | 438.950 | 20261017T152119Z-c9959bb3 |
| 通常2 | 122 | 454.844 | 20261017T152119Z-a4cc7407 |
| 通常3 | 191 | 431.719 | 20261017T152119Z-49edd170 |
| 通常4 | 146 | 423.088 | 20261017T152119Z-83531d76 |
| 通常5 | 203 | 449.033 | 20261017T152119Z-ac8e54d2 |
| 実CAD | 35 | 841.375 | 20261017T152119Z-a6c4f95f |

native画面、高DPI、ANSYS Import/Meshは未検証。既定形状の根元フィレット成立も、この修正の検証対象に含めない。

変更前のGitソースを独立moduleへ読み込んで照合し、旧検証11条件のlevel／field／messageと順序が一致。既定のImpeller／Diffuser／RC × CW／CCWの6条件で、主翼・Splitter全断面のcamber／LE／PS／TE／SS master XYZが完全一致した。追跡済みfixture／既定JSONの6ファイルと原本JSONの不変も確認。根拠は`artifacts/quality-stage2b/baseline-comparison.json`。比較用スクリプト初回はimport path、次に異なるmodule内Enum／dataclass型を直接比較するため失敗した。workspace pathとlevel.value／field／messageによる比較へ修正した後の結果であり、製品コードのエラー・全回帰の結果とは区別する。
