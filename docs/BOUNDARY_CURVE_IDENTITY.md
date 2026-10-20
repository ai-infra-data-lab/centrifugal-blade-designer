# 境界曲線の同一性と係数モデル（Stage 3B-3m）

## 目的と範囲

`geometry/boundary_identity.py::boundary_curve_identity`は、2つのξ端の境界曲線を、
保存されたfloat64 knot/係数が表す**同じSpanパラメータの曲線**として比較する。
`role_boundary_curve_identity`はLE/PS/TE/SSの4宣言継ぎ目を比較する。
元面のsnapshotとfingerprintを保持し、原本・係数・設計値・JSON/GUI/出力を変更しない。
既存のgap包絡・継ぎ目chart・出力条件を置換せず、別の読取り専用診断APIとする。

従来のrawな境界表現の比較は、次数やknotが異なるだけでも不一致になる。
一方、floatのknot挿入や再fitには微小な丸め差が入り得るので、
差が小さいという理由だけで同じ曲線とみなすこともできない。
本APIは、この2つを保存係数モデルの範囲で区別する。

## 正確な入力モデルでの比較

float64は有限な2進有理数なので、`Fraction(float_value)`でその値を正確に取り込める。
元knotとXYZ poleを有理数へ変換し、de Boor評価も加減乗除だけで行う。
SciPyのfloat評価値を比較したり、浮動小数点でknot整合や次数変換してから
「ゼロに見える差」を採用する方法ではない。

両曲線のknotと指定Span範囲の端を合わせて共通区間を作る。
各区間の曲線は次数p以下の多項式（pは両次数の大きい方、1〜3）。
各区間でp+1個の異なる有理パラメータにおけるXYZがすべて厳密に等しければ、
差多項式の次数から、その区間全域で恒等的に等しいと決められる。
端点も使うため、C0連続の境界曲線を対象とし、不連続なSpan knotは拒否する。

たとえば次数3なら端点と区間の1/3・2/3を使う。
従来の0・0.5・1の標本が等しくても、区間内で異なる3次曲線を検出する。
一つでも正確に非ゼロな差があれば、その点を反例として保存して同一性を否定できる。
反例のSpan・XYZ・差は有理数文字列で返し、subnormalやfloat範囲を超える差も
丸めてゼロ/Infinityに置換しない。
大きな整数は9桁ずつ十進文字列へ変換し、Pythonのグローバルな整数文字列桁数制限を変更しない。
許可bit数内の約5,000桁の分子/分母も、正確な文字列とJSONとして返せることを検証した。

| 結果 | 意味 |
|---|---|
| `EXACT_SAME_PARAMETER_CURVE` | 指定範囲の全共通区間で、保存係数モデルの曲線が同一 |
| `EXACT_PARAMETER_CURVE_DIFFERENCE` | 同じSpanで非ゼロの差を持つ正確な反例あり |
| `RESOURCE_LIMIT` | 計算上限に達し、同一性を決定していない |

`same_float64_boundary_representation`は従来のknot/次数/pole表現の一致、
`same_parameter_curve_exact_model`は今回の決定（True/False/None）を分けて表す。
前者がFalseでも、後者がTrueになる次数違い・knot違いを扱える。

## 上限と未判定

- `max_evaluations`（既定8192）: 区間数×(p+1)×2の最大評価数を事前に確認。
- `max_control_points`（既定4096）: 各境界曲線のpole数を確認。
- `max_fraction_bits`（既定16384）: 入力・中間有理数の分子/分母のbit数を制限。

上限超過時は、途中まで同じだった結果を全域の同一性へ昇格させない。
完了評価数・完了区間数・検査した有理数の個数・停止理由を記録する。
4継ぎ目の集約では、どれか一つの確定した差で「すべて同じ」はFalseになるが、
他の継ぎ目が未判定なら`scan_complete=False`を保つ。
全4比較の同一性が決定済みかをこのフラグで表し、全点の標本走査を意味しない。

## 保証しないこと

