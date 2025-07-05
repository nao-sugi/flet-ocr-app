import flet as ft
from models import get_db, OcrList, Condition, UploadedFile, ScannedData, DataItem
from sqlalchemy.orm import joinedload
import os
import datetime
import google.generativeai as genai # 標準的なエイリアスを使用
import time # シミュレーション用
# 非同期処理（シミュレートされたAPI呼び出しなど）に必要
import asyncio

APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class ScanScreen:
    def __init__(self, page: ft.Page):
        self.page = page
        self.db_context = get_db
        self.selected_ocr_list_id = None
        self.selected_condition_id = None

        # --- UIコントロール ---
        self.api_key_field = ft.TextField(
            label="API Key",
            hint_text="Gemini APIキーを入力してください",
            password=True,
            can_reveal_password=True,
            expand=True,
        )
        self.ocr_list_dropdown = ft.Dropdown(
            hint_text="OCRリストを選択",
            options=[],
            on_change=self._on_ocr_list_change,
            expand=True
        )

        self.condition_dropdown = ft.Dropdown(
            hint_text="条件を選択",
            options=[],
            on_change=self._on_condition_change,
            expand=True
        )

        self.files_list_view = ft.ListView(expand=True, spacing=5, auto_scroll=True)
        self.file_scan_status_texts = {} # スキャンボタンのテキスト更新または進捗表示用

        self.extracted_data_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("プレビューと抽出データ"), # タイトルを更新
            content=ft.Column([], scroll=ft.ScrollMode.ADAPTIVE, tight=True, width=400),
            actions=[ft.TextButton("閉じる", on_click=self._close_dialog)],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # --- 初期データ読み込み ---
        self._load_ocr_lists()
        self._load_conditions()

    def refresh(self):
        """画面が表示されたときにデータを再読み込みします。"""
        self._load_ocr_lists()
        self._load_conditions()
        if self.selected_ocr_list_id:
            self._load_files_for_list()
        else:
            self.files_list_view.controls.clear()
            # if self.page: self.files_list_view.update() # change_view内でpage.update()が呼ばれるため不要

    def _load_ocr_lists(self):
        db = next(self.db_context())
        try:
            lists = db.query(OcrList).order_by(OcrList.name).all()
            current_value = self.ocr_list_dropdown.value
            self.ocr_list_dropdown.options = [ft.dropdown.Option(key=str(l.id), text=l.name) for l in lists]
            if not any(opt.key == current_value for opt in self.ocr_list_dropdown.options) and lists:
                 self.ocr_list_dropdown.value = None # 現在の値が無効な場合はリセット
            elif current_value and any(opt.key == current_value for opt in self.ocr_list_dropdown.options):
                self.ocr_list_dropdown.value = current_value # 有効な場合は選択を維持
            else:
                self.ocr_list_dropdown.value = None
            # __init__時にはまだページに追加されていないため、ここではupdateしない
        finally:
            db.close()

    def _load_conditions(self):
        db = next(self.db_context())
        try:
            conditions = db.query(Condition).order_by(Condition.name).all()
            current_value = self.condition_dropdown.value
            self.condition_dropdown.options = [ft.dropdown.Option(key=str(c.id), text=c.name) for c in conditions]
            if not any(opt.key == current_value for opt in self.condition_dropdown.options) and conditions:
                self.condition_dropdown.value = None
            elif current_value and any(opt.key == current_value for opt in self.condition_dropdown.options):
                self.condition_dropdown.value = current_value
            else:
                self.condition_dropdown.value = None
            # __init__時にはまだページに追加されていないため、ここではupdateしない
        finally:
            db.close()

    def _on_ocr_list_change(self, e: ft.ControlEvent):
        if e.control.value:
            self.selected_ocr_list_id = int(e.control.value)
            self._load_files_for_list()
        else:
            self.selected_ocr_list_id = None
            self.files_list_view.controls.clear()
            if self.files_list_view.page: self.files_list_view.update()

    def _on_condition_change(self, e: ft.ControlEvent):
        self.selected_condition_id = int(e.control.value) if e.control.value else None
        # ここでファイルを再読み込みする必要はない（条件はスキャン用）

    def _load_files_for_list(self):
        self.files_list_view.controls.clear()
        self.file_scan_status_texts.clear()
        if not self.selected_ocr_list_id:
            if self.files_list_view.page: self.files_list_view.update()
            return

        db = next(self.db_context())
        try:
            files = db.query(UploadedFile).filter(UploadedFile.ocr_list_id == self.selected_ocr_list_id).order_by(UploadedFile.filename).all()
            if not files:
                self.files_list_view.controls.append(ft.Container(ft.Text("このリストにはスキャン対象のファイルがありません。", text_align=ft.TextAlign.CENTER), padding=20))
            else:
                for f_obj in files:
                    scan_button_text = "スキャン済み" if f_obj.is_scanned else "スキャン実行"
                    scan_button_disabled = f_obj.is_scanned
                    
                    status_text = ft.Text("", width=100, text_align=ft.TextAlign.RIGHT) # 「スキャン中...」用
                    self.file_scan_status_texts[f_obj.id] = status_text

                    # このボタン用の非同期イベントハンドラを定義
                    # ネストされた関数でデフォルト引数を使用して f_obj.id をキャプチャ
                    async def on_scan_button_click(e, file_id_to_scan=f_obj.id):
                        await self._initiate_scan_file(file_id_to_scan)

                    scan_button = ft.ElevatedButton(
                        text=scan_button_text,
                        icon=ft.Icons.DOCUMENT_SCANNER_SHARP, # アイコン変更
                        on_click=on_scan_button_click, # 非同期ハンドラを割り当て
                        disabled=scan_button_disabled,
                        data=f_obj.id # ボタンデータに file_id を格納
                    )

                    file_row_content = ft.Row([
                        ft.Text(f_obj.filename, expand=True, tooltip=f_obj.filename),
                        status_text, # 進捗/ステータス用プレースホルダ
                        scan_button
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    
                    file_container = ft.Container(
                        content=file_row_content,
                        border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.BLACK12)),
                        padding=ft.padding.symmetric(vertical=5, horizontal=10),
                        on_click=lambda _, file_obj=f_obj: self._show_preview_and_data_dialog(file_obj), # 呼び出すメソッドを変更
                        ink=True,
                        border_radius=5
                    )
                    self.files_list_view.controls.append(file_container)
        finally:
            db.close()
        
        if self.files_list_view.page: self.files_list_view.update()

    async def _initiate_scan_file(self, file_id: int):
        if not self.selected_condition_id:
            self.page.snack_bar = ft.SnackBar(ft.Text("スキャンを実行する前に条件を選択してください。"), open=True, bgcolor=ft.Colors.AMBER)
            if self.page: self.page.update()
            return

        # UIを更新して「スキャン中...」を表示
        scan_button_to_update = None
        # files_list_view.controls内のコンテナを正しく特定する
        for ctrl_container in self.files_list_view.controls:
            if isinstance(ctrl_container, ft.Container) and \
               hasattr(ctrl_container.content, 'controls') and \
               len(ctrl_container.content.controls) > 2 and \
               isinstance(ctrl_container.content.controls[2], ft.ElevatedButton) and \
               ctrl_container.content.controls[2].data == file_id:
                scan_button_to_update = ctrl_container.content.controls[2]
                break
        
        status_label = self.file_scan_status_texts.get(file_id)
        if status_label:
            status_label.value = "スキャン中..."
            if scan_button_to_update:
                scan_button_to_update.disabled = True
            if self.page: 
                status_label.update()
                if scan_button_to_update: scan_button_to_update.update()
        
        db = next(self.db_context())
        try:
            file_to_scan = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
            condition_used = db.query(Condition).options(joinedload(Condition.data_items)).filter(Condition.id == self.selected_condition_id).first()

            if not file_to_scan or not condition_used:
                if status_label: status_label.value = "エラー"
                self.page.snack_bar = ft.SnackBar(ft.Text("ファイルまたは条件が見つかりません。"), open=True, bgcolor=ft.Colors.ERROR)
                if self.page: 
                    if status_label: status_label.update()
                    self.page.update()
                return

            # 実際のファイルパスを構築 (UploadedFile.filepath は images/ocr_list_id/unique_filename のような相対パスを想定)
            physical_file_path = os.path.join(APP_BASE_DIR, file_to_scan.filepath)
            print(f"スキャン対象ファイル: {physical_file_path}")

            # --- GEMINI API 連携箇所 ---
            extracted_data_dict = await self.call_gemini_api(physical_file_path, condition_used.data_items, file_to_scan.filetype)
            # # シミュレーション用 (実際のAPI使用時はコメントアウトまたは削除):
            # await asyncio.sleep(2) # ネットワーク遅延をシミュレート
            # extracted_data_dict = {item.name: f"抽出値サンプル for {item.name}" for item in condition_used.data_items}
            # --- GEMINI API 連携終了 ---

            if extracted_data_dict is None:
                # API呼び出し失敗またはデータ抽出なし
                if status_label: status_label.value = "抽出失敗"
                self.page.snack_bar = ft.SnackBar(ft.Text(f"「{file_to_scan.filename}」からのデータ抽出に失敗しました。"), open=True, bgcolor=ft.Colors.ERROR)
                if scan_button_to_update: scan_button_to_update.disabled = False # エラー時は再試行可能に
                if self.page:
                    if status_label: status_label.update()
                    if scan_button_to_update: scan_button_to_update.update()
                    self.page.update()
                return

            # このファイルと条件に対する古いスキャンデータを削除（再スキャン時の重複を避けるため）
            db.query(ScannedData).filter(ScannedData.uploaded_file_id == file_id, ScannedData.condition_id == self.selected_condition_id).delete()

            for item_name, extracted_value in extracted_data_dict.items():
                new_scan_data = ScannedData(
                    uploaded_file_id=file_id,
                    condition_id=self.selected_condition_id,
                    data_item_name=item_name,
                    extracted_value=extracted_value
                )
                db.add(new_scan_data)
            
            file_to_scan.is_scanned = True
            file_to_scan.scanned_at = datetime.datetime.utcnow()
            db.commit()

            if status_label: status_label.value = "" # 「スキャン中...」をクリア
            if scan_button_to_update:
                scan_button_to_update.text = "スキャン済み"
                scan_button_to_update.disabled = True
            
            self.page.snack_bar = ft.SnackBar(ft.Text(f"「{file_to_scan.filename}」のスキャンが完了しました。"), open=True)

        except Exception as e:
            db.rollback()
            print(f"スキャンまたはDB操作中にエラー発生: {e}")
            if status_label: status_label.value = "エラー"
            if scan_button_to_update: scan_button_to_update.disabled = False # エラー時は再試行可能に
            self.page.snack_bar = ft.SnackBar(ft.Text(f"スキャン中にエラー発生: {e}"), open=True, bgcolor=ft.Colors.ERROR)
        finally:
            db.close()
            if self.page: 
                if status_label: status_label.update()
                if scan_button_to_update: scan_button_to_update.update()
                self.page.update()

    async def call_gemini_api(self, file_path: str, data_items: list[DataItem], file_type: str) -> dict | None:
        """
        指定されたファイルからデータを抽出するためにGemini APIを呼び出します。
        """
        api_key = self.api_key_field.value
        if not api_key:
            print("エラー: Gemini APIキーが入力されていません。")
            self.page.snack_bar = ft.SnackBar(ft.Text("スキャンを実行する前にAPIキーを入力してください。"), open=True, bgcolor=ft.Colors.ERROR)
            if self.page: self.page.update()
            return None

        try:
            # APIキーを都度設定
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            if not os.path.exists(file_path):
                print(f"エラー: ファイルが見つかりません {file_path}")
                self.page.snack_bar = ft.SnackBar(ft.Text(f"エラー: スキャン対象ファイルが見つかりません。"), open=True, bgcolor=ft.Colors.ERROR)
                if self.page: self.page.update()
                return None

            # MIMEタイプの決定（簡易版）
            # file_type は 'png', 'jpg', 'pdf' などの拡張子（ドットなし）を想定
            if file_type.lower() in ["png", "jpg", "jpeg"]:
                mime_type = f"image/{file_type.lower()}"
            elif file_type.lower() == "pdf":
                # Gemini Pro Vision はPDFを直接処理するのに最適ではないかもしれません。
                # PDFページをまず画像に変換する必要がある場合があります。
                # ここでは、PDFを画像に変換する処理を挟むことを推奨します。
                # (例: pdf2imageライブラリを使用)
                # 今回は簡略化のため、PDFの場合はエラーメッセージを表示してNoneを返します。
                print(f"警告: PDFファイル ({file_path}) の直接処理はサポートされていません。画像に変換してください。")
                self.page.snack_bar = ft.SnackBar(ft.Text(f"警告: PDFファイルは画像に変換してからスキャンしてください。"), open=True, bgcolor=ft.Colors.AMBER)
                if self.page: self.page.update()
                return None # PDF直接処理は一旦スキップ
            else:
                print(f"Gemini Visionでサポートされていないファイルタイプです: {file_type}")
                self.page.snack_bar = ft.SnackBar(ft.Text(f"サポートされていないファイル形式です: {file_type}"), open=True, bgcolor=ft.Colors.ERROR)
                if self.page: self.page.update()
                return None

            with open(file_path, "rb") as f:
                image_bytes = f.read()
            
            image_part = {"mime_type": mime_type, "data": image_bytes}
            
            prompt_parts = ["以下の画像から、次のデータ項目を抽出してください:\n"]
            for item in data_items:
                prompt_parts.append(f"{item.name}\n")
            prompt_parts.append("\n抽出結果は「項目名: 値」の形式で、各項目を改行で区切って返してください。項目名と値のペアのみを応答してください。")
            # 例:
            # 請求書番号: INV12345
            # 発行日: 2023-10-26
            # 合計金額: 10000

            full_prompt = "".join(prompt_parts)
            print(f"Geminiへのプロンプト: {full_prompt}") # デバッグ用にプロンプトをログ出力

            response = await model.generate_content_async([image_part, full_prompt])
            
            extracted_data = {}
            if response and hasattr(response, 'text') and response.text:
                print(f"Geminiからの応答テキスト: {response.text}") # 生の応答をログ出力
                for line in response.text.splitlines():
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            val = parts[1].strip()
                            # data_items に含まれる項目名のみを抽出対象とする（より厳密に）
                            if any(d_item.name == key for d_item in data_items):
                                extracted_data[key] = val
                            else:
                                print(f"警告: プロンプトにない項目名「{key}」が応答に含まれています。スキップします。")
                        else:
                            print(f"警告: 不正な形式の行です: {line}")
            else:
                print("Geminiからの応答が空またはテキストがありません。")
                if response and response.prompt_feedback:
                    print(f"プロンプトフィードバック: {response.prompt_feedback}")


            # 抽出されたデータがdata_itemsのすべてをカバーしているか確認（任意）
            if len(extracted_data) < len(data_items):
                print(f"警告: すべての要求されたデータ項目が抽出されませんでした。抽出された項目: {len(extracted_data)}/{len(data_items)}")


            return extracted_data

        except Exception as e:
            # 包括的なエラーハンドリング
            error_message = f"Gemini APIエラー: {e}"
            # APIキー関連のエラーか、他のエラーかを少し判別
            if "API_KEY_INVALID" in str(e):
                error_message = "APIキーが無効です。確認してください。"
            print(f"Gemini API呼び出し中にエラー発生: {e}")
            self.page.snack_bar = ft.SnackBar(ft.Text(error_message), open=True, bgcolor=ft.Colors.ERROR)
            if self.page: self.page.update()
            return None

    def _show_preview_and_data_dialog(self, file_obj: UploadedFile):
        """画像プレビューと抽出済みデータをダイアログに表示します。"""
        self.extracted_data_dialog.content.controls.clear()
        self.extracted_data_dialog.title.value = f"{file_obj.filename}"

        # --- 画像プレビュー部分 ---
        physical_file_path = os.path.join(APP_BASE_DIR, file_obj.filepath)
        if file_obj.filetype.lower() in ["png", "jpg", "jpeg"] and os.path.exists(physical_file_path):
            image_control = ft.Image(
                src=physical_file_path,
                width=380,
                fit=ft.ImageFit.CONTAIN,
                border_radius=ft.border_radius.all(5)
            )
            self.extracted_data_dialog.content.controls.append(image_control)
        else:
            message = ft.Text(f"{file_obj.filetype.upper()} のプレビューはサポートされていません。", text_align=ft.TextAlign.CENTER)
            self.extracted_data_dialog.content.controls.append(ft.Container(content=message, alignment=ft.alignment.center, height=100))
        
        self.extracted_data_dialog.content.controls.append(ft.Divider(height=15, thickness=1))
        
        # --- 抽出済みデータ表示部分 ---
        db = next(self.db_context())
        try:
            data_entries = db.query(ScannedData).options(joinedload(ScannedData.condition))\
                             .filter(ScannedData.uploaded_file_id == file_obj.id)\
                             .order_by(ScannedData.condition_id, ScannedData.data_item_name).all()

            if not file_obj.is_scanned or not data_entries:
                self.extracted_data_dialog.content.controls.append(ft.Text("このファイルはまだスキャンされていません。", text_align=ft.TextAlign.CENTER))
            else:
                current_condition_name = None
                for entry in data_entries:
                    condition_display_name = entry.condition.name if entry.condition else "不明な条件"
                    if condition_display_name != current_condition_name:
                        if current_condition_name is not None: 
                            self.extracted_data_dialog.content.controls.append(ft.Divider(height=5))
                        self.extracted_data_dialog.content.controls.append(
                            ft.Text(f"条件: {condition_display_name}", weight=ft.FontWeight.BOLD, size=14)
                        )
                        current_condition_name = condition_display_name
                    
                    self.extracted_data_dialog.content.controls.append(
                        ft.TextField(label=entry.data_item_name, value=entry.extracted_value, read_only=True, border=ft.InputBorder.UNDERLINE)
                    )
        finally:
            db.close()
        
        self.page.open(self.extracted_data_dialog)

    def _close_dialog(self, e: ft.ControlEvent):
        self.page.close(self.extracted_data_dialog)

    def build_content(self) -> ft.Column:
        return ft.Column(
            expand=True,
            spacing=15,
            controls=[
                ft.Text("スキャン実行とデータ確認", size=24, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text("API Key:", width=100, size=16, weight=ft.FontWeight.BOLD), 
                    self.api_key_field
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    ft.Text("OCRリスト:", width=100, size=16, weight=ft.FontWeight.BOLD), 
                    self.ocr_list_dropdown
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    ft.Text("条件選択:", width=100, size=16, weight=ft.FontWeight.BOLD), 
                    self.condition_dropdown
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=10),
                ft.Text("ファイルリスト", size=18, weight=ft.FontWeight.W_600),
                self.files_list_view,
            ]
        )
