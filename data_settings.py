import flet as ft
# import time # No longer needed for the error display
from models import get_db, Condition, DataItem # Import database functions and models
from sqlalchemy.orm import joinedload

class DataSettingsScreen:
    def __init__(self, page: ft.Page):
        self.page = page
        self.data_item_counter = 1
        self.current_editing_condition_id = None # To store the ID of the condition being edited

        # --- Database Session ---
        self.db_context = get_db
        # --- UIコントロールの定義 ---
        self.condition_name_field = ft.TextField(
            hint_text="保存したい条件名を入力してください",
            border=ft.InputBorder.OUTLINE,
            border_radius=5,
            bgcolor=ft.Colors.WHITE,
            expand=True # Row内でスペースを適切に使うため
        )

        # This list will store the TextField controls for data items
        self.data_item_text_fields = []

        # Column to hold data item input rows
        self.data_items_column = ft.Column(
            controls=[] # Initially empty, will be populated
        )
        self._add_initial_data_item_row() # Add the first data item row

        # 保存された条件が表示されるカラム
        self.saved_conditions_list = ft.Column(
            controls=[] # Will be populated from DB
        )
        self._load_saved_conditions() # Load conditions from DB on init

    # ★★★★★★★★★★★★★★★★★★★★
    # refreshメソッドを追加
    def refresh(self):
        """画面が表示されたときにデータを再読み込みするためのメソッド"""
        self._load_saved_conditions()
    # ★★★★★★★★★★★★★★★★★★★★

    def _add_initial_data_item_row(self):
        """Adds the first empty data item row to the form."""
        self.data_item_counter = 1
        self.data_item_text_fields.clear()
        new_item_row, text_field = self._create_data_item_row_controls(self.data_item_counter)
        self.data_items_column.controls.clear()
        self.data_items_column.controls.append(new_item_row)
        self.data_item_text_fields.append(text_field)

    def _create_data_item_row_controls(self, item_number: int, value: str = "") -> tuple[ft.Row, ft.TextField]:
        """データ項目入力行を生成するヘルパー関数です。"""
        text_field = ft.TextField(
            value=value,
            hint_text="取得したいデータ項目を入力してください",
            border=ft.InputBorder.OUTLINE,
            border_radius=5,
            bgcolor=ft.Colors.WHITE,
            expand=True
        )
        # 先にRowのコントロールリストを作成し、Rowインスタンスを生成します
        row_controls = [
            ft.Text(f"データ項目{item_number}", width=120, size=16),
            text_field,
        ]
        row = ft.Row(controls=row_controls, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # 項目番号が1より大きい場合（2つ目以降）に削除ボタンを追加します
        if item_number > 1:
            delete_button = ft.IconButton(
                icon=ft.Icons.CLOSE,
                tooltip="この項目を削除",
                on_click=lambda _, r=row: self._remove_data_item(r) # ラムダ式でRowインスタンスを渡します
            )
            row.controls.append(delete_button)

        return row, text_field

    def _add_data_item(self, e: ft.ControlEvent):
        """「＋ データ項目追加」ボタンのクリックイベントです。"""
        self.data_item_counter += 1
        new_item_row, text_field = self._create_data_item_row_controls(self.data_item_counter)
        self.data_items_column.controls.append(new_item_row)
        self.data_item_text_fields.append(text_field)
        self.data_items_column.update()

    def _remove_data_item(self, row_to_remove: ft.Row):
        """データ項目行をフォームから削除し、残りの項目の番号を振り直します。"""
        text_field_to_remove = next((ctrl for ctrl in row_to_remove.controls if isinstance(ctrl, ft.TextField)), None)
        if text_field_to_remove and text_field_to_remove in self.data_item_text_fields:
            self.data_item_text_fields.remove(text_field_to_remove)
        self.data_items_column.controls.remove(row_to_remove)
        self.data_item_counter = len(self.data_items_column.controls)
        for i, row in enumerate(self.data_items_column.controls):
            if isinstance(row, ft.Row) and len(row.controls) > 0 and isinstance(row.controls[0], ft.Text):
                row.controls[0].value = f"データ項目{i + 1}"
        self.data_items_column.update()

    def _show_snackbar(self, message: str, bgcolor: str = ft.Colors.GREEN_700):
        """スナックバーを表示するヘルパー関数です。"""
        if not self.page:
            return
        # page.open() を使用して、SnackBarをオーバーレイとして直接表示します。
        # これにより、他のUI更新との競合を避けることができます。
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=bgcolor
        )
        self.page.open(snackbar)

    def _create_saved_condition_row(self, condition: Condition) -> ft.Container:
        """保存済み条件の表示行を生成するヘルパー関数です。"""
        return ft.Container(
            padding=ft.padding.symmetric(vertical=5, horizontal=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.BLACK26)),
            content=ft.Row([
                ft.Text(condition.name, size=16, expand=True),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    icon_color=ft.Colors.BLACK54,
                    tooltip="設定",
                    on_click=lambda _, c=condition: self._load_condition_for_editing(c)
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ft.Colors.BLACK54,
                    tooltip="削除",
                    on_click=lambda _, cid=condition.id: self._delete_condition(cid)
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

    def _clear_form(self):
        """Clears the input form."""
        self.condition_name_field.value = ""
        self.condition_name_field.border_color = None # Reset border color
        self._add_initial_data_item_row() # Resets data items column and counter
        self.current_editing_condition_id = None
        self.condition_name_field.update()
        self.data_items_column.update()

    def _save_new_condition_action(self, e: ft.ControlEvent):
        """「新規保存」ボタンのクリックイベントです。"""
        condition_name = self.condition_name_field.value.strip()
        if not condition_name:
            self.condition_name_field.border_color = ft.Colors.RED
            self._show_snackbar("条件名を入力してください。", ft.Colors.ERROR)
            return
        self.condition_name_field.border_color = None
        self.condition_name_field.update()

        data_item_names = [tf.value.strip() for tf in self.data_item_text_fields if tf.value.strip()]
        if not data_item_names:
            # Optionally, show an error if no data items are provided
            # For now, we allow saving conditions with no data items
            pass

        db = next(self.db_context())
        try:
            # Check if condition name already exists
            existing_condition = db.query(Condition).filter(Condition.name == condition_name).first()
            if existing_condition:
                self.condition_name_field.error_text = "この条件名は既に使用されています。"
                self._show_snackbar("この条件名は既に使用されています。", ft.Colors.ERROR)
                return
            self.condition_name_field.error_text = None # Clear error

            new_condition = Condition(name=condition_name)
            for item_name in data_item_names:
                new_condition.data_items.append(DataItem(name=item_name))
            
            db.add(new_condition)
            db.commit()
            self._clear_form()
            self._load_saved_conditions()
            self._show_snackbar(f"条件「{condition_name}」を保存しました。")
        except Exception as ex:
            self._show_snackbar(f"保存中にエラーが発生しました: {ex}", ft.Colors.ERROR)
        finally:
            db.close()

    def _load_saved_conditions(self):
        """Loads all saved conditions from the database and updates the list."""
        db = next(self.db_context())
        try:
            conditions = db.query(Condition).options(joinedload(Condition.data_items)).order_by(Condition.name).all()
            self.saved_conditions_list.controls.clear()
            for cond in conditions:
                self.saved_conditions_list.controls.append(self._create_saved_condition_row(cond))
            # ページにアタッチされている場合のみ更新
            if self.saved_conditions_list.page:
                self.saved_conditions_list.update()
        finally:
            db.close()

    def _load_condition_for_editing(self, condition: Condition):
        """Populates the form with the details of the selected condition for editing."""
        self.current_editing_condition_id = condition.id
        self.condition_name_field.value = condition.name
        self.condition_name_field.error_text = None # Clear any previous error
        self.condition_name_field.border_color = None

        self.data_items_column.controls.clear()
        self.data_item_text_fields.clear()
        self.data_item_counter = 0

        if condition.data_items:
            for item in condition.data_items:
                self.data_item_counter += 1
                row, text_field = self._create_data_item_row_controls(self.data_item_counter, item.name)
                self.data_items_column.controls.append(row)
                self.data_item_text_fields.append(text_field)
        else:
            # Add one empty row if there are no data items
            self._add_initial_data_item_row()
            # Ensure the column is updated even if it was just cleared and re-added
            # This is a bit redundant with _add_initial_data_item_row but ensures UI consistency
            if not self.data_items_column.controls:
                 new_item_row, text_field = self._create_data_item_row_controls(1)
                 self.data_items_column.controls.append(new_item_row)
                 self.data_item_text_fields.append(text_field)

        self.condition_name_field.update()
        self.data_items_column.update()
        self.page.update()

    def _update_condition_action(self, e: ft.ControlEvent):
        """Updates the currently loaded condition in the database."""
        if self.current_editing_condition_id is None:
            self._show_snackbar("更新する条件が選択されていません。", ft.Colors.AMBER)
            return

        new_condition_name = self.condition_name_field.value.strip()
        if not new_condition_name:
            self.condition_name_field.border_color = ft.Colors.RED
            self._show_snackbar("条件名を入力してください。", ft.Colors.ERROR)
            return
        self.condition_name_field.border_color = None
        self.condition_name_field.update()

        new_data_item_names = [tf.value.strip() for tf in self.data_item_text_fields if tf.value.strip()]

        db = next(self.db_context())
        try:
            # Check if the new name conflicts with another existing condition
            conflicting_condition = db.query(Condition).filter(
                Condition.name == new_condition_name,
                Condition.id != self.current_editing_condition_id # Exclude the current condition itself
            ).first()

            if conflicting_condition:
                self.condition_name_field.error_text = "この条件名は既に使用されています。"
                self._show_snackbar("この条件名は既に使用されています。", ft.Colors.ERROR)
                return
            self.condition_name_field.error_text = None # Clear error

            condition_to_update = db.query(Condition).filter(Condition.id == self.current_editing_condition_id).options(joinedload(Condition.data_items)).first()
            if condition_to_update:
                condition_to_update.name = new_condition_name
                
                # Efficiently update data items:
                # Remove old items not in new list
                current_item_names = {item.name for item in condition_to_update.data_items}
                new_item_names_set = set(new_data_item_names)

                # Delete items that are no longer present
                for item in list(condition_to_update.data_items): # Iterate over a copy
                    if item.name not in new_item_names_set:
                        db.delete(item) # SQLAlchemy handles removal from collection
                
                # Add new items or update existing (if we were tracking item IDs, but here we just recreate)
                # For simplicity, we clear and add. A more complex diff could update existing items.
                # Clear existing items (already handled by cascade if we re-assign, but explicit can be clearer)
                # For this approach, we'll rely on the cascade delete-orphan for items removed from the collection,
                # and add new ones.
                
                # Rebuild data_items - simpler than diffing for this case
                # First, remove all existing data items associated with the condition
                for item in list(condition_to_update.data_items):
                    db.delete(item)
                db.flush() # Ensure deletions are processed before adding new items with potentially same names

                # Then, add the new/updated data items
                for item_name in new_data_item_names:
                    condition_to_update.data_items.append(DataItem(name=item_name))

                db.commit()
                self._clear_form()
                self._load_saved_conditions()
                self._show_snackbar(f"条件「{new_condition_name}」を更新しました。")
        except Exception as ex:
            self._show_snackbar(f"更新中にエラーが発生しました: {ex}", ft.Colors.ERROR)
        finally:
            db.close()

    def _delete_condition(self, condition_id: int):
        """Deletes a condition and its associated data items from the database."""
        db = next(self.db_context())
        try:
            condition_to_delete = db.query(Condition).filter(Condition.id == condition_id).first()
            if condition_to_delete:
                condition_name = condition_to_delete.name # 削除前に名前を取得
                db.delete(condition_to_delete) # Cascade will delete related DataItems
                db.commit()
                self._show_snackbar(f"条件「{condition_name}」を削除しました。")

            if self.current_editing_condition_id == condition_id:
                self._clear_form() # Clear form if the deleted condition was being edited
            
            self._load_saved_conditions()
        except Exception as ex:
            self._show_snackbar(f"削除中にエラーが発生しました: {ex}", ft.Colors.ERROR)
        finally:
            db.close()

    def build_content(self) -> ft.Column:
        """データ項目設定画面のUIコンテンツを構築して返します。"""
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=25,
            controls=[
                ft.Text("データ項目設定", size=24, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text("条件名", width=120, size=16),
                    self.condition_name_field,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.data_items_column,
                ft.Container(
                    content=ft.ElevatedButton(
                        text="＋ データ項目追加",
                        on_click=self._add_data_item,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=5)),
                        width=1200,
                    )
                ),
                ft.Row([
                    ft.ElevatedButton(
                        text="新規保存",
                        on_click=self._save_new_condition_action,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_100, shape=ft.RoundedRectangleBorder(radius=5)),
                        expand=True
                    ),
                    ft.ElevatedButton(
                        text="条件更新",
                        on_click=self._update_condition_action, # Connect the update action
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_GREY_100, shape=ft.RoundedRectangleBorder(radius=5)),
                        expand=True
                    ),
                ], spacing=10),
                ft.Divider(),
                ft.Text("保存した条件", size=20, weight=ft.FontWeight.BOLD),
                self.saved_conditions_list,
            ]
        )