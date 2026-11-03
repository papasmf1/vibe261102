"""
네이버페이 증권(stock.naver.com)에서 코스피200 데이터를 수집하는 GUI 앱 (PyQt6 + requests)

https://stock.naver.com/market/stock/kr 페이지는 Next.js로 만든 SPA라서
HTML에는 시세 숫자가 들어있지 않고, 브라우저가 아래 JSON API를 호출해 화면을 채움.
(예전 finance.naver.com 시세 페이지는 "더 이상 제공되지 않습니다"로 종료됨)
그래서 BeautifulSoup으로 HTML을 파싱하는 대신 같은 API를 직접 호출함.

- 코스피200 현재 지수 / 일별 시세 / 편입 종목 전체(페이징)를 수집
- 편입 종목은 종목명·코드로 검색하고, 열 머리글을 눌러 정렬
- 종목을 더블클릭하면 네이버페이 증권 종목 페이지를 브라우저로 엶
- 결과를 CSV 또는 엑셀(.xlsx) 파일로 저장

설치:  pip install requests PyQt6 openpyxl
실행:  python kospi200_crawler.py
"""

import csv
import os
import sys

import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

INDEX_CODE = "KPI200"
REALTIME_URL = "https://polling.finance.naver.com/api/realtime/domestic/index/{code}"
DAILY_URL = "https://m.stock.naver.com/api/index/{code}/price"
STOCKS_URL = "https://m.stock.naver.com/api/index/{code}/enrollStocks"
STOCK_PAGE_URL = "https://stock.naver.com/domestic/stock/{code}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": "https://stock.naver.com/market/stock/kr",
}

DAILY_COLUMNS = ["날짜", "종가", "전일비", "등락률(%)", "시가", "고가", "저가"]
STOCK_COLUMNS = [
    "순위", "종목코드", "종목명", "현재가", "전일비", "등락률(%)",
    "거래량", "거래대금(백만)", "시가총액(억)",
]

# 국내 증시 관례: 상승은 빨강, 하락은 파랑
UP_COLOR = "#f87171"
DOWN_COLOR = "#60a5fa"
FLAT_COLOR = "#cbd5e1"


# ---------------------------------------------------------------------------
# 데이터 수집
# ---------------------------------------------------------------------------

