<div align="center">

# ChangoFilm 🎬

### プロフェッショナルなシリーズ短編ドラマ · ローカルファースト AI スタジオ

<b>テーマ</b>または<b>脚本</b>を提供するだけで、ChangoFilm が文案・映像・ナレーション・
字幕・音楽を生成し、あなたのマシン上で完成したエピソードを合成します。

[![Version](https://img.shields.io/badge/version-1.12.0-blue)](https://github.com/wyg5208/changofilm)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/wyg5208/changofilm)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[简体中文](README.md) | [English](README-en.md) | 日本語

</div>

---

## 概要

ChangoFilm は**ローカルファースト**のシリーズ短編ドラマ制作ツールです。企画選定、
脚本プラン、エピソードごとの素材、最終合成まで、すべての工程がマシン上で完結し、
素材や API キーが外部に送信されることはありません。

制作の入口は 2 つの明確なルートに分かれています：

- **クイック動画**：テーマやキーワードを入力すると、1 本のパイプラインが短編動画を
  自動生成。素早い試作に最適です。
- **プロ短編ドラマ**：脚本プラン（Script Plan）駆動のエピソード制作。シリーズ
  プロジェクト、エピソードごとの脚本と素材管理に対応し、**プロジェクトごとに
  画像 / 動画 / 音声 / 字幕の設定を独立して保持**します。

**WebUI・API・CLI・AI Agent Skill** の 4 つの利用方法を提供。UI は 14 言語対応です。

## 主な機能 🎯

### 脚本とモデルサービス

- 多言語脚本の AI 自動生成・書き換え、カスタム脚本とシステムプロンプトにも対応
- Kimi / Moonshot、OpenAI、Anthropic Claude、Google Gemini、DeepSeek、通義千問、
  Azure OpenAI、火山引擎 Ark、xAI Grok、MiniMax、Xiaomi MiMo などに対応
- OpenRouter、Ollama、LiteLLM、OneAPI、Cloudflare AI Gateway などの統一ゲートウェイ、
  llama.cpp などのローカル推論にも対応。Claude Code / ChatGPT / Codex の
  サブスクリプション認証も利用可能

### 映像素材

- ローカル画像・動画のアップロード、[Pexels](https://www.pexels.com/api/)・
  [Pixabay](https://pixabay.com/api/docs/)・[Coverr](https://coverr.co/developers)
  からの高品質**ストック動画**取得
- **ストック画像**ソース（Pexels / Pixabay）と AI 画像生成を併用可能、
  プロジェクトごとに設定
- AI 動画生成：火山引擎 Seedance、Metaso MiniMax H3（768P / 2K）、WaveSpeed、
  OFox、MuAPI、勝算雲など。OpenAI 互換の画像生成とカスタムゲートウェイにも対応
- ローカル ComfyUI エンジン：画像生成 / 動画生成ワークフローを自分の GPU で実行

### ナレーション・字幕・音楽

- 自動ナレーション / アップロード音声 / ナレーションなしの 3 モード、音色試聴と
  全体プレビュー
- **Edge TTS（無料・キー不要）**、Azure Speech、SiliconFlow、Gemini、MiMo、
  MiniMax、ElevenLabs、Chatterbox、Kokoro、Fish Audio、VoxCPM などを統合
- faster-whisper による自動字幕。フォント・位置・色・縁取り・背景スタイルを調整可能
- ランダム / ローカル / AI 生成の BGM、音量は独立制御

### 出力と公開

- 縦型 `9:16`、横型 `16:9`、正方形 `1:1`
- バッチ生成、タスク履歴と復元、設定プリセットと API キーバックアップの
  エクスポート / インポート
- TikTok・Instagram・YouTube Shorts へのワンクリッククロス投稿

## 動作要件 📦

- Windows 10 以降、macOS 11 以降、または主要な Linux ディストリビューション
- Python **3.11 以降**（3.11 推奨）
- GPU は必須ではありません。ローカル Whisper 転写、ComfyUI エンジン、
  大規模バッチ生成では VRAM 4GB 以上を推奨

| 項目 | 最小構成 | 推奨構成 |
| ---- | -------- | -------- |
| CPU  | 4 コア   | 8 コア以上 |
| RAM  | 4 GB     | 16 GB 以上 |
| GPU  | 不要     | VRAM 4 GB 以上 |

## クイックスタート 🚀

### 方法 1：ソースから（推奨、uv で依存管理）

```sh
git clone https://github.com/wyg5208/changofilm.git
cd changofilm
uv sync
```

WebUI の起動：

- Windows：`webui.bat` をダブルクリック
- macOS / Linux：`./webui.sh`

API サービスの起動（FastAPI、既定 `http://127.0.0.1:8080`）：

```sh
uv run python main.py
```

### 方法 2：pip インストール

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install changofilm
changofilm webui
changofilm cli --help
```

### 方法 3：Docker

```sh
docker compose up -d
```

WebUI は `127.0.0.1:8501`、API は `127.0.0.1:8080` で待ち受けます。
GPU 環境では `docker-compose.gpu.yml` を使用。リリースイメージ
（`ghcr.io/wyg5208/changofilm`）は `docker-compose.release.yml` で利用できます。

### 方法 4：AI Agent Skill

AI Agent が Skill ドキュメントの読み取りとローカルターミナル操作に対応している場合、
次のメッセージを送るだけです：

```text
この Skill を使用：https://raw.githubusercontent.com/wyg5208/changofilm/main/docs/skill/SKILL.md
「AI は日常生活をどう変えるか」というテーマで動画を生成してください。
```

Agent がインストール・設定・生成を自動で実行し、不足している API キーのみを
質問します。詳細は [docs/skill/SKILL.md](docs/skill/SKILL.md)
（[中国語版](docs/skill/SKILL-zh.md)）を参照してください。

## 設定とデータディレクトリ ⚙️

- `config.example.toml` を `config.toml` にコピーするか、WebUI の設定ダイアログで
  モデル・素材ソース・ナレーション・字幕を設定
- インストール版のデータはユーザーディレクトリに保存されます（macOS
  `~/Library/Application Support/ChangoFilm`、Windows `%LOCALAPPDATA%\ChangoFilm`、
  Linux `~/.local/share/ChangoFilm`）
- 環境変数 `CHANGOFILM_HOME` でデータディレクトリを指定可能。旧版の `MPT_HOME`
  も引き続き受け付け、旧ブランドのデータディレクトリは初回起動時に自動移行され、
  ユーザーデータは失われません

## ドキュメント 📚

- [pip パッケージと PyPI リリース](docs/packaging.md)
- [Agent Skill ガイド](docs/skill/SKILL.md)
- [イテレーション記録](docs/迭代记录文档/)：本ブランチの変更履歴と検証エビデンス

## サービスプロバイダーと紹介リンク 🤝

ChangoFilm が統合または推奨するサービス入口です。一部は登録時にボーナスが付与される
紹介リンクです：

| プロバイダー | 機能 | 入口 |
| ------------ | ---- | ---- |
| Kimi / Moonshot | 文案・素材理解 LLM | [プラットフォーム](https://platform.kimi.ai?track_id=track-9e3b711aa2594e378f6fe5b8de718a76&aff=moneyprinterturbo) |
| 火山引擎 Ark | Seedance 動画生成・モデルプラン | [キャンペーン](https://www.volcengine.com/activity/ai618?utm_campaign=hw&utm_content=hw&utm_medium=devrel_tool_web&utm_source=OWO&utm_term=MoneyPrinterTurbo) |
| Metaso | MiniMax H3 動画生成 API | [紹介リンク](https://metaso.cn/minimax-h3/?s=MPT) |
| APIMart | AI 画像 / 動画非同期 API | [登録](https://go.apimart.ai/gh-moneyprinterturbo) |
| OFox | マルチモデル動画 / 画像生成 | [サイト](https://ofox.ai/?utm_source=github&utm_medium=sponsorship&utm_content=moneyprinterturbo) |
| 勝算雲 | モデル API アグリゲーション | [登録](https://www.shengsuanyun.com/?from=CH_XUQ4OTSK) |
| Infistar | LLM / 画像生成 API | [登録](https://infistar.cc/register?aff=6T4EYXP2&ref_source=link) |
| AstraFlow | 動画 / LLM アグリゲーション | [キャンペーン](https://www.ucloud.cn/site/active/astraflow?ytag=geo_waituo_Money) |
| RunningHub | ComfyUI ワークフローとモデル API | [API](https://www.runninghub.ai/call-api?source=github) |
| Jalapeno Cloud | マルチモデル統一アクセス | [登録](https://www.jalapeno-cloud.ai/MoneyPrinterTurbo) |

## 謝辞と参考プロジェクト ❤️

ChangoFilm の制作パイプライン、素材オーケストレーション、エンジニアリング実践は
**複数のオープンソースプロジェクトを参考**にしています。これには以下が含まれます
（これらに限定されません）：

- [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)（harry0703）——
  ワンストップ AI 短編動画生成ツール。本リポジトリは当初ここから fork されました
- [openfilm](https://github.com/openfilm/openfilm) —— HTML モーショングラフィックス
  レンダリングと決定論的フレームパイプライン。その並列レンダリングと検証の考え方は
  ローカル合成の品質保証に活かされています

ChangoFilm はこれらのプロジェクトを基に**大幅にリファクタリングされ、独自に
進化**しています：デュアルルート制作アーキテクチャ、シリーズプロジェクト管理、
プロジェクトごとの独立設定、ストック画像ソース、ローカル ComfyUI エンジン、
完全な回帰テスト体制は本プロジェクトの独自実装です。すべての原作者と
オープンソースコミュニティに感謝します。

## ライセンス

[MIT](LICENSE)