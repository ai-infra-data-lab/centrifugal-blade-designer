# 継続開発手順

## 1. 推奨環境と対象

Windows 11 + VS Code + 既存Windows .venv + Gitを主環境にします。現在のWindows GUI・ファイル操作を維持し、Linux固有の道具が必要な時だけWSLを別環境として検証します。
OpenAIもWindowsのnative sandboxを基本にし、Linuxの道具が必要な場合等にWSLを選ぶ方針です。[公式資料](https://learn.chatgpt.com/docs/windows/windows-sandbox)

親フォルダC:/Codex/pythonのGUI作成は家計簿とこのアプリを含む既存Gitリポジトリです。入れ子のgit init、フォルダ移動、Git履歴の作り直しは行いません。

## 2. VS Codeで開く

1. VS Codeの「ファイル → ワークスペースをファイルから開く」で、このアプリのblade-designer.code-workspaceを選択。
2. 拡張はPython（ms-python.python）、Python Debugger（ms-python.debugpy）、Codex（openai.chatgpt）。.vscode/extensions.jsonに推奨を記載。
3. Ctrl+Shift+P → Python: Select Interpreter → このアプリの.venv/Scripts/python.exeを選択。既に別のPythonを選択していたVS CodeはdefaultInterpreterPathを自動適用しないことがあるため、表示を確認。
4. Codex拡張を開き、本人がサインイン。認証情報はファイルへ保存しない。[公式IDE手順](https://learn.chatgpt.com/docs/codex/ide)
5. 親フォルダ全体ではなく、このワークスペースを開くことで、このアプリの設定・テストだけを使う。ソース管理は親リポジトリを表示するため、家計簿側の変更も一覧に現れ得る。

## 3. 実行・デバッグ

- Ctrl+Shift+P → Tasks: Run Task → Blade Designer: Run。
- F5 → Blade Designer: Design。別の起動モードはBlade Designer: Optimization。
- 停止位置の例: main.pyのwindow = MainWindow(...)、gui/main_window.pyのupdate_geometry、geometry/designer.pyの生成処理へブレークポイントを置く。
- F10: step over、F11: step into、F5: continue。Variables/Watchで入力と配列を確認。
- debugpyの設定・起動ファイルは検証対象ですが、VS Code内でF5とブレークポイント停止を人が確認する作業は別途必要です。
- GUI起動にQT_QPA_PLATFORM=offscreenを設定しない。これは自動GUIテスト用。

## 4. 自動テスト

PowerShell、アプリ直下:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe tools/run_tests.py
# 変更に関係するテストだけ
.\.venv\Scripts\python.exe tools/run_tests.py tests/test_camber.py tests/test_csv_export.py
```

tools/run_tests.pyは実行中Pythonを使い、元のテストを変更せずpytestを起動します。warningsをエラーとして扱います。実行ごとにartifacts/test-runsへJUnit XML・command/exit codeを記録し、一時領域を作ります。
過去のキャッシュとシステムTEMPのアクセス問題を避けるためcacheproviderを無効にします。アプリの判定・テストの期待値は変更しません。

VS Code左側のTestingでRefresh Tests → Run Tests。設定はpytest/既存tests/・同じwarnings条件です。.vscode/python.envでpytestの一時領域をworkspaceに限定します。QT offscreenは既存GUIテストが設定します。
VS CodeのTest Explorer内でのクリック実行は手動確認対象です。CLIのpytest実行と区別してください。

### 数値の基準

- 数学的比較: 定数βmの積分解、Line端点、Arc長・接線、G1、軸流環状面積π(Rs²−Rh²)、XYZ円筒座標一致等。対応する条件での正しさを検証。
- 旧実装の回帰: tests/fixtures/old_v03_profiles.npz等。過去の座標を保つ検証で、実機・CFD・全ての入力に対する物理的正しさの認証ではありません。
- GUI検証: Qt offscreenの生成・入力・drag・Undo等。実ディスプレイ、DPI、nativeテーマ、ダイアログの確認とは別。

## 5. Gitで確認して記録

初回コミットは`16ebf3707ca22d8ab4e8283c8eda0c41809584ae`で、このアプリの156ファイルだけを記録しました。親リポジトリには家計簿の未追跡ファイルもあるため、対象ファイルを明示して記録します。
v0.3.0最終版の保存先は、アプリ専用の非公開リポジトリ `https://github.com/ai-infra-data-lab/centrifugal-blade-designer` です。GitHubではアプリのファイルをリポジトリ直下に置きます。既存ローカルcheckoutと親のGit履歴は維持し、`git subtree split --prefix=centrifugal_blade_designer`でアプリ部分の履歴だけを書き出します。親リポジトリ全体をこの保存先へpushしないでください。

親フォルダから:

```powershell
git status --short
git status --short -- centrifugal_blade_designer
git ls-files --others --exclude-standard -- centrifugal_blade_designer
# 初回は未追跡ファイルなのでgit diffだけでは内容が出ない。VS Codeで各ファイルを開く。
# Stage/Commit/Pushは対象を確認し、ユーザーの許可を得て実行。
# 実際の変更一覧に合わせ、各ファイル名を明示する。一括追加しない。
git add -- centrifugal_blade_designer/main.py centrifugal_blade_designer/README.md
git diff --cached --stat
git diff --cached --check
git diff --cached -- centrifugal_blade_designer
git commit -m "fix: describe the verified blade designer change"
# 最初のコミット後、1機能1ブランチ:
git switch -c feature/short-description
```

.gitignoreは.venv・cache・artifacts・一時ファイル・blade.json/csv・ユーザー原本blade_v03.jsonを除外し、test fixturesとIDE設定、アプリ内defaults/default_project.jsonを含めます。
一括git add .で親フォルダの家計簿を混ぜない。Staged Changesを確認してからコミット。Gitの署名・user.name/emailは本人の設定を使い、こちらで推測しない。
以後は1機能/修正ごとに独立して記録します。自動テストと実画面の手動チェックは区別し、未確認の操作を検証済みとして記録しないでください。

既存親checkoutのremote設定は変更せず、アプリ部分の書き出しコミットを専用リポジトリURLへ明示してpushします。アップロード対象のコミットとタグを確認し、private設定を維持します。将来、専用リポジトリを別の場所へcloneする場合も、既存checkout・ユーザーデータを移動・削除しないでください。

## 6. Codexへの依頼例

> FEATURES.mdと関連コードを確認し、〇〇だけを修正してください。既存GUI、計算、Project/CSV/TurboGrid互換性を維持し、差分を最小にしてください。関連テストと必要な回帰テストを実行し、変更ファイル、結果、未実施項目を報告してください。Gitへはまだ記録しないでください。

手順: 現状確認 → 1機能の範囲指定 → 調査 → 小さな変更 → 対応テスト → 関連回帰 → 手動確認 → FEATURES更新 → 差分確認 → Git記録。
AGENTS.mdはこのプロジェクトのルールです。仕様・手順の詳細は本書と既存仕様を参照します。

## 7. 新しいWindows環境で再現

既存.venvを削除・上書きせず、初めて導入するPC/checkoutで実行:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows-py312.lock.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe tools/run_tests.py
.\.venv\Scripts\python.exe main.py
```

3.12が未導入なら先にPythonを導入。実際に使用されたPythonはsys.executableで確認します。仮想環境のActivate.ps1を使わずexeを指定できるので、PowerShellの実行ポリシーを変更する必要はありません。
固定依存は今回稼働中の環境記録です。新規インストールの成功は未検証。既存requirements.txtで互換環境を作る場合もpip check・回帰・手動起動を行ってから採用します。

## 8. WSL2 / Ubuntu 24.04（提案・未実行）

Linux GUIはWindows 11のWSL2 + WSLgで使えます。[Microsoft公式](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps)
現在のPCは導入状態の確認結果を環境報告に記載。インストール・Windows機能/BIOS設定・再起動は今回実施していません。

必要になった場合、ユーザーが管理者PowerShellで導入を検討:

```powershell
wsl --install -d Ubuntu-24.04
wsl --list --verbose
```

Linux側の別checkout（~/src等）で作業し、Windows .venvをコピー・共用しない。Gitの履歴ができるまでは親リポジトリ全体の移動/cloneを安易に行わない。次はLinux checkoutでの手順例:

```bash
sudo apt update
sudo apt install python3-venv python3-pip git libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python tools/run_tests.py
.venv/bin/python main.py
```

追加のQtシステムライブラリはエラーとQt plugin diagnosticsを確認して必要分だけ導入。WSL向けVS Code拡張とPython/CodexはLinux側でも有効化する。実際のLinux GUI・配布物の検証は別作業です。

## 9. Windows手動チェック（今回未実施）

1. 上記workspaceで正しいPythonを選び、F5でウィンドウが表示される。
2. ブレークポイントで停止・Variables確認・続行できる。
3. Impeller/Diffuserを切替。Hub/Tip角度・厚さの両方を編集。
4. 共通LE/TE、Meridional、XY/XZ/YZ、Full Annulus、Diffuser Curvatureの対象別表示。
5. Zoom/Panと3D cameraを変更してから形状を編集し、Viewが保持される。
6. コピーとUndo/Redo、別モードの最適化候補検証を操作。
7. 一時的な別名Projectへ保存・読込し、専用一時ディレクトリへCSV/TurboGridを書き出す。既存blade.json/csvは上書きしない。
8. Testing画面からテストを実行し、Source Controlでこのアプリの差分だけを確認。
9. Codex拡張で本人が認証し、このフォルダの説明を依頼する。コード変更は別依頼とする。
10. TurboGridを利用できる場合は4ファイルのImport・方向・形状エラーを確認。
