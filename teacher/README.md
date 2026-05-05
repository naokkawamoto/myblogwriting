# Teacher／個人用ブログ執筆リポジトリ

会社の **`onetech-marketing-workspace` にはコミットしない**執筆メモ・下書き・講義用サンプルを置くための **別 Git リポジトリ**を、このフォルダ直下にクローンします。

- **リモート（公開・空でも可）**: [naokkawamoto/myblogwriting](https://github.com/naokkawamoto/myblogwriting)

## セットアップ

ルートで（ネットワーク必須）:

```bash
bash scripts/setup_teacher_blog_repo.sh
```

別 URL にしたい場合:

```bash
TEACHER_BLOG_REPO_URL=https://github.com/you/other.git bash scripts/setup_teacher_blog_repo.sh
```

手動でも同じです。

```bash
mkdir -p teacher
git clone https://github.com/naokkawamoto/myblogwriting.git teacher/myblogwriting
```

## GitHub が空のときの初回プッシュ例

```bash
cd teacher/myblogwriting
echo "# myblogwriting" > README.md
git add README.md
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/naokkawamoto/myblogwriting.git   # まだなければ
git push -u origin main
```

（すでに GitHub 側で README を作っている場合は、`git pull --rebase origin main` してから作業してください。）

## このワークスペースとの関係

- `teacher/myblogwriting/` は **`.gitignore` で除外**しており、親リポジトリにネストした `.git` を誤コミットしにくくしています。
- Cursor では **別ウィンドウで `teacher/myblogwriting` を開く**か、マルチルートワークスペースに追加すると扱いやすいです。
