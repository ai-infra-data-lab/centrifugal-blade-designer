# v0.4 CAD実装・検証報告（2026-10-16）

対象はcentrifugal_blade_designerだけです。要求原文は[CAD_V04_SPEC.md](CAD_V04_SPEC.md)、操作・環境・ANSYS手順は[CAD_EXPORT.md](CAD_EXPORT.md)です。Python側のCAD機能を追加しました。全593件を分割実行してID照合し、失敗・error・skip・実行漏れは0件でした。変更は既存10ファイル・新規38ファイルです。実機寸法未設定のモデルとANSYS未検証項目を完成扱いしません。stage・commit・push・リモート変更は行っていません。

## 1. 既存変更ファイル

| ファイル | 目的 |
|---|---|
| `.gitignore` | 独立CAD環境、ユーザーSTEP/BREP/Parasolid、生成レポート・ケースを除外 |
| `blade_designer/models/parameters.py` | 独立CAD設定を保持 |
| `blade_designer/fileio/project_io.py` | 旧JSON既定補完、任意CAD設定の0.4保存・精度・検証 |
| `blade_designer/gui/main_window.py` | CADタブ、保留入力、Undo、非同期snapshot、出力・表示接続 |
| `blade_designer/gui/preview_3d.py` | 実BREPメッシュ・意味別表示・古いメッシュ抑止・既存カメラ保持 |
| `tests/test_gui.py` / `tests/test_target_layout_gui.py` | Impellerに追加したCADタブの期待値 |
| `README.md` / `FEATURES.md` / `docs/ARCHITECTURE.md` | 使い方・構成・検証状態 |

既存geometryエンジン、既定JSON、ユーザー原本、CSV/TurboGrid exporter、歴史的数値fixtureは変更しません。

## 2. 新規ファイル

- `blade_designer/models/cad.py`: Qt/カーネル非依存の設定・検証。
- `blade_designer/cad/__init__.py`, `backend.py`, `errors.py`: 独立層とバックエンド契約・例外。
- `blade_designer/cad/client.py`: master座標・厳密壁面・不変snapshot・検証済み成果物の公開。
- `blade_designer/cad/occt_backend.py`: 曲面/solid/Hub/Boolean/Fillet/干渉/STEP/tessellation。
- `blade_designer/cad/worker.py`: 独立プロセスの実行・検証・部分成功と失敗レポート。
- `blade_designer/cad/cad_validation.py`: STEP再読込と根元半径サンプル測定。
- `blade_designer/fileio/mechanical_step_export.py`, `turbogrid_cad_export.py`, `cad_validation_report.py`: 検証済みbytesの保存、ANSYS手順、JSON/txt報告。
- `blade_designer/gui/cad_editor.py`, `cad_export_worker.py`: 設定UIとQProcess。
- `requirements-cad.txt`, `requirements-cad-windows-py312.lock.txt`: 独立依存と確認環境の全依存記録。
- `tests/cad/__init__.py`, `conftest.py`: 実カーネルfixture。
- `tests/cad/test_cad_backend.py`, `test_blade_surface.py`, `test_blade_solid.py`, `test_hub_solid.py`, `test_boolean_union.py`, `test_root_fillet.py`, `test_fillet_failure.py`, `test_edge_classification.py`, `test_cad_validity.py`, `test_step_export.py`, `test_step_roundtrip.py`, `test_step_error_budget.py`, `test_mechanical_export.py`, `test_turbogrid_export.py`, `test_cad_parameter_serialization.py`, `test_cad_regeneration.py`, `test_straight_blade.py`: CAD・入出力・再生成・安全性。
- `tests/test_cad_gui.py`: 設定精度・Undo・旧/新JSON・snapshot・カメラ・古いメッシュ抑止。
- `docs/CAD_V04_SPEC.md`, `CAD_EXPORT.md`, `CAD_IMPLEMENTATION_REPORT.md`: 要求原文・手順・本報告。

## 3. バックエンド

Windows Python 3.12.14、`cadquery-ocp 8.0.1.1.0`、NumPy 2.5.4、SciPy 1.18.1。実APIはOpen CASCADEで、CadQuery高水準APIは使用しません。独立`.venv-cad`の`pip check`は成功。既存`.venv`の依存を置き換えません。通常編集でOCPがimportされないことも試験しました。

## 4. CAD Surface方式

各SpanのPS/SS/LE/TEのmaster座標を使用します。正規化子午面パラメータと実Spanのtensor-product B-splineを作り、元master全点との対応点偏差を測定し、33〜513点の適応密度で指定公差以下へ収束させます。滑らかな端部の接線を共有し、Cutoff角は維持します。出力点数変更でもCAD入力NPZは一致する試験があります。Span間全域の誤差の厳密上界は未証明です。

