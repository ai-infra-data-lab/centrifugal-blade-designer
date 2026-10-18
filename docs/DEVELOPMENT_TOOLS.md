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

既にある開発用venvの再作成は不要。アプリ用/CAD用venvへ上書きしない。Ruff 0.17.1、Skill検証用PyYAML 6.0.3を固定した。ruff.tomlはtarget-versionにPython 3.11を指定し、F821/F822/F823（未定義/不正export/束縛前参照）だけを選択し、fix/unsafe-fixesを無効にする。キャッシュ/venv/artifacts/buildを除外する。全体整形や未使用importの自動削除は今回行わない。

既存app/tests/tools/mainの初回指摘は0件。正常入力exit 0、未定義名F821と構文エラーexit 1の実プローブを確認した。構文と限定ルールの成功は型/幾何/工学的な正しさを保証しない。結果はartifacts/devtools/ruff-baseline.json、ruff-probes.json。VS CodeへQuick TestsとRuff Checkのタスクを追加し、既存の実行/回帰/依存確認タスクは維持した。追加2タスクのJSONから同じ実行ファイル/引数を読み出すCLI検証も成功（全回帰並行中にquick約5.0秒、Ruff約0.625秒）。根拠はartifacts/devtools/task-probes.json。VS Codeのタスク選択操作は未確認。

Ruff設定の根拠: https://docs.astral.sh/ruff/configuration/

## 3. プロジェクト専用Codex Skill

`.agents/skills/blade-designer-checks/SKILL.md`を追加した。Codexで`$blade-designer-checks`を明示するか、このアプリの変更/検証で選択されることを想定する。入口を短く保ち、本手順とDEVELOPMENT.mdへ必要時だけ参照する。親の家計簿やユーザー全体のSkill設定は変更しない。

skill-creatorのquick_validate.py成功、参照ファイル解決成功。記載したquick/関連検査/Ruffコマンドはこの環境で実行済み。frontmatter検証は自動選択の精度や新セッションでの表示まで保証しない。Skillが一覧へ出ない場合はプロジェクトを開き直して確認する。形式とproject discoveryの根拠: https://learn.chatgpt.com/docs/build-skills

## 4. RTK OSS（任意の出力圧縮）

Windows x64版RTK OSS 1.0.1を`artifacts/devtools/rtk/rtk.exe`へ配置した。公式releaseのarchive/executable SHA-256を`tools/rtk-release.json`へ固定し、LICENSEも保持する。バイナリやzipはGitへ含めない。

```powershell
# 別PCではこのコマンドで固定版を検証して配置する
.\.venv\Scripts\python.exe tools/install_rtk.py
# このアプリの履歴だけを読取り圧縮（子プロセスは直接argvで実行）
.\.venv\Scripts\python.exe tools/compact_log.py git-log --count 20
# --briefで保存したpytestログの事後圧縮。末尾に元の終了コード/件数/保存先を表示
.\.venv\Scripts\python.exe tools/compact_log.py pytest artifacts/test-runs/<run-id>
```

専用ラッパーが`rtk pipe`へ保存済みの文字列を渡す。RTKへpytest実行・venv選択・終了コード判定を任せない。pytest modeはこのprojectのtest-runs内だけを受け入れ、failed/error/skip/不完全/0件/非0終了をフィルターへ渡さず元ログをそのまま返す。RTKが存在しない、hash不一致、処理失敗の場合もrawへ戻る。元pytestの終了コードと件数を末尾へ明示し、見せ方で成功へ変えない。対象外report/過大countのCLI拒否と、想定外binaryの上書き拒否も隔離プローブで確認した（artifacts/devtools/boundary-probes.json）。Git modeはこのprojectをcwdとして`git log --oneline ... -- .`だけを読み、親家計簿の履歴や書込み操作を対象にしない。

ユーザー全体のPATH、AGENTS、Codex hook、API proxy、アプリ依存は変更しない。RTKの計測/teeの環境変数もproject内へ限定する。`pipe`自体は入力をフィルターへ渡すだけで外部コマンドを実行しない（公式固定版ソースを確認）。アプリ/ユーザーの設計データをRTKへ入力しない。

### 実測と使い分け

- このprojectのGit履歴20件: 元1,202 bytes → 圧縮本文248 bytes（UTF-8）。元/圧縮本文を`artifacts/devtools/git-log.*.txt`へ保持。
- quick pytestログ: 元99 bytes → 圧縮本文26 bytes。ただし件数/終了コード/保存先を付けると304 bytesになり、短い元出力より大きい。
- したがって日常のpytestはまず`--brief`を使い、RTKは長い履歴や必要な保存済みログに限定する。小さいログへ常用しない。これはバイト計測でありCodex全体のトークン/利用枠削減率ではない。
- 実pytestの失敗exit 1、collection error exit 2、skip exit 0で、ラッパーが元ログ全文と終了コードを保持することを確認。RTKのプローブ/測定は`artifacts/devtools/rtk-probes.json`、`output-metrics.json`。初回結合プローブではWindowsのcp932/UTF-8不一致で出力読込みに失敗し、開発CLI自身のstdout/stderrもUTF-8へ揃えた。UTF-8 mode無効の親環境でも日本語pathを読める回帰を追加した。

RTK再配置用helperは既存の想定外binaryを上書きせず、archive/executableの両hashが一致した場合だけ配置する。現PCでの再実行は既存の検証済みbinaryを再利用する。同じWindows PCの隔離した新規ディレクトリでも、helperによるfresh download→2段階hash検証→exe/LICENSE配置を成功確認した（artifacts/devtools/fresh-install-probe.json）。別PC、新セッションでのSkill自動選択、VS Codeタスク操作は未確認。

公式配布/制約: https://github.com/rtk-ai/rtk （固定版v1.0.1）。この環境では自動hookを使わず明示呼出しを採用した。

## 統合検証

ランナー13件とRTK helper/表示保護10件、計23件の関連試験が成功。Ruffの限定チェックも成功。**全1,184一意件成功**（通常1,144・実CAD40）。既存1,161 IDを維持し、新規23 IDを追加した。failure/error/skip/実行漏れ/重複/想定外IDは0。固定273入力（app/tests/tools Python、既定/原本JSON、Ruff/Skill/タスク/固定RTK設定等）は回帰開始から不変。原本と同梱既定JSONも一致した。既存試験の期待値は変更していない。今回変更したのは開発補助のみで、GUI・幾何・既定値・保存/出力アルゴリズムは変更しない。native GUI/ANSYSの再確認は今回の導入検証には含めない。


根拠: `artifacts/quality-devtools/final-test-coverage.json`、`source-hashes.json`、`collected-tests.txt`。通常6群/CAD1群のJUnitを収集IDと照合した。

| 群 | 件数 | 時間 [秒] | 実行ID |
|---|---:|---:|---|
| 通常0 | 116 | 306.808 | 20261018T062936Z-8ce89e0b |
| 通常1 | 143 | 270.635 | 20261018T062936Z-efd7b99c |
| 通常2 | 122 | 318.697 | 20261018T062936Z-686c6ca0 |
| 通常3 | 191 | 224.017 | 20261018T062936Z-30a7b8da |
| 通常4 | 146 | 293.105 | 20261018T062936Z-a8c215fb |
| 通常5 | 426 | 385.937 | 20261018T062936Z-6f20619b |
| 実CAD | 40 | 736.176 | 20261018T062936Z-62615f25 |
