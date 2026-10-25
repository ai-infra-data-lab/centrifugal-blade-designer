# ANSYS環境へ渡す外部解析アダプター開発用インプット

作成日：2026-10-25。アプリ側の確認基準コミット：`d7fbd9a4581d8a0725827d9c716f1fd03fc49792`。
この文書は生成AIへ添付する引継ぎ仕様。**ANSYSアダプター・無人反復は未実装、ANSYS実機は未検証**。
現在のアプリは座標Study出力、外部結果CSV取込、単一/2目的RBF提案、Pareto比較まで実装済み。
別PCのcheckoutが基準より新しい場合は、以下のソース/API/形式を実コードと照合してから実装する。

## 1. 生成AIへ最初に入力する依頼文

以下をそのまま入力し、本ファイルとリポジトリ、実際のStudy一式を添付する。
Studyは`manifest.json`だけでなく、baseline・全case座標・結果テンプレートを含むフォルダ全体が必要。
GUIの未保存値やこの文書だけでは、個々の形状を再現できない。

```text
このリポジトリの centrifugal_blade_designer だけを対象に、ANSYSがインストールされた
この環境で、座標最適化Studyと外部解析を接続するアダプターを作成・デバッグしてください。
最初にAGENTS.md、FEATURES.md、本ファイル、docs/COORDINATE_OPTIMIZATION.mdと
本ファイルに列挙した実コード・テストを読み、現在の実装と照合してください。

目的はStudyの候補座標から外部でメッシュ/解析を実行し、実評価だけを既存CSV形式へ返すことです。
アプリ内にCAD/fillet/3D面最適化を追加せず、既存の設計アルゴリズム、既定値、ユーザーJSON、
座標、数値参照、既存出力形式を変更しないでください。親の家計簿等は対象外です。

まず製品・版・Python/API互換性・実行ファイル・ライセンス・解析テンプレートを調査し、
本ファイルの未設定項目を埋めてください。既存ファイルから確認できる項目は先に確認し、
物理条件・指標・合格条件を決められない場合だけ利用者へ確認してください。
未確認のANSYSコマンド、オブジェクト名、境界条件、効率式を推測して実装しないでください。

順番は、入力検査 → 基準1ケースの手動Import/Mesh/解析/後処理 → 同ケースの自動再現 →
候補バッチ → 複数翼列 → 失敗/取消/再開 → 予算付き自動反復、です。
ANSYSが起動できない、ライセンス不足、メッシュ失敗、未収束は成功扱いにしないでください。
代理モデル予測や模擬値を実評価CSVへ入れないでください。

生成したファイル、実行コマンド、ログ、入力/出力hash、メッシュ品質、収束・保存則の検査、
指標の定義、失敗理由と未検証項目を記録してください。最終CSVはアプリの
read_study()/import_results()を実行して受入確認してください。
最初はCSV連携で閉じ、未実装の自動反復やCLIを既存機能として呼ばないでください。
各段階の変更・実行証拠・再現手順を報告し、Git操作はその環境の利用者の許可に従ってください。
```

## 2. ANSYS側で確定する入力

| 項目 | この文書時点の値/記入内容 |
|---|---|
| リポジトリ/コミット | 実checkoutの場所と`git rev-parse HEAD` |
| 元Studyフォルダ | 未設定。原本は読取専用として扱う |
| 外部work root/結果CSV保存先 | 未設定。Study原本とは別の新規フォルダ |
| OS/ANSYS製品・版・修正パック | 未設定。TurboGrid＋CFXは候補、実際の製品で確定 |
| 実行ファイル/API/Python | 未設定。製品別対応版・起動/終了方法を実機で確認 |
| ライセンス/並列条件 | 未設定。利用可能なライセンス、CPU数、同時ジョブ数 |
| 正常に手動実行できる基準ケース | 未設定。session/CCL等、mesh/解析/後処理テンプレートとhash |
| 対象翼列/解析範囲 | row_id、全段/単独翼列、周期sector/全周、接続面と領域名 |
| 物理条件 | 流体/物性、回転数・符号、入口/出口条件、熱条件、乱流/壁処理 |
| ロータ静翼接続 | 対象製品の実設定、pitch変換、混合面等。名前だけで選ばない |
| 壁面/隙間 | 図面/解析Shroudの選択、物理Tip、隙間モデル、壁の回転条件 |
| mesh/収束の合格条件 | 品質尺度・閾値、残差、保存則、指標安定性、最大反復/時間 |
| 目的/制約 | 数値列名、単位、最大化/最小化、評価面/平均法/基準座標系 |
| evaluation_context | 上記比較条件とテンプレート/指標定義の版を識別する固定文字列 |

