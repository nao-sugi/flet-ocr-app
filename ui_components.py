import flet as ft
from data_settings import DataSettingsScreen
from ocr_list import OcrListScreen
from file_manager import FileManagerScreen
from scan import ScanScreen
from export import ExportScreen

class AIOCRAppUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "AI-OCR"
        self.page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        self.page.vertical_alignment = ft.MainAxisAlignment.START
        self.page.bgcolor = "#f0f2f5"

        # --- 各画面のクラスインスタンスを保持 ---
        self.data_settings_screen = DataSettingsScreen(self.page)
        self.ocr_list_screen = OcrListScreen(self.page)
        self.file_manager_screen = FileManagerScreen(self.page)
        self.scan_screen = ScanScreen(self.page)
        self.export_screen = ExportScreen(self.page)

        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        # 修正点①：ビュー辞書にはUI部品そのものではなく、「画面クラスのインスタンス」を格納する
        # ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
        self.views = {
            "data_settings": self.data_settings_screen,
            "ocr_list": self.ocr_list_screen,
            "file_manager": self.file_manager_screen,
            "scan": self.scan_screen,
            "export": self.export_screen
        }
        
        self.create_ui()
        self.change_view("data_settings") # 初期画面を設定

    def create_ui(self):
        # ナビゲーションドロワー（サイドメニュー）の定義
        # (このメソッドの中身は変更ありません)
        self.nav_drawer = ft.Container(
            width=250,
            bgcolor=ft.Colors.WHITE,
            padding=ft.padding.only(top=10, left=5, right=5),
            margin=0,
            shadow=ft.BoxShadow(blur_radius=2, color=ft.Colors.BLACK12),
            content=ft.Column([
                ft.Container(
                    border_radius=ft.border_radius.all(10),
                    ink=True,
                    on_click=lambda e: self.change_view("data_settings"),
                    content=ft.ListTile(
                        leading=ft.Icon(ft.Icons.DISPLAY_SETTINGS_SHARP),
                        title=ft.Text("データ項目設定"),
                    ),
                ),
                ft.Container(
                    border_radius=ft.border_radius.all(10),
                    ink=True,
                    on_click=lambda e: self.change_view("ocr_list"),
                    content=ft.ListTile(
                        leading=ft.Icon(ft.Icons.LIST_ALT), # アイコン変更
                        title=ft.Text("OCRリスト設定"),
                    ),
                ),
                ft.Container(
                    border_radius=ft.border_radius.all(10),
                    ink=True,
                    on_click=lambda e: self.change_view("file_manager"),
                    content=ft.ListTile(
                        leading=ft.Icon(ft.Icons.FOLDER_OPEN), # アイコン変更
                        title=ft.Text("ファイル管理"),
                    ),
                ),
                ft.Container(
                    border_radius=ft.border_radius.all(10),
                    ink=True,
                    on_click=lambda e: self.change_view("scan"),
                    content=ft.ListTile(
                        leading=ft.Icon(ft.Icons.DOCUMENT_SCANNER_SHARP),
                        title=ft.Text("スキャン/取り込み"),
                    ),
                ),
                ft.Container(
                    border_radius=ft.border_radius.all(10),
                    ink=True,
                    on_click=lambda e: self.change_view("export"),
                    content=ft.ListTile(
                        leading=ft.Icon(ft.Icons.DESCRIPTION_SHARP),
                        title=ft.Text("エクスポート"),
                    ),
                )
            ], spacing=5)
        )

        # アプリバーの定義
        # (このメソッドの中身は変更ありません)
        self.app_bar = ft.Container(
            bgcolor="#003366",
            height=60,
            padding=ft.padding.symmetric(horizontal=10),
            content=ft.Row([
                ft.IconButton(
                    icon=ft.Icons.MENU,
                    icon_color=ft.Colors.WHITE,
                    on_click=self.toggle_drawer
                ),
                ft.Text("AI-OCR", size=18, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(icon=ft.Icons.ACCOUNT_CIRCLE_OUTLINED, icon_color=ft.Colors.WHITE)
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        )

        # メインコンテンツエリアの初期化
        self.main_content = ft.Container(
            expand=True,
            padding=20,
        )

        # ページ全体のレイアウト
        self.page.add(
            ft.Column([
                self.app_bar,
                ft.Row([
                    self.nav_drawer,
                    self.main_content
                ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START)
            ], expand=True, spacing=0)
        )

    def toggle_drawer(self, e):
        # (このメソッドの中身は変更ありません)
        self.nav_drawer.visible = not self.nav_drawer.visible
        self.page.update()

    def change_view(self, view_name):
        """
        画面を切り替えます。
        ★★★ 修正点②：ここで毎回build_content()を呼び出し、UIを再構築する ★★★
        """
        screen_instance_or_view = self.views.get(view_name)

        print(f"--- AIOCRAppUI: change_view CALLED for '{view_name}' (print) ---")
        print(f"--- AIOCRAppUI: Screen instance for '{view_name}': {screen_instance_or_view} (print) ---")

        # ★★★ 画面切り替え時にOverlayをクリアする ★★★
        # これにより、前の画面のFilePickerなどが残らないようにする
        if self.page and hasattr(self.page, 'overlay'):
            print(f"--- AIOCRAppUI: Clearing page.overlay. Current overlay: {self.page.overlay} (print) ---")
            self.page.overlay.clear()
            print(f"--- AIOCRAppUI: page.overlay cleared. Current overlay: {self.page.overlay} (print) ---")
            # 必要であれば、共通のダイアログなどを再追加する処理をここに入れる

        if hasattr(screen_instance_or_view, 'build_content'):
            # DataSettingsScreenなどのクラスインスタンスの場合
            # 毎回build_content()を呼び出し、新しいUI部品を生成する
            print(f"--- AIOCRAppUI: Calling build_content for '{view_name}' (print) ---")
            self.main_content.content = screen_instance_or_view.build_content()
            print(f"--- AIOCRAppUI: build_content for '{view_name}' DONE (print) ---")
            
            # refreshメソッドがあれば呼び出し、画面のデータを最新にする
            if hasattr(screen_instance_or_view, 'refresh'):
                print(f"--- AIOCRAppUI: Calling refresh for '{view_name}' (print) ---")
                screen_instance_or_view.refresh()
                print(f"--- AIOCRAppUI: refresh for '{view_name}' DONE (print) ---")
        else:
            # プレースホルダービューの場合
            self.main_content.content = screen_instance_or_view

        print(f"--- AIOCRAppUI: Calling page.update() after changing view to '{view_name}' (print) ---")
        self.page.update()
        print(f"--- AIOCRAppUI: page.update() DONE for '{view_name}' (print) ---")

    def build_placeholder_view(self, title):
        # (このメソッドの中身は変更ありません)
        return ft.Column([ft.Text(f"{title}画面", size=24, weight=ft.FontWeight.BOLD)])