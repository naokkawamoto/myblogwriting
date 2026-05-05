---
workflows: [note]
tags: [note, theme, ops]
---

# 運用：テーマから note 下書き

**ゴール**: テーマを伝えると、One Technology Japan 社長の note として **本文の下書き** が得られる。

## 手順（どちらか一方でよい）

### 手順1（おすすめ）

1. `prompts/note/sections/99_task_input.md` の **今回の依頼** を書き換える（プレースホルダの正本はこのファイル）。  
2. リポジトリルートで `bash prompts/note/assemble.sh` を実行する。  
3. `prompts/note/dist/note_writer_prompt.md` の **全文** を AI に渡す（Cursor なら `@note_writer_prompt.md`）。  
4. 「上記に従い、note 記事の本文を書いてください」と送る。

### 手順2（結合版はそのまま・依頼だけチャットで足す）

1. `prompts/note/dist/note_writer_prompt.md` を **そのまま** 貼る。  
2. 続けて、`prompts/note/sections/99_task_input.md` の **今回の依頼** 見出しから最後までをコピーし、プレースホルダを埋めて貼る。

---

**メンテ**: 依頼欄の項目を変えるときは **`99_task_input.md` のみ** を直し、`assemble.sh` を再実行する（このファイルには依頼文の複製を置かない）。
