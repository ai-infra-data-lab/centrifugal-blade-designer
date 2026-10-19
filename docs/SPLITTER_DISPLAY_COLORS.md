# スプリッター形状表示の配色

2D・3Dのスプリッターを、主翼と同じ部位別配色で表示します。

|部位|色|表示色コード|
|---|---|---|
|LE|黄|`#e5c76b`|
|PS|水色|`#56d9e0`|
|TE|橙|`#eead72`|
|SS|ピンク|`#f6948c`|

2Dでは主翼は従来の実線、Splitterは破線です。凡例の`Splitter LE/PS/TE/SS`にも同じ色・線種を表示します。単翼・全周、XY/XZ/YZ投影に適用します。

3Dでは、選択翼列・全翼列・全周表示で同じ色を維持します。Camberは灰色、Spanwise補助線は落ち着いた青とし、従来のSplitter全体を緑色にする上書きを取り除きました。カメラ、表示操作、座標配列、形状生成・JSON・出力処理は変更しません。

変更は`gui/plot_widgets.py`と`gui/preview_3d.py`です。`tests/test_splitter_colors.py`の新規16件は、実際の描画ペン・凡例、投影後の座標、Splitterの表示解除と再表示、3Dの部位色・周期展開・全翼列表示、カメラと形状の保持をQt offscreenで確認します。

## 検証

- Quick 63件成功。
- 新規16件を含む関連30件成功（`20261019T032206Z-0b675161`）。
- 変更したPython 3ファイルのRuff検査成功。
- Qt offscreenの2D/3D画像を確認。`artifacts/quality-splitter-colors/2d.png`と`3d.png`に保存。
- 全回帰1,609一意件成功（通常1,564件・実CAD45件）。既存1,593件と新規16件を全収集ID/JUnitで照合し、失敗・error・skip・実行漏れ・重複は0。固定309入力（Python・参照fixture・既定JSON・ユーザー原本等）の変更も0。7区分で実行し、最長区分は869.30秒。記録は`artifacts/quality-splitter-colors/final-test-coverage.json`、各区分のログとJUnitは同フォルダの対応記録を参照。

最初の関連試行は24成功・6失敗でした。全周Plotの既存ペン指定は文字列のため、新規テスト側で`pg.mkPen`を通して読み取るように修正しました。製品コード・期待する色・座標を失敗に合わせて変更したものではありません。環境エラーはありません。

実ディスプレイでの視認性・DPI・F5操作は未確認です。