def get_json(session, url, params=None):
    resp = session.get(url, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_realtime(session):
    """코스피200 현재 지수"""
    data = get_json(session, REALTIME_URL.format(code=INDEX_CODE))
    d = data["datas"][0]
    return {
        "지수명": d["stockName"],
        "현재가": d["closePrice"],
        "전일비": d["compareToPreviousClosePrice"],
        "등락률(%)": d["fluctuationsRatio"],
        "시가": d["openPrice"],
        "고가": d["highPrice"],
        "저가": d["lowPrice"],
        "거래량": d["accumulatedTradingVolume"],
        "거래대금": d["accumulatedTradingValue"],
        "장상태": d["marketStatus"],
        "기준시각": d["localTradedAt"],
    }


def fetch_daily(session, pages=3, page_size=20):
    """코스피200 일별 시세 (최근 pages * page_size 거래일)"""
    rows = []
    for page in range(1, pages + 1):
        items = get_json(
            session,
            DAILY_URL.format(code=INDEX_CODE),
            {"page": page, "pageSize": page_size},
        )
        if not items:
            break
        for d in items:
            rows.append([
                d["localTradedAt"],
                d["closePrice"],
                d["compareToPreviousClosePrice"],
                d["fluctuationsRatio"],
                d["openPrice"],
                d["highPrice"],
                d["lowPrice"],
            ])
    return rows


def fetch_stocks(session, page_size=50, max_pages=20, on_page=None):
    """코스피200 편입 종목 전체 (시가총액 순)

    API는 pageSize가 60을 넘으면 빈 배열을 돌려주기 때문에 한 번에 전부 받을 수 없음.
    그래서 page를 1부터 늘려가며 빈 페이지가 나올 때까지 반복 요청함.
    on_page(page, 이번 페이지 개수, 누적 개수)로 진행 상황을 알림.
    """
    rows = []
    seen = set()
    for page in range(1, max_pages + 1):
        items = get_json(
            session,
            STOCKS_URL.format(code=INDEX_CODE),
            {"page": page, "pageSize": page_size},
        )
        if not items:
            break
        for d in items:
            # 페이지 경계에서 순위가 바뀌어 같은 종목이 두 번 나오는 경우 제외
            if d["itemCode"] in seen:
                continue
            seen.add(d["itemCode"])
            rows.append([
                len(rows) + 1,
                d["itemCode"],
                d["stockName"],
                d["closePrice"],
                d["compareToPreviousClosePrice"],
                d["fluctuationsRatio"],
                d["accumulatedTradingVolume"],
                d["accumulatedTradingValue"],
                d["marketValue"],
            ])
        if on_page:
            on_page(page, len(items), len(rows))
        if len(items) < page_size:
            break
    return rows


def save_csv(path, columns, rows):
    # utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않음
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


def write_sheet(ws, columns, rows):
    header_fill = PatternFill("solid", fgColor="03C75A")
    ws.append(columns)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        ws.append(row)
    for col in ws.columns:
        width = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(width * 1.6 + 2, 40)
    ws.freeze_panes = "A2"


def save_xlsx(path, summary, daily, stocks):
    wb = Workbook()
    ws = wb.active
    ws.title = "현재지수"
    write_sheet(ws, ["항목", "값"], list(summary.items()))
    write_sheet(wb.create_sheet("일별시세"), DAILY_COLUMNS, daily)
    write_sheet(wb.create_sheet("편입종목"), STOCK_COLUMNS, stocks)
    wb.save(path)


def to_number(text):
    """'1,388,000' / '-4.15' 같은 문자열을 정렬용 숫자로 바꿈"""
    try:
        return float(str(text).replace(",", ""))
    except ValueError:
        return None


def change_color(value):
    num = to_number(value)
    if num is None or num == 0:
        return FLAT_COLOR
    return UP_COLOR if num > 0 else DOWN_COLOR


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

# 다크 네이비 배경 + 네이버 그린/퍼플 그라데이션 포인트 테마
STYLE_SHEET = """
QMainWindow, QWidget#central {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f172a, stop:1 #1e1b4b);
}
QWidget {
    font-family: "Malgun Gothic", "맑은 고딕", sans-serif;
    font-size: 10pt;
    color: #e2e8f0;
}
QLabel { background: transparent; }
QLabel#bannerTitle { font-size: 20pt; font-weight: 800; color: #ffffff; }
QLabel#bannerSub { font-size: 9.5pt; color: #e0e7ff; }
QFrame#banner {
    border-radius: 16px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #03c75a, stop:0.5 #0ea5e9, stop:1 #8b5cf6);
}
QFrame#card {
    background: rgba(30, 41, 59, 0.85);
    border: 1px solid #334155;
    border-radius: 14px;
}
QLabel#cardTitle { font-size: 11pt; font-weight: 700; color: #a5b4fc; }
QLabel#indexPrice { font-size: 28pt; font-weight: 800; }
QLabel#indexChange { font-size: 13pt; font-weight: 700; }
QLabel#statName { color: #94a3b8; }
QLabel#statValue { font-weight: 700; color: #f1f5f9; }
QLabel#marketBadge {
    border-radius: 9px;
    padding: 3px 10px;
    font-weight: 700;
    color: #ffffff;
}
QLineEdit {
    background: #0f172a;
    border: 2px solid #334155;
    border-radius: 10px;
    padding: 7px 12px;
    selection-background-color: #6366f1;
}
QLineEdit:focus { border: 2px solid #03c75a; }
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 5px;
    border: 2px solid #475569;
    background: #0f172a;
}
QCheckBox::indicator:checked { background: #03c75a; border-color: #03c75a; }
QPushButton {
    border: none;
    border-radius: 10px;
    padding: 9px 18px;
    font-weight: 700;
    color: #ffffff;
}
QPushButton#fetchBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #03c75a, stop:1 #10b981);
}
QPushButton#fetchBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22e57a, stop:1 #34d399);
}
QPushButton#csvBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0ea5e9, stop:1 #6366f1);
}
QPushButton#csvBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #818cf8);
}
QPushButton#excelBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
}
QPushButton#excelBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a78bfa, stop:1 #f472b6);
}
QPushButton:pressed { padding-top: 11px; padding-bottom: 7px; }
QPushButton:disabled { background: #334155; color: #64748b; }
QTabWidget::pane { border: none; }
QTabBar::tab {
    background: #111c33;
    color: #94a3b8;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 700;
}
QTabBar::tab:selected { background: #6366f1; color: #ffffff; }
QTableWidget {
    background: transparent;
    alternate-background-color: rgba(51, 65, 85, 0.35);
    border: none;
    gridline-color: transparent;
    selection-background-color: transparent;
    outline: none;
}
QTableWidget::item { padding: 4px 8px; border-bottom: 1px solid #273449; }
QTableWidget::item:hover { background: rgba(99, 102, 241, 0.18); }
QTableWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(3, 199, 90, 0.45), stop:1 rgba(99, 102, 241, 0.35));
    color: #ffffff;
}
QHeaderView::section {
    background: #111c33;
    color: #a5b4fc;
    font-weight: 700;
    border: none;
    border-bottom: 2px solid #6366f1;
    padding: 8px;
}
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #475569; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #6366f1; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QStatusBar { background: #0b1222; color: #94a3b8; border-top: 1px solid #1e293b; }
QProgressBar {
    background: #1e293b;
    border: none;
    border-radius: 6px;
    min-width: 220px;
    max-height: 12px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    border-radius: 6px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #03c75a, stop:1 #8b5cf6);
}
"""

# 자동 갱신 주기 (네이버 화면의 폴링 주기와 비슷하게)
AUTO_REFRESH_MS = 10_000


def make_card(title, widget):
    """제목이 있는 둥근 카드 패널을 만듦"""
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    label = QLabel(title)
    label.setObjectName("cardTitle")
    layout.addWidget(label)
    layout.addWidget(widget)
    add_shadow(card)
    return card


def add_shadow(widget, blur=24, alpha=120):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, 4)
    shadow.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(shadow)


