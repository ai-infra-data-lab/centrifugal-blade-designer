# 元曲面対応を保った接触候補の局所細分（Stage 3B-3f）

## 対象と変更範囲

前段の自己診断が返すface IDを元splineのrole・Span区間・xi区間・対角半分へ対応づけ、
選択した2三角形の領域だけを細分して、位置誤差込みの接触・近接診断を再実行します。
設計アルゴリズム・元spline・GUI・JSON・出力条件は変更しません。
局所単射性、全翼面の自己交差、最終CAD、丸め保証や出力ゲートの完成ではありません。

```python
from blade_designer.geometry.contact_refinement import refine_contact_pair

# envelope は同じ surfaces から作った merged_role_error_envelope の結果。
# self_report はその mesh と merged_triangle_upper_mm に対する自己診断。
for item in self_report['nonlocal_examples']:
    result = refine_contact_pair(
        surfaces, envelope, item['first_face'], item['second_face'],
        target_mm=0.001, clearance_mm=0.0, area_epsilon_mm2=1e-16,
        max_depth=4, max_cells=256, max_work=500000, max_records=100,
    )
```

例の数値は製造公差の推奨ではありません。XYZ・誤差・要求距離はmm、面積閾値はmm²。
`source_triangle_patch(envelope, face_id)`で対応だけを取り出すこともできます。
`refine_source_triangle(surface, patch, ...)`は指定三角形領域の細分を単独で実行します。
後者だけでは以前の診断snapshotとの同一性は確認しません。

## 古いface IDを別の曲面へ適用しない

`merged_role_error_envelope`のmeshがある結果へ次の追加fieldを記録します。

| field | 内容 |
|---|---|
| `source_fingerprints` | 各roleの両方向knots・degree・Cartesian control netの識別値 |
| `mapping_fingerprint` | 診断meshの頂点/face/結合前face/role順とSpan/xi軸の識別値 |

数値の元上限・結合・face順・旧fieldの値は変えていません。
識別値は内部のSHA-256で、JSON設計schemaや外部ファイル形式へ追加するものではありません。
元の補間条件を変えるknot挿入など、同じ形状を表す別表現でもsnapshotの変更として拒否します。
悪意あるcallerの改ざん防止や信頼できない入力の署名ではありません。

再評価ではmappingの一致と選択roleのsource識別値を検査し、作業用に曲面をコピーします。
隅の座標が同じでも内部係数を変更したsourceは拒否します。
ID不正・mapping変更・source変更・識別情報のない旧診断結果はValueErrorです。
その場合は現在のsourceから前段のenvelopeと自己診断を再生成してください。
meshがない資源上限/継ぎ目不成立の結果を部分meshで代用しません。

## 元三角形の領域だけを細分する

roleごとのtensor格子セルrow-major、各セルABC/ACDの順からfaceを復元します。
対角はA=(0,0)、B=(1,0)、C=(1,1)、D=(0,1)です。
元セルを正規化した座標で、ABCはu≥v、ACDはu≤vの半分です。
矩形全体へ領域を広げると、元三角形が含まない正常接続部を比較に混ぜるため、そうしません。

元セル境界へknotを挿入し、対応するBézier control netを抜き出します。
元曲面の再fitや接点移動はありません。内部knotを跨ぐ不正なセルは拒否します。
de Casteljauで両方向を二分し、対角上の子セルは元の片側だけを残します。
完全に三角形内にある子セルは2三角形、対角セルは1三角形とします。
領域外の子セルは除き、元三角形領域全体と境界を覆います。

既存のcontrol net対双一次面の上限＋対角三角形の上限に、
sourceから実評価した四隅とcontrol netの四隅との差を加えます。
誤差上限の大きい葉から細分し、`target_mm`・深さ・葉セル数で制限します。
上限に達しても残る領域は捨てず、有限な上限を持つ粗い葉として残し、`UNRESOLVED`にします。
各葉に元区間・深さ・対角セルかどうか・上限、各三角形に対応上限を返します。
`parameter_vertices`とfacesで、細分後の各点/三角形を元パラメータへ追跡できます。

葉の独立細分はT junctionや重複座標IDを許します。2つの領域の比較には各三角形の
被覆と誤差上限を使えますが、そのmeshを共有IDの自己接続/位相検査へそのまま渡せません。
`contact_ready=False`のままです。

## 再評価結果の意味

2つの元領域を別々に細分し、`error_aware_mesh_contacts`で全三角形組を再評価します。
基準は`original_unmerged_splines`です。前段の継ぎ目結合meshを再細分するのではなく、
同一snapshotの元splineを再評価するため、新しいmeshでは継ぎ目の座標結合を行いません。
前段の結合後誤差をそのまま流用せず、この元面対新三角形の誤差を計算し直します。

`refinement_target_met`は両領域の細分誤差目標を満たしたかです。
`contact_report.status`は数値分離・未判定・三角形接触候補・走査不完全を表します。
上流の誤差目標未達でも有限な保守的上限から分離できる場合があるため、両状態を別に返します。
分離できたときに証拠を与えるのは、この**選択2領域だけ**です。
共有接続を含む組を指定すれば、その境界の接触候補は残ります。正常接続の除外や局所単射性の証明はしません。
局所的なJacobian/継ぎ目の成立、包含、遠い周期コピー、全Span、cap/fillet/STEPを代わりにPASSへ進めません。
`whole_geometry_verified`・`continuous_surface_certified`・`roundoff_certified`はFalseです。