## 5. Solid方式

4曲面とHub/Tip端面をsewingし、1閉shellからsolidを作ります。端面が平面なら厳密な平面を使い、非平面のときだけ高精度の充填面を使います。平面を高次数曲面へ近似してBoolean/Filletを長時間化させないためです。BREP analyzerだけでなく自己交差検査、閉shell、正体積、solid数を検査します。検証サンプルでは1個の有効solidです。

## 6. Hub Disk方式

所属Hub壁面の厳密Line/Arcと明示入力した裏面・内径を閉じてZ軸回転します。裏面・内径は既定Noneです。ユーザー実機寸法を推定しません。独立試験ディスクはR250/内径R20/厚さ40の解析体積`π(250²−20²)40`と照合します。この寸法は試験用で実機既定値ではありません。

## 7. Boolean Union

翼＋HubをFuseし、接続した1solidであることを要求します。全周は実solidをピッチ複製し、batch Fuse、周期セクタは実Boolean切断です。既存表示用の複製だけでSTEP全周を偽装しません。結合不能時は拒否します。Hub内部への翼延長は現実装では0 mmです。

## 8. Hub Fillet R8

Hub流路面の生成履歴と翼PS/SS/LE/TE面の隣接関係でRoot Edgeを識別し、曖昧な場合は停止します。OCCTのMakeFilletへ8.0 mmを渡し、生成面をHUB_FILLETおよびPS/SS/LE/TE別に追跡します。Shroudフィレットは無効です。失敗時に小半径へ自動変更しません。

## 9. 成功・失敗検証

独立した広い流路の曲がった翼（厚さ20〜24 mm、Span 0/0.5/1、β15→25°、2枚）でR8と周期/全周の実体を確認しています。生成フィレット面数・根元識別・自己交差・干渉を検査し、STEP前後の根元局所主曲率半径を8 mmと照合します。面全域の厳密半径は`NOT_TESTED`です。

Fixture Aは実座標エンジンのβ=0の直線翼、厚さ6 mm、根元R1で、結合・フィレット・STEP後の半径測定を検証します。独立した箱のR1/R8は正体積・体積減少・STEP round tripを検証し、同じ箱同士の重なりを拒否する試験もあります。Span高さ2 mmの不成立R8はFAILで、半径を変更せず、既存STEPのsentinel bytesを保持します。

開発中には曲面補間の振動、履歴参照のずれ、BREP妥当でも自己交差するフィレットを検出しました。制御点補間と正規wireからの履歴取得へ修正し、自己交差を合格扱いしない検査を追加しました。数値参照の置換や公差緩和で試験を合わせていません。

## 10. STEP Export

Blade Only/単翼＋Hub/全周/周期のScopeがあります。正規出力前にSTEP再読込を検証し、SHA256で検証済みbytesを照合します。失敗形状はjob内のデバッグ名に限定します。機械用の部分成功とTurboGrid変換必要を別statusにします。

## 11. STEP再読込

MMのSI_UNIT、solid数、BREP/閉鎖/自己交差、体積、bbox、edge toleranceを確認します。比較許容値と実測値は各artifactのroundtripにあります。体積はB-splineノット区間を考慮したGauss-Kronrod積分（要求相対誤差1e-9、実際の誤差推定も記録）で測定し、非収束を拒否します。bboxの比較閾値は元・再読込BREPの実edge toleranceの和を基準に、指定CAD公差を上限とします。精密な形状には従来の比較精度`max(1e-7, CAD公差×0.01)`を適用し、体積の比較閾値はこの精度から計算する従来式を維持します。誤差予算を超えるbbox差、CAD公差超過edge、過大な体積差を拒否する試験を追加しました。R8はtrimされた元フィレット面の内部点で再読込面を幾何照合して測定します。単純な面番号の一致には依存しません。

最終Fixture B/Dでは根元フィレット4面、翼間干渉PASS、Mechanical周期セクタ1solid、体積差0.00009730 mm³、bbox差約4.79e-12 mmで再読込PASSです。流路CADも1solid、体積差0.00046014 mm³、同程度のbbox差でPASSです。流路STEPの妥当性がPASSでも、成果物statusはCONVERSION_REQUIREDのままで、全体はWARNINGです。

## 12. TurboGrid CAD

Hub/Shroudで閉じた流路から全周翼材料を差し引く流体領域を1ピッチ化します。必要な境界役割を検査し、役割と面積・重心・bboxをsidecarへ保存します。Mechanicalのディスク外形を流路として流用しません。流路STEPは再読込合格の中間成果物です。Parasolid変換器は`UNAVAILABLE`、出力statusは`CONVERSION_REQUIRED`で、対象リリースでの直接Importは未確認です。

