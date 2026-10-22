# 同一CADオブジェクトの検査結果再利用

CAD生成・STEP出力では、同じ完成形状のBREP/自己交差/体積検査を複数回呼び出す。
`OcctBackend.validate_solid`に、バックエンドinstance内だけの上限8件の再利用を追加する。
生成形状・公差・検査内容・出力形式は変更しない。

## 成立条件

- 同じ`CadShape`オブジェクトであることをweak referenceで確認する。
- OCCT `BinTools.Write_s`によるバイナリBREP全体のSHA-256が一致すること。
  メモリ上で生成し、検査結果と指紋だけを保持する。BREP本体や形状の強参照は保持しない。
- 実検査の前後でもバイナリBREPが一致すること。検査中に表現が変わった場合は保持しない。
- 保存するのは成功した実検査だけ。失敗は次の呼出しでも実検査する。
- 指紋作成やweak referenceが使えない場合は実検査する。検査を省略して成功にはしない。
- 結果はdeep copyで返す。呼出し側の辞書/list変更を別の検査結果へ伝播させない。

STEP再読込みや新しい`CadShape`には、同じ形状を持つ場合でも実検査する。
公差、向き、位置、曲線・曲面、topology、meshを含むバイナリBREPの変更で再検査する。
1ULPの寸法変更も独立に検査する。ポインタ一致やbounding box/体積一致だけを根拠にしない。
外部ファイル・別process・別バックエンドinstanceから成功結果を取り込む機能はない。
同じshapeを別threadで同時変更する使い方は対象外で、CAD workerの逐次処理契約を維持する。

## 再利用しない検査

roleの完全性、root cap内包、翼間・root group間距離、指定fillet半径、
基準形状との偏差、STEP前後の比較と出力公開可否は、このcacheの対象外。
既存の呼出し箇所と拒否条件を維持する。再利用されたBREP検査だけでANSYS連携や
全面精度の成功を判定しない。

## 検証

`tests/cad/test_solid_validation_cache.py`は実カーネルで、同一objectの再利用、
別objectの実検査、結果の独立性、公差/向き/1ULP変更、失敗の非保持、
上限とweak reference、指紋失敗時の実検査、検査中の変更、weak reference非対応を検査する。
既存のSTEP・既定小R・全周/周期の回帰も実行する。

同時実行するCAD診断と全回帰はソース版を分けて記録する。実測せずに速度改善率を報告しない。

最終全回帰は2,267一意ID成功（通常2,206・実CAD61、既存2,261保持、新規6）。
失敗/error/skip/漏れ/重複/未期待IDは0、固定361入力は不変。
関連24件、短縮63件、変更PythonのRuff、Git差分検査も成功した。
根拠は`artifacts/quality-solid-validation-cache/final-test-coverage.json`と各JUnit/raw log。
通常2群と数値ライブラリ1 threadを使用し、実CAD群は独立した全周STEP診断終了後に開始した。
この資源配分はアプリ設定や依存バージョンを変更するものではない。