## 非局所のIDを別枠で保存

自己診断へ`nonlocal_examples`・`nonlocal_examples_truncated`を追加しました。
従来の`examples`は走査順の先着保存と旧値を維持します。
新しい別枠も`max_examples`件までですが、局所未判定で埋まりません。
局所と非局所の両方に枠を持つため、保存例は従来の最大2倍です。
上限後も全体の走査と件数集計を続ける規則は変えていません。
別枠も省略ありなら全対象IDを列挙したとは扱わず、細分した組だけの結果として報告します。

## 検証

新規42件：全faceの元role/cell/対角対応、mapping/座標軸の変更拒否、ID不正、
両対角半分の被覆面積/領域/三角形数、saddle解析解の4分の1収束、
粗い近似の未判定が細分で分離する例と実交差negative、資源上限でも領域を保持、
source/結果の不変、隅が同じで内部係数が異なるsourceの拒否、型/範囲、
内部knot区間の抽出、cubic面の独立した重心座標標本による包絡確認、
旧診断拒否・同じfaceの拒否、非局所IDの保存枠を確認しました。
基礎63件、最終関連114件、限定Ruffが成功。
全回帰は**1,920一意件成功**（通常1,875・実CAD45）、既存1,878 ID維持・新規42 ID。
失敗/error/skip/漏れ/重複/想定外IDは0、原本/同梱既定JSONを含む固定335入力のhashは不変。
通常7区分と実CAD1区分をproject runnerで実行し、全収集/実行IDを照合しました。
CAD45件は既存出力経路の回帰で、この局所診断を最終CAD面へ適用したという意味ではありません。
テストの環境エラーはありません。
旧自己診断の2ケースは、新規2fieldを除く全fieldが修正前の記録と一致しました。
テスト期待値・歴史的fixture・原本/同梱既定JSONは変更していません。

全回帰の`source-hashes.json`・`collected-tests.txt`・`final-test-coverage.json`、
旧fieldの比較記録`old-self-reports.json`・`compare_reports.py`、実形状試行は
`artifacts/quality-contact-refinement/`へ保存しました。
native GUI/F5・ANSYS Import/Meshは未実施です。

変更は`contact_sources.py`・`contact_refinement.py`の新設、
`merged_role_error.py`の識別情報追加、`error_aware_self_contacts.py`の非局所例枠追加、
新規テスト、本書、FEATURES・ARCHITECTURE・DEVELOPMENT_ROADMAP・ERROR_AWARE_SELF_CONTACTSの10ファイル。
既存設計値/アルゴリズム・GUI・出力・数値fixture・原本/同梱既定JSON・親フォルダの家計簿は変更していません。

## 同梱既定の非局所9組の再評価

Impeller Main/Splitterのfit65基準面で、前段は誤差目標0.02 mm・join tol=1e-8 mm、
自己診断はclearance=0・adjacency tol=1e-9 mm・area epsilon=1e-16 mm²・max_work=500,000・
max_examples=16としました。前回と同じ非局所未判定6/3組を取得し、省略がないことを確認しました。
局所再評価は各領域target=0.001 mm・max_depth=4・max_cells=256、比較のmax_records=100です。

全9組でsource identity一致、両領域の誤差目標達成、比較走査完了、`NUMERIC_SEPARATED`を確認。
いずれもLE/LEの別三角形領域です。形状を移動/修復したのではなく、元の同じ曲面を再評価した結果です。

| 対象 | 元face IDの組 | 細分後の三角形数（第1/第2領域） |
|---|---|---|
| Main | 409 / 412 | 16 / 4 |
| Main | 408 / 411 | 16 / 4 |
| Main | 408 / 412 | 16 / 4 |
| Main | 538 / 542 | 4 / 16 |
| Main | 539 / 542 | 4 / 16 |
| Main | 538 / 541 | 4 / 7 |
| Splitter | 408 / 412 | 16 / 4 |
| Splitter | 409 / 412 | 16 / 4 |
| Splitter | 408 / 411 | 16 / 4 |

IDはこのsource/mapping snapshotに限定されるため、他の設計/密度の同番号を指しません。
元のrole・Span/xi区間・対角半分、新しい誤差/三角形数、比較reportは
`probe.py`・`default-probe.json`へ保存しています。
全体の自己走査はMain約166秒、Splitter約176秒、選択組の再評価は各0.02–0.06秒でした。
全回帰と並行した今回の実測であり、単独性能やGUI応答性のbenchmarkではありません。

これで当該9組の非局所未判定は解消できますが、元の自己診断を全面PASSへ書き換えません。
共有部の局所未判定、patch内部の単射性、遠い周期コピー、包含、最終CADの未検査は残ります。

次は共有近傍の局所単射性/連続継ぎ目の証拠と、局所再評価結果を集約する条件です。
遠いコピー/包含、最終CAD照合、float丸め保証、全面誤差予算、小R根元fillet、native GUI/ANSYSも残ります。
