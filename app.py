import asyncio
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, OptionList, Button, Static, Input, TabbedContent, TabPane
from textual.widgets.option_list import Option
import json
import urllib.request
import urllib.parse


def get_installed_extensions():
    try:
        output = subprocess.check_output(['gnome-extensions', 'list'], text = True)
        return [line.strip() for line in output.split('\n') if line.strip()]
    except Exception:
        return []

def get_extensions_info(uuid):
    try:
        output = subprocess.check_output(['gnome-extensions', 'info', uuid], text = True)
        info = {}
        for line in output.split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                info[key.strip()] = val.strip()
        return info
    except Exception:
        return {"Name": uuid, "State": "UNKNOWN", "Description": "ERR While fetch info ><"}

def search_extensions_online(query):
    safe_query = urllib.parse.quote(query)
    url = f"https://extensions.gnome.org/extension-query/?search={safe_query}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get("extensions", [])
    except Exception as e:
        return []


def get_shell_version():
    try:
        output = subprocess.check_output(['gnome-shell', '--version'], text=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Unable to detect the GNOME Shell version") from error
    version = re.search(r"\b\d+(?:\.\d+)*", output)
    if not version:
        raise RuntimeError("Unable to parse the GNOME Shell version")
    return version.group()


def install_extension(uuid):
    params = urllib.parse.urlencode({
        "uuid": uuid,
        "shell_version": get_shell_version(),
        "disable_version_validation": "false",
    })
    info_url = f"https://extensions.gnome.org/extension-info/?{params}"
    with urllib.request.urlopen(info_url, timeout=30) as response:
        detail_data = json.load(response)
    download_url = detail_data.get("download_url")
    if not download_url:
        raise RuntimeError("This extension is not available for the current GNOME version")
    full_url = urllib.parse.urljoin("https://extensions.gnome.org/", download_url)
    with tempfile.TemporaryDirectory(prefix="gnome-extension-") as temp_dir:
        zip_path = Path(temp_dir) / "extension.zip"
        with urllib.request.urlopen(full_url, timeout=30) as response:
            with zip_path.open("wb") as archive:
                shutil.copyfileobj(response, archive)
        if not zipfile.is_zipfile(zip_path):
            raise RuntimeError("The downloaded file is not a valid ZIP archive")
        subprocess.run(
            ['gnome-extensions', 'install', str(zip_path), '--force'],
            check=True, capture_output=True, text=True,
        )


#-------UI Elements---------

class ExtensionDetails(Static):
    def update_info(self, info):
        name = info.get("Name", "Unknown")
        state = info.get("State", "Unknown")
        desc = info.get("Description", "No Description")
        version = info.get("Version", "N/A")
        
        state_color = "green" if state == "ENABLED" else "red"

        content = f"[b]{escape(str(name))}[/b]\n\n"
        content += f"[b]Status:[/b] [{state_color}]{escape(str(state))}[/{state_color}]\n"
        content += f"[b]Version:[/b] {escape(str(version))}\n\n"
        content += escape(str(desc))

        self.update(content)

#-------Main Code---------------
class GNOMEExtensionManager(App):
    TITLE = "GNomeEXention_manager_tui"
    SUB_TITLE = "GNOME Extension Manager"

    CSS = """
    .left-pane {
        width: 40%;
        border-right: solid $primary;
    }
    .right-pane {
        width: 60%;
        padding: 1 2;
    }
    #action-buttons {
        height: 3;
        margin-top: 2;
    }
    Button {
        margin-right: 2;
    }
    #search-box{
        dock:bottom;
    }
    """
    BINDINGS = [("q", "quit")]

    def __init__(self):
        super().__init__()
        self.current_local_uuid = None
        self.current_online_uuid = None
        self.all_uuids = []
        self.online_results_data = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-local"):
            with TabPane("Local Extensions", id = "tab-local"):
                with Horizontal():
                    with Vertical(classes="left-pane"):
                        yield OptionList(id = "ext-list")
                        yield Input(placeholder = "input something to search", id = "search-box")
                    with Vertical(classes="right-pane"):
                        yield ExtensionDetails("Choose an extension from left pane", id="ext-details")
                        with Horizontal(id="action-buttons"):
                            yield Button("Enable", id="btn-enable", variant="success")
                            yield Button("Disable", id="btn-disable", variant="error")
            with TabPane("Online Search", id = "tab-online"):
                with Horizontal():
                    with Vertical(classes="left-pane"):
                        yield Input(placeholder = "Search Extensions from web: Input Keyword and press Enter", id = "online-search-box")
                        yield OptionList(id = "online-ext-list")
                    with Vertical(classes="right-pane"):
                        yield ExtensionDetails("Select a Extension to see Details", id = "online-ext-details")
                        yield Button("Install", id = "btn-install", variant = "primary")
        yield Footer()
    def update_list(self, uuids_to_show):
        if self.current_local_uuid not in uuids_to_show:
            self.current_local_uuid = None
            self.query_one("#ext-details", ExtensionDetails).update("Choose an extension from left pane")
        ext_list = self.query_one("#ext-list", OptionList)

        ext_list.clear_options()
        for uuid in uuids_to_show:
            ext_list.add_option(Option(uuid, id = uuid))
    
    def on_mount(self):
        self.all_uuids = get_installed_extensions()
        self.update_list(self.all_uuids)

    def on_input_changed(self, event: Input.Changed):
        if event.input.id != "search-box":
            return
        search_text = event.value.lower()
        if not search_text:
            self.update_list(self.all_uuids)
        else:
            filtered_uuids = [uuid for uuid in self.all_uuids if search_text in uuid.lower()]
            self.update_list(filtered_uuids)
    
    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        if event.option_list.id == "ext-list":
            self.current_local_uuid = event.option.id
            info = get_extensions_info(self.current_local_uuid)
            self.query_one("#ext-details", ExtensionDetails).update_info(info)
        elif event.option_list.id == "online-ext-list":
            self.current_online_uuid = event.option.id
            self.update_online_details()

    def update_online_details(self):
        if self.current_online_uuid:
            ext_data = self.online_results_data.get(self.current_online_uuid, {})
            versions = sorted({
                str(value["version"])
                for value in ext_data.get("shell_version_map", {}).values()
                if "version" in value
            })
            info = {
                "Name": ext_data.get("name", "Unknown"),
                "State": "Installed" if self.current_online_uuid in self.all_uuids else "Not installed",
                "Description": ext_data.get("description", "No Description"),
                "Version": str(ext_data.get("version", ", ".join(versions) or "N/A")),
            }
            self.query_one("#online-ext-details", ExtensionDetails).update_info(info)

    async def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        if button_id not in {"btn-enable", "btn-disable", "btn-install"}:
            return
        uuid = self.current_online_uuid if button_id == "btn-install" else self.current_local_uuid
        if not uuid:
            self.notify("Choose an extension in this tab first", severity="warning")
            return
        try:
            if button_id == "btn-enable":
                subprocess.run(['gnome-extensions', 'enable', uuid], check=True)
                self.notify(f"Successfully enabled {uuid}", title="Enabled")
            elif button_id == "btn-disable":
                subprocess.run(['gnome-extensions', 'disable', uuid], check=True)
                self.notify(f"Successfully disabled {uuid}", title="Disabled")
            elif button_id == "btn-install":
                self.notify("Downloading and installing... Please wait...")
                await asyncio.to_thread(install_extension, uuid)
                try:
                    subprocess.run(['gnome-extensions', 'enable', uuid], check=True, capture_output=True)
                    self.notify("Installed and enabled", title="Finished")
                except subprocess.CalledProcessError:
                    self.notify("Installed successfully. Log out and log in again, then enable the extension.", title="Login required", severity="warning", timeout=5)
                self.all_uuids = get_installed_extensions()
                search_text = self.query_one("#search-box", Input).value.lower()
                self.update_list([item for item in self.all_uuids if search_text in item.lower()])
                self.update_online_details()
        except Exception as e:
            self.notify(f"Operation failed:{e}", severity = "warning", title = "error")
        if self.current_local_uuid:
            info = get_extensions_info(self.current_local_uuid)
            self.query_one("#ext-details", ExtensionDetails).update_info(info)

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "online-search-box":
            search_text =  event.value.strip()
            if not search_text:
                return
            self.notify(f"searching online...{search_text}")
            results = await asyncio.to_thread(search_extensions_online, search_text)
            online_list = self.query_one("#online-ext-list", OptionList)
            online_list.clear_options()
            self.online_results_data.clear()
            self.current_online_uuid = None
            self.query_one("#online-ext-details", ExtensionDetails).update("Select an extension to see details")
            if not results:
                self.notify("Can't find any extensions QwQ", severity = "warning")
                return
            for ext in results:
                display_text = f"{ext.get('name')} (Author: {ext.get('creator')})"
                uuid = ext.get('uuid')
                if not uuid or uuid in self.online_results_data:
                    continue
                self.online_results_data[uuid] = ext
                online_list.add_option(Option(display_text, id = uuid))
            self.notify(f"Found {len(results)} Extensions!!", title = "search complete")

if __name__ == "__main__":
    app = GNOMEExtensionManager()
    app.run()