## 13. Profile Points

従来exporterをそのまま使い、フィレットなしの現行設計snapshotから出力します。同じsnapshotの従来関数とbytesが一致する試験があります。既存Impellerの歴史的12ファイルハッシュ回帰も維持します。スプリッター付きProfile Pointsは従来どおり拒否し、主翼だけの不完全出力を防ぎます。

## 14. pytest

選択環境`.venv\Scripts\python.exe tools/run_tests.py`を使用します。

| 検証 | 結果 | artifacts/test-runs/ |
|---|---|---|
| 編集前全回帰 | 558 passed | `20261015T213215Z-d202d33e` |
| Project/翼列/Rake/Splitter | 56 passed | `20261015T215405Z-1a2c08dc` |
| 既存GUI/Preview/Project/Splitter | 33 passed | `20261015T220913Z-e0b44229` |
| CAD設定/Undo/snapshot | 11 passed | `20261015T221849Z-0587fe22` |
| 実CAD・STEP・R8失敗保護 | 22 passed | `20261015T222210Z-93ff4bbe` |
| CAD再生成/単純R1・R8/GUI | 6 passed | `20261015T223546Z-ea15cd29` |
| 最終CAD設定/周期Scope/JSON | 12 passed | `20261015T225239Z-93125798` |
| 最終CAD表示復帰/既存3D | 7 passed | `20261015T225453Z-63df0360` |
| 直線翼・小半径R1のFixture A | 1 passed | `20261015T230639Z-e5e34b44` |
| STEP誤差予算・直線翼R1再確認 | 5 passed | `20261015T231415Z-8435ef7a` |
| 最終実CAD/GUI（比較誤差予算修正を含む） | 31 passed / 533.72秒 | `20261015T231329Z-3ca0ca45` |
| 変更後の既存機能全回帰 | 558 passed / 972.19秒 | `20261015T230934Z-42da3606` |

最終回帰は上の558件、31件、STEP比較/R1の5件に分けて実行しました。R1の1件が重複するため一意の件数は593です。`--collect-only`の593個別IDと3つのJUnitを機械照合し、missing/unexpected/failure/error/skipがすべて0でした。照合記録は`artifacts/cad-review/final-test-coverage.json`です。単一実行で593 passedと主張するものではありません。既存558件の途中でCAD専用のSTEP比較を修正し、この比較を使うCAD31件と独立比較4件・R1を修正後に実行しています。既存geometry・既定JSON・歴史的数値参照は変更していません。

実CADfixtureはoptional backendが存在しなければskipになります。今回はバックエンドを導入したこのPCでskipせず成功しました。先行全回帰（`20261015T223703Z-1e49c429`、`20261015T224246Z-476d9330`、`20261015T224639Z-e00dc147`、`20261015T224807Z-6e4ac496`、`20261015T225606Z-545f8330`）は修正を加えたため、この作業のテストプロセスだけを特定して中断しました。中断を試験失敗や成功として集計しません。関連試験のファイル名を1回誤指定（`20261015T225443Z-b02908f4`、no tests ran）し、正しい指定で上記7件成功を確認しました。実装のテスト失敗や環境エラーとは区別します。集計時にシェル出力末尾の文字コード差も検出し、UTF-8の個別ID行とJUnit XMLだけを照合しました。

## 15. GUI

Qt offscreenで、CAD設定、精度、Undo/Redo、独立翼列、保存/再読込、不正裏面入力時の既存JSON保護、途中編集による旧CAD非表示と現在の翼ワイヤーフレームへの復帰、UndoでのCAD復帰、カメラ保持を検証しました。周期ScopeはFullを選ぶまで周期モデルを表示します。β・厚さ・LE形状・Rake変更後の実CAD再生成も成功しています。

main.pyの`create_window`で保存済み既定JSONを読み、Impellerを選択したGUIからQProcessでBlade Only STEP出力し、再読込、CADメッシュ表示、カメラ保持まで確認しています（`artifacts/cad-review/gui-application-default.json`、対応job `199837d8a1554c4a8ee543a7e58ead85`）。元体積7348.8774 mm³、再読込7348.8806 mm³、差0.003159 mm³、bbox差0.000009915 mm（比較閾値0.001924643 mm）、再読込edge tolerance 0.000938855 mmでPASSです。

別途、MainWindow単体の設計クラス標準値でもGUIから出力を確認しています（`artifacts/cad-review/gui-final.json`、job `5981d5079eae49cda4106d0974279995`）。こちらは元体積6727.1943 mm³、再読込6727.1828 mm³、差0.011445 mm³でPASSです。先行確認時にこれを保存済み既定JSONと混同していたため、上記の実起動経路の確認を追加しました。両方ともBlade OnlyはNO_FILLETで、翼間干渉はNOT_TESTEDです。

