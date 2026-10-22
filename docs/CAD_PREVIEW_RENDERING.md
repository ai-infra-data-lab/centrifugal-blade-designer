# 大きなCADプレビューの読込みと描画

## 変更する範囲

CAD overlayの表示中、壁面を含む可視面数が4,096を超える場合だけ、完成画像の生成をworkerへ移す。
設計値、面の補間方式、BREP、STEP、CSV、TurboGrid、保存JSONは変更しない。
それ以下のCAD overlayと、CADを表示しない通常の翼/回転壁表示は従来の同期描画を維持する。
通常形状の再生成、全翼列生成、CADフィレットのマウス当たり判定は別の同期処理として残る。

`gui/surface_render.py`は独立したQImageに描画し、QWidgetやチェックボックスを参照しない。
GUI側で位置配列を独立した読取り専用配列へ複製し、色・カメラ・投影基底を固定して渡す。
QPainterの順序、照明、色、alphaは既存の同期描画と同じである。
Qtの[スレッドと描画の規約](https://doc.qt.io/qt-6.10/threads-modules.html)に従い、
workerは専用QImageだけを使い、完成後にGUIスレッドが表示する。

viewごとに実行中1件と差替え可能な最新要求1件だけを持つ。
CAD設定世代、壁配列、全表示切替、カメラ、サイズ、DPRが一致する完成画像だけを表示する。
同じpayloadオブジェクトを再設定しても世代を更新する。元の視点へ戻る場合はキャッシュを
再利用し、不要になった要求を取り消す。取消は256 polygonごとに確認する。
非表示/close/destroy時は完了待ちをせず取消を要求し、workerはwidgetを保持しない。

待機中は最大1,000面の輪郭を一時表示し、`Rendering CAD surfaces...`と明示する。
これは操作中のフィードバックであり、出力meshや評価形状には使わない。
完成時は全polygonを描く。失敗時は粗い表示と失敗表示を残し、別視点やモデルの古い画像を表示しない。

## 内部キャッシュと互換性

`cad/preview_cache.py`は従来の`preview.json`を保持したまま、job内部に
`preview.cache.npz`を追加する。書込みはCAD process側で行う。
全triangle/edge座標をfloat64で保存し、同じshape/bytesの配列だけを共有する。
間引き、丸め、設計JSONの変換は行わない。読み込んだ配列は読取り専用とする。

読込みではpickleを許可せず、展開前のNPY header、dtype、shape、長さ、展開量、
role参照、edge offset、座標の有限性、必須metadataを検査する。
512 MiBの制限は任意の内部キャッシュだけに適用し、旧JSONやCAD出力に新しい容量制限を加えない。
JSONのサイズ/mtimeが変わったキャッシュや壊れたキャッシュは、理由を記録して旧JSONへ戻る。
statの照合はキャッシュ失効のためであり、暗号学的なsource認証やCAD妥当性の証拠ではない。
公開CADの既存hash/受入れ検査は別に維持する。

プレビュー自体が読めない場合も、メッセージを残してGUI workerの終了処理を完了する。
既に検証されたCAD出力を表示エラーのために変更せず、次のCAD操作を妨げない。
キャッシュを使えない旧jobのJSON読込みは同期のままである。

## 検証

関連52件、quick63件、変更PythonのRuffは成功。描画順の修正後の全回帰は、
全2,333一意ID成功（通常2,236・実CAD97、既存2,303保持・新規30）。
失敗/error/skip/漏れ/重複0、固定369入力のhashは不変だった。
新規30件は画像一致、最新要求の採用、取消/close、失敗後の回復、視点の再利用、
同一payload再設定、設計変更、表示切替、旧JSON、cache不正/欠落/NaN/object/過大header、
全scopeと空role、表示失敗後のworker解放を扱う。
画像比較はDPR 1/1.5/2で行い、設計データとカメラの維持も確認する。

Windows nativeの製品Preview3D単体で、既定R0.1の全周57,956三角形を使用した。
カメラ、Root/Full切替、リサイズ、モデル再設定、closeを実行し、最後の画像は同期描画と
画素単位で一致した。9.5秒のタイマー設定でheartbeat441回、最大間隔94 ms、最大paint94 ms、
cache読込み47 ms、close呼出し0.0 sを計測した。描画errorとcache警告は0。
これは1回の計測であり、一定FPS、全モデル/低メモリ/複数monitorでの応答を保証しない。
終了後に別途行った同期画像比較の時間は操作中の応答計測へ含めない。
記録と画像は`artifacts/quality-native-cad-render/`。

独立したcache試作ではJSON51,344,814 bytesに対しNPZ2,249,608 bytesで、
全triangle/edge値の一致と元JSONのhash不変を確認した。
この試作と製品GUIの計測を混ぜて速度改善率を算出しない。

native MainWindowの単翼＋Hubの限定経路は下記で追加確認した。
他のscope、物理的なmonitor移動、長時間の反復操作、人によるF5/マウス操作は別途確認が必要。
ANSYS Import/Meshは今回の対象外・NOT_TESTED。

## キャッシュと元JSONの描画順

CAD workerはpreview.jsonのobject keyを辞書順で保存する。一方、OCCTの面発見順は
辞書順ではない。初期実装でcacheのrole順をそのまま復元すると、同深度の半透明面の
重ね順が変わる条件を確認した。座標やCAD形状が変わった問題ではない。

read_preview_cacheでroleを元JSONと同じ辞書順へ戻す修正と、3枚の同深度・異色の
合成polygonを使う回帰を追加した。これは描画合成の単体試験で、有効BREPの証拠ではない。
修正前に画像hash不一致で失敗（20261022T214608Z-468db272）、修正後に関連52件成功
（20261022T214630Z-e48d39a5）を確認した。

実全周モデルでも、元JSONとcacheの全triangle/edge値がbyte単位で一致し、role順と
等角/上面/正面の画像が一致した。記録はartifacts/quality-cache-legacy-order/result.json。
同一cacheデータ同士の画像一致だけで、元JSONとの一致を代用しない。

修正前の全回帰はCAD97件と通常1,128件の成功後に意図的に中断した。
途中結果を修正後の成功件数へ流用せず、ログと中断理由を
artifacts/quality-cad-preview-render/interruption.jsonに保持した。
修正後は全2,333 ID（既存2,303＋新規30）を新しい固定369入力で全実行した。
記録はartifacts/quality-cad-preview-render-v2/final-test-coverage.json。
通常の2組は20261022T222843Z-32ce7986（1,128件）と
20261022T224222Z-f85ce94a（1,108件）、実CADは
20261022T214947Z-4afe418f（97件）で、全reportと監査controllerの終了codeは0。
独立に保持するユーザーJSONとpackaged defaultが同一であるとは要求せず、両方の不変を検査した。

native MainWindowの初回準備は、直接生成したMainWindowへ既定projectを渡しておらず、
翼列の選択前にTypeErrorで停止した。製品コードの不具合やCAD失敗には数えない。
失敗logはartifacts/quality-native-main-cad-preview/process.logに保持し、
main.create_windowを使う修正版を別のartifacts/quality-native-main-cad-preview-v2/で実行した。

## native MainWindowの限定経路と残る停止

本来のcreate_windowからpackaged defaultを読み、Impellerを選択し、メモリ内で明示R0.1 mm・
Blade+Hubを指定した。実際のstart_cad_job、数値準備process、CAD backend、私有caseへの公開、
cache表示、CAD Full切替、視点変更、resize、closeを実行した。
Mechanical PASS、公開STEP 1件のhash一致、画面とjobのsnapshot一致、最新frame採用、
render errorなし、原本JSON不変、destroy時のqueue閉鎖/取消を確認した。
closeは0.016 s、destroyは0.0 sだった。記録は
artifacts/quality-native-main-cad-preview-v2/35ed9f8170be40f2855682f9abe5a6f3/。

この経路の59,684可視polygonのCAD Fullは単翼meshの周期配置であり、全周一体solidの表示ではない。
全周solidの成立は別の実CAD回帰で確認する。仮ディスクのためoverall WARNINGを保持する。
既定の所属範囲がLE/TEを含まないdomain_errorも保持し、流体CAD/ANSYSの成功へ昇格させない。

全319.19 sの最大heartbeat gapは9.859 sだった。したがって、製品view単体の94 msを
MainWindow全体の応答性PASSへ読み替えない。受入れた既存jobだけを再公開/表示する別の診断では、
profilingありの完了callbackが0.437 s、最大gap0.453 s、paint最大0.110 sだった。
記録はartifacts/quality-native-main-cad-profile-v2/e7f2ac34848b4bfcb7e33e9af27c6282/。
これはCAD再計算を含まない別実行で、最初の9.859 sを消す再試験ではない。

start_cad_jobには、queue前の同期make_provisional_diskが残る。
独立profileでは13.359 sのうちhub_blade_extentが12.966 s、project_to_wallは9,458呼出し。
入力不変を確認した（artifacts/quality-provisional-disk-profile/）。profiling overheadを含むため
9.859 sとの時間差を直接比較せず、次の非同期化対象とする。数式/標本数/投影法は変更していない。

再利用jobの最初の診断も、自動生成後の仮ディスクを含まない入力でsnapshot不一致となった。
公開前に停止し、所有する診断process treeだけを終了した。失敗記録は
artifacts/quality-native-main-cad-profile/attempt-1.json。修正版はjobのgeometry_snapshotを使った。

## 次の計算分離の事前確認

私有のowned-process pipe試作でImpeller/Diffuser/内向きRCの選択形状・全3翼列・面積・error値が
同期計算と一致し、入力不変、childのQt未読込みを確認した。約4.2～4.3 MBの結果を約2.05～2.20 sで
生成した1回ずつの試行で、製品GUIへの非同期計算実装ではない。
記録はartifacts/quality-design-process-prototype/result.json。
一般再計算、仮ディスク生成、履歴/取消/世代照合への組込みは次の独立作業単位とする。
