# 継続開発環境の整備結果

確認日: 2026-10-08。対象: `centrifugal_blade_designer`。同じ親フォルダの家計簿アプリは対象外です。今回、GUI構造・数値計算・入出力仕様を変更していません。

## 現在の構成

- 起動: `main.py`。通常のdesignと、既存のoptimizationモードがあります。
- パッケージ: `blade_designer/`の65 Pythonモジュール。GUI、geometry、fileio、models等を分離した既存構成です。
- GUI: PySide6 Qt Widgets。2D描画はPyQtGraph、3DはQPainterによるワイヤーフレームです。フレームワークは変更していません。
- 既存テスト: 54テストファイル、277テスト。解析解との比較と、過去の実装結果を保持する回帰fixtureを区別して扱います。
- 確認した環境: Windows 11 build 26300、プロジェクト仮想環境Python 3.12.14、NumPy 2.5.3、SciPy 1.18.1、PySide6 6.11.2、PyQtGraph 0.14.0、pytest 9.1.1。
- 詳細な依存関係・入出力・モジュール構成: [ARCHITECTURE.md](docs/ARCHITECTURE.md)。全機能と検証状態: [FEATURES.md](FEATURES.md)。

## 推奨環境

Windows上のVS Codeと既存の`.venv`を主環境にします。現在のGUIとファイル操作を直接検証できるためです。CodexのWindows対応も[公式資料](https://learn.chatgpt.com/docs/windows/windows-sandbox)で確認しました。

WSLの読み取り確認では、ディストリビューションは未インストールで、現在のマシン構成はWSL1/WSL2に対応していないとの診断でした。WSL2にはWindowsのVirtual Machine PlatformとBIOS仮想化の確認が必要です。Windows機能変更、Ubuntu導入、再起動は実施していません。Linux向けの別仮想環境と検証手順は[DEVELOPMENT.md](docs/DEVELOPMENT.md)に記載しました。Linux実行は未確認です。

## 作成・変更したファイル

既存ファイルの変更:

- `README.md`: 開発環境、実行・テスト、詳細資料への案内を追加。既存アプリの説明は維持。
- `.gitignore`: 仮想環境、キャッシュ、テスト成果物、一時ファイル、ローカル出力と秘密設定を除外。既存fixtureは除外していません。

新規ファイル:

- `AGENTS.md`: Codex用の最小変更・既存機能維持・検証・差分確認ルール。
- `FEATURES.md`: 実装確認と自動・手動の動作確認を分けた機能一覧。
- `blade-designer.code-workspace`: 対象アプリのみを開くワークスペース。
- `.vscode/settings.json`: 仮想環境、pytest、親Gitリポジトリの検出設定。
- `.vscode/launch.json`: 通常・最適化モードのdebugpy起動設定。
- `.vscode/tasks.json`: 起動、回帰テスト、依存整合性確認。
- `.vscode/extensions.json`: Python、Python Debugger、Codexの推奨拡張。
- `.vscode/python.env`: UTF-8とテスト用一時ディレクトリ設定。GUIの通常起動をoffscreenにはしません。
- `tools/run_tests.py`: 書き込み可能な実行別一時ディレクトリで既存pytestを呼び、XMLと終了結果を保存。
- `requirements-windows-py312.lock.txt`: 今回確認したWindows/Python環境の依存バージョン記録。クリーン環境への再インストールとLinux利用は未検証。
- `docs/ARCHITECTURE.md`: 構造・依存関係・入出力・検証境界。
- `docs/DEVELOPMENT.md`: VS Code、Git、Codex、再現手順、WSL、手動チェック。
- `DEVELOPMENT_SETUP_REPORT.md`: 本報告。

検証ログ・画面画像・変更レビュー用差分はGit対象外の`artifacts/`に保存しています。既存アプリ本体、既存テスト・fixture、既存設定、ユーザーJSON/CSVなど129ファイルのSHA-256を前後比較し、変更なしを確認しました。

## VS Codeからの起動・デバッグ

1. `blade-designer.code-workspace`を開きます。今回、VS Code CLIから新しいウィンドウで開く処理は終了コード0でした。
2. `Python: Select Interpreter`で、このアプリの`.venv/Scripts/python.exe`を選びます。
3. F5で`Blade Designer: Design`を選びます。既存の最適化画面は`Blade Designer: Optimization`です。
4. `main.py`等にブレークポイントを設定し、F5で開始、F10/F11でステップ実行します。
5. テストはTestingパネル、またはタスク`Regression Tests`を使用します。

VS Code 1.138.0とPython/Debugger拡張を確認しました。公式Codex拡張`openai.chatgpt` 26.1002.51308をインストール済みです。自動依存の`openai.codex-audio`も導入されました。本人によるCodexサインイン、F5の実操作、ブレークポイント停止、Testingパネル操作は未確認です。

## 自動確認結果

| 確認 | 結果 |
|---|---|
| 最初の既存pytest実行 | 一時ディレクトリ作成権限による47 setup errors、数値比較等のfailureは0。既存キャッシュへのアクセス警告も終了時に発生 |
| 新しい実行手順で入出力関連テスト | 8 passed、1.49秒 |
| 新しい実行手順で全既存テスト | **277 passed、163.49秒、failure/error/skip/warningは0** |
| テスト収集 | 277 tests collected |
| `pip check` | No broken requirements found |
| 通常・最適化GUI画面生成 | 両方PASS。Qt offscreenによる自動確認 |
| VS Code設定・ワークスペースJSON | 構文と起動対象を確認 |
| Git除外設定 | 仮想環境・成果物を除外、fixtureと開発設定を保護 |
| 既存129ファイル | 全て変更なし |

最初の環境エラーを避けるため、テスト実行時の一時領域をプロジェクト配下に置き、pytestのキャッシュ機能を無効にしました。既存テストの期待値やアプリコードを変更して通したものではありません。再実行:

```powershell
.\.venv\Scripts\python.exe tools/run_tests.py
```

成功した全テストの記録: `artifacts/test-runs/20261008T120403Z-b0f5f5fc/pytest.xml`。GUIスモークの記録: `artifacts/development-environment/gui-smoke.json`。

## Gitの状態と変更レビュー

親フォルダには既存Gitリポジトリがあります。現在はmaster、コミット0、追跡ファイル0、リモート0です。未追跡ファイルと他アプリのデータを維持しました。Git初期化のやり直し、追加のリポジトリ、stage、commit、remote変更、pushは実施していません。

現状は追跡ファイルがないため通常の`git diff`だけでは未追跡ファイルの内容を確認できません。既存README/ignoreのレビュー用差分を`artifacts/development-environment/existing-file-changes.diff`に保存しました。手動確認後、対象ファイルだけをstageし、`git diff --cached`で確認してから最初のコミットを作成する手順をDEVELOPMENT.mdに記載しています。親リポジトリ全体のStage Allは、別アプリを含むため避けてください。

## 手動確認が必要な内容

- Windows実画面での起動、主要操作、Zoom/Pan/3Dカメラ保持、通常・最適化モード。
- VS CodeのF5、ブレークポイント停止、Test Explorer。
- Codex本人サインインと、変更差分を確認する操作。
- 保存・再読込と既存入力ファイルの代表例を使った操作確認。
- TurboGridへの実機インポート。今回、TurboGrid起動・読込は実施していません。
- クリーンな仮想環境への再インストールとLinux/WSL実行。

手動チェックリストはDEVELOPMENT.mdにあります。自動テスト成功を、実画面操作やTurboGrid互換性の全面確認とは扱っていません。

## 今後の機能追加手順

手動確認と差分レビュー後に、対象アプリの初期状態をGitへ記録します。その後は1機能または1修正を1作業単位にし、要求・対象外・維持する挙動を明示してCodexへ依頼します。既存コード調査、必要最小限の変更、関連テストと全回帰、FEATURES更新、差分レビュー、コミットの順で進めてください。GitHub公開・push・リモート設定は別途承認後に行います。
