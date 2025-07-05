import flet as ft
from models import get_db, OcrList, UploadedFile
from sqlalchemy.orm import joinedload
import os
import shutil
import uuid

# プロジェクトのベースディレクトリを取得
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# UPLOAD_DIR を 'images' フォルダに設定
UPLOAD_DIR_NAME = "images"
UPLOAD_BASE_DIR = os.path.join(APP_BASE_DIR, UPLOAD_DIR_NAME)

if not os.path.exists(UPLOAD_BASE_DIR):
    os.makedirs(UPLOAD_BASE_DIR)

class FileManagerScreen:
    def __init__(self, page: ft.Page):
        self.page = page
        self.db_context = get_db
        self.selected_ocr_list_id = None
        self.file_checkboxes = {}

        # --- UI Controls ---
        self.ocr_list_dropdown = ft.Dropdown(
            hint_text="OCRリストを選択",
            options=[],
            on_change=self._on_ocr_list_change,
            expand=True
        )

        self.file_picker = ft.FilePicker(on_result=self._on_files_picked)

                # モダンなデザインのアップロードボタンに変更
        self.upload_button = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, color=ft.Colors.PRIMARY, size=24),
                    ft.Text("クリックしてファイルを選択", color=ft.Colors.PRIMARY, weight=ft.FontWeight.BOLD, size=16),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=15,
            ),
            height=100,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
            border=ft.border.all(2, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)),
            border_radius=10,
            ink=True,
            on_click=lambda _: self.file_picker.pick_files(
                allow_multiple=True,
                allowed_extensions=["png", "jpg", "jpeg", "pdf"]
            ),
            tooltip="PNG, JPG, PDF ファイルを複数選択できます"
        )

        self.select_all_checkbox = ft.Checkbox(label="一括選択/解除", on_change=self._toggle_select_all_files, disabled=True)
        self.delete_selected_button = ft.ElevatedButton(
            "選択したファイルを削除",
            icon=ft.Icons.DELETE_SWEEP,
            on_click=self._delete_selected_files_action,
            disabled=True,
            style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_700)
        )

        self.files_table_area = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=5)
        
        # --- 初期データの読み込み ---
        self._load_ocr_lists()

    def refresh(self):
        """画面が表示されたときにデータを再読み込みするためのメソッド"""
        self._load_ocr_lists()
        if self.selected_ocr_list_id:
            self._load_files_for_list()

    def _get_ocr_list_upload_dir(self, ocr_list_id: int) -> str:
        """特定のOCRリスト用のアップロードディレクトリパスを取得し、存在しなければ作成します。"""
        if ocr_list_id is None:
            return None
        list_upload_dir = os.path.join(UPLOAD_BASE_DIR, str(ocr_list_id))
        if not os.path.exists(list_upload_dir):
            os.makedirs(list_upload_dir)
        return list_upload_dir

    def _load_ocr_lists(self):
        db = next(self.db_context())
        try:
            lists = db.query(OcrList).order_by(OcrList.name).all()
            new_options = [
                ft.dropdown.Option(key=str(l.id), text=l.name) for l in lists
            ]
            current_value = self.ocr_list_dropdown.value
            self.ocr_list_dropdown.options = new_options

            # 削除などで現在の値が無効になった場合、選択をリセット
            if not any(opt.key == current_value for opt in new_options):
                self.ocr_list_dropdown.value = None
                self.selected_ocr_list_id = None
            
            if self.ocr_list_dropdown.page:
                self.ocr_list_dropdown.update()
        finally:
            db.close()

    def _on_ocr_list_change(self, e: ft.ControlEvent):
        if e.control.value:
            self.selected_ocr_list_id = int(e.control.value)
            self._load_files_for_list()
            self.select_all_checkbox.disabled = False
        else:
            self.selected_ocr_list_id = None
            self.files_table_area.controls.clear()
            self.select_all_checkbox.value = False
            self.select_all_checkbox.disabled = True
            if self.files_table_area.page:
                self.files_table_area.update()
            if self.select_all_checkbox.page:
                self.select_all_checkbox.update()
        self._update_delete_selected_button_state()

    def _load_files_for_list(self):
        self.files_table_area.controls.clear()
        self.file_checkboxes.clear()
        if not self.selected_ocr_list_id:
            if self.files_table_area.page: self.files_table_area.update()
            self._update_delete_selected_button_state()
            self.select_all_checkbox.disabled = True
            if self.select_all_checkbox.page: self.select_all_checkbox.update()
            return

        self.select_all_checkbox.disabled = False
        if self.select_all_checkbox.page: self.select_all_checkbox.update()

        db = next(self.db_context())
        try:
            files = db.query(UploadedFile).filter(UploadedFile.ocr_list_id == self.selected_ocr_list_id).order_by(UploadedFile.filename).all()
            if not files:
                self.files_table_area.controls.append(ft.Container(ft.Text("このリストにはファイルがありません。", text_align=ft.TextAlign.CENTER), padding=20))
            else:
                for f_obj in files:
                    checkbox = ft.Checkbox(data=f_obj.id, on_change=self._on_file_checkbox_change)
                    self.file_checkboxes[f_obj.id] = checkbox
                    row = ft.Row([
                        checkbox,
                        ft.Text(f_obj.filename, expand=True, tooltip=f_obj.filename),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="削除", data=f_obj, on_click=self._delete_single_file_action)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    container = ft.Container(row, border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.BLACK12)), padding=ft.padding.symmetric(vertical=2, horizontal=5))
                    self.files_table_area.controls.append(container)
        finally:
            db.close()
        
        if self.files_table_area.page:
            self.files_table_area.update()
        self._update_delete_selected_button_state()
        self.select_all_checkbox.value = False
        if self.select_all_checkbox.page:
            self.select_all_checkbox.update()

    def _on_files_picked(self, e: ft.FilePickerResultEvent):
        if not self.selected_ocr_list_id:
            self.page.snack_bar = ft.SnackBar(ft.Text("先にOCRリストを選択してください。"), open=True)
            self.page.update()
            return
        if e.files:
            self._save_picked_files(e.files)

    def _save_picked_files(self, picked_files: list):
        list_upload_dir = self._get_ocr_list_upload_dir(self.selected_ocr_list_id)
        if not list_upload_dir:
            return

        db = next(self.db_context())
        saved_count = 0
        try:
            for picked_file in picked_files:
                original_filename = picked_file.name
                source_path = picked_file.path
                file_ext = os.path.splitext(original_filename)[1].lower()

                unique_filename = f"{uuid.uuid4()}{file_ext}"
                save_path_absolute = os.path.join(list_upload_dir, unique_filename)
                
                db_filepath = os.path.join(UPLOAD_DIR_NAME, str(self.selected_ocr_list_id), unique_filename).replace("\\", "/")

                shutil.copy(source_path, save_path_absolute)

                new_file_db = UploadedFile(
                    filename=original_filename,
                    filepath=db_filepath,
                    filetype=file_ext.replace(".", ""),
                    ocr_list_id=self.selected_ocr_list_id
                )
                db.add(new_file_db)
            db.commit()
            saved_count = len(picked_files)
            self.page.snack_bar = ft.SnackBar(ft.Text(f"{saved_count} 個のファイルをアップロードしました。"), open=True)
        except Exception as ex:
            db.rollback()
            print(f"Error saving files: {ex}")
        finally:
            db.close()
        
        if saved_count > 0:
            self._load_files_for_list()
            self.page.update()

    def _delete_single_file_action(self, e: ft.ControlEvent):
        file_to_delete: UploadedFile = e.control.data
        self._execute_delete([file_to_delete.id])

    def _delete_selected_files_action(self, e: ft.ControlEvent):
        selected_file_ids = [fid for fid, checkbox in self.file_checkboxes.items() if checkbox.value]
        if not selected_file_ids:
            self.page.snack_bar = ft.SnackBar(ft.Text("削除するファイルが選択されていません。"), open=True)
            self.page.update()
            return
        self._execute_delete(selected_file_ids)

    def _execute_delete(self, file_ids: list[int]):
        if not file_ids:
            return

        db = next(self.db_context())
        try:
            files_to_delete = db.query(UploadedFile).filter(UploadedFile.id.in_(file_ids)).all()
            if not files_to_delete:
                return

            deleted_count = 0
            parent_dirs_affected = set()

            for f_obj in files_to_delete:
                physical_file_path = os.path.join(APP_BASE_DIR, f_obj.filepath)
                parent_dir = os.path.dirname(physical_file_path)
                
                # 1. 物理ファイルの削除
                try:
                    if os.path.exists(physical_file_path):
                        os.remove(physical_file_path)
                        parent_dirs_affected.add(parent_dir)
                    # 物理ファイルが存在しなくても、DB削除は試行
                    elif os.path.exists(parent_dir):
                         parent_dirs_affected.add(parent_dir)
                except OSError as ose:
                    # 物理ファイルの削除に失敗した場合、このトランザクションを中止してエラーを報告
                    db.rollback()
                    self.page.snack_bar = ft.SnackBar(ft.Text(f"エラー: '{f_obj.filename}'を削除できませんでした。"), bgcolor=ft.Colors.ERROR)
                    self.page.update()
                    print(f"Failed to delete physical file {physical_file_path}: {ose}")
                    return # 処理を中断

                # 2. DBレコードの削除
                db.delete(f_obj)
                deleted_count += 1
            
            # 3. トランザクションのコミット
            db.commit()

            # 4. 空になった親ディレクトリのクリーンアップ
            for p_dir in sorted(list(parent_dirs_affected), key=len, reverse=True):
                try:
                    if os.path.exists(p_dir) and not os.listdir(p_dir):
                        os.rmdir(p_dir)
                except OSError as rmdir_ose:
                    print(f"Error deleting empty parent directory {p_dir}: {rmdir_ose}")
            
            self.page.snack_bar = ft.SnackBar(ft.Text(f"{deleted_count} 個のファイルを削除しました。"))

        except Exception as ex:
            db.rollback()
            self.page.snack_bar = ft.SnackBar(ft.Text("削除処理中に予期せぬエラーが発生しました。"), bgcolor=ft.Colors.ERROR)
            print(f"General error during deletion process: {ex}")
        finally:
            db.close()
            # 5. UIの更新
            self._load_files_for_list()
            self.page.update()

    def _on_file_checkbox_change(self, e: ft.ControlEvent):
        self._update_delete_selected_button_state()
        all_selected = all(cb.value for cb in self.file_checkboxes.values()) if self.file_checkboxes else False
        self.select_all_checkbox.value = all_selected
        if self.select_all_checkbox.page:
            self.select_all_checkbox.update()

    def _toggle_select_all_files(self, e: ft.ControlEvent):
        is_checked = e.control.value
        for checkbox_control in self.file_checkboxes.values():
            checkbox_control.value = is_checked
        if self.files_table_area.page:
            self.files_table_area.update()
        self._update_delete_selected_button_state()

    def _update_delete_selected_button_state(self):
        any_selected = any(cb.value for cb in self.file_checkboxes.values())
        self.delete_selected_button.disabled = not any_selected
        if self.delete_selected_button.page:
            self.delete_selected_button.update()

    def build_content(self) -> ft.Column:
        # FilePickerをpage.overlayに追加 (存在しない場合)
        # ui_components.pyのchange_viewでoverlay.clear()が呼ばれるため、
        # build_contentが呼ばれるたびに追加する必要がある
        if self.page and hasattr(self.page, 'overlay') and self.file_picker not in self.page.overlay:
            self.page.overlay.append(self.file_picker)

        return ft.Column(
            expand=True,
            spacing=15,
            controls=[
                ft.Text("ファイル管理", size=24, weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("OCRリスト:", width=100, size=18, weight=ft.FontWeight.BOLD), self.ocr_list_dropdown], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text("ファイルアップロード", size=18, weight=ft.FontWeight.W_600),
                self.upload_button,
                ft.Divider(height=10),
                ft.Text("アップロード済みファイル", size=18, weight=ft.FontWeight.W_600),
                ft.Row([self.select_all_checkbox, self.delete_selected_button], alignment=ft.MainAxisAlignment.START, spacing=20, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.files_table_area,
            ]
        )