条件IDは単なる文字列照合であり、境界条件の物理的一致をアプリが自動証明するものではない。
mesh方針・物性・作動点・指標定義/単位を変えた評価を同じIDで混ぜない。
実行ファイル/テンプレートはローカル設定へ分離し、別PCの絶対パスや認証情報をソースへ固定しない。

## 3. アプリ → 外部解析：実装済み入力契約

```text
study/
  manifest.json
  baseline.json
  external_results_template.csv
  case_0000/                 # 中立基準、values={}
    shared_hub_rz.csv
    shared_shroud_rz.csv
    row_001/...
    row_002/...
  case_0001/...
```

ファイル名や存在を固定推測せず、manifestの`cases[].sha256`と`options`から列挙する。

| フィールド | 外部側が使う意味 |
|---|---|
| schema | `coordinate-study-1` |
| coordinate_geometry_version | 現在`rounded-nose-1`。実コードの定数と照合 |
| run_id | Study識別子。別Studyと混ぜない |
| baseline_hash | baseline.jsonの生バイトSHA-256 |
| row_ids / rows | 選択翼列のID、表示名、kind、rowディレクトリの対応 |
| cases[].candidate_id | `case_0000`等。同じcase番号でも別runは別候補 |
| cases[].values | 基準設計への差分パラメータ。座標そのものではない |
| cases[].candidate_hash | 候補の全設計snapshotのhash。CSV返却時にそのままコピー |
| cases[].status | `READY_FOR_EXTERNAL`だけ解析。`FAILED`は座標不成立であり解析しない |
| cases[].sha256 | Studyからの相対ファイル名→生バイトSHA-256。読込前後/転送後に照合 |
| cases[].rows | 翼列ごとのsections、Main/Splitter、span、輪郭点数、壁面chunk点数 |
| options | 座標列と順序、CSV/TXT、metadata有無、span分割、壁面分割、Shroud選択 |
| unit / rotation_axis / theta_positive | Studyはmm、Z軸、+Z側から見たθ正方向CCW |
| proposal / prediction | RBFの履歴・予測。**CFD実評価の入力値として流用禁止** |

`candidate_hash`はファイルhashではない。外部変換ファイルやmeshのhashで置換しない。
caseごとのproject JSONは現状出力されない。必要なら以下で候補を復元する。

```python
# 読取専用の確認例。既存API。study_directoryは実際の保存先に置き換える。
from pathlib import Path
from blade_designer.fileio.coordinate_study import read_study, project_hash

study_directory = Path(r"C:\analysis\input\study")
study, manifest = read_study(study_directory)  # 形状版/基準/座標hashも検査
print(manifest['run_id'], manifest.get('evaluation_context', ''))
for case in manifest['cases']:
    if case['status'] != 'READY_FOR_EXTERNAL':
        continue
    candidate = study.candidate(case['values'])
    assert project_hash(candidate) == case['candidate_hash']
    print(case['candidate_id'], case['candidate_hash'], len(case['sha256']))
```

`.venv`のPythonを使い、リポジトリルートで実行する。CLIの`coordinate_study`は
私有jobから座標を生成する既存入口であり、ANSYSを実行するCLIではない。

### 座標の読み方

- XYZはmm。円筒列は`r_mm`、`theta_deg`/`theta_rad`、`z_mm`。`rtheta_mm=r*theta_rad`。
  メートルへ変換するなら一度だけ行い、元/変換先単位と軸変換行列をログへ残す。
