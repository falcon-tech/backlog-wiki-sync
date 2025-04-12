# Backlog Wiki Sync

ローカルのマークダウンファイルを任意のBacklogのWikiページに同期するためのPythonスクリプトとGitHub Actions。

## 前準備

- BacklogのAPIキーの取得
- BacklogのスペースIDの取得
- BacklogのプロジェクトIDの取得
- BacklogWikiの記法をマークダウン形式に設定する

## 使い方

1. 本レポジトリの内容を自身のリポジトリにコピーする

2. 自身のリポジトリのレポジトリシークレットに`BACKLOG_API_KEY`を登録する
  - 値には前準備で取得したBacklogのAPIキーを設定する

3. GitHub Actionsの設定ファイルを編集する
  - `.github/workflows/backlog_wiki_sync.yaml`のenvに前準備で取得したBacklogのスペースID、プロジェクトIDを設定する

```
env:
  BACKLOG_API_KEY: ${{ secrets.BACKLOG_API_KEY }}
  BACKLOG_SPACE_ID: xxxx
  BACKLOG_PROJECT_ID: xxxx
  DELETE_MODE: false
```

4. docsにBacklogWikiに同期するマークダウンファイルを配置する

5. レポジトリに変更内容をPushする

## ディレクトリ構造

```
.
├── .github/
  ├── workflows/
    ├── backlog_wiki_sync.yaml  # GitHub Actionsの設定ファイル
├── backlog_wiki_sync.py  # メインスクリプト
├── requirements.txt      # 依存パッケージ
├── docs/                 # Backlogに同期するマークダウンファイルの保存先
└── files/                # 添付ファイルの保存先
```

## 仕様
- 同期するマークダウンファイルは`docs`配下に配置する
- 同期先のBacklogWikiの階層は`docs`配下にディレクトリを作成して表現する
  - `docs`直下がBacklogWikiのトップ階層
- ドキュメント内に埋め込むファイル(ローカル)は`files`配下に配置(直下に配置すること)し、相対パスで指定する
  - 画像リンクは`![hoge](../files/hoge.png)`のように指定する
  - ファイルリンクは`[fuga](../files/fuga.pdf)`のように指定する
- BacklogWikiページの削除
  - GitHub Actionsのenvにある`DELETE_MODE`を`true`にすると、`docs`配下に存在しないBacklogWikiページは削除される

## 注意事項
- 既存のBacklogWikiページは、レポジトリのドキュメントの内容を正として上書きされるので、BacklogWikiページを直接更新することは避けること
- BacklogWikiページは一度削除してしまうと、元に戻すことはできないので、`DELETE_MODE`を`true`にする場合は慎重に行うこと