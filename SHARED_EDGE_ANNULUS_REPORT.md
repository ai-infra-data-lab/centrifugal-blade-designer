# 共通LE/TE・対象別Full Annulus 実装報告

日付: 2026-10-05。

## 結果

- ImpellerのLE/TE形状タイプ（Circular / Elliptical / Cutoff）と楕円比をHub/Tip・中間Spanで共通編集。
- DiffuserのLE/TE形状は独立。Hub/Tipの角度・厚さは引き続き別々に同じグラフから編集。
- Diffuser CurvatureタブはImpeller選択時に非表示。Diffuser選択時に再表示し、現在のDiffuser設定から更新。
- Full AnnulusはToolbarのImpeller/Diffuserへ追従。Impellerでは選択したHub/Tip/中間SpanとXY/XZ/YZ投影へ追従し、指定した翼枚数を表示。
- 全周配置は実際のXYZ座標をZ軸まわりに回転してから投影。XZ/YZのZ座標を周方向座標として誤回転しません。
- 更新時のZoom/Panと3D Camera保持を維持。自動Fitは既存の起動・New・Open・Fit Viewだけ。

## コピー操作

`Copy Hub → Tip`: Hubの角度と厚さのControl PointをTipへコピーし、Tipの既存値を上書きします。

`Copy Tip → Hub`: Tipの角度と厚さをHubへコピーし、Hubの既存値を上書きします。

コピー後も各断面は独立した分布です。コピー元は変更しません。LE/TE形状・壁面・翼端位置はコピーしません。Undo/Redo対応。ボタン名とツールチップへ対象と上書き内容を明記しました。

## 既存Project

旧JSONでHub/TipのLE/TE形状が異なる場合、GUIで読み込む時にHub側の形状を全Impeller断面の共通設定として採用します。読込だけで元ファイルを書き換えません。保存したProjectには全断面へ同じ設定を記録します。ロード直後の表示にも共通設定から生成した形状を使用します。

角度・厚さ・独立したHub/Tip翼端位置、Diffuser設定を保持。既存schemaと幾何計算APIは維持し、共通化はGUIの設計・保存・Exportに使用するProject Parametersへ反映しています。CSV/TurboGridのファイル形式は変更していません。

## ファイル

変更:

- `blade_designer/geometry/annulus.py`: Qtに依存しないXYZ回転・投影関数。
- `blade_designer/gui/plot_widgets.py`: Impeller全周表示、対象・断面・投影名と軸表示、Diffuser表示への復帰。
- `blade_designer/gui/main_window.py`: 共通LE/TE設定、旧Project読込の統一、Curvature表示切替、対象別Annulus、コピー対象の整理。
- `blade_designer/gui/section_selector.py`: 選択対象とコピー操作の説明。
- `README.md`: 現在のGUI動作、コピーの意味と手動確認項目。

新規:

- `tests/test_shared_edges_annulus_gui.py`: 共通LE/TE、旧Project・保存読込、Diffuser独立、Curvature表示、Hub/Tip×XY/XZ/YZ、全周回転とZoom保持、両方向コピーとUndo。
- `tools/shared_edges_annulus_smoke.py`: 対象別の画面生成・JSON往復・既存ファイル保持を検証。
- 本報告。画像・結果は `artifacts/shared-edges-annulus/`。

変更前ソース: `artifacts/before-shared-edges-annulus.zip`。既存の `blade.json` / `blade.csv` はSHA-256不変を確認。

## 検証

- 変更前全体: `pytest -q` → **266 passed in 270.21s**。
- 変更後既存GUI関連: **22 passed in 37.05s**。
- 新規GUI＋既存Annulus: **12 passed in 20.13s**。
- 最終全体: `pytest -q -W error` → **277 passed in 167.68s (0:02:47)、0 failure / 0 warning、exit 0**。
- `python tools/shared_edges_annulus_smoke.py`: PASS。共通LE/TE、Diffuser独立、対象別Curvature・Annulus、保存読込、既存JSON/CSV保持。
- Qt offscreen生成画像5枚を目視確認: Impeller共通LE/TE、Hub全周XY、Tip全周XZ、Diffuser全周XY、Diffuser Curvature。

実デスクトップでの人による手動操作とTurboGrid実機Importは今回未実施。GUI検証はQt offscreenでの自動操作と画面画像の目視確認です。Full Annulusは選択した断面のワイヤー表示です。