先行の追加GUI出力確認はスクリプトの300秒待機上限に達し、未生成メッシュ属性へのアクセスで確認処理が例外終了しました。検証スクリプトを修正し、Blade Onlyにアセンブリ干渉検査を要求しない区別を実装した後、上記の最終確認に成功しました。未完了の先行確認をPASSに含めません。実ディスプレイの手動操作、ネイティブF5、DPI、Cancel操作の実画面確認は`NOT_TESTED`です。初期画像には環境のフォント欠落があり、最終画像取得プロセスだけMeiryoを読み込みました。製品フォント設定は変更していません。

## 16. Mechanical実機

Import、solid認識、単位、フィレット測定、Meshingはすべて`NOT_TESTED`です。対象ANSYS環境・ライセンスが提供されていません。手順はREADMEからリンクしたCAD_EXPORT.mdとケース内import_instructions.mdにあります。

## 17. TurboGrid実機

対象リリース未指定。Profile Points Import、CAD変換/Import、Complex Blade End、フィレット認識、Mesh、品質はすべて`NOT_TESTED`です。Blade Blend/CAD From Profile Pointsは対象リリースのライセンスとスタンドアロン条件を確認してください。

## 18. 制約・未完了

- 実モデルのディスク裏面・内径は未指定。R8を適用したユーザー実モデルの完成品は未作成です。
- 現在の既定Projectには所属壁面の終端が翼TEを含まない条件があり、Hub付きCAD/TurboGrid CADはそのままでは拒否します。Blade Only検査をこの所属制約だけで止めません。所属や設計値の原本は自動修正しません。
- 既定ProjectのBlade Only初期試作は最大edge toleranceが約0.0232 mmで指定0.01 mmを超過しました。公差を緩めず、端面充填の制御点数・反復・最大分割を増やすと約0.00236 mmへ改善しました。改善設定を実装し、残る公差超過はSurfaceConstructionErrorとして拒否します。
- 設計クラス標準形状の初回STEP比較では従来Gauss積分で体積差9.323 mm³（許容0.9985 mm³）を検出し拒否しました。独立したノット区間別Gauss-Kronrod積分では元6727.1943 mm³、再読込6727.1828 mm³（差約0.01145 mm³）へ収束し、体積測定の方式を修正しました。設計公差0.01 mmと体積の比較式は維持します。
- 保存済み既定JSONの直接読込ケースでは、1回の関連実行で13 passed / 1 failedとなりました（`20261015T230510Z-b481523b`）。元BREPのedge toleranceが0.003442 mmに対しbbox比較を一律0.0001 mmへ設定していたため、STEP読込後の0.000515 mm差を拒否していました。元・再読込BREPの実誤差予算を使い、設計公差で上限を制限する比較へ修正しています。数値参照やCAD指定公差を置換せず、過大なbbox/edge/volumeを拒否する独立試験を追加しました。修正後は既定JSONの直接読込ケースを含むCAD/GUI31件と比較/R1の5件が成功しました。
- Blade Onlyでスプリッターを有効にした場合、ファイルは主翼/スプリッター別に検証・保存しますが、CADプレビューは主翼単体です。既存のワイヤーフレーム表示はスプリッターを含んで維持します。Hub付きCADは両方のsolidを処理します。スプリッター付きCADの実設計ごとの成立確認は必要です。
- Surface Edgesは計算したScopeのedgeを表示します。表示用Full切替時にすべての複製edgeへ追従する表示は未対応です。
- ディスク裏面UIはLine/Arc JSON入力です。既存子午面エディタへ新しい裏面編集表を増設していません。
- 現方式で閉じない・自己交差する・根元を一意に識別できない・R8が成立しない設計は拒否します。全設計での成功は保証しません。
- Filletの局所測定は面全域の厳密半径保証ではありません。エンジニアリング妥当性、応力、CFDは未検証です。
- Parasolidの自動変換とANSYS実機検証は未完了です。Named Selectionを自動で保証しません。
- 周期セクタはZ軸を通る放射状平面で切断します。翼の巻き角によっては切断面が翼を横切り、TurboGrid向け周期面の追加準備が必要です。流路BREPの妥当性を、実機メッシュ適合性やそのままImport可能という意味に拡張しません。
- 同一snapshotの部分成功だけを保存し、ケース全体のI/Oトランザクションはありません。途中パラメータ変更後の出力はsnapshotの版です。
- 別PC、CAD環境のPython 3.11、他OS、native UIの全操作は未検証です。

Python側の検証済み機能と上記未完了を分け、ANSYS連携全体の完成・実機R8設計の完成とは報告しません。
