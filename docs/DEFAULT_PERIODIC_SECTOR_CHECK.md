# 既定形状の周期セクター追加診断

## 入力と範囲

既存の全周Mechanical実試験 `20261023T131844Z-dceb882c` が作ったSTEPを読み、
既存 `OcctBackend.sector` でZ軸まわり0〜2π/11を切り出した。
同梱既定モデルの主翼11枚＋Splitter11枚、明示R0.1 mm、仮ディスクのケース。
元STEP SHA256は `6ca3d8ee3a0cb5aad7d470ae6b2631f13fc4fb0f829171958c4f9a684ea15c35`。
設計値・既定JSON・ユーザーJSON・公差・製品コード・出力ガードは変更しない。
全周STEPの読込みからの診断であり、設計値から周期workerを最後まで走らせた証拠ではない。

## 単一連結実体の条件は未達

`artifacts/quality-default-sector/e629be9c2d7440a2bda1613910a4937b/result.json`。
552.750 sで終了。読込み後の全周はBREP/自己交差/閉鎖/正体積/1solidを確認したが、
切出し後は2solidになり、診断の1solid条件でFAILした。各周期側のfaceは2枚。
切出し後もnative妥当性・自己交差・閉鎖・積分収束は成立する。
このFAILは維持し、後続の標本成功で単一実体へ読み替えない。

製品の `validate_solid` は正のsolid数を許容し、`sector` は固定角度のCommonである。
非凸な連結体を角度で切ると複数実体になり得るため、2solidという事実だけで不正BREPとしない。
逆に、実機用途で単一連結体が必須かは別の受入れ条件であり、合格を宣言しない。

## 実体の内訳（原因の切り分け）

`artifacts/quality-default-sector/eefef81d6336404b8a25a7f63b6a7893/result.json`。
同じ角度Commonを再実行し、私有BREPを保存。元の全周検査は再実行せず、内訳調査だけに
使った（FORENSIC_ONLY）。製品の検査を省略する変更はしていない。

| 実体 | 体積 mm³ | face数 | 周期切断面 |
|---|---:|---:|---|
| 0 | 95,810.669204 | 51 | LOW 1枚、HIGH 2枚 |
| 1 | 27.735754 | 5 | LOW 1枚 |

実体間距離は5.782809 mm。合計体積は最初の診断と同じ95,838.404958 mm³。
小さい実体のLOW面積20.641223401 mm²と、大きい実体のHIGHの一面20.641223399 mm²が対応する。
2つ目を数値片として捨てたり、実体を繋ぐ肉を追加したりしない。

## 別条件での周期面・STEP標本確認

`artifacts/quality-default-sector/8ebded0a009f4b1ab45c482a6496d029/result.json`。
保存した2solidの診断BREPを再読込みし、native妥当性を改めて確認してから検査した。
結果名は `PASS_SAMPLED_MULTIBODY_DIAGNOSTIC`、単一連結条件は `FAIL_TWO_SOLIDS`。

- 全周体積/11との差0.001526 mm³、既存STEP予算式を用いた診断上限1.864353 mm³以内。
  この独立体積比チェックを全面精度の保証にはしない。
- LOW面群をZ軸まわり2π/11回転し、外向き法線を反転してHIGH面群と比較。
  両方向とも全2面・12標本、最大距離約3.553e-15 mm、最大法線角0 deg。
- 私有STEP書出し・再読込みは2solidを維持。mm単位、BREP/自己交差/閉鎖、体積/bbox/edge公差を確認。
  体積差1.7863e-5 mm³、bbox差3.3552e-11 mm。
- 全56面を両方向各437標本で比較。最大距離約5.273e-10 mm、最大法線角約1.479e-6 deg。
  距離上限は従来の0.01 mm。法線の受入れ規則は従来どおり正の内積であり、
  測定角が小さい事実と、一般の厳格な角度保証を区別する。
- 元STEP/request/result、診断BREP、ユーザーJSON、同梱既定JSONのhashは検査前後で不変。
  元STEPは公開済み記録のhashとも一致。出力は私有artifactsだけに保持した。

## 未検証と次の確認

切断後filletのrole半径、trim境界全域、全域法線/距離、設計値からの周期worker全経路、
実機寸法、ANSYS Import/MeshはNOT_TESTED。ディスクはPROVISIONALのまま。
入力の全周Mechanical requestには `Select a blade row for the assigned meridional export domain.`
というdomain_errorがあり、これをTurboGrid成立の証拠にはしない。
次は設計値からの周期worker実経路を独立の私有jobで調べ、2solidの保持とfillet/STEPを確認する。
固定角度で単一実体を必須にする仕様変更や境界位置の変更は、この診断から勝手に実装しない。

今回の差分は文書のみ。製品修正の全回帰2,472件成功は[CAD期限修正](CAD_TIME_BUDGETS.md)を参照。
上記の実CAD診断3実行をpytest件数へ加算しない。最初のFAILと後続の限定成功を両方保持する。
