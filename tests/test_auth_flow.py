import io


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["version"]


def test_firebase_login_returns_token(client):
    resp = client.post("/api/auth/firebase-login", json={"id_token": "dummy"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "token" in data and data["token"]
    assert data["user"]["email"] == "test@example.com"


def test_analyze_flow(client, auth_headers, sample_image_file):
    data = {
        "profile": (sample_image_file, "profile.jpg")
    }

    resp = client.post(
        "/bd/analyze",
        data=data,
        headers=auth_headers,
        content_type="multipart/form-data"
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["username"] == "testuser"
    assert payload["analysis_text"]
    assert payload["value_estimation"]["account_asset_value"] > 0


