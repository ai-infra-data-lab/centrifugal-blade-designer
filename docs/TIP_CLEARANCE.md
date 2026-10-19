# オープンインペラの翼端クリアランス

既存の隙間を図面用として維持し、同じ翼Tipに対する解析用Shroudを別に生成する機能を追加しました。以下は従来の図面用Tip生成の定義・検証記録です。新しい解析用ラインの操作・共通法線・出力先は[解析用Shroud](ANALYSIS_SHROUD.md)を参照してください。

## 操作と定義

Impellerを選び、右側の`LE / TE`にある`オープンインペラ / Tip Clearance`を有効にします。`LE clearance [mm]`と`TE clearance [mm]`を入力し、Enterまたは入力欄からフォーカスを移して確定します。入力途中の各桁では再生成しません。

既存のShroud子午面を固定ケーシングとし、各点の接線に直交するHub側の法線へ指定距離だけ移した翼Tip子午面を生成します。LE–TE間はケーシング上の物理的な弧長で線形補間します。R差だけ、Z差だけ、翼の周方向距離による補間ではありません。ケーシングの解析Line／Arcは変更しません。

子午面のShroud LE／TEのR/Z表はケーシング上の基準点です。実際のTipは内側になります。TEが一定外径Cutoffの場合は従来のHub TE半径を維持し、TE隙間を確保したTipとその円筒面との交点を解き、補間のTE基準とします。従って旧Shroud TE基準と実際のTip TEに対応するケーシング点は異なる場合があります。複数交点では旧TEに最も近いものを選びます。

端部輪郭などLE／TE外側の計算に使う範囲では端の隙間を一定延長します。中間Spanを新規追加せず、既存SpanをHubから新しいTipへ接続します。Hub断面、入力β・厚さ、TE Rake Mapperを維持し、βの巻き角は変更後のSpan子午線から再計算します。Splitterも同じTipに従い、Splitter LEの隙間は主翼のLE–TE補間から決まります。

設定はImpeller翼列ごとに独立し、Undo／Redo、JSON保存／再読込に対応します。未編集の保存精度を維持します。未指定・無効・両端0 mmでは従来の生成経路を使い、未指定のJSONには新しいキーを保存しません。設定を持つJSONはschema 0.4です。静翼には適用しません。起動既定JSON・ユーザー原本は変更していません。

## 表示と流路解析

- 子午面に固定ケーシング（`Casing / Shroud`）と緑の実Tipキャンバーの子午線・端点を表示します。子午面選択時は設定済みの各翼列を表示します。
- 3Dでは翼自体を新しいTipで生成します。`Casing`と`Tip`で回転ケーシング面と翼端包絡面を個別に表示できます。緑のTip回転面は位置確認用の包絡面で、閉じた物理シュラウドではありません。
- 流路のGrossはHub–ケーシングのまま、翼厚閉塞は実際のHub–Tip区間だけで積分します。`Tip-gap / N`は1主翼ピッチの翼端開口面積です。Netはこの開口も含み、Splitter両側が求まる断面では`Main–Splitter + Splitter–Main + Tip-gap / N = Net / main pitch`です。スロートのSpan積分は実翼のHub–Tip高さです。

面積は幾何学的な値で、漏れ流量、境界層、クリアランス渦、空力性能を予測しません。

## 無効形状と出力の制約

負・非有限・数値でない隙間、Hubへ届く隙間、向きの曖昧な法線、正半径を失うTip、Tip子午線の折返し・サンプル自己交差、到達不能な一定外径TEを拒否します。子午線の検証は翼間の3D干渉を保証するものではありません。形状エラー時は理由を表示し、古い形状で流路解析を実行しません。

正の隙間を持つImpellerのTurboGrid Profile Pointsは、2026-10-17の追加で実Tip断面とShroud延長断面を同じprofileファイルへ出力できます。読込み後にShroud TipのProfile Numberへ実Tipの番号を指定します。詳細は[クリアランス付きTurboGrid](TURBOGRID_CLEARANCE.md)。TurboGrid CAD（TurboGrid出力を有効にしたBothを含む）とSplitter付きは引き続き未対応で、ファイル・job作成前に拒否します。ゼロ隙間の従来出力は維持します。以下の検証記録は追加前の履歴です。

