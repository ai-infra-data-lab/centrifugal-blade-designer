# 基準スプラインの区間別Jacobian包絡

Stage 3Aの位置差包絡に続き、`geometry/surface_regularity.py::surface_jacobian_envelope`を追加した。既存の形状生成・GUI・CAD格子採用・保存・出力ガードは変更しない。Qt/OCP/ファイル形式から独立した読取り専用APIである。Hypothesis/uvは使用・導入しない。

## 評価する量

領域[0,1]²の基準tensor splineについて、`N = dS/dspan × dS/dxi`とその大きさ`J = |N|`を評価する。XYZはmm、Span/xiは無次元なのでJはmm²のパラメータ面積密度である。面積積分値でも体積の符号付きJacobianでもない。Nの向きもCAD solidの外向きを意味しない。

対象は前段の位置差包絡と同じclamped/非周期、degree 1〜3の実XYZ面で、元knotの多重度からC1を保証できるものに限る。形式上C0の継ぎ目がある場合は拒否し、法線を平均化して隠さない。係数が偶然直線になる等の理由で実際にはC1でも、この構造検査では対象外となることがある。拒否は形状不良の証明ではない。row/role/派生元の意味は呼出し側が確認する。

## 全区間の包絡

1. knot挿入により、元の面をrefitせずtensor Bézier区間へ分解する。
2. 各区間のcontrol netの差分から、元のSpan/xiに対する微分のBernstein係数を作る。区間幅による除算を省略しない。
3. 微分どうしの外積をBernstein積の係数へ展開する。単なる同indexのpole外積ではない。
4. Nの係数を包含する直方体の原点からの距離と、中央N方向への分離射影からJの下限を取る。N係数ノルムの最大値から上限を取る。

積の係数は次の恒等式を2方向へ適用して導く。

`B_i^p(t) B_j^r(t) = binom(p,i) binom(r,j) / binom(p+r,i+j) × B_(i+j)^(p+r)(t)`

Bernstein基底の定義は[SciPy BPoly](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.BPoly.html)、形状を維持するknot挿入は[SciPy insert_knot](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.BSpline.insert_knot.html)を参照。

これらは実数モデル上の包絡である。実装はfloat64であり、丸め誤差を包含する区間演算ではない。必ず`roundoff_certified=False`を返し、工学的な公差のPASSにしない。既存CADの公差は変更しない。

## APIと状態の意味

```python
result = surface_jacobian_envelope(surface, singular_mm2=1e-12, refinements=0, max_cells=4096)
```

退化の閾値は呼出し側が有限・非負の値を指定する。上の値は診断例であり、製造/設計公差ではない。面のスケール・パラメータによってJの尺度も変わる。

- 各cellにSpan/xi範囲、`lower_mm2`/`upper_mm2`、元スプラインの9標本での最小Jを返す。
- `numeric_regular`: 下限が閾値より大きく、閾値以下の標本もない区間。丸めを含む証明やCAD成立とは異なる。
- `unresolved_cells`: 上記を確保できない区間数。これだけでつぶれがあるとは断定しない。追加細分化で絞れる場合がある。
- `sampled_at_or_below_threshold_cells`: 9標本のいずれかで閾値以下だった区間数。必ずしもJが厳密に0ではない。同じ境界点を共有する複数cellは別々に数え、点の一意件数ではない。

全体には各件数、最小下限/最大上限/標本最小値も返す。細分化は0〜4回で、全区間へ中点を挿入する。cell数の上限を超えたらBézier netを作る前に拒否する。元のknot・係数を変更せず、不正入力や非有限演算を黙って修正しない。判定不能をPASSにするfallbackはない。

## 独立negativeと制限

- `S(s,t)=(t,(s−0.37)²,0)`はs=0.37で退化する。0/0.5/1の標本は非零でも、包絡は該当区間の正の下限を確保できず未判定として残す。
- `S(s,t)=((s−0.25)(s−0.75),(s−0.25)(s−0.75)(s−0.5),t)`はs=0.25/0.75の内部で同じ位置を通るが、局所微分は同時に0にならない。細分化した全cellで数値下限が正でも、面は内部交差する。この例を固定試験にし、局所正則を自己交差なしへ変換しない。
- 元のC0継ぎ目を拒否する試験も含む。形状を平滑化して試験を通さない。

