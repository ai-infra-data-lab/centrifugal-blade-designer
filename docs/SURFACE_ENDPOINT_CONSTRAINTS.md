# 共有境界の端点制約

## 問題と修正

既定16継ぎ目のmaster断面端点は完全一致していたが、沿翼方向の混合補間方程式で
端点poleまで未知数として解くと、10継ぎ目で約1e-17〜3e-14 mmの差が現れた。
前段の厳密比較では216候補中130組に係数モデルの差を検出していた。

`geometry/surface_evaluation.py::fit_surface_spline`は、従来と同じsample、次数、knot、
接線条件を使い、端点位置を固定した補間方程式として構成する。
clamped knotでは端点poleは入力端点に等しい。接線指定時は隣接poleを
`c1=c0+d0*(t[k+1]-t[1])/k`と末端の対応式で固定し、残りを内部sampleの
B-spline collocation行列で解く。固定poleの寄与を右辺へ移してから疎LUで解く。

補間後の面をweldしたり、一方のroleのpoleを他方へコピーする処理ではない。
共有する入力端点とSpan構成が同じなら、その境界の入力pole列が同じになり、
Span補間でも同じ係数を得る。実入力に1 ULPのgapがあれば、その差は保持する。
旧参照値を置換せず、同じ数学的補間と解析解で整合性を確認する。
LE/TE、β、厚さ、R/Z、元制御点、設計JSON、CSV/Profile Pointsは変更しない。
CAD/基準表示の係数は丸め規模で変化するため、旧診断のfingerprintや古いgap数値は
新しい面へ流用しない。必要な診断は新sourceで再生成する。

## 検証

次数1/2/3、密度2〜129、接線指定、非均一Spanの解析3次面、異なる内部形状/接線/密度を
持つ共通境界、入力不変、1 ULPの実gapを検査する。関連63件、Ruff成功。
全回帰2,192一意件成功（通常2,147・実CAD45）。既存2,179 IDを保持、新規13件。
失敗/error/skip/漏れ/重複/予期しないIDは0。固定352入力のSHA256は検査中不変。
通常7群・実CAD1群を選択`.venv`の`tools/run_tests.py`で実行し、全収集IDとJUnitを照合。
証跡は`artifacts/quality-fixed-endpoints/final-test-coverage.json`、`source-hashes.json`、
`collected-tests.txt`と各group log、`artifacts/test-runs/`に保存した。

packaged defaultのfit65基準面で、16継ぎ目と216候補すべての境界曲線が厳密一致になった。
従来の表現不一致130組は解消した。以前と同じgap/position/単調性閾値で再生成した診断では、
balanced方式で200組が局所数値条件成立、主翼の16組は条件未達。
この16組を既存APIの`refinements=1`で再評価すると、すべて同じ親セル領域のroot条件が成立した。
この細分は診断包絡を絞る操作であり、要求範囲や元形状を小さくして成功させる処理ではない。
全候補が今回の局所数値条件を満たしても、非共有/非局所/包含/最終CAD/丸めは別の検査である。

旧HEADの補間コードを独立moduleとして実行し、新旧の同一knot/次数の全control netを比較した。
保存係数モデルに基づく位置差の数値上限は、Main約3.70e-14 mm、Splitter約3.56e-14 mm、
Diffuser約7.15e-14 mm、RC約7.11e-14 mm以下だった（float丸めの区間保証ではない）。
これらは旧数学的補間からの丸め規模の差で、原本の設計値は変更していない。
証跡は`artifacts/quality-fixed-endpoints/default-probe.json`、`legacy-comparison.json`、
`refined-candidates.json`と各再現スクリプトに保存した。

これは共有境界の生成契約の修正であり、全面非干渉やfloat区間保証、
最終CAD/filletの成立証明ではない。