- 座標列は任意の順・部分集合も許される。必要な3D情報が不足するStudyは解析前に拒否し、
  新しいStudyとして再出力する。列位置や拡張子だけで判定しない。
- CSVはカンマ、TXTはタブ、UTF-8 BOMあり。ヘッダーで列を読む。
- 推奨入力はXYZ＋metadata、翼/Hub/Shroudを含める設定。通常のGUI出力設定そのものは変更しない。
- metadata先頭12列は`row_id,row_name,row_kind,engine,variant,snapshot_hash,significant_digits,blade_set,span,segment,index,m_blade_norm`。
  `blade_set`は`main/splitter/hub/shroud/analysis_shroud`。翼segmentは`LE,PS,TE,SS`。
- 曲線を識別してindex順に読む。全行を単一ポリラインにしない。接続点・閉鎖点・
  LE/TEマーカーは専用exporter/テストの定義を使い、座標を勝手に並べ替えない。
- metadata無効の一括ファイルはMain/Splitterや輪郭区分を確実に区別できない場合がある。
  不明な場合は推測せずmetadata付きで新規出力する。
- `shared_*_rz.csv`は共有元壁面。選択翼列の所属壁面/解析Shroudではない。
  流路meshには各rowの所属壁面出力を使い、chunkがある場合も隙間を直線で勝手に埋めない。
- 0〜1のspanと流れ方向座標を区別する。静翼のHub/Tipのみから中間断面を勝手に設計追加しない。
- `row_kind=diffuser`はDiffuserとRCの両方を含む。RCは外径流入/内径出口を座標/LE/TEから確認し、
  半径が増える向きへ自動ソートしない。表示名を境界名や物理種別の唯一の根拠にしない。
- 周方向の主翼枚数・Splitter有無・回転方向は復元候補の該当rowを確認する。
  Study座標は全周複製データではない。sector質量流量/トルクの全周換算を二重に掛けない。

## 4. TurboGrid接続で必要な追加作業

**Studyの汎用CSV/TXTは、そのままTurboGridのProfile Points入力ではない。**
Studyには現状、TurboGrid専用の`BladeGen.inf`やメッシュは自動出力されない。

推奨は、復元候補から既存の`fileio/turbogrid_export.py`を再利用し、外部workへ専用入力を作る経路。
ただし、これは今後アダプターで実装・検証する接続であり、既存Study用の完成APIではない。

- `prepare_turbogrid_export(params)`は検査済みファイル内容を返す。
  `export_turbogrid(directory, params)`は既存publisherを使って書く。外部側は毎回新規作業先を使う。
- GUIの`MainWindow._activate_blade_row`/`get_parameters`、`models/blade_rows.row_parameters`と
  exporterのactive row検査を読み、Qt非依存の候補→選択row投影を作る場合は別途テストする。
  **active_blade_rowだけを書き換えたり、row_parametersだけを直接渡して静翼判定を失わないこと。**
- `BladeGen.inf`とHub/Shroud/profileの4ファイル。曲線ファイル名は出力設定依存であり、
  `hub.curve`等へ固定しない。単位/回転軸はTurboGrid設定によってStudyのmm/Zから変換され得る。
- Main/Splitterは専用profile内で別翼。MainをBlade 0、SplitterをBlade 1とする既存出力を維持し、
  Blade SetsとBlades Per Setを区別する。周方向向き・実枚数・pitchを実機で確認する。
- 正のTip隙間では、物理TipとShroudまでの延長断面を両方出す場合がある。
  `BladeGen.inf`のコメントは設定命令ではない。実Tip Profile NumberをTurboGrid側へ明示設定し、
  Main/Splitterの双方で実際の隙間を検証する。汎用CSVへこの延長処理は自動適用されていない。
