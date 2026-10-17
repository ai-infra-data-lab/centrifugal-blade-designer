# Aboutメニュー

画面内の大きなアプリ名と、その下のバージョン・角度定義の行を取り除きました。設計エリアをメニューバー直下から使えます。

メニューバーの`About → About Blade Designer`で、アプリ名、Impeller / Vaned Diffuser v0.3、βm=0°の定義、Normalized Meridional、現在のDesign／Optimizationモードを表示します。OSのウィンドウタイトルは維持します。Aboutの表示で設計値・履歴を変更しません。

変更は`gui/main_window.py`、既存メニュー順序の期待値は`tests/test_standard_menus_gui.py`です。`tests/test_about_gui.py`の2件で両モードの情報・画面内ヘッダーの除去・設計とUndo履歴の不変を検査します。

関連9件成功、12.33秒（`20261017T011517Z-bcc5a823`）。補間変更を含む最終関連67件も成功（99.87秒、`20261017T012147Z-065d842d`）。最終全回帰713件が成功し、収集IDとJUnitの照合で実行漏れ・失敗・error・skipは0件でした。分割結果・変更範囲は[SPLITTER_INTERPOLATION.md](SPLITTER_INTERPOLATION.md)へ記録しています。

Qt offscreenで実MainWindowとAboutダイアログを画像化し、画面内の大きな見出しがなく、Aboutに元の説明が表示されることを確認しました。`artifacts/about-interpolation-review/thickness.png`、`angle.png`、`about.png`と`smoke.json`へ記録。画像取得プロセスだけMeiryoを読み込み、製品のフォント設定は変更していません。

実画面／F5／DPIは未確認。stage・commit・pushは行いません。
