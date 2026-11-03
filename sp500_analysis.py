"""S&P 500 과거 데이터 클렌징 및 분석 GUI 앱 (PyQt6 + Pandas + Matplotlib)

사용법: python sp500_analysis.py [CSV 경로]
설치:  pip install PyQt6 pandas matplotlib

- CSV를 불러오면 자동으로 클렌징 후 분석한다.
- 기간(기본 2000-01 ~ 2019-12)을 바꾸고 [적용]을 누르면 그래프와 통계가 다시 계산된다.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

plt.rcParams["font.family"] = "Malgun Gothic"  # 한글 폰트 (Windows)
plt.rcParams["axes.unicode_minus"] = False

CSV_NAME = "S&P 500 과거 데이터.csv"
ICON_NAME = "sp500.ico"


def resource_path(name: str) -> Path:
    """PyInstaller로 묶인 exe에서는 임시 폴더(_MEIPASS), 아니면 스크립트 폴더 기준 경로"""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def default_csv() -> Path:
    """현재 폴더 → exe/스크립트 폴더 → exe에 포함된 샘플 데이터 순으로 CSV 탐색"""
    exe_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    for path in (Path.cwd() / CSV_NAME, exe_dir / CSV_NAME, resource_path(CSV_NAME)):
        if path.exists():
            return path
    return Path(CSV_NAME)


DEFAULT_START = QDate(2000, 1, 1)
DEFAULT_END = QDate(2019, 12, 31)
UP_COLOR, DOWN_COLOR = "#2ca02c", "#d62728"


# ---------------------------------------------------------------- 1. 데이터 클렌징
def load_and_clean(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """CSV를 읽어 정제한 DataFrame과 클렌징 로그를 반환"""
    log = []
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    log.append(f"[원본] {df.shape[0]}행 x {df.shape[1]}열, 컬럼: {list(df.columns)}")

    df = df.rename(columns={
        "날짜": "Date", "종가": "Close", "시가": "Open", "고가": "High",
        "저가": "Low", "거래량": "Volume", "변동 %": "Change",
    })
    missing = {"Date", "Close", "Open", "High", "Low", "Change"} - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {sorted(missing)}")

    # 날짜: "2019- 11- 14" 처럼 공백이 섞여 있으므로 제거 후 변환
    df["Date"] = pd.to_datetime(df["Date"].str.replace(" ", "", regex=False),
                                format="%Y-%m-%d", errors="coerce")

    # 가격: 천 단위 콤마 제거 후 숫자 변환
    for col in ["Close", "Open", "High", "Low"]:
        df[col] = pd.to_numeric(df[col].str.replace(",", "", regex=False), errors="coerce")
    log.append("[클렌징] 날짜 공백 제거, 가격 천 단위 콤마 제거 후 숫자 변환")

    # 변동 %: "%" 제거 후 실수 변환
    df["Change"] = pd.to_numeric(df["Change"].str.replace("%", "", regex=False), errors="coerce")

    # 거래량: 전부 비어 있으면 제거 (K/M/B 단위가 있으면 환산)
    if "Volume" in df.columns:
        vol = df["Volume"].fillna("").str.strip()
        if (vol == "").all():
            log.append("[클렌징] 거래량 컬럼이 전부 비어 있어 제거")
            df = df.drop(columns="Volume")
        else:
            mult = vol.str[-1].map({"K": 1e3, "M": 1e6, "B": 1e9}).fillna(1)
            df["Volume"] = pd.to_numeric(vol.str.rstrip("KMB"), errors="coerce") * mult

    before = len(df)
    df = df.dropna(subset=["Date", "Close"])
    df = df.drop_duplicates(subset="Date")
    log.append(f"[클렌징] 결측/중복 제거: {before - len(df)}행")

    # 이상치 점검: 고가 < 저가 등 논리 오류
    bad = df[(df["High"] < df["Low"]) | (df["Close"] <= 0)]
    log.append(f"[클렌징] 논리 오류(고가<저가, 종가<=0) 행 제거: {len(bad)}행")
    df = df.drop(bad.index)

    # 날짜 오름차순 정렬 후 인덱스로 설정
    df = df.sort_values("Date").set_index("Date")

    # 일간 수익률 재계산 (원본 변동 %와 비교 검증용)
    df["Return"] = df["Close"].pct_change() * 100
    diff = (df["Return"] - df["Change"]).abs().max()
    log.append(f"[검증] 재계산 수익률과 원본 변동 % 최대 차이: {diff:.3f}%p")

    log.append(f"[정제 후] {len(df)}행, 기간 {df.index.min().date()} ~ {df.index.max().date()}")
    log.append(f"[정제 후] 컬럼별 결측치:\n{df.isna().sum().to_string()}")
    return df, log


# ---------------------------------------------------------------- 2. 다각도 분석
def analyze(df: pd.DataFrame) -> dict:
    """선택 기간의 DataFrame을 분석해 결과를 dict로 반환"""
    close = df["Close"]
    ret = close.pct_change().dropna() * 100  # 기간 첫날 기준으로 다시 계산

    years = max((df.index[-1] - df.index[0]).days / 365.25, 1 / 365.25)
    total = close.iloc[-1] / close.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1

    peak = close.cummax()
    dd = (close / peak - 1) * 100
    trough = dd.idxmin()
    peak_date = close.loc[:trough].idxmax()

    yearly = close.resample("YE").last()
    yearly_ret = yearly.pct_change() * 100
    yearly_ret.iloc[0] = (yearly.iloc[0] / close.iloc[0] - 1) * 100
    yearly_ret.index = yearly_ret.index.year
    yearly_vol = ret.groupby(ret.index.year).std() * np.sqrt(252)

    monthly_ret = close.resample("ME").last().pct_change() * 100
    by_month = monthly_ret.groupby(monthly_ret.index.month).mean()
    dow = ret.groupby(ret.index.dayofweek).mean()
    dow.index = [["월", "화", "수", "목", "금", "토", "일"][i] for i in dow.index]

    summary = [
        ("기간", f"{df.index[0].date()} ~ {df.index[-1].date()} ({len(df):,} 거래일)"),
        ("시작 / 종료 종가", f"{close.iloc[0]:,.2f} → {close.iloc[-1]:,.2f}"),
        ("최고 종가", f"{close.max():,.2f} ({close.idxmax().date()})"),
        ("최저 종가", f"{close.min():,.2f} ({close.idxmin().date()})"),
        ("누적 수익률", f"{total:.2%}"),
        ("연평균 수익률(CAGR)", f"{cagr:.2%}"),
        ("연환산 변동성", f"{ret.std() * np.sqrt(252):.2f}%"),
        ("최대 낙폭(MDD)", f"{dd.min():.2f}% ({peak_date.date()} → {trough.date()})"),
        ("상승 / 하락 연도", f"{(yearly_ret > 0).sum()}개 / {(yearly_ret < 0).sum()}개"),
        ("일간 평균 / 표준편차", f"{ret.mean():.3f}% / {ret.std():.3f}%"),
        ("왜도 / 첨도", f"{ret.skew():.3f} / {ret.kurt():.3f}"),
        ("상승일 비율", f"{(ret > 0).mean():.1%}"),
        ("최대 상승일", f"{ret.max():+.2f}% ({ret.idxmax().date()})"),
        ("최대 하락일", f"{ret.min():+.2f}% ({ret.idxmin().date()})"),
    ]
    return {
        "close": close, "ret": ret, "dd": dd, "summary": summary,
        "yearly_ret": yearly_ret, "yearly_vol": yearly_vol,
        "by_month": by_month, "dow": dow,
        "top_up": ret.nlargest(10), "top_down": ret.nsmallest(10),
        "describe": df[["Close", "Open", "High", "Low"]].assign(Return=ret).describe(),
    }


# ---------------------------------------------------------------- 3. GUI 위젯
class DataFrameModel(QAbstractTableModel):
    """정제된 DataFrame을 QTableView로 보여주는 모델 (5천 행도 빠르게 표시)"""

    def __init__(self, df: pd.DataFrame | None = None):
        super().__init__()
        self._df = df if df is not None else pd.DataFrame()

    def set_frame(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        value = self._df.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return "" if pd.isna(value) else f"{value:,.2f}"
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and self._df.columns[index.column()] in ("Change", "Return"):
            if not pd.isna(value) and value != 0:
                return QColor(UP_COLOR if value > 0 else DOWN_COLOR)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return str(self._df.index[section].date())


class ChartPanel(QWidget):
    """Matplotlib Figure + 툴바(확대/이동/저장)를 담은 패널"""

    def __init__(self, figsize=(12, 6)):
        super().__init__()
        self.figure = Figure(figsize=figsize, layout="tight")
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas)


def make_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return table


def fill_table(table: QTableWidget, rows: list[tuple], color_col: int | None = None):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if isinstance(value, float):
                item = QTableWidgetItem(f"{value:,.2f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == color_col and value != 0:
                    item.setForeground(QColor(UP_COLOR if value > 0 else DOWN_COLOR))
            else:
                item = QTableWidgetItem(str(value))
            table.setItem(r, c, item)


class MainWindow(QMainWindow):
    def __init__(self, csv_path: Path | None = None):
        super().__init__()
        self.setWindowTitle("S&P 500 데이터 분석기")
        self.resize(1300, 850)
        self.df: pd.DataFrame | None = None

        # ---- 상단 컨트롤 바
        self.open_btn = QPushButton("CSV 열기")
        self.open_btn.clicked.connect(self.open_csv)
        self.file_label = QLabel("파일을 불러오세요")
        self.file_label.setStyleSheet("color: gray")

        self.start_edit = QDateEdit(DEFAULT_START)
        self.end_edit = QDateEdit(DEFAULT_END)
        for edit in (self.start_edit, self.end_edit):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
        self.apply_btn = QPushButton("적용")
        self.apply_btn.clicked.connect(self.refresh)
        self.reset_btn = QPushButton("전체 기간")
        self.reset_btn.clicked.connect(self.select_full_range)

        self.ma50_check = QCheckBox("50일 이동평균")
        self.ma200_check = QCheckBox("200일 이동평균")
        for check in (self.ma50_check, self.ma200_check):
            check.toggled.connect(self.draw_close_chart)

        self.save_btn = QPushButton("그래프 PNG 저장")
        self.save_btn.clicked.connect(self.save_charts)

        bar = QHBoxLayout()
        bar.addWidget(self.open_btn)
        bar.addWidget(self.file_label, 1)
        bar.addWidget(QLabel("기간"))
        bar.addWidget(self.start_edit)
        bar.addWidget(QLabel("~"))
        bar.addWidget(self.end_edit)
        bar.addWidget(self.apply_btn)
        bar.addWidget(self.reset_btn)
        bar.addSpacing(16)
        bar.addWidget(self.ma50_check)
        bar.addWidget(self.ma200_check)
        bar.addSpacing(16)
        bar.addWidget(self.save_btn)

        # ---- 탭
        self.close_chart = ChartPanel((13, 6))
        self.dash_chart = ChartPanel((13, 8))

        self.summary_table = make_table(["항목", "값"])
        self.yearly_table = make_table(["연도", "수익률(%)", "변동성(%)"])
        self.extreme_table = make_table(["최대 상승일", "등락(%)", "최대 하락일", "등락(%)"])
        self.describe_table = make_table(["통계", "Close", "Open", "High", "Low", "Return"])
        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(self.summary_table)
        left.addWidget(self.describe_table)
        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self.yearly_table)
        right.addWidget(self.extreme_table)
        stats_tab = QSplitter(Qt.Orientation.Horizontal)
        stats_tab.addWidget(left)
        stats_tab.addWidget(right)

        self.data_model = DataFrameModel()
        data_view = QTableView()
        data_view.setModel(self.data_model)
        data_view.setAlternatingRowColors(True)
        data_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.log_view = QPlainTextEdit(readOnly=True)
        self.log_view.setFont(QFont("Consolas", 10))

        self.tabs = QTabWidget()
        self.tabs.addTab(self.close_chart, "종가 추이")
        self.tabs.addTab(self.dash_chart, "분석 대시보드")
        self.tabs.addTab(stats_tab, "통계 요약")
        self.tabs.addTab(data_view, "정제 데이터")
        self.tabs.addTab(self.log_view, "클렌징 로그")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(bar)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)
        self.set_controls_enabled(False)

        if csv_path and csv_path.exists():
            self.load(csv_path)

    # ---- 동작
    def set_controls_enabled(self, enabled: bool):
        for w in (self.start_edit, self.end_edit, self.apply_btn, self.reset_btn,
                  self.ma50_check, self.ma200_check, self.save_btn):
            w.setEnabled(enabled)

    def open_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "S&P 500 CSV 열기", str(Path.cwd()),
                                              "CSV 파일 (*.csv);;모든 파일 (*)")
        if path:
            self.load(Path(path))

    def load(self, path: Path):
        try:
            df, log = load_and_clean(path)
        except Exception as e:
            QMessageBox.critical(self, "불러오기 실패", f"{path.name}\n\n{e}")
            return
        self.df = df
        self.file_label.setText(f"{path.name}  ({len(df):,}행)")
        self.file_label.setStyleSheet("")
        self.log_view.setPlainText("\n".join(log))
        self.data_model.set_frame(df)

        lo, hi = df.index.min(), df.index.max()
        for edit in (self.start_edit, self.end_edit):
            edit.setDateRange(QDate(lo.year, lo.month, lo.day), QDate(2100, 12, 31))
        self.set_controls_enabled(True)
        self.refresh()

    def select_full_range(self):
        lo, hi = self.df.index.min(), self.df.index.max()
        self.start_edit.setDate(QDate(lo.year, lo.month, lo.day))
        self.end_edit.setDate(QDate(hi.year, hi.month, hi.day))
        self.refresh()

    def period(self) -> pd.DataFrame:
        start = self.start_edit.date().toString("yyyy-MM-dd")
        end = self.end_edit.date().toString("yyyy-MM-dd")
        return self.df.loc[start:end]

    def refresh(self):
        if self.df is None:
            return
        sub = self.period()
        if len(sub) < 2:
            QMessageBox.warning(self, "기간 오류", "선택한 기간에 데이터가 2일 이상 있어야 합니다.")
            return
        self.result = analyze(sub)
        self.draw_close_chart()
        self.draw_dashboard()
        self.fill_stats()
        last = sub.index[-1].date()
        self.statusBar().showMessage(
            f"분석 기간: {sub.index[0].date()} ~ {last} ({len(sub):,} 거래일)"
            + ("   ※ 데이터는 선택 종료일 이전에 끝납니다" if pd.Timestamp(self.end_edit.date().toPyDate()) > sub.index[-1] else ""))

    def draw_close_chart(self):
        if self.df is None:
            return
        close = self.result["close"]
        fig = self.close_chart.figure
        fig.clear()
        ax = fig.add_subplot()
        ax.plot(close.index, close.values, color="tab:blue", lw=1.2, label="종가")

        # 이동평균은 전체 데이터로 계산해 기간 시작 부분도 끊기지 않게 함
        for check, window, color in ((self.ma50_check, 50, "tab:orange"), (self.ma200_check, 200, "tab:green")):
            if check.isChecked():
                ma = self.df["Close"].rolling(window).mean().loc[close.index[0]:close.index[-1]]
                ax.plot(ma.index, ma.values, color=color, lw=1, label=f"{window}일 이동평균")

        start = self.start_edit.date().toString("yyyy년 M월")
        end = self.end_edit.date().toString("yyyy년 M월")
        ax.set_title(f"S&P 500 종가 추이 ({start} ~ {end})", fontsize=15)
        ax.set_xlabel("날짜")
        ax.set_ylabel("종가 (USD)")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.grid(alpha=.3)

        # 최고/최저점 표시
        for label, date, offset in (("최고", close.idxmax(), (-60, 10)), ("최저", close.idxmin(), (60, 10))):
            ax.annotate(f"{label} {close[date]:,.1f}\n({date.date()})",
                        xy=(date, close[date]), xytext=offset,
                        textcoords="offset points", ha="center", va="bottom",
                        arrowprops=dict(arrowstyle="->"))
        if len(ax.get_lines()) > 1:
            ax.legend(loc="upper left")
        self.close_chart.canvas.draw()

    def draw_dashboard(self):
        r = self.result
        fig = self.dash_chart.figure
        fig.clear()
        axes = fig.subplots(2, 2)

        ax = axes[0, 0]
        ax.fill_between(r["dd"].index, r["dd"], 0, color=DOWN_COLOR, alpha=.4)
        ax.set_title("고점 대비 낙폭(%)"); ax.grid(alpha=.3)

        ax = axes[0, 1]
        yr = r["yearly_ret"]
        ax.bar(yr.index, yr, color=[UP_COLOR if v > 0 else DOWN_COLOR for v in yr])
        ax.set_xticks(yr.index[:: max(1, len(yr) // 10)])
        ax.set_title("연도별 수익률(%)"); ax.grid(alpha=.3, axis="y")

        ax = axes[1, 0]
        bm = r["by_month"]
        ax.bar([f"{m}월" for m in bm.index], bm, color=[UP_COLOR if v > 0 else DOWN_COLOR for v in bm])
        ax.set_title("월별 평균 수익률(%) — 계절성"); ax.grid(alpha=.3, axis="y")

        ax = axes[1, 1]
        ax.hist(r["ret"], bins=100, color="tab:blue", alpha=.7)
        ax.set_title("일간 수익률 분포(%)"); ax.grid(alpha=.3)
        self.dash_chart.canvas.draw()

    def fill_stats(self):
        r = self.result
        fill_table(self.summary_table, r["summary"])
        fill_table(self.yearly_table,
                   [(str(y), float(r["yearly_ret"][y]), float(r["yearly_vol"].get(y, np.nan)))
                    for y in r["yearly_ret"].index], color_col=1)
        fill_table(self.extreme_table,
                   [(str(ud.date()), float(uv), str(dd_.date()), float(dv))
                    for (ud, uv), (dd_, dv) in zip(r["top_up"].items(), r["top_down"].items())])
        for row in range(self.extreme_table.rowCount()):
            self.extreme_table.item(row, 1).setForeground(QColor(UP_COLOR))
            self.extreme_table.item(row, 3).setForeground(QColor(DOWN_COLOR))
        desc = r["describe"]
        fill_table(self.describe_table,
                   [(name, *map(float, desc.loc[name])) for name in desc.index])

    def save_charts(self):
        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택", str(Path.cwd()))
        if not folder:
            return
        start = self.start_edit.date().toString("yyyyMM")
        end = self.end_edit.date().toString("yyyyMM")
        paths = [Path(folder) / f"close_{start}_{end}.png", Path(folder) / f"dashboard_{start}_{end}.png"]
        self.close_chart.figure.savefig(paths[0], dpi=120)
        self.dash_chart.figure.savefig(paths[1], dpi=120)
        QMessageBox.information(self, "저장 완료", "\n".join(str(p) for p in paths))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 9))
    if resource_path(ICON_NAME).exists():
        app.setWindowIcon(QIcon(str(resource_path(ICON_NAME))))
    window = MainWindow(Path(sys.argv[1]) if len(sys.argv) > 1 else default_csv())
    window.show()
    sys.exit(app.exec())