- 図面Shroud/解析Shroud、物理Tip、派生Shroud/外径カット後の形状を取り違えない。
  Export前後の座標比較では、追加のShroud延長と明示した単位/軸変換だけを区別して記録する。
  表示/座標/CADの補間方式を勝手に統一せず、既存方式の差と未検証範囲を残す。
- CAD/filletを経由する方法へ勝手に置き換えない。`Profile Points`と`CAD From Profile Points`は別経路。
- 複数翼列は各rowに入力を作るだけで全段解析にはならない。領域/接続/回転静止/周期pitchの
  設定が必要。同一候補の全rowを使い、旧候補のメッシュと混ぜない。

初回はアプリから手動で出力した専用入力でTurboGridのImport/Meshを成立させ、
その後にStudyからの自動出力を同じ入力・座標で比較する。

## 5. 外部解析 → アプリ：実装済み出力契約

`external_results_template.csv`のコピーを外部workで更新し、アプリで取り込む。
テンプレートの初期評価列は`efficiency`のみ。2目的なら必要な数値列を追加する。

```csv
run_id,candidate_id,candidate_hash,evaluation_context,status,efficiency,pressure_ratio
<manifestのrun_id>,case_0000,<そのcaseのcandidate_hash>,<manifestのevaluation_context>,success,<実解析値>,<実解析値>
<manifestのrun_id>,case_0001,<そのcaseのcandidate_hash>,<manifestのevaluation_context>,failed,,
<manifestのrun_id>,case_0002,<そのcaseのcandidate_hash>,<manifestのevaluation_context>,pending,,
```

上は書式説明であり、`<...>`を残したCSVは取込用ではない。実ID/hash/数値を使う。

- 必須列は`run_id,candidate_id,candidate_hash,status`。
  `evaluation_context`を設定したStudyではその列も必須、値は完全一致。RBF提案には空でない条件IDが必要。
- statusは小文字の`pending/success/failed`。case IDは元manifestにある出力成功候補だけ。
  `READY_FOR_EXTERNAL/FAILED`という座標生成statusを、この解析status列へコピーしない。
- `success`の評価値は有限数値。NaN/Infinity、数値の単位文字・百分率記号、桁区切り文字は入れない。
  多目的RBFへ進むには両目的と必要な制約の成功値がそろう必要がある。
- `failed/pending`は**全評価列を空欄**。0、罰則点、代理モデル予測を入れない。
- エラー文・ログパス・attempt_id等の文字列列を追加しない。固定列以外は数値評価列として読まれる。
  失敗理由/収束履歴/単位/出所は別JSON・ログへ保存する。
- 未完了候補はpendingを維持する。未知ID、重複行/列、別run、異なるhash、条件ID違いは拒否される。
- CSV全体を私有一時ファイルへ作成・検査してから、新しい完成ファイルとして公開する。
  読込中の書換えを避け、Study原本・旧評価CSV・過去解析フォルダを上書きしない。

受入れはGUIだけに依存せず、次の既存APIでも確認する。

```python
from blade_designer.fileio.coordinate_study import read_study, import_results, pareto_results

_, manifest = read_study(study_directory)
results = import_results(r"C:\analysis\output\external_results.csv", manifest)
order, fronts = pareto_results(results, [
    {'name': 'efficiency', 'maximize': True},
    {'name': 'pressure_ratio', 'maximize': True},
])
print(order, fronts)  # 外部結果が形式上正しいことと、解析が物理的に妥当なことは別
```

### 指標の定義を確定する

圧力比なら絶対圧の入口/出口全圧、評価面、平均法、静止/相対座標系、単位を指定する。
効率は全圧/静圧、断熱/ポリトロープ、流体モデル等で定義が変わるため、
検証したCFX/CFD-Post等の式・領域・平均法をテンプレートとともに保存する。
既定のgamma・cpや理想気体式を無条件に当てはめない。
出力する効率が比か%か、質量流量がsectorか全周かも明記し、全候補で統一する。
終了コード0や結果fileの存在だけを収束とせず、残差/質量・エネルギー保存/指標安定性の合格根拠を残す。

## 6. これから作るアダプターの提案インターフェース（未実装）

