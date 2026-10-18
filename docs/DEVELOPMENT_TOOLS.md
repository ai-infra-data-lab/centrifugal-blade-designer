# 開発検査と簡潔な結果報告

既存のアプリ用`.venv`・pytest・Git・CAD環境を維持し、開発補助だけを段階追加する。形状計算・既定JSON・保存/出力形式・既存の数値期待値は変更しない。

## 1. 短時間検査とpytest要約

```powershell
# 基礎数値の短時間検査（全回帰の代用ではない）
.\.venv\Scripts\python.exe tools/run_tests.py --suite quick --brief
# 関連試験は任意のpytest引数を指定
.\.venv\Scripts\python.exe tools/run_tests.py --brief tests/test_surface_diagnostics.py
# 全回帰。従来の引数なし呼出しも同じ対象
.\.venv\Scripts\python.exe tools/run_tests.py --suite full --brief
```

quickはcamber・分布・子午面Line/Arc・曲面評価/微分の6ファイル。2026-10-18に63件成功。GUI/CAD・保存・全出力は含まれず、編集対象に応じた関連検査と、AGENTS.mdが要求する全回帰を追加する。`--suite`と追加pytest引数の併用は拒否し、対象の黙った縮小を防ぐ。

`--brief`時は完全なstdout/stderrを`artifacts/test-runs/<run>/pytest.log`へ保存し、passed/failed/errors/skipped・終了コード・問題ID（最大10件）・ログ/JUnit保存先を表示する。`result.json`の既存項目は維持し、summary、runner_returncode等を追加する。通常モードのpytestコンソール出力も維持する。

プロジェクト内TEMP、UTF-8、warnings=error、pytest cache無効、実行中Pythonを使う設定は従来通り。collection errorを試験失敗と区別し、skipを成功件数へ含めない。収集だけの実行はCOLLECTION ONLYと明示。正常終了なのにJUnitが読めない場合はrunner終了2とし、検証済みにしない。元pytestの非0終了コードは維持する。要約に失敗詳細がない場合は保存したraw logを読む。テスト実行中は簡潔モードに途中出力がないため、長時間処理ではprocess状態と保存ログを確認する。

## 導入順と範囲

1. ランナーの短時間対象/要約を検証してcommit。
2. Ruffを開発用独立環境へ固定導入し、少数の重大ルールで既存指摘を調査。自動修正/一括整形を行わない。
3. このアプリ専用Skillをproject内へ追加し、AGENTSと本手順への参照を短く保つ。
4. RTKをローカルに配置し、PowerShellで明示的に試す。終了コード/詳細の保護を実測し、用途を限定する。全体hookやAPI proxyは導入しない。

Hypothesis/uvは今回の4段階へ自動追加しない。後続の数値境界試験/別環境再現として個別に検証する。
`--brief`の実subprocess検証12件成功（通常出力互換、失敗、collection error、skip、warnings、収集のみ、0件、対象誤指定）。短時間63件成功・全件収集成功も確認した。アプリの幾何/GUI/保存コードは変更していない。

## 2. Ruff（独立した開発用環境）

```powershell
.\.venv\Scripts\python.exe -m venv artifacts/devtools/venv
.\artifacts\devtools\venv\Scripts\python.exe -m pip install -r requirements-dev-tools.txt
.\artifacts\devtools\venv\Scripts\python.exe -m ruff check --config ruff.toml --no-cache blade_designer tests tools main.py
```

既にある開発用venvの再作成は不要。アプリ用/CAD用venvへ上書きしない。Ruff 0.17.1、Skill検証用PyYAML 6.0.3を固定した。ruff.tomlはPython 3.11互換構文、F821/F822/F823（未定義/不正export/束縛前参照）だけを選択し、fix/unsafe-fixesを無効にする。キャッシュ/venv/artifacts/buildを除外する。全体整形や未使用importの自動削除は今回行わない。

既存app/tests/tools/mainの初回指摘は0件。正常入力exit 0、未定義名F821と構文エラーexit 1の実プローブを確認した。構文と限定ルールの成功は型/幾何/工学的な正しさを保証しない。結果はartifacts/devtools/ruff-baseline.json、ruff-probes.json。VS CodeへQuick TestsとRuff Checkのタスクを追加し、既存の実行/回帰/依存確認タスクは維持した。CLIからの実行は検証済み、VS Codeのタスク選択操作は未確認。

Ruff設定の根拠: https://docs.astral.sh/ruff/configuration/
