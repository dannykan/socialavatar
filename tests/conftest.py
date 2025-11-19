import json
import os
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

# 確保專案根目錄在 sys.path 中
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


# 使用獨立的 SQLite DB，避免影響真實資料
os.environ.setdefault("DATABASE_URL", "sqlite:///test-data.sqlite3")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("APP_BASE_URL", "http://localhost:8000")


ANALYSIS_JSON = {
    "basic_info": {
        "username": "testuser",
        "display_name": "Test User",
        "followers": 1500,
        "following": 250,
        "posts": 35
    },
    "visual_quality": {"overall": 7.5, "consistency": 6.0},
    "content_type": {"primary": "生活風格", "category_tier": "mid"},
    "content_format": {"video_focus": 5, "personal_connection": 6},
    "professionalism": {"has_contact": True, "is_business_account": False},
    "personality_type": {"primary_type": "type_5", "reasoning": "測試理由"},
    "improvement_tips": ["持續分享高品質內容", "提升粉絲互動頻率"]
}

ANALYSIS_TEXT = f"""
毒舌短評：這是一段測試短評
```json
{json.dumps(ANALYSIS_JSON, ensure_ascii=False)}
```
"""


@pytest.fixture(scope="session")
def app_module():
    """匯入 Flask app 模組"""
    import app as app_module  # noqa

    return app_module


@pytest.fixture(autouse=True)
def _reset_db(app_module):
    """每個測試前清空資料"""
    app_module.Base.metadata.drop_all(bind=app_module.engine)
    app_module.Base.metadata.create_all(bind=app_module.engine)


@pytest.fixture
def client(monkeypatch, app_module):
    """提供測試用的 Flask client，並替換外部依賴"""

    # 模擬 Firebase 狀態
    monkeypatch.setattr(app_module, "firebase_app", object())

    def fake_verify(token):
        return {
            "uid": "test_uid",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://example.com/avatar.png",
            "firebase": {"sign_in_provider": "google.com"}
        }

    monkeypatch.setattr(app_module, "verify_firebase_token", fake_verify)

    class DummyAnalyzer:
        def analyze_profile(self, image):
            return ANALYSIS_TEXT, "這是測試短評"

    monkeypatch.setattr(app_module, "analyzer", DummyAnalyzer())

    return app_module.app.test_client()


@pytest.fixture
def auth_headers(client):
    """取得測試用 JWT token"""
    resp = client.post("/api/auth/firebase-login", json={"id_token": "dummy"})
    data = resp.get_json()
    token = data["token"]
    return {"Authorization": f"Bearer {token}"}


def create_test_image():
    """建立一張臨時圖片（BytesIO）"""
    image = Image.new("RGB", (512, 512), color=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


@pytest.fixture
def sample_image_file():
    return create_test_image()

