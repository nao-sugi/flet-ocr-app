# export.py (完全な置換用コード)

import flet as ft
from models import get_db, OcrList, ScannedData, UploadedFile
from sqlalchemy.orm import joinedload
import io
import csv
from openpyxl import Workbook
import logging # loggingモジュールを追加

# ロガーの設定 (コンソールにDEBUGレベル以上を出力)
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class ExportScreen:
    def __init__(self, page: ft.Page):
        self.page = page
        self.db_context = get_db
        self.selected_ocr_list_id = None
        self.selected_file_type = "CSV"
        
        # ファイルデータを一時的に保持する変数
        self.bytes_to_save = None
        
        # FilePickerをインスタンス変数として保持。build_contentで初期化。
        self.save_file_dialog = None

        # --- UI Controls (FilePicker以外) ---

        # --- UI Controls (FilePicker以外) ---
        self.ocr_list_dropdown = ft.Dropdown(
            hint_text="OCRリストを選択",
            options=[],
            on_change=self._on_ocr_list_change,
            expand=True,
        )
        self.file_type_dropdown = ft.Dropdown(
            hint_text="出力ファイル形式を選択",
            options=[ft.dropdown.Option("CSV"), ft.dropdown.Option("Excel")],
            value=self.selected_file_type,
            on_change=self._on_file_type_change,
            expand=True,
        )
        self.download_button = ft.ElevatedButton(
            #"ダウンロード",
            #icon=ft.Icons.DOWNLOAD,
            #on_click=self._show_save_dialog,
            "ファイルを保存",
            icon=ft.Icons.SAVE, # アイコンを保存に変更
            on_click=self._initiate_save_file, # メソッド名を変更
            disabled=True,
        )
        self.files_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text("ダウンロードしたいOCRリストを選択してください"))],
            rows=[],
            expand=True,
            # show_checkbox_column=True # チェックボックスカラムを削除
        )
        self._load_ocr_lists()

    def refresh(self):
        logger.debug("ExportScreen: refresh called")
        self._load_ocr_lists()
        if self.selected_ocr_list_id:
            self._load_files_table()
        elif hasattr(self, 'files_table') and self.files_table.page:
            self.files_table.columns = [ft.DataColumn(ft.Text("ダウンロードしたいOCRリストを選択してください"))]
            self.files_table.rows = []
            self.files_table.update()
            
    def _load_ocr_lists(self):
        db = next(self.db_context())
        logger.debug("ExportScreen: _load_ocr_lists called")
        try:
            lists = db.query(OcrList).order_by(OcrList.name).all()
            current_value = self.ocr_list_dropdown.value
            self.ocr_list_dropdown.options = [ft.dropdown.Option(key=str(l.id), text=l.name) for l in lists]
            if not any(opt.key == current_value for opt in self.ocr_list_dropdown.options):
                 self.ocr_list_dropdown.value = None
                 self.selected_ocr_list_id = None
            if self.ocr_list_dropdown.page:
                self.ocr_list_dropdown.update()
        finally:
            db.close()

    def _on_ocr_list_change(self, e: ft.ControlEvent):
        logger.debug(f"ExportScreen: _on_ocr_list_change, value: {e.control.value}")
        if e.control.value:
            self.selected_ocr_list_id = int(e.control.value)
            self._load_files_table()
            self.download_button.disabled = False
        else:
            self.selected_ocr_list_id = None
            self.files_table.columns = [ft.DataColumn(ft.Text("ダウンロードしたいOCRリストを選択してください"))]
            self.files_table.rows = []
            self.download_button.disabled = True
        if self.page:
            self.files_table.update()
            self.download_button.update()

    def _on_file_type_change(self, e: ft.ControlEvent):
        logger.debug(f"ExportScreen: _on_file_type_change, value: {e.control.value}")
        self.selected_file_type = e.control.value

    def _load_files_table(self):
        logger.debug(f"ExportScreen: _load_files_table for ocr_list_id: {self.selected_ocr_list_id}")
        if not self.selected_ocr_list_id:
            return

        db = next(self.db_context())
        try:
            # 効率的なクエリ
            scanned_files = (
                db.query(UploadedFile)
                .filter(UploadedFile.ocr_list_id == self.selected_ocr_list_id, UploadedFile.is_scanned == True)
                .options(joinedload(UploadedFile.scanned_data))
                .all()
            )

            if not scanned_files:
                self.files_table.columns = [ft.DataColumn(ft.Text("スキャン済みのファイルがありません"))]
                self.files_table.rows = []
                logger.debug("ExportScreen: No scanned files found for this OCR list.")
                if self.files_table.page: self.files_table.update()
                return

            all_data_items_names = set()
            for file in scanned_files:
                for data_entry in file.scanned_data:
                    all_data_items_names.add(data_entry.data_item_name)
            
            sorted_data_item_names = sorted(list(all_data_items_names))
            self.files_table.columns = [ft.DataColumn(ft.Text("ファイル名"))] + [ft.DataColumn(ft.Text(item_name)) for item_name in sorted_data_item_names]
            logger.debug(f"ExportScreen: Table columns set: {[col.label.value for col in self.files_table.columns]}")

            self.files_table.rows = []
            for file in scanned_files:
                row_cells_text = [file.filename]
                file_scan_map = {data.data_item_name: data.extracted_value for data in file.scanned_data}
                for item_name in sorted_data_item_names:
                    row_cells_text.append(file_scan_map.get(item_name, "")) # 該当なしは空文字
                # DataRowのselectedプロパティを初期化
                self.files_table.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(cell_value)) for cell_value in row_cells_text])) # selectedプロパティを削除
            logger.debug(f"ExportScreen: Table rows added: {len(self.files_table.rows)}")
        finally:
            db.close()
        if self.files_table.page:
            self.files_table.update()

    def _initiate_save_file(self, e: ft.ControlEvent):
        print("--- ExportScreen: _initiate_save_file CALLED (print) ---") # ★最優先で確認するログ
        logger.debug("ExportScreen: _initiate_save_file called.")
        if not self.selected_ocr_list_id or not self.files_table.rows:
            logger.warning("ExportScreen: No data to export (no OCR list selected or no rows in table).")
            self.page.snack_bar = ft.SnackBar(ft.Text("エクスポートするデータがありません。"), open=True)
            self.page.update()
            return
        
        if self.save_file_dialog is None:
            logger.error("ExportScreen: self.save_file_dialog is None. It should have been initialized in build_content.")
            self.page.snack_bar = ft.SnackBar(ft.Text("ファイル保存機能の初期化に問題があります。画面を再読み込みしてください。"), open=True, bgcolor=ft.colors.ERROR)
            self.page.update()
            return

        active_file_picker = self.save_file_dialog
        logger.debug(f"ExportScreen: Using self.save_file_dialog: {active_file_picker}")
        if active_file_picker.on_result != self._on_save_result:
             logger.warning(f"ExportScreen: Mismatch in on_result! Expected {self._on_save_result}, got {active_file_picker.on_result}") # 注意: ログレベル

        # DataTableのすべての行をエクスポート対象とする
        all_rows_data = self.files_table.rows
        logger.debug(f"ExportScreen: Number of rows to export: {len(all_rows_data)}")
        if not all_rows_data:
            logger.warning("ExportScreen: No rows in table to export.")
            self.page.snack_bar = ft.SnackBar(ft.Text("エクスポートするデータがテーブルにありません。"), open=True)
            self.page.update()
            return

        header = [col.label.value for col in self.files_table.columns]
        export_data_rows = [header] + [[cell.content.value for cell in row.cells] for row in all_rows_data]
        logger.debug(f"ExportScreen: Data prepared for export. Header: {header}, Rows: {len(export_data_rows)-1}")

        try:
            if self.selected_file_type == "CSV":
                buffer = io.StringIO()
                writer = csv.writer(buffer)
                writer.writerows(export_data_rows)
                self.bytes_to_save = buffer.getvalue().encode("utf-8-sig") # BOM付きUTF-8でExcelでの文字化けを防ぐ
                file_ext = "csv"
            else:
                buffer = io.BytesIO()
                wb = Workbook()
                ws = wb.active
                for row_data in export_data_rows:
                    ws.append(row_data)
                wb.save(buffer)
                self.bytes_to_save = buffer.getvalue()
                file_ext = "xlsx"
            logger.info(f"ExportScreen: File content generated for {self.selected_file_type}. Size: {len(self.bytes_to_save)} bytes.")

            # OCRリスト名を取得（ファイル名に使用）
            ocr_list_name_option = next((opt for opt in self.ocr_list_dropdown.options if opt.key == str(self.selected_ocr_list_id)), None)
            ocr_list_name = ocr_list_name_option.text.replace(" ", "_") if ocr_list_name_option else "export"
            download_filename = f"{ocr_list_name}.{file_ext}"
            logger.debug(f"ExportScreen: Proposed download filename: {download_filename}")

            active_file_picker.save_file(
                dialog_title="ファイルを保存",
                file_name=download_filename,
                file_type=ft.FilePickerFileType.ANY,
                allowed_extensions=[file_ext] # ユーザーに適切な拡張子を提示
            )
            logger.info("ExportScreen: save_file dialog initiated.")
        except Exception as ex:
            logger.error(f"ExportScreen: Error during file content generation or save_file call: {ex}", exc_info=True)
            self.page.snack_bar = ft.SnackBar(ft.Text(f"ファイル生成中にエラー: {ex}"), open=True, bgcolor=ft.Colors.ERROR)
            self.page.update()

    def _on_save_result(self, e: ft.FilePickerResultEvent):
        logger.info(f"ExportScreen: _on_save_result called. Path: {e.path}") # e.errorへのアクセスを削除

        if not e.path:  # ユーザーがダイアログをキャンセルしたか、ダイアログでエラーが発生した場合
            logger.info("ExportScreen: File save cancelled or dialog error (no file selected).")
            self.page.snack_bar = ft.SnackBar(ft.Text("ファイル保存がキャンセルされました。"), open=True)  # より一般的なメッセージに変更
        elif e.path and self.bytes_to_save:  # e.path のチェックは、以前のコードのままで問題ありません
            try:
                with open(e.path, "wb") as f:
                    f.write(self.bytes_to_save)
                logger.info(f"ExportScreen: File saved successfully to {e.path}")
                self.page.snack_bar = ft.SnackBar(ft.Text(f"ファイルを保存しました: {e.path}"), open=True)
            except Exception as ex:
                logger.error(f"ExportScreen: Error writing file to disk: {ex}", exc_info=True)
                self.page.snack_bar = ft.SnackBar(ft.Text(f"ファイル保存エラー: {ex}"), open=True, bgcolor=ft.Colors.ERROR)
        elif e.path and not self.bytes_to_save: # 通常は起こり得ないはず
            logger.warning("ExportScreen: Save path provided, but no bytes_to_save. This indicates a logic error.")
            self.page.snack_bar = ft.SnackBar(ft.Text("保存するデータが準備されていませんでした。"), open=True, bgcolor=ft.colors.WARNING)
        else:
            # e.path is None (ユーザーがダイアログをキャンセルした場合)
            logger.info("ExportScreen: File save cancelled by user.")
            if not self.bytes_to_save and not e.error: # データ準備前にキャンセルされた場合など
                self.page.snack_bar = ft.SnackBar(ft.Text("ファイル保存がキャンセルされました。"), open=True)
            # bytes_to_save があるのに e.path がない場合はキャンセル

        self.bytes_to_save = None
        self.page.update()

    def build_content(self) -> ft.Column:
        print("--- ExportScreen: build_content CALLED (print) ---")
        logger.debug("ExportScreen: build_content called.")
        
        # FilePickerインスタンスを生成または再利用し、self.save_file_dialogに格納
        # on_resultコールバックもここで再確認
        self.save_file_dialog = ft.FilePicker(on_result=self._on_save_result)
        print(f"--- ExportScreen: Created self.save_file_dialog: {self.save_file_dialog} with on_result: {self.save_file_dialog.on_result} (print) ---")
        logger.debug(f"ExportScreen: Created self.save_file_dialog: {self.save_file_dialog} with on_result: {self.save_file_dialog.on_result}")
        
        # この画面のFilePickerがpage.overlayになければ追加する
        # ui_components.pyのchange_viewでoverlay.clear()が呼ばれる前提
        if self.page and hasattr(self.page, 'overlay'):
            if self.save_file_dialog not in self.page.overlay:
                self.page.overlay.append(self.save_file_dialog)
                print(f"--- ExportScreen: Appended self.save_file_dialog to page.overlay. Current overlay: {self.page.overlay} (print) ---")
                logger.debug(f"ExportScreen: Appended self.save_file_dialog to page.overlay. Current overlay: {self.page.overlay}")
            else:
                print(f"--- ExportScreen: self.save_file_dialog ALREADY in page.overlay. Current overlay: {self.page.overlay} (print) ---")
                logger.debug(f"ExportScreen: self.save_file_dialog already in page.overlay. Current overlay: {self.page.overlay}")
        else:
            logger.warning("ExportScreen: self.page or self.page.overlay is not available in build_content.")

        print(f"--- ExportScreen: download_button.on_click IS: {self.download_button.on_click} (print) ---")
        logger.debug(f"ExportScreen: download_button.on_click is: {self.download_button.on_click}")
        
        return ft.Column(
            expand=True,
            spacing=15,
            controls=[
                ft.Text("データエクスポート", size=24, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text("OCRリスト:", width=100, size=16, weight=ft.FontWeight.BOLD),
                    self.ocr_list_dropdown,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    ft.Text("出力形式:", width=100, size=16, weight=ft.FontWeight.BOLD),
                    self.file_type_dropdown,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.download_button,
                ft.Divider(height=10),
                self.files_table,
            ],
        )