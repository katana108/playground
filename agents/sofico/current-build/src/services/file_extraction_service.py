"""
File Extraction Service
Extracts text from various file formats (PDF, DOCX, TXT, etc.)
"""

import logging
import os
import requests
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class FileExtractionService:
    """
    Extracts text content from various file formats.
    Handles Slack file downloads and local files.
    """

    def __init__(self, slack_client=None):
        self.slack_client = slack_client

    def extract_from_slack_file(self, file_info: dict) -> str:
        """
        Download and extract text from a Slack file.

        Args:
            file_info: Slack file object with url_private, filetype, etc.

        Returns:
            Extracted text content
        """
        try:
            file_type = file_info.get("filetype", "").lower()
            url = file_info.get("url_private")
            name = file_info.get("name", "unknown")

            logger.info(f"Extracting text from Slack file: {name} ({file_type})")

            # Download file using the bot token for auth
            bot_token = os.getenv("SLACK_BOT_TOKEN")
            headers = {"Authorization": f"Bearer {bot_token}"}

            # Use url_private_download if available, else url_private
            download_url = file_info.get("url_private_download") or url
            file_response = requests.get(download_url, headers=headers)
            file_response.raise_for_status()
            content = file_response.content

            # Extract based on file type
            return self._extract_text(content, file_type)

        except Exception as e:
            logger.error(f"Error extracting from Slack file: {e}")
            raise

    def extract_from_path(self, file_path: str) -> str:
        """
        Extract text from a local file path.

        Args:
            file_path: Path to the file

        Returns:
            Extracted text content
        """
        try:
            path = Path(file_path)
            file_type = path.suffix.lower().lstrip('.')

            logger.info(f"Extracting text from local file: {path.name} ({file_type})")

            with open(path, 'rb') as f:
                content = f.read()

            return self._extract_text(content, file_type)

        except Exception as e:
            logger.error(f"Error extracting from file path: {e}")
            raise

    def _extract_text(self, content: bytes, file_type: str) -> str:
        """
        Extract text from file content based on type.

        Args:
            content: Raw file bytes
            file_type: File extension (pdf, txt, docx, etc.)

        Returns:
            Extracted text
        """
        try:
            if file_type in ["txt", "md", "markdown"]:
                return content.decode('utf-8')

            elif file_type == "pdf":
                return self._extract_from_pdf(content)

            elif file_type in ["doc", "docx"]:
                return self._extract_from_docx(content)

            elif file_type in ["html", "htm"]:
                return self._extract_from_html(content)

            else:
                # Try to decode as text
                logger.warning(f"Unknown file type {file_type}, attempting text decode")
                return content.decode('utf-8', errors='ignore')

        except Exception as e:
            logger.error(f"Error extracting text from {file_type}: {e}")
            raise

    def _extract_from_pdf(self, content: bytes) -> str:
        """Extract text from PDF using pypdf"""
        try:
            import io
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader  # fallback for older installs

            pdf_file = io.BytesIO(content)
            reader = PdfReader(pdf_file)

            text = []
            for page in reader.pages:
                text.append(page.extract_text())

            return "\n\n".join(text)

        except ImportError:
            logger.error("pypdf not installed. Install with: pip install pypdf")
            raise ImportError("pypdf required for PDF extraction. Run: pip install pypdf")
        except Exception as e:
            logger.error(f"Error extracting PDF: {e}")
            raise

    def _extract_from_docx(self, content: bytes) -> str:
        """Extract text from DOCX using python-docx"""
        try:
            import docx
            import io

            doc_file = io.BytesIO(content)
            doc = docx.Document(doc_file)

            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)

            return "\n\n".join(text)

        except ImportError:
            logger.error("python-docx not installed. Install with: pip install python-docx")
            raise ImportError("python-docx required for DOCX extraction")
        except Exception as e:
            logger.error(f"Error extracting DOCX: {e}")
            raise

    def _extract_from_html(self, content: bytes) -> str:
        """Extract text from HTML using BeautifulSoup"""
        try:
            from bs4 import BeautifulSoup

            html = content.decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text

        except ImportError:
            logger.error("beautifulsoup4 not installed. Install with: pip install beautifulsoup4")
            raise ImportError("beautifulsoup4 required for HTML extraction")
        except Exception as e:
            logger.error(f"Error extracting HTML: {e}")
            raise
