<div align="center">

# 🪶 Neverbor

**A Claude Code plugin that saves context and usage limits.**

It shrinks noisy tool output *before* the model reads it, remembers your progress across `/compact`, and stops Claude from going in circles.

![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-D97757)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

**up to −96% characters** on long outputs · no proxy · no API keys · originals always kept

[Русская версия](README.ru.md)

<img src="assets/demo.gif" alt="pytest output with 314 tests: 18,870 characters without Neverbor, 1,246 with it (−93%)" width="720">

</div>

---

## ✨ Features

- 🗜 **Compresses Bash and MCP output.** Strips colors, progress bars and repeats; shortens long JSON and huge logs.
- 🔁 **Nothing is lost.** The full original is saved to disk, and Claude can read it whenever it needs to.
- ✂️ **Shorter answers.** At session start Claude gets a few rules: no preambles, no recaps, no needless re-reading.
- 🛡 **Safety first.** Exact output (`cat`, `git diff`, `Read`, `Edit`…) is never touched. If the hook fails, the session goes on as usual.
- 🧠 **Knows common outputs.** A package install becomes one line instead of hundreds. Library frames are folded in stack traces. Long file lists are grouped by folder.
- ♻️ **Repeats.** The same command with the same output in one session is replaced by a pointer to the earlier run.
- 🎚 **Modes and config.** `light`, `normal`, `aggressive`, plus a settings file for fine-tuning.
- 📒 **Work log.** After `/compact` Claude still knows which files it changed and how the last commands ended, so it doesn't re-read everything.
- 🔄 **No going in circles.** The same error three times in a row, and Claude is told to change its approach.
- 🗺 **Project map.** Folders, languages and build commands in one short note instead of a long exploration.
- 📖 **No needless re-reads** *(opt-in)*. Re-reading an unchanged file returns a pointer to the copy Claude already has.
- 📊 **Stats.** `/neverbor stats today` shows the day's savings and top commands, and a short note after each answer says how many tokens were saved. There's also a chart page, tuning advice and a status line.

## 📉 Numbers

| Command | Before | After | Saved |
|---|---:|---:|---:|
| `ls -laR` over a repo | 74 702 | 6 981 | **−91%** |
| `find` in a folder (2 900 files) | 303 371 | 18 328 | **−94%** |
| `grep -rn 'def '` | 242 930 | 37 566 | **−85%** |
| JSON with 150 issues | 24 683 | 1 192 | **−96%** |
| `pip install`, 60 packages | 15 088 | 1 143 | **−92%** |
| `pytest -v`, 314 tests, 2 failing | 18 870 | 1 246 | **−93%** |
| stack trace through flask/sqlalchemy | 10 392 | 1 236 | **−88%** |
| `git diff` *(with `compress_diff`)* | 8 372 | 984 | **−88%** |
| `cat Cargo.lock` | 139 846 | 139 846 | 0% *(on purpose)* |

<sub>Sizes in characters; tokens are roughly 4× fewer. Reproduce with `python3 scripts/bench.py`.</sub>

## 🚀 Install

Inside Claude Code:

```
/plugin marketplace add koigkio/Neverbor-Demo-plugin
/plugin install neverbor@neverbor
```

Or from a terminal:

```bash
claude plugin marketplace add koigkio/Neverbor-Demo-plugin && claude plugin install neverbor@neverbor
```

Restart the session after installing.

**Requires** Python 3.8 or newer. Neverbor finds it as `python3`, `python` or `py`.