MechanicalのBlade Onlyは新しいmaster断面をCADへ渡し、既存の閉solid・自己交差・STEP再読込検証を行います。一定隙間2 mmの厚翼例、LE 2／TE 3 mmの薄翼例は実CAD試験で成功しました。一方、厚さ20→24→20 mmの既存CAD試験形状へLE 2／TE 3 mmを適用した試行は、閉solidでも自己交差検証で拒否されました（SURFACES / BLADE SOLIDS、BREP=True、self-intersection-free=False）。この厚翼・可変隙間ケースは未解決で、成功扱いしません。翼＋ディスクの既存フィレット制約も継続します。

## 変更箇所と検証

数値処理は`geometry/tip_clearance.py`に分離し、`models/parameters.py`と`models/geometry_3d.py`で設定と派生Tipを保持します。`geometry/geometry_3d.py`、`splitter.py`、`passage.py`が同じTipを参照します。GUIは`tip_clearance_editor.py`、`main_window.py`、`context_meridional.py`、`preview_3d.py`、`passage_widget.py`、保存／保護は`project_io.py`、`turbogrid_export.py`、`cad/client.py`、検証は`models/validation.py`です。

新規試験は`tests/test_tip_clearance.py`、`test_tip_clearance_gui.py`、`tests/cad/test_tip_clearance_cad.py`。直線・円錐の解析座標、曲線ケーシングへの法線距離、LE／TE補間、固定外径、Splitter、Hub不変、ゼロ隙間の配列／TurboGridバイト一致、保存精度・翼列独立、Undo、入力確定、表示、無効時の出力保護を検証します。過去の数値参照は変更していません。

途中のGUI試験では簡易壁面オブジェクトにTip属性がない経路を検出し、任意属性として扱う修正後に成功しました。CAD試験のimport指定と、存在しない試験ファイル名による2試行はテスト収集前のエラーで、修正して再実行しました。既定面積の単発確認でも翼枚数属性名の誤指定があり、正しい`geometry.vane_count`で29断面・エラー0を確認しています。環境障害と扱いません。

関連56件成功（136.45秒、`20261016T124521Z-91b0d2d3`）、上記成功CAD例2件（18.34秒、`20261016T124258Z-edbf6f3b`）。全回帰開始後、子午面のTip表示キーへ翼列IDを付け、同名翼列でも線を上書きしないよう修正しました。この修正と同名翼列の追加アサートを含む最終GUI3件は新規プロセスで成功（26.45秒、`20261016T125532Z-8f3e430e`）。

CAD全回帰35件成功、681.31秒（`20261016T124857Z-3371f22b`）。初期の厚翼・可変隙間の拒否例をCAD成立として数えず、閉solid検証に成功する一定隙間厚翼／可変隙間薄翼の2例を含みます。

その他の全回帰612件成功、973.03秒（`20261016T124857Z-a4ed18b5`）。上のCAD35件・表示修正後GUI3件と合わせて650実行、重複を除く全収集647テストIDを照合し、実行漏れ・unexpected・失敗・error・skipは0件でした。最終固定後のpackage／testの197 Pythonファイルもハッシュ一致を確認しました。単一実行の647 passedという意味ではありません。最終ソースハッシュとJUnitの照合記録は`artifacts/tip-clearance-review/final-test-coverage.json`です。

追加の単発確認で、CW／CCW双方について隙間＋TE Rake 25°＋Splitterの組合せでもHub配列・β・厚さが不変、Rake実測24.999999999999982°を確認しました（`rake-combination.json`）。最初の完全一致アサートはZ=19.000000000000004と19の浮動小数点差で失敗し、既存数値試験と同じ1e-9 mmの比較で成功しています。数値参照は変更していません。

既定JSONのコピーへLE 0.5／TE 1.0 mmを適用したQt offscreen画面を`artifacts/tip-clearance-review/controls.png`、`meridional.png`、`area.png`へ保存し、入力欄、緑のTip線、Tip／Casingの別表示を目視確認しました。流路解析は335断面・エラー0、最小Tip-gap / Nは19.447206 mm²。測定値は`smoke.json`。Meiryoは画像取得プロセスだけで読み込み、製品フォントは変更していません。

git diff --check成功、既定JSONのSHA256は変更前の6511ea9186e18acad72ef055f0dbc1de4ac0700c27dc75627abad065a9121bceと一致。以前の未コミットCAD・流路解析変更を維持し、今回の数値参照・ユーザー原本は変更していません。

実ディスプレイ／F5／DPI／別PC／Python 3.11の今回変更後再検証、ANSYS Import／Mesh、実機／CFD照合は未確認です。stage・commit・pushは行っていません。
