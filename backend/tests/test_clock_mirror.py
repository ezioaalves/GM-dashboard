from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gm_dashboard.relay_client import RelayClient, RelayError


class TestRelayClient:
    def _client(self):
        return RelayClient("https://relay.example", "key123", "client-abc")

    @patch("gm_dashboard.relay_client.requests.get")
    def test_get_unwraps_data(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"type": "get", "uuid": "Setting.x", "data": {"key": "v"}},
        )
        assert self._client().get("Setting.x") == {"key": "v"}
        args, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"x-api-key": "key123"}
        assert kwargs["params"] == {"uuid": "Setting.x", "clientId": "client-abc"}

    @patch("gm_dashboard.relay_client.requests.put")
    def test_update_wraps_payload(self, mock_put):
        mock_put.return_value = MagicMock(
            status_code=200, json=lambda: {"entity": [{"ok": True}]}
        )
        out = self._client().update("Setting.x", {"value": "{}"})
        assert out == {"entity": [{"ok": True}]}
        assert mock_put.call_args.kwargs["json"] == {"data": {"value": "{}"}}

    @patch("gm_dashboard.relay_client.requests.get")
    def test_error_raises_relay_error(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=404, json=lambda: {"error": "nf", "message": "not found"},
            text="not found",
        )
        with pytest.raises(RelayError):
            self._client().get("Setting.missing")