| System | What to do |
|---|---|
| macOS | usually nothing. If Python is missing, macOS offers to install the Command Line Tools on first run — accept |
| Linux | usually nothing: Python 3 is almost everywhere. Otherwise `sudo apt install python3` or similar |
| Windows | install Python from [python.org](https://www.python.org/downloads/) or the Microsoft Store |

Without Python the plugin simply does nothing and Claude Code works as usual.

## 🎛 Commands

| Command | What it does |
|---|---|
| `/neverbor` or `/neverbor stats` | all-time savings |
| `/neverbor stats today` · `week` | today or this week, with top commands |
| `/neverbor on` · `/neverbor off` | turn compression on or off |
| `/neverbor brief` | the work log Claude gets after `/compact` |
| `/neverbor map` · `map on` · `map off` | project map; `on` adds it at the start of every session |
| `/neverbor reread on` · `off` | a pointer instead of re-reading an unchanged file |
| `/neverbor report` | a page with a savings chart and top commands |
| `/neverbor advise` | tuning advice based on your stats |
| `/neverbor statusline` | savings in the Claude Code status line (shows what to add to settings) |
| `/neverbor mode light` · `normal` · `aggressive` | how hard to compress |
| `/neverbor config` | show settings; `/neverbor config min_chars 4000` changes one |
| `/neverbor terse on` · `off` | the brevity rules (from the next session) |
| `/neverbor quiet on` · `off` | quiet flags for `npm install`, `pip install`, `git clone`, `cargo build` |

**Modes.** `light` — only colors, progress bars and repeats, from 5 000 characters. `normal` — full compression (default). `aggressive` — long outputs are cut harder: 80 lines instead of 150.

**Quiet flags** are off by default. When on, Neverbor adds a flag like `-q` to a simple command and **always** asks you to confirm the changed command. Compound commands (`&&`, `|`, `$(…)`) are left alone.

<details>
<summary><b>Fine-tuning</b></summary>

Settings live in `~/.claude/neverbor/config.json`. The easy way to change them is `/neverbor config <key> <value>`; reset with `/neverbor config <key> reset`.

| Key | Default | Meaning |
|---|---|---|
| `min_chars` | `2500` | shorter outputs are not compressed |
| `max_lines` · `head` · `tail` | `150` · `50` · `40` | beyond `max_lines`, the head, the tail and every error line are kept |
| `min_saving` | `0.15` | don't compress if it saves less than 15% |
| `cache_days` | `3` | how many days originals are kept |
| `passthrough` | `""` | your own exceptions, as a regex: `rg\|kubectl` |
| `compress_diff` | `false` | compress context lines in `git diff` (all `+`/`-` lines stay) |
| `rules_extra` | `""` | your own rule added to the brevity rules |
| `lang` | `"en"` | language of the savings note: `en` or `ru` |
| `brief` | `true` | work log after `/compact` |
| `reread` | `false` | a pointer instead of re-reading a file |
| `map_on_start` | `false` | project map at session start |

Also:
- `# neverbor:off` at the end of a bash command turns compression off for that command only.
- `NEVERBOR=0` turns compression off through the environment, `NEVERBOR_TERSE=0` the brevity rules, `NEVERBOR_QUIET=1` turns quiet flags on.
- `NEVERBOR_PASSTHROUGH='rg|kubectl'` wins over `passthrough` from the config.
- `NEVERBOR_DEBUG=1` prints hook errors to stderr.

</details>

## ⚙️ How it works

```
Claude calls Bash / an MCP tool
        │  raw output (logs, find, grep, JSON…)
        ▼
PostToolUse hook  scripts/post_tool.py
        │  0. same command, same output earlier in the session? → pointer to that run
        │  1. strips ANSI colors and progress-bar redraws (\r)
        │  2. cuts minified JS/base64 (long lines without spaces)
        │  3. package download lines → a counter
        │  4. stack traces: library frames → "… N library frames"
        │  5. folds repeated and look-alike lines
        │  6. JSON: minified, long arrays → first 5 + last 2 + the ones with errors
        │  7. >150 lines: head + tail + every line with error/fail/warning/traceback
        │  8. original → ~/.claude/neverbor/cache/…, with a pointer at the end
        ▼
Claude sees the short version and can read the original if needed
```

- `SessionStart` adds the brevity rules, which cuts **output** tokens too. After `/compact` it resets the repeat memory so Claude sees outputs in full again.
- `Stop` shows you a short note after an answer that saved more than 300 tokens. It never reaches the model's context.
- `PreToolUse` only acts when quiet flags are on.
- `PostToolUse` on `Edit`/`Write` keeps a session log of changed files. `PostToolUseFailure` records failed commands and notices repeated errors. The work log after `/compact` is built from it.
- The log is stored locally in `~/.claude/neverbor/sessions/` and is never sent anywhere.

## 🛡 What is never compressed

- Output under 2 500 characters, or where the saving is under 15%.
- Exact-view commands: `cat`, `head`, `tail`, `sed`, `awk`, `jq`, `diff`, `git diff/show/blame` and the like. For diffs this can be turned on with `compress_diff`.
- The `Read`, `Edit` and `Grep` tools: Claude needs exact text to edit. The one exception is `reread on`: re-reading an unchanged file returns a pointer, and if Claude asks for the file again right after, it gets it in full.
- Commands that failed: Claude Code doesn't allow changing their output.

Originals are kept for 3 days (`cache_days`) in `~/.claude/neverbor/cache/`.

## 🗺 Roadmap

- [x] Quiet flags via `PreToolUse` — `/neverbor quiet on`.
- [x] Diff compression: ±3 context lines — `compress_diff`.
- [x] Package installs, stack traces, repeats, modes, settings, savings note.
- [x] Work log after `/compact`, repeat-failure hint, project map, report and advice.
- [ ] More formats: `docker build`, `terraform plan`, `kubectl get`.
- [ ] Long tables (`ls -la`, `ps aux`): keep the columns that matter.

## 📄 License

[MIT](LICENSE) © koigkio
