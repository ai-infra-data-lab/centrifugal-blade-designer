# RCの表示と既定モデル（2026-10-17）

## 既定モデル

指定された`blade_v03.json`を、配布用`blade_designer/defaults/default_project.json`へ内容を変えずにコピーしました。元ファイルは変更しません。両者のSHA256は`aa724c8253463289caec919960d7d486d698765cee35202c13e4efd17a603dd6`です。

Impeller・Diffuser・RCの3翼列を保持し、保存時に選択されていたRC（row-3）で起動します。Newでも同じ既定値へ戻ります。`--project`の指定と別プロジェクトの読込は従来どおり優先します。元ファイルの将来の編集へ自動追従する仕組みではなく、この時点のスナップショットです。数値モデルのBladeParametersや、引数なしMainWindowの互換用既定値は変更しません。

## 原因

中央2Dの静翼表示は、旧2D専用計算の`geometry.r_le=100`・`r_te=160`を参照していました。下段3DとTurboGridは、共有の子午面上のLE/TEと所属壁面から、別の生成処理で作られていました。

指定モデルのDiffuserは実LE R=85→TE R=130 mm、RCは実LE R=130→TE R=90 mmです。旧2Dの100→160 mmはどちらにも対応せず、RCでは流れの半径方向も逆になります。RCの3D生成はすでに内向き流れを扱えていたため、入力のLE/TE・角度・厚さや生成式を入れ替える修正は必要ありません。

## 変更

有効な静翼3Dが生成されたときは、そのHub断面のmaster LE/PS/TE/SS・camberを中央2DへXY投影します。単翼／Full Annulusとも同じ断面を使い、全周は同じ枚数・Z軸回転です。タイトルへ翼列名・Hub・XYを表示し、旧2Dモデルのスロート線を重ねません。3Dには従来どおりHub/Tipの両断面とSpanwise接続があります。両断面が異なるモデルでは、2DはHubの投影である点を区別してください。

RCという名前による特別な計算分岐は追加しません。静翼の共通kindは`diffuser`のまま、子午面のLEからTEへ進む距離とR/Zで形状・流れ方向を決めます。内向きでも子午面距離mは下流へ増え、一定βの純径流では`θ−θ_LE = rotation_sign × tan(β) × log(R_LE/R)`となります。Rを小さい順に並べ替えたり、LE/TEやβの符号を自動反転したりしません。

起動・New、編集・Undo/Redo、翼列切替、JSON読込で表示を更新します。3Dが無効な場合の従来動作（最後の有効3Dとエラー、更新された旧2D診断）を保持し、単翼のタイトルを`legacy 2D / 3D unavailable`と明示します。全周のフォールバックでも3Dエラーはメッセージ欄に表示します。有効な3Dとの一致を保証するのは正常生成時です。

## 折り返し流路の断面対応

新しい既定モデルで回帰試験を実行すると、戻り部の平均線法線を無限に延長した面が上流Impellerにも交わり、m_flow_norm≈0.67／0.68の戻り部をImpellerの断面と誤認していました。実Hub点との不一致を「壁面からのずれ」と誤検出する原因です。

geometry/passage.pyでは、生成断面のHub物理距離を使い、Hub足点がその翼列の実LE〜TE区間内にある断面だけを測定します。遠方の別枝に属する法線を除外し、面積式・スロート式は変更しません。距離メタデータを持たない既存の解析テスト用形状は従来経路を保持します。折り返し流路の隙間なし／ありで誤検出がないことと、実際にずれた生成断面を引き続き拒否することを試験します。

## 互換性と確認範囲

翼の数値生成・JSON schema・旧2D API・最適化・CSV形式は変更しません。ViewのMetrics／Diffuser Curvature、旧2D診断メッセージ、ステータスのThroat、CSVは旧半径設定の2D計算です。中央の子午面ベース形状と混同しないでください。RCの実形状を使う解析はPassage Area / Throat、座標出力は既存TurboGrid静翼経路です。TurboGridの実機Import／Meshは未確認です。

指定モデルのImpellerは専用Splitterが有効です。このデータを保持するため、従来から未対応のSplitter付きImpeller TurboGrid出力は引き続き拒否します。クリアランス出力だけを調べる既存テストでは、使い捨てコピーのSplitterを明示的に無効化して条件を分離しました。製品の既定設定は無効化せず、元のSplitter付きモデルが拒否され既存出力を保護する試験も追加しています。

変更ファイル：