役割は`validate_input → prepare_mesh_input → mesh → solve → extract_metrics → publish_results`。
まず1候補ずつ評価する関数/CLIを外部側で作り、座標StudyやQtへANSYS依存を混ぜない。
例として`evaluate(study_dir, candidate_id, config, work_root)`を想定できるが、現在のAPIではない。

作業先は`work_root/run_id/candidate_id/attempt_id/`。IDを安全な単一ディレクトリ名として検査し、
work root外へ書かない。再試行は別attemptへ保存し、全候補に同じ一時名を使わない。

外部専用の`evaluation.json`には次を保存する（既存Study schemaへ追加する仕様ではない）。

| 区分 | 必要な情報 |
|---|---|
| 出所 | run/candidate/hash/geometry版、対象row、入力座標/変換後fileのhash |
| 設定 | evaluation_context、設定/テンプレートhash、製品/API/Python版、並列条件 |
| 実行 | stage別開始終了時刻/exit code、stdout/stderr、所有PID/ジョブID、timeout/取消 |
| 品質 | mesh尺度と合否、収束/保存則/指標安定性の実測値と基準 |
| 評価 | 指標値/単位/定義/評価面、失敗段階と機械可読error code |
| 成果物 | mesh、solver入力/結果、後処理report、結果CSVの場所とhash |

内部エラーはINPUT_INVALID、LICENSE_UNAVAILABLE、MESH_FAILED、SOLVER_FAILED、
NOT_CONVERGED、METRIC_MISSING、TIMEOUT、CANCELLED等へ分類できる。
これらは提案する外部ログ分類。既存CSVのstatusへ新しい文字列を流し込まない。
実行前/待機中はpending、確定失敗はfailedとし、取消・再試行の採否規則も実装前に決める。
取消で他人のANSYSプロセスを終了せず、所有PID/サーバージョブだけを止める。

## 7. 実機デバッグの順序と完成条件

| 段階 | 実行内容 | 完成の証拠 |
|---|---|---|
| A | ローカル製品/API/ライセンス確認、Studyと座標の検査 | 環境記録、hash一致、未設定項目の解消 |
| B | 基準1ケースの手動Import/Mesh/解析/後処理 | 実画面/設定、mesh品質、収束/保存則、指標の独立照合 |
| C | Bの自動再現 | 同じ入力/テンプレート、再現性の許容差と根拠、正しい結果CSV受入 |
| D | 少数の候補を逐次解析 | run/case取り違えなし、候補間の形状変化と評価変化、原本保護 |
| E | 全段・RC・Splitter・隙間・派生カット | 各構成の対応表、境界/回転/隙間/marker/枚数とmeshの実確認 |
| F | 失敗/timeout/取消/再開/転送改変 | 正常ケースを壊さず失敗分類、重複実行防止、旧結果保持 |
| G | 予算付き自動反復 | 実評価だけで再学習、世代/評価数/時間/同時数/停滞/失敗率で停止、永続再開 |

全段CFDの成立は、各翼列でmeshが作れたという証拠とは別。
Split/clearanceやRCを試さず「全構成PASS」にしない。実施していない段階はNOT_TESTEDとする。
模擬テストの値は隔離し、実解析値として学習・報告しない。

Gは候補生成→座標→外部mesh/解析→実結果→再学習→次候補までが対象になり得る。
現状はその無人ループ、監視、停止条件、永続再開を実装していない。
自動反復でも最終Pareto候補の通常設計への適用は明示操作とし、既存出力を消して巻き戻さない。

## 8. 必ず読むソースとテスト

