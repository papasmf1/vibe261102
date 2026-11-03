"""
네이버 검색 결과에서 신문기사를 크롤링하는 GUI 앱 (PyQt6 + requests + BeautifulSoup4)

- 검색어를 입력하면 기사 제목 / 언론사 / 요약 / 원문 링크 / 네이버뉴스 링크를 수집
- 네이버뉴스(n.news.naver.com) 링크가 있는 기사는 본문까지 가져옴
- 목록에서 기사를 선택하면 본문을 보여주고, 더블클릭하면 브라우저로 원문을 엶
- 결과를 CSV 또는 엑셀(.xlsx) 파일로 저장

설치:  pip install requests beautifulsoup4 PyQt6 openpyxl
실행:  python naver_news_crawler.py
"""

import csv
import html
import os
import sys
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 검색 범위: 통합검색은 뉴스가 3건 정도, 뉴스탭은 10건 정도 나옴
SEARCH_TYPES = {
    "통합검색": "nexearch",
    "뉴스탭": "news",
}


def build_url(keyword, where):
    return (
        "https://search.naver.com/search.naver"
        f"?where={where}&sm=top_hty&fbm=0&ie=utf8&query={quote(keyword)}"
    )


# ---------------------------------------------------------------------------
# 크롤링 함수
# ---------------------------------------------------------------------------

def clean_text(tag):
    """'새 창 열림' 같은 숨김 안내 문구를 제외하고 텍스트만 추출"""
    if tag is None:
        return ""
    for hidden in tag.select("span[class^='PTx_']"):
        hidden.decompose()
    text = tag.get_text(" ", strip=True)
    return text.replace("새 창 열림", "").strip()


def find_item_container(title_tag):
    """제목 태그에서 위로 올라가며 언론사(.prof) 정보까지 포함한 기사 블록을 찾음"""
    node = title_tag
    for _ in range(10):
        node = node.parent
        if node is None:
            break
        if node.select_one('a[data-heatmap-target=".prof"]'):
            return node
    return title_tag.parent


def parse_search_page(html):
    """검색 결과 HTML에서 기사 목록을 추출"""
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen = set()

    # 네이버는 클래스명이 난독화되어 자주 바뀌므로, 비교적 안정적인 data-heatmap-target 속성을 사용
    for title_tag in soup.select('a[data-heatmap-target=".tit"]'):
        link = title_tag.get("href", "")
        if not link or link in seen:
            continue
        seen.add(link)

        item = find_item_container(title_tag)
        # .prof 링크는 로고 이미지와 언론사명 두 개가 있으므로 텍스트가 있는 것을 사용
        press = next(
            (t for t in (clean_text(a) for a in item.select('a[data-heatmap-target=".prof"]')) if t),
            "",
        )
        body_tag = item.select_one('a[data-heatmap-target=".body"]')
        naver_tag = item.select_one('a[data-heatmap-target=".nav"]')

        articles.append({
            "title": clean_text(title_tag),
            "press": press,
            "summary": clean_text(body_tag),
            "link": link,
            "naver_link": naver_tag["href"] if naver_tag else "",
            "content": "",
        })
    return articles


def fetch_naver_article(url):
    """네이버뉴스 기사 페이지에서 본문을 추출"""
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    body = soup.select_one("#dic_area") or soup.select_one("#articeBody")
    if body is None:
        return ""
    # 사진 설명, 스크립트 등 본문이 아닌 요소 제거
    for tag in body.select("script, style, .img_desc, .end_photo_org em"):
        tag.decompose()
    lines = [line.strip() for line in body.get_text("\n").splitlines()]
    return "\n".join(line for line in lines if line)


def save_csv(articles, filename):
    fields = ["title", "press", "summary", "link", "naver_link", "content"]
    # utf-8-sig: 엑셀에서 한글이 깨지지 않도록
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(articles)


# 엑셀 열 구성: (키, 머리글, 열 너비)
EXCEL_COLUMNS = [
    ("press", "언론사", 14),
    ("title", "제목", 50),
    ("summary", "요약", 60),
    ("link", "원문 링크", 30),
    ("naver_link", "네이버뉴스 링크", 30),
    ("content", "본문", 80),
]
EXCEL_CELL_LIMIT = 32767  # 엑셀 셀 하나에 들어갈 수 있는 최대 글자 수


