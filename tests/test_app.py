import io
import json
import subprocess
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import app
from textual.widgets import Button, Input, OptionList, TabbedContent
from textual.widgets.option_list import Option


class ShellVersionTests(unittest.TestCase):
    def test_versions(self):
        for output, expected in [
            ("GNOME Shell 50.1\n", "50.1"),
            ("GNOME Shell 3.38.6\n", "3.38.6"),
            ("GNOME Shell 49.beta\n", "49"),
        ]:
            with self.subTest(output=output):
                with patch.object(app.subprocess, "check_output", return_value=output) as command:
                    self.assertEqual(app.get_shell_version(), expected)
                    command.assert_called_once_with(['gnome-shell', '--version'], text=True)

    def test_detection_failure(self):
        for error in [FileNotFoundError(), subprocess.CalledProcessError(1, 'gnome-shell')]:
            with patch.object(app.subprocess, "check_output", side_effect=error):
                with self.assertRaises(RuntimeError):
                    app.get_shell_version()

    def test_invalid_output(self):
        with patch.object(app.subprocess, "check_output", return_value="unknown"):
            with self.assertRaises(RuntimeError):
                app.get_shell_version()


class InstallTests(unittest.TestCase):
    def setUp(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("metadata.json", '{"uuid": "online@example.org"}')
        self.archive = archive.getvalue()
        self.metadata = {"download_url": "/download-extension/online.zip?version_tag=1"}

    def test_download_before_install_and_cleanup(self):
        paths = []

        def run(command, **kwargs):
            path = Path(command[2])
            paths.append(path)
            self.assertEqual(path.read_bytes(), self.archive)
            self.assertTrue(zipfile.is_zipfile(path))
            self.assertEqual(command[:2], ['gnome-extensions', 'install'])
            self.assertEqual(command[3], '--force')
            self.assertTrue(kwargs['check'])

        with patch.object(app, "get_shell_version", return_value="50.1"):
            with patch.object(app.urllib.request, "urlopen", side_effect=[io.BytesIO(json.dumps(self.metadata).encode()), io.BytesIO(self.archive)]) as request:
                with patch.object(app.subprocess, "run", side_effect=run):
                    app.install_extension("online+test@example.org")
        params = parse_qs(urlparse(request.call_args_list[0].args[0]).query)
        self.assertEqual(params['uuid'], ['online+test@example.org'])
        self.assertEqual(params['shell_version'], ['50.1'])
        self.assertEqual(params['disable_version_validation'], ['false'])
        self.assertEqual(request.call_args_list[1].args[0], 'https://extensions.gnome.org/download-extension/online.zip?version_tag=1')
        self.assertFalse(paths[0].exists())

    def test_no_compatible_version(self):
        with patch.object(app, "get_shell_version", return_value="50"):
            with patch.object(app.urllib.request, "urlopen", return_value=io.BytesIO(b'{}')):
                with patch.object(app.subprocess, "run") as command:
                    with self.assertRaisesRegex(RuntimeError, "not available"):
                        app.install_extension("online@example.org")
                    command.assert_not_called()

    def test_invalid_download(self):
        with patch.object(app, "get_shell_version", return_value="50"):
            with patch.object(app.urllib.request, "urlopen", side_effect=[io.BytesIO(json.dumps(self.metadata).encode()), io.BytesIO(b'not a zip')]):
                with patch.object(app.subprocess, "run") as command:
                    with self.assertRaisesRegex(RuntimeError, "valid ZIP"):
                        app.install_extension("online@example.org")
                    command.assert_not_called()

    def test_cleanup_after_install_failure(self):
        paths = []

        def fail(command, **kwargs):
            paths.append(Path(command[2]))
            raise subprocess.CalledProcessError(1, command)

        with patch.object(app, "get_shell_version", return_value="50"):
            with patch.object(app.urllib.request, "urlopen", side_effect=[io.BytesIO(json.dumps(self.metadata).encode()), io.BytesIO(self.archive)]):
                with patch.object(app.subprocess, "run", side_effect=fail):
                    with self.assertRaises(subprocess.CalledProcessError):
                        app.install_extension("online@example.org")
        self.assertFalse(paths[0].exists())

    def test_network_failure_does_not_install(self):
        with patch.object(app, "get_shell_version", return_value="50"):
            with patch.object(app.urllib.request, "urlopen", side_effect=TimeoutError("Timed out")):
                with patch.object(app.subprocess, "run") as command:
                    with self.assertRaises(TimeoutError):
                        app.install_extension("online@example.org")
                    command.assert_not_called()


class InterfaceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.installed = patch.object(app, "get_installed_extensions", return_value=["local@example.org"])
        self.installed.start()
        self.info = patch.object(app, "get_extensions_info", return_value={"Name": "Local", "State": "ENABLED"})
        self.info.start()
        self.addCleanup(self.installed.stop)
        self.addCleanup(self.info.stop)
        self.application = app.GNOMEExtensionManager()
        self.context = self.application.run_test(size=(120, 40))
        self.pilot = await self.context.__aenter__()

    async def asyncTearDown(self):
        await self.context.__aexit__(None, None, None)

    async def press(self, button_id):
        button = self.application.query_one(f"#{button_id}", Button)
        await self.application.on_button_pressed(Button.Pressed(button))

    async def test_startup_and_english_title(self):
        self.assertEqual(self.application.query_one("#ext-list", OptionList).option_count, 1)
        self.assertTrue(self.application.title.isascii())
        self.assertTrue(self.application.sub_title.isascii())

    async def test_local_actions_use_local_selection(self):
        self.application.current_local_uuid = "local@example.org"
        self.application.current_online_uuid = "online@example.org"
        with patch.object(app.subprocess, "run") as command:
            await self.press("btn-enable")
            await self.press("btn-disable")
        self.assertEqual(command.call_args_list[0].args[0], ['gnome-extensions', 'enable', 'local@example.org'])
        self.assertEqual(command.call_args_list[1].args[0], ['gnome-extensions', 'disable', 'local@example.org'])

    async def test_selecting_in_both_tabs(self):
        self.application.query_one("#ext-list", OptionList).focus()
        await self.pilot.press("down", "enter")
        self.application.online_results_data = {"online@example.org": {"name": "Online"}}
        online_list = self.application.query_one("#online-ext-list", OptionList)
        online_list.add_option(Option("Online", id="online@example.org"))
        self.application.query_one(TabbedContent).active = "tab-online"
        await self.pilot.pause()
        online_list.focus()
        await self.pilot.press("down", "enter")
        self.assertEqual(self.application.current_local_uuid, "local@example.org")
        self.assertEqual(self.application.current_online_uuid, "online@example.org")

    async def test_online_selection_does_not_allow_local_actions(self):
        self.application.current_online_uuid = "online@example.org"
        with patch.object(app.subprocess, "run") as command:
            await self.press("btn-enable")
            command.assert_not_called()

    async def test_local_selection_does_not_allow_install(self):
        self.application.current_local_uuid = "local@example.org"
        with patch.object(app, "install_extension") as install:
            await self.press("btn-install")
            install.assert_not_called()

    async def test_filter_clears_hidden_selection(self):
        self.application.current_local_uuid = "local@example.org"
        self.application.query_one("#search-box", Input).value = "missing"
        await self.pilot.pause()
        self.assertIsNone(self.application.current_local_uuid)

    async def test_online_details(self):
        self.application.current_online_uuid = "online@example.org"
        self.application.online_results_data = {"online@example.org": {
            "name": "Example [test]", "description": "Description [test]",
            "shell_version_map": {"50": {"version": 7}},
        }}
        self.application.update_online_details()
        rendered = str(self.application.query_one("#online-ext-details").render())
        for value in ["Example [test]", "Description [test]", "Not installed", "7"]:
            self.assertIn(value, rendered)

    async def test_search_clears_online_selection(self):
        self.application.current_online_uuid = "old@example.org"
        field = self.application.query_one("#online-search-box", Input)
        with patch.object(app, "search_extensions_online", return_value=[]):
            await self.application.on_input_submitted(Input.Submitted(field, "missing"))
        self.assertIsNone(self.application.current_online_uuid)

    async def test_install_routes_and_refreshes(self):
        self.application.current_local_uuid = "local@example.org"
        self.application.current_online_uuid = "online@example.org"
        self.application.online_results_data = {"online@example.org": {"name": "Online"}}
        with patch.object(app, "install_extension") as install:
            with patch.object(app, "get_installed_extensions", return_value=["local@example.org", "online@example.org"]):
                with patch.object(app.subprocess, "run") as command:
                    await self.press("btn-install")
        install.assert_called_once_with("online@example.org")
        self.assertEqual(command.call_args.args[0], ['gnome-extensions', 'enable', 'online@example.org'])
        self.assertEqual(self.application.query_one("#ext-list", OptionList).option_count, 2)
        self.assertEqual(self.application.current_local_uuid, "local@example.org")

    async def test_enable_failure_after_install(self):
        self.application.current_online_uuid = "online@example.org"
        with patch.object(app, "install_extension"):
            with patch.object(app.subprocess, "run", side_effect=subprocess.CalledProcessError(1, 'enable')):
                with patch.object(self.application, "notify") as notify:
                    await self.press("btn-install")
        self.assertTrue(any(call.kwargs.get("title") == "Login required" for call in notify.call_args_list))


if __name__ == "__main__":
    unittest.main()