| ソース | 確認対象 |
|---|---|
| `blade_designer/fileio/coordinate_study.py` | queue/export/read/import/rank/pareto、ID/hash/CSV/原本保護 |
| `blade_designer/fileio/coordinate_csv.py`、`row_xyz_csv.py` | 座標/metadata/列順/区切り/Span/壁面 |
| `blade_designer/optimization/coordinate_parameters.py` | baselineからの候補復元、変数/連動/対象翼列 |
| `blade_designer/fileio/coordinate_proposal.py` | 凍結CSV、同条件の履歴、実評価のみの再学習 |
| `blade_designer/optimization/surrogate_proposals.py`、`pareto.py` | 学習条件、2目的、予測/実評価の境界 |
| `blade_designer/gui/coordinate_study_dialog.py` | 現在の操作・完了/取消・候補適用 |
| `blade_designer/fileio/turbogrid_export.py` | 専用書式、軸/単位、profile閉鎖、LE/TE、Splitter、Tip延長 |
| `blade_designer/models/blade_rows.py`、`gui/main_window.py` | row snapshot/共有壁面/active rowの扱い |
| `blade_designer/geometry/geometry_3d.py`、`row_domain.py` | 実断面、所属壁面、RCの流れ方向 |

関連資料：[座標Study](COORDINATE_OPTIMIZATION.md)、[汎用座標](COORDINATE_CSV.md)、
[Splitter専用出力](TURBOGRID_SPLITTER.md)、[隙間専用出力](TURBOGRID_CLEARANCE.md)、
[解析Shroud](ANALYSIS_SHROUD.md)、[開発手順](DEVELOPMENT.md)。

最低限の関連テストは`test_coordinate_study_io.py`、`test_coordinate_proposal_io.py`、
`test_multiobjective.py`、`test_multiobjective_io.py`、`test_turbogrid_export.py`、
`test_stator_turbogrid_export.py`、`test_splitter_turbogrid.py`、`test_turbogrid_clearance.py`、
`test_turbogrid_profile_validation.py`。実際のパスは`tests/`で確認する。
選択`.venv`の`python tools/run_tests.py --brief <関連パス>`を使い、
GUI/形状/保存変更時はAGENTS.mdに従い全回帰も行う。ANSYS実行試験は別の証拠として記録する。

## 9. 製品側の一次資料と適用条件

参照日：2026-10-25。インストール製品の版のマニュアルを優先し、現地でAPI/コマンドを再確認する。

- [PyTurboGrid公式・基本mesh例](https://turbogrid.docs.pyansys.com/version/stable/examples/basic_read_inf_rotor37.html)：
  INF読込からmesh生成/保存までの公式例。これは本アプリの形状/全構成のmesh成功の証拠ではない。
- [PyTurboGrid API](https://turbogrid.docs.pyansys.com/version/stable/api_reference/pyturbogrid_core.html)：
  ローカル起動/接続等のAPI。対応製品・Pythonを現地で確認して採用する。
- [PyCFX公式](https://cfx.docs.pyansys.com/)：セットアップ・実行・結果抽出のPython連携。
  参照時の対応はCFX 2025 R2 SP3以降。古い製品へ無条件に導入しない。
- [TurboGrid 2026 R1 User's Guide](https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/pdf/Ansys_TurboGrid_Users_Guide.pdf)：
  Profile Points等の製品仕様。実機では導入版に対応する入力モード/隙間設定を確認する。

## 10. この引継ぎ文書の検証状態

本資料の作成ではANSYSを実行せず、製品のインストール/ライセンス/既存設計値/コードを変更しない。
基準コミットのアプリ全回帰2,647件成功は以前のローカル検証であり、ANSYS接続の合格証拠ではない。
この文書の作成時に、入出力を実ソースと照合し、短時間数値63件成功を再確認した。
CSV例のID/hash/数値はプレースホルダー。現在の実形状/物理条件/実測値は必ずStudyと現地設定で渡す。

作成時の確認記録：短時間63件`20261025T085748Z-2138c777`、Study IO19件
`20261025T090254Z-59451380`が成功。文中Python例2本を既存の模擬Studyへ適用し、
10候補の読込/未評価CSV受入、入力53ファイルのhash不変、ローカル文書リンク6件を確認した。
記録は`artifacts/quality-ansys-handoff/`。これは入出力説明のローカル確認であり、
ANSYSのImport/Mesh/Solveや物理指標の妥当性を検証したものではない。
