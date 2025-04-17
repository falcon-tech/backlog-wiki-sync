#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List
import re

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BacklogWikiSync:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('BACKLOG_API_KEY')
        self.space_id = os.getenv('BACKLOG_SPACE_ID')
        self.project_id = os.getenv('BACKLOG_PROJECT_ID')
        self.delete_mode = os.getenv('DELETE_MODE', 'False').lower() == 'true'
        self.base_url = f"https://{self.space_id}.backlog.jp/api/v2"
        self.headers = {
            'Content-Type': 'application/json',
            'apiKey': self.api_key
        }
        self.docs_dir = Path('docs')
        self.files_dir = Path('files')

        # 設定値のログ出力（APIキーは除く）
        logger.info(f"Space ID: {self.space_id}")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Project ID: {self.project_id}")
        logger.info(f"Delete Mode: {self.delete_mode}")

    def mask_api_key(self, text: str) -> str:
        """APIキーを秘匿する"""
        return re.sub(r'apiKey=[^&"\s]+', 'apiKey=***', text)

    def get_wiki_pages(self) -> List[Dict]:
        """BacklogのWikiページ一覧を取得"""
        try:
            response = requests.get(
                f"{self.base_url}/wikis",
                params={'apiKey': self.api_key, 'projectIdOrKey': self.project_id}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e.response, 'text'):
                error_text = self.mask_api_key(e.response.text)
                logger.error(f"API Error: {error_text}")
            raise

    def create_wiki_page(self, name: str, content: str) -> Dict:
        """Wikiページを作成"""
        data = {
            "projectId": int(self.project_id),
            "name": name,
            "content": content
        }
        try:
            response = requests.post(
                f"{self.base_url}/wikis",
                params={'apiKey': self.api_key},
                json=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e.response, 'text'):
                error_text = self.mask_api_key(e.response.text)
                logger.error(f"API Error: {error_text}")
            raise

    def update_wiki_page(self, wiki_id: int, name: str, content: str) -> Dict:
        """Wikiページを更新"""
        data = {
            "name": name,
            "content": content
        }
        try:
            response = requests.patch(
                f"{self.base_url}/wikis/{wiki_id}",
                params={'apiKey': self.api_key},
                json=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e.response, 'text'):
                error_text = self.mask_api_key(e.response.text)
                logger.error(f"API Error: {error_text}")
            raise

    def delete_wiki_page(self, wiki_id: int) -> None:
        """Wikiページを削除"""
        try:
            response = requests.delete(
                f"{self.base_url}/wikis/{wiki_id}",
                params={'apiKey': self.api_key}
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if hasattr(e.response, 'text'):
                error_text = self.mask_api_key(e.response.text)
                logger.error(f"API Error: {error_text}")
            raise

    def upload_attachment(self, wiki_id: int, file_path: Path) -> Dict:
        """ファイルを添付"""
        try:
            # ファイルをアップロードし、Attachment IDを取得
            logger.info(f"Uploading file to space: {file_path}")
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f)}
                response = requests.post(
                    f"{self.base_url}/space/attachment",
                    params={'apiKey': self.api_key},
                    files=files
                )
                response.raise_for_status()
                response_data = response.json()
                logger.info(f"Space attachment response: {response_data}")
                attachment_id = response_data.get('id')

            if not attachment_id:
                error_msg = f"Failed to get attachment ID from response: {response_data}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # Wikiページにファイルを添付
            logger.info(f"Attaching file to wiki page {wiki_id} with attachment ID {attachment_id}")
            files = {'attachmentId[]': (None, str(attachment_id))}
            response = requests.post(
                f"{self.base_url}/wikis/{wiki_id}/attachments",
                params={'apiKey': self.api_key},
                files=files
            )
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"Wiki attachment response: {response_data}")
            return response_data
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                error_text = self.mask_api_key(e.response.text)
                logger.error(f"API Error: Status {e.response.status_code}, Response: {error_text}")
            else:
                logger.error(f"Request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during file upload: {str(e)}")
            raise

    def get_wiki_attachments(self, wiki_id: int) -> List[Dict]:
        """Wikiページに添付されているファイルの一覧を取得"""
        try:
            response = requests.get(
                f"{self.base_url}/wikis/{wiki_id}/attachments",
                params={'apiKey': self.api_key}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e.response, 'text'):
                error_text = self.mask_api_key(e.response.text)
                logger.error(f"API Error: {error_text}")
            raise

    def convert_references(self, content: str, wiki_id: int, upload_new_files: bool = False) -> str:
        """画像参照とファイルリンクをBacklog Wiki形式に変換"""
        # 既存の添付ファイルを取得
        existing_attachments = {att['name']: att['id'] for att in self.get_wiki_attachments(wiki_id)}

        # 画像参照とファイルリンクを検出する正規表現パターン(パスが/files/で始まるに限る)
        image_pattern = r'!\[(.*?)\]\((/files/.*)\)'
        file_pattern = r'(?<!!)\[(.*?)\]\((/files/.*)\)'

        # コンテンツ内の画像参照を検出し、リストに格納
        image_matches = list(re.finditer(image_pattern, content))
        logger.info(f"Found {len(image_matches)} image references in content")

        # コンテンツ内のファイルリンクを検出し、リストに格納
        file_matches = list(re.finditer(file_pattern, content))
        logger.info(f"Found {len(file_matches)} file references in content")

        # 元のコンテンツをコピーして、後続の置換処理で使用する
        processed_content = content

        # 検出した画像参照をBacklog Wiki形式に変換
        for match in image_matches:
            alt_text = match.group(1)
            image_path = match.group(2)
            original_ref = match.group(0)

            # 画像参照で参照しているファイル名を取得
            file_name = Path(image_path).name
            logger.info(f"The file name of the image referenced in {original_ref}: {file_name}")

            # ファイルの存在確認
            file_path = self.files_dir / file_name
            logger.info(f"Looking for file at: {file_path}")

            if file_path.exists() and file_path.is_file():
                try:
                    # 既存の添付ファイルをチェック
                    if file_name in existing_attachments:
                        logger.info(f"File {file_name} already attached with ID {existing_attachments[file_name]}")
                        attachment_id = existing_attachments[file_name]
                    elif upload_new_files:
                        logger.info(f"Uploading file: {file_path}")
                        response = self.upload_attachment(wiki_id, file_path)

                        # アップロードされたファイルの情報を取得
                        if isinstance(response, list) and len(response) > 0:
                            attachment = response[0]
                            attachment_id = attachment['id']
                        else:
                            logger.error(f"Unexpected attachment response format: {response}")
                            continue
                    else:
                        continue

                    # Backlog Wiki形式に変換
                    new_ref = f"![{alt_text}][{attachment_id}]"
                    logger.info(f"Replacing reference: {original_ref} -> {new_ref}")
                    processed_content = processed_content.replace(original_ref, new_ref)
                except Exception as e:
                    logger.error(f"Failed to process file {image_path}: {e}")
            else:
                logger.warning(f"File not found: {file_path}")

        # 検出したファイルリンクをBacklog Wiki形式に変換
        for match in file_matches:
            link_text = match.group(1)
            file_path = match.group(2)
            original_ref = match.group(0)

            # ファイルリンクで参照しているファイル名を取得
            file_name = Path(file_path).name
            logger.info(f"The file name of the file referenced in {original_ref}: {file_name}")

            # ファイルの存在確認
            file_path = self.files_dir / file_name
            logger.info(f"Looking for file at: {file_path}")

            if file_path.exists() and file_path.is_file():
                try:
                    # 既存の添付ファイルをチェック
                    if file_name in existing_attachments:
                        logger.info(f"File {file_name} already attached with ID {existing_attachments[file_name]}")
                        attachment_id = existing_attachments[file_name]
                    elif upload_new_files:
                        logger.info(f"Uploading file: {file_path}")
                        response = self.upload_attachment(wiki_id, file_path)

                        # アップロードされたファイルの情報を取得
                        if isinstance(response, list) and len(response) > 0:
                            attachment = response[0]
                            attachment_id = attachment['id']
                        else:
                            logger.error(f"Unexpected attachment response format: {response}")
                            continue
                    else:
                        continue

                    # Backlog Wiki形式に変換
                    new_ref = f"[{link_text}][{attachment_id}]"
                    logger.info(f"Replacing reference: {original_ref} -> {new_ref}")
                    processed_content = processed_content.replace(original_ref, new_ref)
                except Exception as e:
                    logger.error(f"Failed to process file {file_path}: {e}")
            else:
                logger.warning(f"File not found: {file_path}")

        return processed_content

    def normalize_content(self, content: str) -> str:
        """コンテンツの正規化"""
        # 改行コードを統一
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        # 空白文字の正規化
        lines = []
        for line in content.split('\n'):
            # 行の前後の空白を削除
            line = line.strip()
            if line:  # 空行でない場合のみ追加
                # 連続する空白を1つに
                line = ' '.join(line.split())
                lines.append(line)

        # 空白文字の正規化で分割した行を結合
        return '\n'.join(lines)

    def get_wiki_content(self, wiki_id: int) -> str:
        """Wikiページの内容を取得"""
        try:
            response = requests.get(
                f"{self.base_url}/wikis/{wiki_id}",
                params={'apiKey': self.api_key}
            )
            response.raise_for_status()
            return response.json().get('content', '')
        except requests.exceptions.RequestException as e:
            if hasattr(e.response, 'text'):
                error_text = self.mask_api_key(e.response.text)
                logger.error(f"API Error: {error_text}")
            raise

    def sync(self):
        """ドキュメントとWikiページを同期"""
        try:
            # 既存のWikiページを取得
            wiki_pages = {page['name']: page for page in self.get_wiki_pages()}

            # docs配下のファイルを処理
            if not self.docs_dir.exists():
                logger.error("docs directory not found")
                return

            processed_pages = set()

            for file_path in self.docs_dir.glob('**/*.md'):
                relative_path = file_path.relative_to(self.docs_dir)
                wiki_name = str(relative_path.with_suffix('')).replace('\\', '/')
                processed_pages.add(wiki_name)
                logger.info(f"Processing page: {wiki_name}")

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if wiki_name in wiki_pages:
                        # 既存ページの更新
                        wiki_id = wiki_pages[wiki_name]['id']
                        wiki_content = self.get_wiki_content(wiki_id)

                        # 内容を正規化して比較
                        normalized_content = self.convert_references(self.normalize_content(content), wiki_id, upload_new_files=False)
                        normalized_wiki_content = self.normalize_content(wiki_content)

                        if normalized_content != normalized_wiki_content:
                            logger.info(f"Content changed for wiki page: {wiki_name}")
                            content = self.convert_references(content, wiki_id, upload_new_files=True)
                            self.update_wiki_page(wiki_id, wiki_name, content)
                            logger.info(f"Updated wiki page: {wiki_name}")
                        else:
                            logger.info(f"No changes detected for wiki page: {wiki_name}")
                    else:
                        # 新規ページの作成
                        wiki_id = self.create_wiki_page(wiki_name, content)['id']
                        content = self.convert_references(content, wiki_id, upload_new_files=True)
                        self.update_wiki_page(wiki_id, wiki_name, content)
                        logger.info(f"Created wiki page: {wiki_name}")

                except Exception as e:
                    logger.error(f"Failed to process {wiki_name}: {e}")

            # 削除されたページの処理
            if self.delete_mode:
                for wiki_name, page in wiki_pages.items():
                    if wiki_name not in processed_pages:
                        try:
                            self.delete_wiki_page(page['id'])
                            logger.info(f"Deleted wiki page: {wiki_name}")
                        except Exception as e:
                            logger.error(f"Failed to delete {wiki_name}: {e}")
            else:
                logger.info("Delete mode is disabled. Skipping deletion of removed pages.")

        except Exception as e:
            logger.error(f"Sync failed: {str(e)}")
            if isinstance(e, requests.exceptions.RequestException) and hasattr(e.response, 'text'):
                error_text = self.mask_api_key(e.response.text)
                logger.error(f"API Error Details: {error_text}")
            sys.exit(1)

def main():
    syncer = BacklogWikiSync()
    syncer.sync()

if __name__ == "__main__":
    main()