| ファイル | 内容 |
|---|---|
| blade_designer/defaults/default_project.json | 指定モデルの既定値コピー |
| blade_designer/gui/main_window.py | 正常生成した静翼Hub断面を中央の単翼／全周表示へ接続 |
| blade_designer/gui/plot_widgets.py | 全周投影のタイトルに翼列名を渡す |
| blade_designer/geometry/passage.py | 折り返し部の法線が別枝の翼列へ誤対応しないよう、実Hub距離で測定区間を限定 |
| tests/test_return_channel.py（新規） | 内向き流れの解析巻き角、CW/CCW・±β・全TE形状の12件と、既定Splitterの出力保護1件 |
| tests/test_return_channel_gui.py（新規） | 実モデルの起動／New、2Dと3Dの全master座標一致、編集・履歴・保存・選択の3件 |
| tests/test_application_defaults_gui.py | 3翼列の既定値に対応 |
| tests/test_folded_passage.py（新規） | 折り返し断面の隙間なし／ありと、本物の変位の拒否を3件で確認 |
| tests/test_turbogrid_clearance.py | 出力未対応のSplitterを試験用コピーだけ無効化し、クリアランス延長の試験条件を明示 |
| tests/test_target_editor_gui.py、test_shared_edges_annulus_gui.py | 静翼表示の正本を旧2Dから3D投影へ変更した期待値 |
| README.md、FEATURES.md、docs/ARCHITECTURE.md、この文書 | 既定値・原因・表示の基準・制限 |

歴史的な数値fixtureは置き換えていません。Qt offscreen画像は`artifacts/return-channel-review/rc-corrected.png`。画像取得プロセスだけMeiryoを使用し、製品のフォント設定は変更しません。実画面操作・F5・CFD・性能は未確認です。今回stage・commit・pushは行いません。

## 検証記録

- 初回関連35件は32成功／3失敗（192.13秒、20261017T063045Z-6382e1f0）。3件は新規テスト側で、消去したPlotDataの`None`を空配列として`len`判定していたためです。`None`と空配列の両方を許容するテスト補助関数へ修正し、数値参照・製品コードはその失敗のために変更していません。
- 修正後の新規GUI3件は成功（44.96秒、20261017T063211Z-56294681）。すべてのmaster点を単翼・全周・3Dで照合し、編集・Undo/Redo・JSON・翼列切替・旧半径設定の影響分離も確認しました。純数値の内向き流れ12件も成功しています。
- 既定JSONと原本のバイト一致は`artifacts/return-channel-review/default-copy.json`、正常時の画面は`visual-review.json`／`rc-corrected.png`に記録。画面取得スクリプトの端末出力だけCP932文字化けエラーになりましたが、UTF-8の記録とPNGは保存済みで、製品エラーではありません。
- RCのTurboGrid試行は`artifacts/return-channel-review/turbogrid-RC-review.json`へ記録。設定された有効数字6桁でHub/Tip輪郭を丸めると、3D断面と全座標が一致します。初回試行で高精度の未丸め座標との比較が失敗したため、設定精度を明示した比較に訂正しました。元設定・出力精度は変更しません。実機Importは未確認です。
- 全試験の収集ID照合と最終入力の比較を`artifacts/return-channel-review/final-test-coverage.json`へ記録しました。全768収集IDを実行し、失敗・error・skip・実行漏れ・予期しないIDは0件です。
- 最初の全回帰で、新既定モデルの折り返しに由来する遠方交点の誤検出と、既定で有効になったSplitterの出力制限を確認しました。数値fixture・許容差は変更せず、上記の断面対応とテスト用コピーの条件分離で対応しました。補正後の関連69件は成功（93.26秒、20261017T064733Z-76f81fc8）。CADコード・入力はこの補正で変更していないため、そのCAD回帰と、補正後に再実行した非CAD全回帰を照合しました。最初の全回帰764件は759成功／5失敗で、5件は上記の2つの原因でした。


### 最終の全回帰

| 実行 | 結果 | 秒 | 記録ID |
|---|---:|---:|---|
| 非CAD分割1 | 256成功 | 1149.33 | 20261017T064954Z-f014dfc8 |
| 非CAD分割2 | 273成功 | 1513.08 | 20261017T064955Z-bff702ba |
| 非CAD分割3 | 204成功 | 1125.81 | 20261017T064953Z-bcef194c |
| CAD（新既定モデルのBlade-only STEPを含む） | 35成功 | 1481.10 | 20261017T063309Z-1a63b178 |
| 改行正規化後のデータ照合の再確認 | 1成功 | 65.00 | 20261017T065957Z-4a574a74 |

769実行から、意図した照合テストの再確認1件だけを重複として除くと768件です。別PCのGit改行設定で誤判定しないよう、データ照合テストはCRLF／LFだけを正規化したSHA256を使います。製品コードと既定JSONは最終回帰開始時から変えていません。変更したのは当該テストの入力照合だけで、再確認1件も成功しています。経緯は`provenance-test-revision.json`、回帰開始時と最終の221入力のハッシュは`regression-source-hashes.json`／`final-source-hashes.json`に保存しています。

追加の数値試行では、既定モデルのDiffuserとRCを51位置で調べ、Diffuserは8断面／スロート1件、RCは9断面／スロート1件、両方エラー0でした。`stator-passages.json`へ記録しています。これは近似の幾何解析で、CFDや実機性能の確認ではありません。

最終差分は15ファイルです。原本JSONと既定JSONはバイト一致し、歴史的な数値fixtureは不変、stage済みファイルは0件です。`final-review.json`へ記録しました。ユーザー原本・家計簿には書き込まず、commit／pushも行っていません。
