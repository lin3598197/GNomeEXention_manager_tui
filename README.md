# GNomeEXention_manager_tui

使用終端機管理 GNOME Shell 擴充套件的文字介面（TUI）工具，以 Python 與 [Textual](https://textual.textualize.io/) 開發。

## 功能

- **本機套件清單**：列出已安裝的 GNOME Shell 擴充套件。
- **本機搜尋**：依套件的 UUID 即時篩選清單。
- **詳細資訊**：查看本機套件的名稱、狀態、版本與說明。
- **啟用與停用**：透過按鈕切換所選本機套件的狀態。
- **線上搜尋**：在「Online Search」分頁搜尋 [GNOME Extensions](https://extensions.gnome.org/) 上的套件。線上詳細資訊與安裝功能仍有已知問題，請參閱下方限制。

## 執行環境

- Linux 與 GNOME 桌面環境，請在已登入的 GNOME 桌面工作階段內執行。
- 從原始碼執行時，需要 Python 3、`pip` 與 `venv`，並安裝 `requirements.txt` 中的相依套件。
- 系統須提供 `gnome-extensions` 指令，並可從終端機執行；程式也會嘗試透過 `gnome-shell --version` 取得 GNOME 版本。
- 使用線上搜尋時需要網路連線。

## 從原始碼安裝與執行

```bash
git clone https://github.com/lin3598197/GNomeEXention_manager_tui.git
cd GNomeEXention_manager_tui
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

程式入口為 `app.py`。

之後再次啟動時，進入本機的專案資料夾並啟用虛擬環境即可：

```bash
cd GNomeEXention_manager_tui
source .venv/bin/activate
python app.py
```

若將專案放在其他路徑，請將 `cd` 後的路徑改為實際位置。

## 執行已發布的 AppImage

1. 前往 [Releases 頁面](https://github.com/lin3598197/GNomeEXention_manager_tui/releases)下載適用的 AppImage。目前 v1.0.0 提供 x86_64 版本。
2. 在 GNOME 桌面環境中開啟終端機，切換到下載檔案所在的資料夾。
3. 加上執行權限後啟動：

```bash
chmod +x gnex_cli-x86_64.AppImage
./gnex_cli-x86_64.AppImage
```

既有 v1.0.0 發布檔仍使用舊名稱 `gnex_cli-x86_64.AppImage`，因此上述指令保留實際檔名。已發布的 AppImage 不會隨原始碼修改而自動更新。

## 操作方式

- **分頁**：切換「Local Extensions」（本機套件）與「Online Search」（線上搜尋）。
- **滑鼠**：點選清單中的套件查看資訊，再點選「Enable」（啟用）或「Disable」（停用）。
- **鍵盤**：使用 `↑`、`↓` 移動清單游標，按 `Enter` 選取套件並載入資訊；使用 `Tab` 切換焦點，在按鈕上按 `Enter` 執行操作。
- **本機搜尋**：在本機分頁下方的搜尋欄輸入 UUID 的部分文字，即可篩選清單。
- **線上搜尋**：在線上分頁輸入關鍵字並按 `Enter`，即可載入搜尋結果。
- **離開**：按 `q` 結束程式；若焦點位於文字輸入欄，請先按 `Tab` 移出輸入欄。

## 已知問題與限制

- **線上安裝尚未完成**：目前程式取得下載網址後，未實際下載 ZIP，就直接執行安裝指令；一般情況下會因找不到安裝檔而失敗。
- **GNOME 版本偵測有誤**：目前版本偵測函式的 `subprocess.check_output` 參數及輸出處理有問題，會落入例外處理並回傳固定值 `50`，可能導致套件相容性判斷不正確。
- **線上詳細資訊顯示不正確**：搜尋結果與詳細資訊元件使用的欄位名稱不一致，可能顯示「Unknown」或缺少說明。
- **本機與線上分頁共用選取狀態**：切換分頁後，按鈕可能操作到另一分頁先前選取的 UUID。

## 問題回報

如有問題或功能建議，歡迎至 [Issues](https://github.com/lin3598197/GNomeEXention_manager_tui/issues) 回報。請附上 GNOME 版本、Python 版本、重現步驟與錯誤訊息，方便查明原因。

## AI 使用說明

本專案使用 AI 協助修改程式、除錯、翻譯與撰寫文件。
