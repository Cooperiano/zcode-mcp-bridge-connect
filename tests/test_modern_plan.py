import unittest
import io
import pathlib
import tempfile
from unittest import mock

from zcode_protocol import ZCodeProtocolClient, ProtocolError, modern_plan_config


def runtime():
    return {
        "model": {"providerId": "bigmodel---coding-plan", "modelId": "GLM-5.3"},
        "thoughtLevel": "high",
        "provider": {"baseURL": "https://open.bigmodel.cn/api/anthropic",
                     "apiKey": {"source": "inline", "value": "a" * 32 + "." + "b" * 32}},
    }


class ModernPlanTests(unittest.TestCase):
    def test_plan_projection_preserves_endpoint_and_access_type(self):
        config = modern_plan_config(runtime())["config"]
        provider = config["providerConfigRules"]["providerRules"][0]["config"]
        self.assertEqual("zhipu-coding-plan-api-key", provider["access"]["type"])
        self.assertEqual("https://open.bigmodel.cn/api/anthropic", provider["api"]["baseUrl"])

    def test_rejects_metered_endpoint_and_managed_placeholder(self):
        for field, value in (("baseURL", "https://open.bigmodel.cn/api/paas/v4"),
                             ("apiKey", {"value": "managed"})):
            model = runtime()
            model["provider"][field] = value
            with self.assertRaises(ProtocolError):
                modern_plan_config(model)

    def test_modern_create_and_send_remove_secret_bearing_runtime_without_mutation(self):
        with mock.patch.dict("os.environ", {"ZCODE_BRIDGE_MODERN_PROTOCOL": "1"}):
            client = ZCodeProtocolClient("unused", "unused")
        client._modern_model = runtime()["model"]
        original = {"runtimeModel": runtime(), "thoughtLevel": "high"}
        for method, key in (("session/create", "model"), ("session/send", "modelSelection")):
            mapped = client._request_params(method, original)
            self.assertNotIn("runtimeModel", mapped)
            self.assertEqual("high", mapped[key]["options"]["reasoningLevel"])
        self.assertIn("runtimeModel", original)
        self.assertNotIn("options", original["runtimeModel"]["model"])

    def test_modern_create_requires_reasoning_even_without_a_saved_level(self):
        with mock.patch.dict("os.environ", {"ZCODE_BRIDGE_MODERN_PROTOCOL": "1"}):
            client = ZCodeProtocolClient("unused", "unused")
        model = runtime()
        model.pop("thoughtLevel")
        client._modern_model = model["model"]
        mapped = client._request_params("session/create", {"runtimeModel": model})
        self.assertEqual("high", mapped["model"]["options"]["reasoningLevel"])

    def test_modern_model_cannot_switch_to_a_different_provider(self):
        with mock.patch.dict("os.environ", {"ZCODE_BRIDGE_MODERN_PROTOCOL": "1"}):
            client = ZCodeProtocolClient("unused", "unused")
        client._modern_model = runtime()["model"]
        with self.assertRaises(ProtocolError):
            client._request_params("session/setModel", {"model": {"providerId": "metered", "modelId": "GLM-5.3"}})

    def test_missing_modern_configuration_does_not_launch_app_server(self):
        with mock.patch.dict("os.environ", {"ZCODE_BRIDGE_MODERN_PROTOCOL": "1"}), \
                mock.patch("zcode_protocol.resolve_runtime_model", return_value=None), \
                mock.patch("zcode_protocol.resolve_modern_personal_plan", return_value=None), \
                mock.patch("zcode_protocol.subprocess.Popen") as popen:
            client = ZCodeProtocolClient("unused", "unused")
            with self.assertRaises(ProtocolError):
                client.start()
            popen.assert_not_called()

    def test_provider_files_are_removed_after_child_restart_and_close(self):
        first, second = mock.Mock(), mock.Mock()
        for proc in (first, second):
            proc.poll.return_value = None
            proc.stdout = []
            proc.stderr = []
            proc.stdin = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.dict("os.environ", {"ZCODE_BRIDGE_MODERN_PROTOCOL": "1"}), \
                mock.patch("zcode_protocol.Path.home", return_value=pathlib.Path(directory)), \
                mock.patch("zcode_protocol.resolve_runtime_model", side_effect=lambda: runtime()), \
                mock.patch("zcode_protocol.subprocess.Popen", side_effect=[first, second]), \
                mock.patch("zcode_protocol.os.killpg", create=True):
            client = ZCodeProtocolClient("unused", "unused")
            client.start()
            old_path = pathlib.Path(client._provider_config_file)
            first.poll.return_value = 0
            client.start()
            new_path = pathlib.Path(client._provider_config_file)
            self.assertFalse(old_path.exists())
            self.assertTrue(new_path.exists())
            client.close()
            self.assertFalse(new_path.exists())

    def test_failed_spawn_and_failed_shutdown_remove_private_file(self):
        for fail_on_spawn in (True, False):
            proc = mock.Mock()
            proc.poll.return_value = None
            proc.stdout = []
            proc.stderr = []
            proc.wait.side_effect = OSError("shutdown failed")
            with tempfile.TemporaryDirectory() as directory, \
                    mock.patch.dict("os.environ", {"ZCODE_BRIDGE_MODERN_PROTOCOL": "1"}), \
                    mock.patch("zcode_protocol.Path.home", return_value=pathlib.Path(directory)), \
                    mock.patch("zcode_protocol.resolve_runtime_model", side_effect=lambda: runtime()), \
                    mock.patch("zcode_protocol.subprocess.Popen", side_effect=OSError("spawn failed") if fail_on_spawn else None, return_value=proc), \
                    mock.patch("zcode_protocol.os.killpg", create=True):
                client = ZCodeProtocolClient("unused", "unused")
                if fail_on_spawn:
                    with self.assertRaises(OSError):
                        client.start()
                else:
                    client.start()
                    with self.assertRaises(OSError):
                        client.close()
                self.assertEqual([], list(pathlib.Path(directory).rglob("provider-*.json")))

    def test_legacy_payload_is_preserved(self):
        with mock.patch.dict("os.environ", {"ZCODE_BRIDGE_MODERN_PROTOCOL": "0"}):
            client = ZCodeProtocolClient("unused", "unused")
        original = {"runtimeModel": runtime()}
        self.assertIs(original, client._request_params("session/create", original))


if __name__ == "__main__":
    unittest.main()