この正確さは**保存float64係数をそのまま有理数とみなしたモデル**に対するもの。
元の設計意図、再fit前の理想曲線、係数生成時の丸め誤差の上限は推定しない。
異なる表現を別々のfloat評価器で計算した結果のbit一致も保証しない。

同じSpanでの差は、最近接距離やHausdorff距離ではない。
同じ線分を逆向きや非線形パラメータでたどる場合も、同じSpan曲線としては不一致になる。
微小な差を製作上の隙間・設計不良と断定しない。
したがって`input_generation_error_bounded/physical_gap_certified`はFalseのまま。
`seam_chart_ready/roundoff_certified/continuous_surface_certified/whole_geometry_verified`もFalseを保つ。
有理数比較自体は正確でも、そのまま3D微分包絡や最終CADの丸め保証へ広げない。

表現が異なっても完全一致する曲線を現行のchartへ自動採用する変更は今回行っていない。
元境界を移動・weld・refitせず、既存の接触reportや出力可否も書き換えない。

## 既定モデルの結果

前段と同じpackaged defaultのfit65参照面、Span全域と選択候補の親セル範囲を使用。
元knot/係数をそのまま比較し、上限による未判定はなかった。

| 群 | 全継ぎ目：同一／差あり | 選択候補：同一／差あり |
|---|---:|---:|
| Impeller Main | 2／2 | 6／6 |
| Impeller Splitter | 1／3 | 3／9 |
| Diffuser | 1／3 | 1／3 |
| RC | 2／2 | 2／2 |
| 合計 | 6／10 | 12／20 |

以前に境界不一致で未判定となった20候補は、保存係数の対応曲線にも非ゼロの差があった。
単に次数やknotの表記が違うだけとは扱えない。
ただし差の起源が丸めか設計上の不連続かを、この比較だけでは決められない。
前段の微小gap包絡の[観測記録](BOUNDARY_GAP_ENVELOPE.md)と併せて解釈する。
20候補の未判定、既存12候補の数値条件成立、既存の形状/出力条件は維持した。
試行と正確な反例は`artifacts/quality-boundary-identity/probe.py`・`default-probe.json`に保存した。

## テストと残課題

新規36件は、次数/knotが異なる同一曲線、C0区間、隠れた3次差、1 ULP/subnormalの差、
float範囲を超える有理数の差、非線形/逆向きパラメータ、指定区間、
計算途中のbit上限・評価/pole上限、既知の差と未判定が混在する集約、入力拒否・元係数不変、
大きな反例の文字列/JSON化とグローバル設定の不変を確認する。
quick63件、関連105件、変更PythonのRuffは成功。

最初の全回帰は、大きな有理数の標準文字列化がPythonの桁数制限に当たる例を確認したため中断した。
当該テスト用process treeのみ停止し、終了競合でtaskkillが非ゼロを返したが、残存processがないことを確認した。
その実行は`artifacts/quality-boundary-identity/interrupted-run.json`でNOT_PASSとして記録している。
反例の文字列化を補強後、関連105件/Ruffを再実行し、最終コードの全回帰を別ディレクトリで実行した。
補強前後の既定16継ぎ目・選択32候補の全診断内容は一致を確認した。

最終の全回帰は2,146一意件成功（通常2,101・実CAD45）。既存2,110 IDを保持し、新規36件を追加。
失敗/error/skip/漏れ/重複/予期しないIDはいずれも0。
通常7群・実CAD1群を選択`.venv`の`tools/run_tests.py`で実行し、全収集IDとJUnitを照合した。
固定348入力のSHA256は検査中不変。原本`blade_v03.json`とpackaged defaultもそれぞれ維持した。
最終全回帰の証跡は`artifacts/quality-boundary-identity-final/final-test-coverage.json`、
`source-hashes.json`、`collected-tests.txt`、各`group-*.log`へ保存した。

次は差を持つ保存係数モデルの扱いと、元の生成精度・物理的対応を含めた採用条件を整理する。
全候補の品質集約、遠い周期翼/包含、最終CAD/fillet/STEP照合、全面誤差予算は残る。
native GUI/F5・ANSYS Import/Meshは今回未実行。
