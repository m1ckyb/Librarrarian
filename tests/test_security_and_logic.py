import logging
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Ensure testing mode is enabled before importing dashboard_app so no DB/threads start
os.environ["LIBRARRARIAN_TESTING"] = "1"
os.environ["AUTH_ENABLED"] = "false"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "dashboard"))
sys.path.insert(0, os.path.join(REPO_ROOT, "worker"))


def _stub_missing_optional_deps():
    """Provide lightweight stubs if optional runtime packages (e.g., plexapi, authlib, psycopg2) are not installed locally."""
    if "psycopg2" not in sys.modules:
        psycopg2_mod = types.ModuleType("psycopg2")
        psycopg2_mod.OperationalError = Exception
        psycopg2_mod.Error = Exception
        psycopg2_mod.connect = MagicMock()
        psycopg2_mod.extensions = types.SimpleNamespace(TRANSACTION_STATUS_INERROR=3)
        pool_mod = types.ModuleType("psycopg2.pool")
        pool_mod.ThreadedConnectionPool = MagicMock()
        extras_mod = types.ModuleType("psycopg2.extras")
        extras_mod.RealDictCursor = MagicMock()
        psycopg2_mod.pool = pool_mod
        psycopg2_mod.extras = extras_mod
        sys.modules["psycopg2"] = psycopg2_mod
        sys.modules["psycopg2.pool"] = pool_mod
        sys.modules["psycopg2.extras"] = extras_mod

    if "plexapi" not in sys.modules:
        plexapi_mod = types.ModuleType("plexapi")
        myplex_mod = types.ModuleType("plexapi.myplex")
        myplex_mod.MyPlexAccount = MagicMock()
        myplex_mod.MyPlexPinLogin = MagicMock()
        server_mod = types.ModuleType("plexapi.server")
        server_mod.PlexServer = MagicMock()
        sys.modules["plexapi"] = plexapi_mod
        sys.modules["plexapi.myplex"] = myplex_mod
        sys.modules["plexapi.server"] = server_mod

    if "authlib" not in sys.modules:
        authlib_mod = types.ModuleType("authlib")
        integrations_mod = types.ModuleType("authlib.integrations")
        flask_client_mod = types.ModuleType("authlib.integrations.flask_client")
        flask_client_mod.OAuth = MagicMock()
        sys.modules["authlib"] = authlib_mod
        sys.modules["authlib.integrations"] = integrations_mod
        sys.modules["authlib.integrations.flask_client"] = flask_client_mod


_stub_missing_optional_deps()

import transcode  # noqa: E402
import dashboard_app  # noqa: E402


class TestWorkerPathValidation:
    def test_allows_valid_media_path(self):
        assert transcode.validate_filepath("/media/movies/test.mkv") is True

    def test_blocks_path_traversal(self):
        assert transcode.validate_filepath("/media/../../etc/passwd") is False

    def test_blocks_cwd_application_files(self):
        cwd_file = os.path.join(os.path.abspath("."), "transcode.py")
        assert transcode.validate_filepath(cwd_file) is False

    def test_translate_validates_after_mapping(self):
        # Mapping a safe-looking path into /etc must be rejected after translation
        settings = {"plex_path_to": "/media", "plex_path_from": "/etc"}
        assert transcode.translate_path_for_worker("/media/passwd", settings) is None


class TestDashboardSecurityHelpers:
    def test_safe_service_url_allows_http_https(self):
        ok, err = dashboard_app.is_safe_service_url("http://sonarr:8989")
        assert ok is True and err is None

    def test_safe_service_url_blocks_metadata_and_bad_schemes(self):
        assert dashboard_app.is_safe_service_url("http://169.254.169.254/latest/meta-data")[0] is False
        assert dashboard_app.is_safe_service_url("file:///etc/passwd")[0] is False
        assert dashboard_app.is_safe_service_url("http://metadata.google.internal")[0] is False

    def test_resolve_safe_media_path_blocks_traversal_and_absolute(self):
        assert dashboard_app._resolve_safe_media_path("../../etc") is None
        assert dashboard_app._resolve_safe_media_path("/etc/passwd") == os.path.realpath("/media/etc/passwd")
        assert dashboard_app._resolve_safe_media_path("movies") == os.path.realpath("/media/movies")

    def test_resolve_safe_backup_path_whitelist(self):
        assert dashboard_app._resolve_safe_backup_path("../secret.txt") is None
        assert dashboard_app._resolve_safe_backup_path("arbitrary.sql") is None
        assert dashboard_app._resolve_safe_backup_path("20261128.020000.sql.gz") is not None
        assert dashboard_app._resolve_safe_backup_path("20261128.020000.tar.gz") is not None

    def test_health_check_filter_handles_gunicorn_dict_args(self):
        f = dashboard_app.HealthCheckFilter()
        gunicorn_record = logging.LogRecord(
            name="gunicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="%(U)s",
            args=(),
            exc_info=None,
        )
        gunicorn_record.args = {"U": "/api/status", "r": "GET /api/status HTTP/1.1"}
        assert f.filter(gunicorn_record) is False

        normal_record = logging.LogRecord(
            name="gunicorn.access",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="%(U)s",
            args=(),
            exc_info=None,
        )
        normal_record.args = {"U": "/api/jobs", "r": "GET /api/jobs HTTP/1.1"}
        assert f.filter(normal_record) is True


class TestDashboardApiSecurity:
    def test_csrf_blocks_unauthenticated_post_without_token(self):
        dashboard_app.app.config["AUTH_ENABLED"] = False
        dashboard_app.app.config["TESTING_SKIP_CSRF"] = False
        client = dashboard_app.app.test_client()
        resp = client.post("/api/jobs/clear", json={"force": False})
        assert resp.status_code == 403

    def test_worker_api_key_blocked_from_admin_endpoints(self):
        dashboard_app.app.config["AUTH_ENABLED"] = True
        with patch.dict(os.environ, {"API_KEY": "test-worker-key"}):
            client = dashboard_app.app.test_client()
            resp = client.get("/api/export", headers={"X-API-Key": "test-worker-key"})
            assert resp.status_code == 403

    def test_api_settings_redacts_secrets(self):
        dashboard_app.app.config["AUTH_ENABLED"] = False
        fake_settings = {
            "plex_token": {"setting_value": "super-secret-plex-token"},
            "jellyfin_api_key": {"setting_value": "super-secret-jf-key"},
            "sonarr_api_key": {"setting_value": "super-secret-sonarr-key"},
            "hardware_acceleration": {"setting_value": "vaapi"},
        }
        with patch.object(dashboard_app, "get_worker_settings", return_value=(fake_settings, None)):
            client = dashboard_app.app.test_client()
            resp = client.get("/api/settings")
            assert resp.status_code == 200
            data = resp.get_json()["settings"]
            assert data["plex_token"] == "***REDACTED***"
            assert data["jellyfin_api_key"] == "***REDACTED***"
            assert data["sonarr_api_key"] == "***REDACTED***"
            assert data["hardware_acceleration"] == "vaapi"

    def test_update_job_rejects_invalid_status(self):
        dashboard_app.app.config["AUTH_ENABLED"] = False
        client = dashboard_app.app.test_client()
        resp = client.post(
            "/api/update_job/123",
            json={"status": "bogus"},
            headers={"X-API-Key": "any"},
        )
        assert resp.status_code == 400