法線の全域方向比較、周期翼/主翼-Splitter干渉、cap/fillet/STEP面、構造/流体境界の一致、Preview/trimとの物理対応は未対応。Stage 3A/3B全体の完了ではない。現既定の根元fillet未成立も別課題である。

## 現既定Impellerの診断

同梱既定JSONのMain/Splitter、4roleを固定格子65/129/257/513で作り、細分化0・閾値1e−12 mm²で調べた。表のcell数は4roleの合計。全条件で未判定0・閾値以下を標本で観測したcell0だった。これを全体の自己交差なし・最終CAD/STEP成立とは報告しない。

| 集合 | 格子 | cell数 | 4roleの最小数値下限 [mm²] |
|---|---:|---:|---:|
| Main | 65 | 256 | 7.97522 |
| Main | 129 | 512 | 7.99417 |
| Main | 257 | 1,024 | 8.00940 |
| Main | 513 | 2,048 | 8.01833 |
| Splitter | 65 | 256 | 14.0467 |
| Splitter | 129 | 512 | 14.0258 |
| Splitter | 257 | 1,024 | 14.0209 |
| Splitter | 513 | 2,048 | 14.0196 |

根拠は`artifacts/quality-surface-regularity/probe.py`、`default-probe.json`。各roleの最小下限付近3cellと未判定cellを保存する。原本/同梱既定JSONは不変（SHA-256 `aa724c8253463289caec919960d7d486d698765cee35202c13e4efd17a603dd6`）。

## 検証

新規25件（数値24・実OCCT1）。平面とmm²の二乗スケール、3次面の解析J、標本間の折返し、完全につぶれた面、内部自己交差との区別、C0拒否、不正閾値/細分化/資源上限、入力不変を確認する。

関連82件成功（`20261018T072331Z-59f50f94`）。内部交差negativeを強化した後、新規25件再成功（`20261018T072414Z-e4390dd6`）。期待する解析値や既存fixtureの数値は変更しない。実OCCTはMain/Splitter＋gap/Rakeの8基準面で、各cellの9点をD1から外積して包絡と照合する。演算比較に`4096×machine epsilon×max(1,上限)`の許容幅を使うが、これは丸めの証明やCAD公差ではない。

**全1,238一意件成功**（通常1,196・実CAD42）。既存1,213 IDを維持し、新規25 IDを追加。failure/error/skip/実行漏れ/重複/想定外IDは0。固定279入力は回帰開始から不変で、原本/同梱既定JSONも一致した。既存数値fixture/期待値は変更していない。native GUI・高DPI・ANSYS Import/Meshは今回未検証。診断はまだGUI/出力ゲートへ自動接続していない。

追加の解析プローブではs=0.37の折返しを細分化0〜4回で調べた。9標本/cellはどの段階でも閾値以下を観測しなかったが、未判定Spanは[0,1]→[0,0.5]→[0.25,0.5]→[0.25,0.375]→[0.3125,0.375]へ狭まった。`artifacts/quality-surface-regularity/fold-localization.json`へ保存し、この追加プローブを全回帰の件数に加算しない。


全回帰の根拠: `artifacts/quality-surface-regularity/final-test-coverage.json`、`source-hashes.json`、`collected-tests.txt`。通常6群/CAD1群のJUnitを収集IDと照合した。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 282.051 | 20261018T072436Z-6cb7dc39 |
| 通常1 | 143 | 251.684 | 20261018T072436Z-c42b6eec |
| 通常2 | 122 | 295.940 | 20261018T072436Z-b81eff1c |
| 通常3 | 191 | 206.055 | 20261018T072436Z-e535fb10 |
| 通常4 | 146 | 273.271 | 20261018T072436Z-339a6cbe |
| 通常5 | 478 | 361.940 | 20261018T072436Z-2d365bcb |
| 実CAD | 42 | 724.655 | 20261018T072436Z-61f5b2ac |
