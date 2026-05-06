# インフォグラフィック用プロンプト（テキスト管理）

**目的**: Web ヒーロー画像／OGP 向けの **画像生成AI用プロンプト** を、ここで版管理する。  
実際のレンダリングは **ChatGPT の画像生成**（通称で「Nano Banana」等と呼ばれることがある）や、その他ツールに渡してよい。**本フォルダはテキストの正本**であり、特定の画像モデル名に縛られない。

## ファイル

| ファイル | 役割 |
|----------|------|
| `spec_hero_ogp_infographic.md` | Web ヒーロー／**OGP 向けフラット・図解**の仕様の正本 |
| `spec_note_editorial_cinematic.md` | **B**・note 向け編集リアル／シネマティック（画像内テキスト原則なし） |
| `spec_note_dx_workflow_infographic.md` | **C（既定）**・横長 **DXワークフロー** インフォ（5ステップ＋下部KPI＋日本語キャプション） |
| `meta_build_image_prompt.md` | **A / B / C** を選んで**画像AI用1本**を生成する **メタ用**（note アイキャッチ未指定時は **C**） |

## 運用の流れ

1. `meta_build_image_prompt.md` をレビュー用／執筆用の **別LLM** に渡し、**用途モード（A／B／C）** と **「今回のキャプション・ステップ文言」** 等を入力する（note のサービス事例アイキャッチで未指定なら **C**）。  
2. 出力された **画像生成用プロンプト** を人間が手直しする。  
3. 手直し済みを画像生成AIに貼る。  
4. 仕様を変えるときは **`spec_hero_ogp_infographic.md`（A）**、`spec_note_editorial_cinematic.md`（B）、**`spec_note_dx_workflow_infographic.md`（C）** のいずれかを編集し、**`meta_build_image_prompt.md`** とも整合させる。

## 言語

- メタ→中間プロンプト→画像AIは、**日本語でよい**（利用する画像生成が日本語指示に対応している前提）。英語にしたい場合は `meta_build_image_prompt.md` の出力言語指示を変える。
