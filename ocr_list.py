import flet as ft
from models import get_db, OcrList
import os
import shutil

# プロジェクトのベースディレクトリを取得
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR_NAME = "images"
UPLOAD_BASE_DIR = os.path.join(APP_BASE_DIR, UPLOAD_DIR_NAME)

class OcrListScreen:
    def __init__(self, page: ft.Page):
        self.page = page
        self.current_editing_list_id = None
        self.db_context = get_db

        # --- UIコントロールの定義 ---
        self.list_name_field = ft.TextField(
            hint_text="保存したいリスト名を入力してください",
            border=ft.InputBorder.OUTLINE,
            border_radius=5,
            bgcolor=ft.Colors.WHITE,
            expand=True
        )

        # 保存されたリストが表示されるカラム
        self.saved_lists_column = ft.Column(
            controls=[] # DBから読み込んで設定
        )
        self._load_saved_lists() # 初期化時にDBからリストを読み込む

    def refresh(self):
        """画面が表示されたときにデータを再読み込みするためのメソッド"""
        self._load_saved_lists()

    def _create_saved_list_row(self, ocr_list: OcrList) -> ft.Container:
        """保存済みリストの表示行を生成するヘルパー関数です。"""
        return ft.Container(
            padding=ft.padding.symmetric(vertical=5, horizontal=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.BLACK26)),
            content=ft.Row([
                ft.Text(ocr_list.name, size=16, expand=True),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    icon_color=ft.Colors.BLACK54,
                    tooltip="編集",
                    on_click=lambda _, ol=ocr_list: self._load_list_for_editing(ol)
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ft.Colors.BLACK54,
                    tooltip="削除",
                    on_click=lambda _, lid=ocr_list.id: self._delete_list(lid)
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

    def _clear_form(self):
        """入力フォームをクリアします。"""
        self.list_name_field.value = ""
        self.list_name_field.error_text = None
        self.list_name_field.border_color = None
        self.current_editing_list_id = None
        self.list_name_field.update()

    def _show_snackbar(self, message: str, bgcolor: str = ft.Colors.GREEN_700):
        """スナックバーを表示するヘルパー関数です。"""
        if not self.page:
            return
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=bgcolor
        )
        self.page.open(snackbar)

    def _save_new_list_action(self, e: ft.ControlEvent):
        """「新規保存」ボタンのクリックイベントです。"""
        list_name = self.list_name_field.value.strip()
        if not list_name:
            self.list_name_field.border_color = ft.Colors.RED
            self._show_snackbar("リスト名を入力してください。", ft.Colors.ERROR)
            return
        self.list_name_field.border_color = None
        self.list_name_field.update()

        db = next(self.db_context())
        try:
            existing_list = db.query(OcrList).filter(OcrList.name == list_name).first()
            if existing_list:
                self.list_name_field.error_text = "このリスト名は既に使用されています。"
                self._show_snackbar("このリスト名は既に使用されています。", ft.Colors.ERROR)
                return
            self.list_name_field.error_text = None

            new_ocr_list = OcrList(name=list_name)
            db.add(new_ocr_list)
            db.commit()
            self._show_snackbar(f"リスト「{list_name}」を保存しました。")
            self._clear_form()
            self._load_saved_lists()
        except Exception as ex:
            self._show_snackbar(f"保存中にエラーが発生しました: {ex}", ft.Colors.ERROR)
        finally:
            db.close()

    def _load_saved_lists(self):
        """DBから保存済みの全リストを読み込み、UIを更新します。"""
        db = next(self.db_context())
        try:
            ocr_lists = db.query(OcrList).order_by(OcrList.name).all()
            self.saved_lists_column.controls.clear()
            for ocr_list_item in ocr_lists:
                self.saved_lists_column.controls.append(self._create_saved_list_row(ocr_list_item))
            if self.saved_lists_column.page:
                self.saved_lists_column.update()
        finally:
            db.close()

    def _load_list_for_editing(self, ocr_list: OcrList):
        """選択されたリストの情報をフォームに読み込み、編集状態にします。"""
        self.current_editing_list_id = ocr_list.id
        self.list_name_field.value = ocr_list.name
        self.list_name_field.error_text = None
        self.list_name_field.border_color = None
        self.list_name_field.update()
        self.page.update()

    def _update_list_action(self, e: ft.ControlEvent):
        """現在読み込まれているリストをDBで更新します。"""
        if self.current_editing_list_id is None:
            self._show_snackbar("更新するリストが選択されていません。", ft.Colors.AMBER)
            return

        new_list_name = self.list_name_field.value.strip()
        if not new_list_name:
            self.list_name_field.border_color = ft.Colors.RED
            self._show_snackbar("リスト名を入力してください。", ft.Colors.ERROR)
            return
        self.list_name_field.border_color = None
        self.list_name_field.update()

        db = next(self.db_context())
        try:
            conflicting_list = db.query(OcrList).filter(
                OcrList.name == new_list_name,
                OcrList.id != self.current_editing_list_id
            ).first()

            if conflicting_list:
                self.list_name_field.error_text = "このリスト名は既に使用されています。"
                self._show_snackbar("このリスト名は既に使用されています。", ft.Colors.ERROR)
                return
            self.list_name_field.error_text = None

            list_to_update = db.query(OcrList).filter(OcrList.id == self.current_editing_list_id).first()
            if list_to_update:
                list_to_update.name = new_list_name
                db.commit()
                self._show_snackbar(f"リスト「{new_list_name}」を更新しました。")
                self._clear_form()
                self._load_saved_lists()
        except Exception as ex:
            self._show_snackbar(f"更新中にエラーが発生しました: {ex}", ft.Colors.ERROR)
        finally:
            db.close()

    def _delete_list(self, list_id: int):
        """リストをDBから削除し、関連する物理フォルダも削除します。"""
        list_folder_path = os.path.join(UPLOAD_BASE_DIR, str(list_id))
        db = next(self.db_context())
        try:
            list_to_delete = db.query(OcrList).filter(OcrList.id == list_id).first()
            if list_to_delete:
                list_name = list_to_delete.name # 削除前に名前を取得
                if os.path.exists(list_folder_path):
                    try:
                        shutil.rmtree(list_folder_path)
                        print(f"Successfully deleted directory: {list_folder_path}")
                    except OSError as e:
                        print(f"Error deleting directory {list_folder_path}: {e.strerror}")
                        self._show_snackbar(f"フォルダの削除中にエラー: {e.strerror}", ft.Colors.ERROR)

                db.delete(list_to_delete)
                db.commit()
                self._show_snackbar(f"リスト「{list_name}」を削除しました。")

            if self.current_editing_list_id == list_id:
                self._clear_form()
            self._load_saved_lists()
        except Exception as ex:
            db.rollback()
            self._show_snackbar(f"削除中にエラーが発生しました: {ex}", ft.Colors.ERROR)
        finally:
            db.close()

    def build_content(self) -> ft.Column:
        """OCRリスト画面のUIコンテンツを構築して返します。"""
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=25,
            controls=[
                ft.Text("OCRリスト設定", size=24, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text("リスト名", width=120, size=16),
                    self.list_name_field,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    ft.ElevatedButton(
                        text="新規保存",
                        on_click=self._save_new_list_action,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_100, shape=ft.RoundedRectangleBorder(radius=5)),
                        expand=True
                    ),
                    ft.ElevatedButton(
                        text="リスト名更新",
                        on_click=self._update_list_action,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_100, shape=ft.RoundedRectangleBorder(radius=5)),
                        expand=True
                    ),
                ], spacing=10),
                ft.Divider(),
                ft.Text("保存したリスト", size=20, weight=ft.FontWeight.BOLD),
                self.saved_lists_column,
            ]
        )