def make_table(columns):
    table = QTableWidget(0, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    # 첫 열 오름차순이 기본 정렬. 사용자가 바꾼 정렬은 다시 수집해도 유지됨
    table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
    return table


class NumericItem(QTableWidgetItem):
    """'1,388,000' 같은 값을 문자열이 아니라 숫자 크기로 정렬하는 셀"""

    def __lt__(self, other):
        a, b = to_number(self.text()), to_number(other.text())
        if a is None or b is None:
            return super().__lt__(other)
        return a < b


class CrawlWorker(QThread):
    """수집 중에도 화면이 멈추지 않도록 별도 스레드에서 실행"""

    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(dict, list, list)
    failed = pyqtSignal(str)

    def run(self):
        try:
            with requests.Session() as session:
                self.progress.emit("현재 지수 가져오는 중...")
                summary = fetch_realtime(session)
                self.progress.emit("일별 시세 가져오는 중...")
                daily = fetch_daily(session)
                stocks = fetch_stocks(
                    session,
                    on_page=lambda page, count, total: self.progress.emit(
                        f"편입 종목 {page}페이지: {count}개 (누적 {total}개)"
                    ),
                )
            self.finished_ok.emit(summary, daily, stocks)
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📈 코스피200 크롤러")
        self.resize(1200, 860)
        self.setStyleSheet(STYLE_SHEET)
        self.summary = {}
        self.daily = []
        self.stocks = []
        self.worker = None

        # 맨 위: 그라데이션 배너
        banner = QFrame()
        banner.setObjectName("banner")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(24, 16, 24, 16)
        title = QLabel("📈  KOSPI 200 CRAWLER")
        title.setObjectName("bannerTitle")
        subtitle = QLabel("네이버페이 증권에서 코스피200 지수 · 일별 시세 · 편입 종목을 수집하고 CSV · 엑셀로 저장합니다")
        subtitle.setObjectName("bannerSub")
        banner_layout.addWidget(title)
        banner_layout.addWidget(subtitle)
        add_shadow(banner, blur=30, alpha=160)

        # 버튼 줄
        self.fetch_btn = QPushButton("🔄  데이터 수집")
        self.fetch_btn.setObjectName("fetchBtn")
        self.fetch_btn.clicked.connect(self.start_crawl)

        self.auto_check = QCheckBox(f"{AUTO_REFRESH_MS // 1000}초마다 자동 갱신")
        self.auto_check.toggled.connect(self.toggle_auto_refresh)
        self.timer = QTimer(self)
        self.timer.setInterval(AUTO_REFRESH_MS)
        self.timer.timeout.connect(self.start_crawl)

        self.csv_btn = QPushButton("📄  CSV 저장")
        self.csv_btn.setObjectName("csvBtn")
        self.csv_btn.setEnabled(False)
        self.csv_btn.clicked.connect(self.save_csv_files)

        self.excel_btn = QPushButton("📊  엑셀 저장")
        self.excel_btn.setObjectName("excelBtn")
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.save_excel_file)

        for btn in (self.fetch_btn, self.csv_btn, self.excel_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addWidget(self.fetch_btn)
        button_row.addWidget(self.auto_check)
        button_row.addStretch(1)
        button_row.addWidget(self.csv_btn)
        button_row.addWidget(self.excel_btn)

        # 현재 지수 카드
        self.price_label = QLabel("-")
        self.price_label.setObjectName("indexPrice")
        self.change_label = QLabel("")
        self.change_label.setObjectName("indexChange")
        self.market_badge = QLabel("")
        self.market_badge.setObjectName("marketBadge")
        self.market_badge.setVisible(False)
        self.time_label = QLabel("[데이터 수집]을 누르세요")
        self.time_label.setObjectName("statName")

        price_box = QVBoxLayout()
        price_box.addWidget(self.price_label)
        change_row = QHBoxLayout()
        change_row.addWidget(self.change_label)
        change_row.addWidget(self.market_badge)
        change_row.addStretch(1)
        price_box.addLayout(change_row)
        price_box.addWidget(self.time_label)

        self.stat_labels = {}
        stats = QGridLayout()
        stats.setHorizontalSpacing(24)
        stats.setVerticalSpacing(8)
        for i, name in enumerate(["시가", "고가", "저가", "거래량", "거래대금"]):
            name_label = QLabel(name)
            name_label.setObjectName("statName")
            value_label = QLabel("-")
            value_label.setObjectName("statValue")
            self.stat_labels[name] = value_label
            stats.addWidget(name_label, i % 3, (i // 3) * 2)
            stats.addWidget(value_label, i % 3, (i // 3) * 2 + 1)

        index_body = QWidget()
        index_layout = QHBoxLayout(index_body)
        index_layout.setContentsMargins(0, 0, 0, 0)
        index_layout.addLayout(price_box, 1)
        index_layout.addLayout(stats, 1)
        self.index_card = make_card("💹  코스피 200", index_body)

        # 편입 종목 탭: 검색창 + 표
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("🔍  종목명 또는 종목코드로 검색")
        self.filter_edit.textChanged.connect(self.apply_filter)
        self.stock_table = make_table(STOCK_COLUMNS)
        self.stock_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.stock_table.cellDoubleClicked.connect(self.open_stock_page)

        stock_tab = QWidget()
        stock_layout = QVBoxLayout(stock_tab)
        stock_layout.setContentsMargins(0, 10, 0, 0)
        stock_layout.addWidget(self.filter_edit)
        stock_layout.addWidget(self.stock_table)

        self.daily_table = make_table(DAILY_COLUMNS)
        # 일별 시세는 최신 날짜가 위로
        self.daily_table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.DescendingOrder)

        self.tabs = QTabWidget()
        self.tabs.addTab(stock_tab, "🏢  편입 종목")
        self.tabs.addTab(self.daily_table, "📅  일별 시세")

        # 하단: 진행 상태
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 전체 페이지 수를 미리 알 수 없어 대기 표시
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.statusBar().showMessage("  [데이터 수집]을 누르세요. 종목을 더블클릭하면 종목 페이지가 열립니다.")

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 12)
        layout.setSpacing(14)
        layout.addWidget(banner)
        layout.addLayout(button_row)
        layout.addWidget(self.index_card)
        layout.addWidget(self.tabs, 1)
        central = QWidget()
        central.setObjectName("central")
        central.setLayout(layout)
        self.setCentralWidget(central)

    def start_crawl(self):
        if self.worker and self.worker.isRunning():
            return
        self.fetch_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.statusBar().showMessage("  데이터 수집 시작...")

        self.worker = CrawlWorker()
        self.worker.progress.connect(lambda msg: self.statusBar().showMessage(f"  {msg}"))
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def toggle_auto_refresh(self, checked):
        if checked:
            self.timer.start()
            self.start_crawl()
        else:
            self.timer.stop()

    def on_finished(self, summary, daily, stocks):
        self.summary, self.daily, self.stocks = summary, daily, stocks
        self.show_summary()
        self.fill_table(self.daily_table, daily, change_cols=(2, 3))
        self.fill_table(self.stock_table, stocks, change_cols=(4, 5))
        self.apply_filter(self.filter_edit.text())

        self.fetch_btn.setEnabled(True)
        self.csv_btn.setEnabled(True)
        self.excel_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.tabs.setTabText(0, f"🏢  편입 종목 · {len(stocks)}개")
        self.tabs.setTabText(1, f"📅  일별 시세 · {len(daily)}일")
        self.statusBar().showMessage(
            f"  ✅ 수집 완료: 편입 종목 {len(stocks)}개, 일별 시세 {len(daily)}일"
        )

    def on_failed(self, error):
        self.fetch_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("  ❌ 수집 실패")
        # 자동 갱신 중이면 팝업을 반복해서 띄우지 않음
        if not self.timer.isActive():
            QMessageBox.critical(self, "오류", f"데이터를 가져오지 못했습니다.\n{error}")

    def show_summary(self):
        s = self.summary
        color = change_color(s["전일비"])
        arrow = "▲" if color == UP_COLOR else "▼" if color == DOWN_COLOR else "-"
        self.price_label.setText(s["현재가"])
        self.price_label.setStyleSheet(f"color: {color};")
        self.change_label.setText(f"{arrow} {s['전일비'].lstrip('-')}  ({s['등락률(%)']}%)")
        self.change_label.setStyleSheet(f"color: {color};")

        is_open = s["장상태"] == "OPEN"
        self.market_badge.setText("장중" if is_open else "장마감")
        self.market_badge.setStyleSheet(f"background: {'#03c75a' if is_open else '#475569'};")
        self.market_badge.setVisible(True)
        self.time_label.setText(f"기준 {s['기준시각'].replace('T', ' ')[:19]}")
        for name, label in self.stat_labels.items():
            label.setText(s[name])

    def fill_table(self, table, rows, change_cols):
        table.setSortingEnabled(False)  # 채우는 도중 정렬되면 행이 섞임
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            color = change_color(row[change_cols[0]])
            for c, value in enumerate(row):
                item = NumericItem(str(value))
                if to_number(value) is not None:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if c in change_cols:
                    item.setForeground(QColor(color))
                table.setItem(r, c, item)
        table.setSortingEnabled(True)

    def apply_filter(self, text):
        text = text.strip().lower()
        for r in range(self.stock_table.rowCount()):
            code = self.stock_table.item(r, 1).text()
            name = self.stock_table.item(r, 2).text().lower()
            self.stock_table.setRowHidden(r, bool(text) and text not in name and text not in code)

    def open_stock_page(self, row, _column):
        code = self.stock_table.item(row, 1).text()
        QDesktopServices.openUrl(QUrl(STOCK_PAGE_URL.format(code=code)))

    def save_csv_files(self):
        folder = QFileDialog.getExistingDirectory(self, "CSV를 저장할 폴더 선택")
        if not folder:
            return
        daily_path = os.path.join(folder, "kospi200_daily.csv")
        stocks_path = os.path.join(folder, "kospi200_stocks.csv")
        try:
            save_csv(daily_path, DAILY_COLUMNS, self.daily)
            save_csv(stocks_path, STOCK_COLUMNS, self.stocks)
        except OSError as e:
            QMessageBox.critical(
                self, "오류", f"저장하지 못했습니다. 파일이 열려 있다면 닫고 다시 시도하세요.\n{e}"
            )
            return
        self.statusBar().showMessage(f"  {daily_path}, {stocks_path} 파일로 저장했습니다.")

    def save_excel_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", "kospi200.xlsx", "엑셀 파일 (*.xlsx)"
        )
        if not filename:
            return
        if not filename.lower().endswith(".xlsx"):
            filename += ".xlsx"
        try:
            save_xlsx(filename, self.summary, self.daily, self.stocks)
        except OSError as e:
            # 같은 파일이 엑셀에 열려 있으면 PermissionError가 발생
            QMessageBox.critical(
                self, "오류", f"저장하지 못했습니다. 파일이 열려 있다면 닫고 다시 시도하세요.\n{e}"
            )
            return
        self.statusBar().showMessage(f"  {filename} 파일로 저장했습니다.")


def resource_path(name):
    """PyInstaller로 묶인 exe에서는 임시 폴더(_MEIPASS), 아니면 스크립트 폴더 기준 경로"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def main():
    app = QApplication(sys.argv)
    icon_path = resource_path("kospi200.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
