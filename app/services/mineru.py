import os
import logging
import requests
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class MinerUClient:
    """
    MinerU PDF 解析服务客户端
    """
    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv("MINERU_API_URL", "http://localhost:8000")
        self.enabled = bool(self.api_url)

    @classmethod
    def is_available(cls) -> bool:
        # 简单检查环境变量或配置
        return bool(os.getenv("MINERU_API_URL"))

    def extract(self, file_path: str) -> Dict:
        """
        调用 MinerU 提取 PDF 内容
        """
        if not self.enabled:
            raise RuntimeError("MinerU service is not enabled")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(f"{self.api_url}/extract", files=files, timeout=60)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"MinerU extraction failed: {e}")
            raise e