def save_excel(articles, filename, sheet_title="뉴스"):
    wb = Workbook()
    ws = wb.active
    # 시트 이름에 쓸 수 없는 문자를 제거하고 31자로 제한
    ws.title = "".join(c for c in sheet_title if c not in r'[]:*?/\\')[:31] or "뉴스"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4472C4")
    ws.append(["번호"] + [name for _, name, _ in EXCEL_COLUMNS])
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for i, art in enumerate(articles, 1):
        row = [i]
        for key, _, _ in EXCEL_COLUMNS:
            # 엑셀에서 허용하지 않는 제어 문자 제거
            value = ILLEGAL_CHARACTERS_RE.sub("", art.get(key, ""))
            row.append(value[:EXCEL_CELL_LIMIT])
        ws.append(row)

        for col, (key, _, _) in enumerate(EXCEL_COLUMNS, 2):
            cell = ws.cell(row=i + 1, column=col)
            cell.alignment = Alignment(vertical="top", wrap_text=key != "content")
            if key in ("link", "naver_link") and cell.value:
                cell.hyperlink = cell.value
                cell.font = Font(color="0563C1", underline="single")

    ws.column_dimensions["A"].width = 6
    for col, (_, _, width) in enumerate(EXCEL_COLUMNS, 2):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
    ws.freeze_panes = "A2"  # 머리글 고정
    ws.auto_filter.ref = ws.dimensions

    wb.save(filename)


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
QLabel#bannerTitle {
    font-size: 20pt;
    font-weight: 800;
    color: #ffffff;
    background: transparent;
}
QLabel#bannerSub {
    font-size: 9.5pt;
    color: #c7d2fe;
    background: transparent;
}
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
QLabel#cardTitle {
    font-size: 11pt;
    font-weight: 700;
    color: #a5b4fc;
    background: transparent;
}
QLineEdit {
    background: #0f172a;
    border: 2px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 11pt;
    selection-background-color: #6366f1;
}
QLineEdit:focus {
    border: 2px solid #03c75a;
}
QComboBox {
    background: #0f172a;
    border: 2px solid #334155;
    border-radius: 10px;
    padding: 7px 12px;
    min-width: 90px;
}
QComboBox:hover { border-color: #6366f1; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #1e293b;
    border: 1px solid #475569;
    selection-background-color: #6366f1;
    outline: none;
}
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border-radius: 5px;
    border: 2px solid #475569;
    background: #0f172a;
}
QCheckBox::indicator:checked {
    background: #03c75a;
    border-color: #03c75a;
}
QPushButton {
    border: none;
    border-radius: 10px;
    padding: 9px 18px;
    font-weight: 700;
    color: #ffffff;
}
QPushButton#searchBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #03c75a, stop:1 #10b981);
}
QPushButton#searchBtn:hover {
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
QPushButton:disabled {
    background: #334155;
    color: #64748b;
}
QTableWidget {
    background: transparent;
    alternate-background-color: rgba(51, 65, 85, 0.35);
    border: none;
    gridline-color: transparent;
    selection-background-color: transparent;
    outline: none;
}
QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #273449;
}
QTableWidget::item:hover {
    background: rgba(99, 102, 241, 0.18);
}
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
QTextBrowser {
    background: transparent;
    border: none;
}
QSplitter::handle { background: transparent; height: 10px; }
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #475569;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #6366f1; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QStatusBar {
    background: #0b1222;
    color: #94a3b8;
    border-top: 1px solid #1e293b;
}
QProgressBar {
    background: #1e293b;
    border: none;
    border-radius: 6px;
    height: 12px;
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

# 상세 보기(QTextBrowser)용 HTML 스타일
DETAIL_CSS = """
<style>
  h2 { color: #ffffff; font-size: 15pt; margin: 0 0 6px 0; }
  .press { color: #03c75a; font-weight: bold; }
  .label { color: #a5b4fc; font-weight: bold; }
  a { color: #38bdf8; text-decoration: none; }
  .summary { color: #cbd5e1; background-color: #1e293b; }
  .content { color: #e2e8f0; line-height: 160%; }
  .empty { color: #64748b; }
</style>
"""


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

class CrawlWorker(QThread):
    """크롤링 중에도 화면이 멈추지 않도록 별도 스레드에서 실행"""

    progress = pyqtSignal(int, int, str)   # 현재, 전체, 메시지
    finished_ok = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, url, fetch_content):
        super().__init__()
        self.url = url
        self.fetch_content = fetch_content

    def run(self):
        try:
            res = requests.get(self.url, headers=HEADERS, timeout=10)
            res.raise_for_status()
            articles = parse_search_page(res.text)

            total = len(articles)
            for i, art in enumerate(articles, 1):
                if self.fetch_content and art["naver_link"]:
                    self.progress.emit(i, total, f"본문 수집 중: {art['title'][:30]}")
                    try:
                        art["content"] = fetch_naver_article(art["naver_link"])
                    except requests.RequestException as e:
                        art["content"] = f"(본문 수집 실패: {e})"
                    time.sleep(0.5)  # 서버 부하를 줄이기 위한 대기
                else:
                    self.progress.emit(i, total, "")
            self.finished_ok.emit(articles)
        except requests.RequestException as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📰 네이버 뉴스 크롤러")
        self.resize(1200, 820)
        self.setStyleSheet(STYLE_SHEET)
        self.articles = []
        self.worker = None

        # 맨 위: 그라데이션 배너
        banner = QFrame()
        banner.setObjectName("banner")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(24, 16, 24, 16)
        title = QLabel("📰  NEWS CRAWLER")
        title.setObjectName("bannerTitle")
        subtitle = QLabel("네이버 검색 결과에서 신문기사를 수집하고 CSV · 엑셀로 저장합니다")
        subtitle.setObjectName("bannerSub")
        banner_layout.addWidget(title)
        banner_layout.addWidget(subtitle)
        add_shadow(banner, blur=30, alpha=160)

        # 검색 조건
        self.keyword_edit = QLineEdit("반도체")
        self.keyword_edit.setPlaceholderText("🔍  검색어를 입력하세요")
        self.keyword_edit.returnPressed.connect(self.start_crawl)

        self.type_combo = QComboBox()
        self.type_combo.addItems(SEARCH_TYPES.keys())

        self.content_check = QCheckBox("본문 수집")
        self.content_check.setChecked(True)

        self.search_btn = QPushButton("🔍  검색")
        self.search_btn.setObjectName("searchBtn")
        self.search_btn.clicked.connect(self.start_crawl)

        self.save_btn = QPushButton("📄  CSV 저장")
        self.save_btn.setObjectName("csvBtn")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_file)

        self.excel_btn = QPushButton("📊  엑셀 저장")
        self.excel_btn.setObjectName("excelBtn")
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.save_excel_file)

        for btn in (self.search_btn, self.save_btn, self.excel_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        search_row = QWidget()
        search_row.setObjectName("searchRow")
        search_row.setStyleSheet("QWidget#searchRow { background: transparent; }")
        top = QHBoxLayout(search_row)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        top.addWidget(self.keyword_edit, 1)
        top.addWidget(self.type_combo)
        top.addWidget(self.content_check)
        top.addWidget(self.search_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.excel_btn)

        # 가운데: 기사 목록 + 상세 내용
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["No", "언론사", "제목"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.cellDoubleClicked.connect(self.open_link)

        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(True)

        self.list_card = make_card("🗂  기사 목록", self.table)
        self.list_title = self.list_card.findChild(QLabel, "cardTitle")

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.list_card)
        splitter.addWidget(make_card("📖  기사 상세", self.detail))
        splitter.setSizes([330, 420])

        # 하단: 진행 상태
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.statusBar().showMessage("  검색어를 입력하고 [검색]을 누르세요. 기사를 더블클릭하면 원문이 열립니다.")
        self.show_placeholder()

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 12)
        layout.setSpacing(14)
        layout.addWidget(banner)
        layout.addWidget(search_row)
        layout.addWidget(splitter, 1)
        central = QWidget()
        central.setObjectName("central")
        central.setLayout(layout)
        self.setCentralWidget(central)

    def show_placeholder(self):
        self.detail.setHtml(
            DETAIL_CSS
            + "<p class='empty' align='center'><br><br>✨ 검색을 실행하면 기사 내용이 여기에 표시됩니다 ✨</p>"
        )

    def start_crawl(self):
        keyword = self.keyword_edit.text().strip()
        if not keyword:
            QMessageBox.warning(self, "알림", "검색어를 입력하세요.")
            return
        if self.worker and self.worker.isRunning():
            return

        url = build_url(keyword, SEARCH_TYPES[self.type_combo.currentText()])
        self.table.setRowCount(0)
        self.list_title.setText("🗂  기사 목록")
        self.detail.setHtml(
            DETAIL_CSS + "<p class='empty' align='center'><br><br>⏳ 기사를 수집하고 있습니다...</p>"
        )
        self.search_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.excel_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # 기사 수를 알기 전에는 대기 표시
        self.progress_bar.setVisible(True)
        self.statusBar().showMessage(f"'{keyword}' 검색 결과 가져오는 중...")

        self.worker = CrawlWorker(url, self.content_check.isChecked())
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_progress(self, current, total, message):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        if message:
            self.statusBar().showMessage(f"[{current}/{total}] {message}")

    def on_finished(self, articles):
        self.articles = articles
        self.table.setRowCount(len(articles))
        for row, art in enumerate(articles):
            no_item = QTableWidgetItem(str(row + 1))
            no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            no_item.setForeground(QColor("#64748b"))
            press_item = QTableWidgetItem(art["press"])
            press_item.setForeground(QColor("#03c75a"))
            font = press_item.font()
            font.setBold(True)
            press_item.setFont(font)
            self.table.setItem(row, 0, no_item)
            self.table.setItem(row, 1, press_item)
            self.table.setItem(row, 2, QTableWidgetItem(art["title"]))

        self.search_btn.setEnabled(True)
        self.save_btn.setEnabled(bool(articles))
        self.excel_btn.setEnabled(bool(articles))
        self.progress_bar.setVisible(False)
        self.list_title.setText(f"🗂  기사 목록  ·  {len(articles)}건")
        self.statusBar().showMessage(f"  ✅ 수집 완료: 기사 {len(articles)}건")
        if articles:
            self.table.selectRow(0)
        else:
            self.show_placeholder()

    def on_failed(self, error):
        self.search_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("  ❌ 검색 실패")
        self.show_placeholder()
        QMessageBox.critical(self, "오류", f"페이지를 가져오지 못했습니다.\n{error}")

    def show_detail(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.articles):
            return
        art = {k: html.escape(v) for k, v in self.articles[row].items()}  # 기사 내용 속 <, & 등이 HTML로 해석되지 않도록
        parts = [
            DETAIL_CSS,
            f"<h2>{art['title']}</h2>",
            f"<p><span class='press'>🏢 {art['press']}</span>",
            f" &nbsp;│&nbsp; <a href='{art['link']}'>🔗 원문 보기</a>",
        ]
        if art["naver_link"]:
            parts.append(f" &nbsp;│&nbsp; <a href='{art['naver_link']}'>🟢 네이버뉴스</a>")
        parts.append("</p>")
        if art["summary"]:
            parts.append(
                "<table width='100%' cellpadding='12' class='summary'><tr><td>"
                f"<span class='label'>💡 요약</span><br>{art['summary']}</td></tr></table>"
            )
        if art["content"]:
            parts.append(f"<p class='content'>{art['content'].replace(chr(10), '<br>')}</p>")
        else:
            parts.append(
                "<p class='empty'>본문 없음 — 네이버뉴스 링크가 없거나 '본문 수집'이 꺼져 있습니다.</p>"
            )
        self.detail.setHtml("".join(parts))

    def open_link(self, row, _column):
        art = self.articles[row]
        QDesktopServices.openUrl(QUrl(art["naver_link"] or art["link"]))

    def save_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "CSV로 저장", "naver_news.csv", "CSV 파일 (*.csv)"
        )
        if not filename:
            return
        try:
            save_csv(self.articles, filename)
        except OSError as e:
            QMessageBox.critical(self, "오류", f"저장하지 못했습니다.\n{e}")
            return
        self.statusBar().showMessage(f"{filename} 파일로 저장했습니다.")

    def save_excel_file(self):
        keyword = self.keyword_edit.text().strip() or "뉴스"
        filename, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", f"naver_news_{keyword}.xlsx", "엑셀 파일 (*.xlsx)"
        )
        if not filename:
            return
        if not filename.lower().endswith(".xlsx"):
            filename += ".xlsx"
        try:
            save_excel(self.articles, filename, sheet_title=keyword)
        except OSError as e:
            # 같은 파일이 엑셀에 열려 있으면 PermissionError가 발생
            QMessageBox.critical(
                self, "오류", f"저장하지 못했습니다. 파일이 열려 있다면 닫고 다시 시도하세요.\n{e}"
            )
            return
        self.statusBar().showMessage(f"{filename} 파일로 저장했습니다.")


def resource_path(name):
    """PyInstaller로 묶인 exe에서는 임시 폴더(_MEIPASS), 아니면 스크립트 폴더 기준 경로"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def main():
    app = QApplication(sys.argv)
    icon_path = resource_path("app.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
