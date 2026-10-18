import subprocess
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
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get("extensions", [])
    except Exception as e:
        return []


def get_shell_version():
    try:
        output = subprocess.check_output(['gnome-shell', '--version'], check = True)
        return output.strip().split(' ')[2].split('.')[0]
    except Exception:
        return "50"


#-------UI Elements---------

class ExtensionDetails(Static):
    def update_info(self, info):
        name = info.get("Name", "Unknown")
        state = info.get("State", "Unknown")
        desc = info.get("Description", "No Description")
        version = info.get("Version", "N/A")
        
        state_color = "green" if state == "ENABLED" else "red"

        content = f"[b]{name}[/b]\n\n"
        content += f"[b]Status:[/b] [{state_color}]{state}[/{state_color}]\n"
        content += f"[b]Version:[/b] {version}\n\n"
        content += f"{desc}"

        self.update(content)

#-------Main Code---------------
class GNOMEExtensionManager(App):
    TITLE = "GNomeEXention_manager_tui"
    SUB_TITLE = "GNOME 擴充套件管理器"

    CSS = """
    #left-pane {
        width: 40%;
        border-right: solid ascii;
    }
    #right-pane {
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
        self.current_uuid = None
        self.all_uuids = []
        self.online_results_data = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-local"):
            with TabPane("Local Extensions", id = "tab-local"):
                with Horizontal():
                    with Vertical(id="left-pane"):
                        yield OptionList(id = "ext-list")
                        yield Input(placeholder = "input something to search", id = "search-box")
                    with Vertical(id="right-pane"):
                        yield ExtensionDetails("Choose an extension from left pane", id="ext-details")
                        with Horizontal(id="action-buttons"):
                            yield Button("Enable", id="btn-enable", variant="success")
                            yield Button("Disable", id="btn-disable", variant="error")
            with TabPane("Online Search", id = "tab-online"):
                with Horizontal():
                    with Vertical(id = "left-pane"):
                        yield Input(placeholder = "Search Extensions from web: Input Keyword and press Enter", id = "online-search-box")
                        yield OptionList(id = "online-ext-list")
                    with Vertical(id = "right-pane"):
                        yield ExtensionDetails("Select a Extension to see Details", id = "online-ext-details")
                        yield Button("Install", id = "btn-install", variant = "primary")
        yield Footer()
    def update_list(self, uuids_to_show):
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
            self.current_uuid = event.option.id
            info = get_extensions_info(self.current_uuid)
            self.query_one("#ext-details", ExtensionDetails).update_info(info)
        elif event.option_list.id == "online-ext-list":
            self.current_uuid = event.option.id
            ext_data = self.online_results_data.get(self.current_uuid, {})
            info = {
                "name": ext_data.get("Name", "Unknown"),
                "Stats": "Not installed",
                "Description": ext_data.get("Description", "No Description"),
                "Version": str(ext_data.get("Version", "N/A"))
            }
            self.query_one("#online-ext-details", ExtensionDetails).update_info(info)

    def on_button_pressed(self, event: Button.Pressed):
        if not self.current_uuid:
            self.notify("Choose a extensions from left pane", severity = "warning")
            return
        button_id = event.button.id
        try:
            if button_id == "btn-enable":
                subprocess.run(['gnome-extensions','enable', self.current_uuid], check = True)
                self.notify(f"successful enabled {self.current_uuid}", title = "Enabled")
            elif button_id == "btn-disable":
                subprocess.run(['gnome-extensions','disable', self.current_uuid], check = True)
                self.notify(f"successful disabled {self.current_uuid}", title = "Disabled", severity = "error")
            elif button_id == "btn-install":
                self.notify("Searching Package Online...", severity = "information")

                shell_version = get_shell_version()
                info_url = f"https://extensions.gnome.org/extension-info/?uuid={self.current_uuid}&shell_version={shell_version}"

                req = urllib.request.Request(info_url)
                with urllib.request.urlopen(req) as response:
                    detail_data = json.loads(response.read().decode('utf-8'))
                
                download_url = detail_data.get("download_url")
                if not download_url:
                    self.notify("This extension is not avaliable for current GNOME version", severity = "error")
                    return
                
                self.notify("Downloading...Please wait...")
                full_url = f"https://extensions.gnome.org{download_url}"
                zip_path = f"/tmp/{self.current_uuid}.zip"

                subprocess.run(['gnome-extensions', 'install', zip_path, '--force'], check=True, capture_output=True)

                try:
                    subprocess.run(['gnome-extensions', 'enable', self.current_uuid], check = True, capture_output = True)
                    self.notify("Install and enabled", title = "Finished")
                except subprocess.CalledProcessError:
                    self.notify("Successfully installed ! but the task failed when enabled the extension\n please reboot or re-login and try enable from local list", title="Reboot or re-login needed", severity="warning", timeout=5)



        except Exception as e:
            self.notify(f"Operation failed:{e}", severity = "warning", title = "error")
        
        info = get_extensions_info(self.current_uuid)
        self.query_one("#ext-details", ExtensionDetails).update_info(info)

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "online-search-box":
            search_text =  event.value.strip()
            if not search_text:
                return
            self.notify(f"searching online...{search_text}")
            results = search_extensions_online(search_text)
            online_list = self.query_one("#online-ext-list", OptionList)
            online_list.clear_options()
            self.online_results_data.clear()
            if not results:
                self.notify("Can't find any extensions QwQ", severity = "warning")
                return
            for ext in results:
                display_text = f"{ext.get('name')} (Author: {ext.get('creator')})"
                uuid = ext.get('uuid')
                self.online_results_data[uuid] = ext
                online_list.add_option(Option(display_text, id = uuid))
            self.notify(f"Found {len(results)} Extensions!!", title = "search complete")

if __name__ == "__main__":
    app = GNOMEExtensionManager()
    app.run()
