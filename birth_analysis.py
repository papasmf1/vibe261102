"""대한민국 출생아수 데이터(KOSIS) 클렌징 및 다각도 분석 GUI 앱 (PyQt6 + Pandas + Matplotlib)

사용법: python birth_analysis.py [엑셀 경로]
설치:  pip install PyQt6 pandas openpyxl matplotlib

- 엑셀을 불러오면 가로(연도=열) 형태의 KOSIS 표를 세로(연도=행)로 바꾸고 자동으로 클렌징한다.
- 연도 범위(기본 1970~2025)를 바꾸고 [적용]을 누르면 그래프와 통계가 다시 계산된다.
"""
import sys
from numbers import Number
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
import matplotlib.pyplot as plt
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
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

XLSX_NAME = "출생아수__합계출산율__자연증가_등.xlsx"
DEFAULT_START, DEFAULT_END = 1970, 2025
UP_COLOR, DOWN_COLOR = "#16a34a", "#dc2626"
LINE_COLOR = "#2563eb"

# KOSIS 원본 항목명 → 분석용 컬럼명
COLUMN_MAP = {
    "출생아수(명)": "출생아수",
    "자연증가건수(명)": "자연증가",
    "조출생률(천명당)": "조출생률",
    "자연증가율(천명당)": "자연증가율",
    "합계출산율(명)": "합계출산율",
    "출생성비(명)": "출생성비",
}

# 값이 가질 수 있는 상식적인 범위 (이상치 검사용)
VALID_RANGE = {
    "출생아수": (0, 2_000_000),
    "자연증가": (-1_000_000, 2_000_000),
    "조출생률": (0, 60),
    "자연증가율": (-30, 60),
    "합계출산율": (0, 8),
    "출생성비": (90, 130),
}


def resource_path(name: str) -> Path:
    """PyInstaller로 묶인 exe에서는 임시 폴더(_MEIPASS), 아니면 스크립트 폴더 기준 경로"""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def default_xlsx() -> Path:
    """현재 폴더 → exe/스크립트 폴더 → exe에 포함된 샘플 데이터 순으로 엑셀 탐색"""
    exe_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    for path in (Path.cwd() / XLSX_NAME, exe_dir / XLSX_NAME, resource_path(XLSX_NAME)):
        if path.exists():
            return path
    return Path(XLSX_NAME)


# ---------------------------------------------------------------- 1. 데이터 클렌징
def load_and_clean(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """KOSIS 엑셀을 읽어 정제한 DataFrame과 클렌징 로그를 반환"""
    log = []
    raw = pd.read_excel(path, sheet_name=0, header=None)
    log.append(f"[원본] {raw.shape[0]}행 x {raw.shape[1]}열 (항목=행, 연도=열 형태)")

    # 첫 열이 항목명, 첫 행이 연도인 가로형 표를 전치
    raw = raw.set_index(0)
    df = raw.iloc[1:].T
    df.index = raw.iloc[0].values
    df.columns = [str(c).strip() for c in df.columns]
    log.append("[클렌징] 표 전치: 연도=행, 항목=열")

    # 항목명 표준화 (알 수 없는 항목은 단위 괄호만 제거)
    df = df.rename(columns=lambda c: COLUMN_MAP.get(c, c.split("(")[0]))
    missing_cols = {"출생아수", "자연증가", "합계출산율", "출생성비"} - set(df.columns)
    if missing_cols:
        raise ValueError(f"필수 항목이 없습니다: {sorted(missing_cols)}")
    log.append(f"[클렌징] 항목명 표준화: {list(df.columns)}")

    # 숫자 변환: 콤마·공백·KOSIS 결측 기호('-', '…', 'x')를 정리한 뒤 숫자로
    df = df.apply(
        lambda s: pd.to_numeric(
            s.astype(str).str.replace(",", "").str.strip().replace({"-": None, "…": None, "x": None, "nan": None}),
            errors="coerce",
        )
    )
    log.append("[클렌징] 콤마·공백·결측 기호 제거 후 숫자 변환")

    # 연도 정리: 숫자가 아닌 연도 제거 → 정수형 → 중복 제거 → 정렬
    df.index = pd.to_numeric(pd.Series(df.index).astype(str).str.extract(r"(\d{4})")[0], errors="coerce")
    df = df[df.index.notna()]
    df.index = df.index.astype(int)
    df.index.name = "연도"
    dup = df.index.duplicated(keep="last").sum()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    log.append(f"[클렌징] 연도 정수 변환·정렬, 중복 연도 제거: {dup}건")

    # 정수 항목은 정수형으로
    for col in ("출생아수", "자연증가"):
        df[col] = df[col].round().astype("Int64")

    # 결측 / 누락 연도 / 범위 이탈 점검
    missing = df.isna().sum()
    gaps = sorted(set(range(df.index.min(), df.index.max() + 1)) - set(df.index))
    out_of_range = {
        col: df.index[(df[col] < lo) | (df[col] > hi)].tolist()
        for col, (lo, hi) in VALID_RANGE.items()
        if col in df and ((df[col] < lo) | (df[col] > hi)).any()
    }
    log.append(f"[검증] 결측값: {int(missing.sum())}건"
               + ("" if missing.sum() == 0 else f" {missing[missing > 0].to_dict()}"))
    log.append(f"[검증] 누락 연도: {gaps or '없음'}")
    log.append(f"[검증] 범위 이탈 값: {out_of_range or '없음'}")

    # 결측이 있으면 연도 기준 선형 보간 (양 끝은 보간하지 않음)
    if missing.sum():
        df = df.interpolate(method="index", limit_area="inside")
        log.append("[클렌징] 결측값 연도 기준 선형 보간")

    # 파생 변수
    df["사망자수"] = df["출생아수"] - df["자연증가"]  # 자연증가 = 출생 - 사망
    df["전년대비증감"] = df["출생아수"].diff()
    df["전년대비증감률(%)"] = df["출생아수"].astype(float).pct_change() * 100
    df["5년이동평균"] = df["출생아수"].astype(float).rolling(5, center=True).mean()
    df["연대"] = (df.index // 10 * 10).astype(str) + "년대"
    log.append("[파생] 사망자수, 전년대비증감, 전년대비증감률(%), 5년이동평균, 연대")

    log.append(f"[정제 후] {len(df)}개 연도 ({df.index.min()}~{df.index.max()}), {df.shape[1]}개 컬럼")
    return df, log


# ---------------------------------------------------------------- 2. 다각도 분석
def first_year(df: pd.DataFrame, cond: pd.Series):
    hit = df.index[cond.fillna(False)]
    return int(hit[0]) if len(hit) else None


def analyze(df: pd.DataFrame) -> dict:
    """선택 연도 범위의 DataFrame을 분석해 결과를 dict로 반환"""
    births = df["출생아수"].astype(float)
    first, last = int(df.index[0]), int(df.index[-1])
    peak, low = births.idxmax(), births.idxmin()
    cagr = ((births[last] / births[first]) ** (1 / (last - first)) - 1) * 100

    # 최장 연속 감소 구간
    down = (df["전년대비증감"] < 0).fillna(False).astype(int)
    streak = down.groupby((down != down.shift()).cumsum()).cumsum()
    streak_end, streak_len = int(streak.idxmax()), int(streak.max())

    summary = [
        ("분석 기간", f"{first}~{last}년 ({len(df)}개 연도)"),
        ("시작 / 종료 출생아수", f"{births[first]:,.0f}명 → {births[last]:,.0f}명"),
        ("변화", f"{births[last] / births[first] * 100:.1f}% 수준 ({births[last] - births[first]:+,.0f}명)"),
        ("최대 출생아수", f"{peak}년 {births[peak]:,.0f}명"),
        ("최소 출생아수", f"{low}년 {births[low]:,.0f}명"),
        ("연평균 증감률(CAGR)", f"{cagr:+.2f}%"),
        ("증가 / 감소 연도", f"{(df['전년대비증감'] > 0).sum()}개 / {(df['전년대비증감'] < 0).sum()}개"),
        ("최장 연속 감소", f"{streak_end - streak_len + 1}~{streak_end}년 ({streak_len}년)" if streak_len else "-"),
    ]

    # 주요 마일스톤 (기간 내 처음 도달한 해)
    milestones = {
        "출생아수 50만 명 미만": df["출생아수"] < 500_000,
        "출생아수 40만 명 미만": df["출생아수"] < 400_000,
        "출생아수 30만 명 미만": df["출생아수"] < 300_000,
        "합계출산율 2.1 미만 (인구대체수준)": df["합계출산율"] < 2.1,
        "합계출산율 1.3 미만 (초저출산)": df["합계출산율"] < 1.3,
        "합계출산율 1.0 미만": df["합계출산율"] < 1.0,
        "자연감소 시작 (데드크로스)": df["자연증가"] < 0,
    }
    summary += [(f"처음 도달: {name}", f"{first_year(df, cond) or '-'}") for name, cond in milestones.items()]

    # 출생성비 불균형 (여아 100명당 남아 110명 이상)
    ratio = df["출생성비"]
    high = ratio[ratio >= 110]
    summary.append(("출생성비 110 이상 연도", f"{len(high)}개"))
    summary.append(("출생성비 최고", f"{ratio.idxmax()}년 {ratio.max()}"))

    # 저점 이후 반등
    if low != last:
        summary.append(("최저점 이후 반등", f"{low}→{last}년 {(births[last] / births[low] - 1) * 100:+.1f}%"))

    decade = df.groupby("연대").agg(
        평균출생아수=("출생아수", "mean"),
        평균사망자수=("사망자수", "mean"),
        평균합계출산율=("합계출산율", "mean"),
        평균출생성비=("출생성비", "mean"),
        연도수=("출생아수", "size"),
    ).astype(float)
    decade["직전연대대비(%)"] = decade["평균출생아수"].pct_change() * 100

    # 구간별 CAGR (선택 범위와 겹치는 구간만)
    bounds = [b for b in (1970, 1983, 1990, 2000, 2005, 2015, 2023) if first < b < last]
    bounds = [first, *bounds, last]
    cagr_rows = [
        (f"{a}~{b}", ((births[b] / births[a]) ** (1 / (b - a)) - 1) * 100, int(births[a]), int(births[b]))
        for a, b in zip(bounds, bounds[1:])
    ]

    chg = df[["전년대비증감", "전년대비증감률(%)"]].dropna().astype(float)
    corr_cols = ["출생아수", "사망자수", "조출생률", "합계출산율", "출생성비"]
    return {
        "df": df,
        "summary": summary,
        "decade": decade,
        "cagr": cagr_rows,
        "top_down": chg.nsmallest(10, "전년대비증감"),
        "top_up": chg.nlargest(10, "전년대비증감"),
        "describe": df[["출생아수", "사망자수", "자연증가", "조출생률", "합계출산율", "출생성비"]].astype(float).describe(),
        "corr": df[corr_cols].astype(float).corr(),
    }


# ---------------------------------------------------------------- 3. 그래프
man_formatter = FuncFormatter(lambda v, _: f"{v / 10_000:,.0f}만")


def draw_births_line(fig: Figure, df: pd.DataFrame, show_ma: bool, show_marker: bool):
    """연도별 출생아수 라인 그래프"""
    s = df["출생아수"].astype(float)
    start, end = int(s.index[0]), int(s.index[-1])
    fig.clear()
    ax = fig.add_subplot()
    ax.plot(s.index, s.values, color=LINE_COLOR, linewidth=2.2,
            marker="o" if show_marker else None, markersize=3.5, label="출생아수")
    ax.fill_between(s.index, s.values, color=LINE_COLOR, alpha=0.08)
    if show_ma:
        ax.plot(df.index, df["5년이동평균"], color="#f59e0b", linewidth=1.5, linestyle="--", label="5년 이동평균")

    # 최대·최소·마지막 연도 강조
    marks = {s.idxmax(): (DOWN_COLOR, 10), s.idxmin(): (DOWN_COLOR, -14), end: ("#111827", 10)}
    for year, (color, dy) in marks.items():
        ax.scatter(year, s[year], color=color, s=60, zorder=5)
        ax.annotate(f"{year}년\n{s[year]:,.0f}명", (year, s[year]), xytext=(0, dy),
                    textcoords="offset points", ha="center", va="bottom" if dy > 0 else "top",
                    fontsize=9.5, color=color, fontweight="bold")

    for level in (500_000, 300_000):
        if s.min() < level < s.max() * 1.1:
            ax.axhline(level, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
            ax.text(start, level + s.max() * 0.01, f" {level // 10_000}만 명", color="gray", fontsize=9)

    ax.set_title(f"대한민국 연도별 출생아수 ({start}~{end})", fontsize=16, fontweight="bold", pad=14)
    ax.set_xlabel("연도")
    ax.set_ylabel("출생아수 (명)")
    ax.yaxis.set_major_formatter(man_formatter)
    step = 5 if end - start > 15 else 1
    ax.set_xticks(range(start - start % step + (step if start % step else 0), end + 1, step))
    ax.set_xlim(start - 1, end + 1)
    ax.set_ylim(0, s.max() * 1.15)
    ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper right")
    fig.text(0.99, 0.01, "자료: 통계청(국가데이터처) 「인구동향조사」, KOSIS", ha="right", fontsize=8, color="gray")


def draw_dashboard(fig: Figure, df: pd.DataFrame):
    """다각도 분석 대시보드 (2x3)"""
    fig.clear()
    axes = fig.subplots(2, 3)
    x = df.index

    # (1) 출생아수 vs 사망자수 → 데드크로스
    ax = axes[0, 0]
    ax.plot(x, df["출생아수"].astype(float), label="출생아수", color=LINE_COLOR, linewidth=2)
    ax.plot(x, df["사망자수"].astype(float), label="사망자수", color="#6b7280", linewidth=2)
    cross = first_year(df, df["자연증가"] < 0)
    if cross:
        ax.axvline(cross, color=DOWN_COLOR, linestyle="--", linewidth=1)
        ax.text(cross - 0.5, ax.get_ylim()[1] * 0.9, f"{cross}년\n데드크로스", color=DOWN_COLOR, ha="right", fontsize=9)
    ax.yaxis.set_major_formatter(man_formatter)
    ax.set_title("출생아수 vs 사망자수")
    ax.legend()

    # (2) 합계출산율
    ax = axes[0, 1]
    ax.plot(x, df["합계출산율"], color="#7c3aed", linewidth=2)
    for lvl, txt in ((2.1, "대체출산율 2.1"), (1.3, "초저출산 1.3"), (1.0, "1.0")):
        ax.axhline(lvl, color="gray", linestyle="--", linewidth=0.8)
        ax.text(x[-1], lvl, txt, ha="right", va="bottom", fontsize=8.5, color="gray")
    ax.set_title("합계출산율 (여성 1명당)")

    # (3) 전년 대비 증감률
    ax = axes[0, 2]
    rate = df["전년대비증감률(%)"].fillna(0)
    ax.bar(x, rate, color=np.where(rate >= 0, UP_COLOR, DOWN_COLOR))
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("출생아수 전년 대비 증감률 (%)")

    # (4) 연대별 평균 출생아수
    ax = axes[1, 0]
    dec = df.groupby("연대")["출생아수"].mean().astype(float)
    bars = ax.bar(dec.index, dec.values, color="#60a5fa")
    ax.bar_label(bars, labels=[f"{v / 10_000:.1f}만" for v in dec.values], fontsize=9)
    ax.yaxis.set_major_formatter(man_formatter)
    ax.set_title("연대별 평균 출생아수")

    # (5) 출생성비
    ax = axes[1, 1]
    ax.plot(x, df["출생성비"], color="#ea580c", linewidth=2)
    ax.axhspan(103, 107, color=UP_COLOR, alpha=0.12, label="자연 성비(103~107)")
    ax.set_title("출생성비 (여아 100명당 남아)")
    ax.legend(loc="upper right")

    # (6) 자연증가
    ax = axes[1, 2]
    nat = df["자연증가"].astype(float)
    ax.fill_between(x, nat, where=nat >= 0, color=UP_COLOR, alpha=0.5, interpolate=True, label="자연증가")
    ax.fill_between(x, nat, where=nat < 0, color=DOWN_COLOR, alpha=0.5, interpolate=True, label="자연감소")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.yaxis.set_major_formatter(man_formatter)
    ax.set_title("자연증가 건수 (출생 - 사망)")
    ax.legend()

    for ax in axes.flat:
        ax.grid(alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"대한민국 출생·인구동향 다각도 분석 ({x[0]}~{x[-1]})", fontsize=15, fontweight="bold")


# ---------------------------------------------------------------- 4. GUI 위젯
def format_value(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (int, np.integer)):
        return f"{value:,}"
    if isinstance(value, Number):
        return f"{value:,.2f}"
    return str(value)


class DataFrameModel(QAbstractTableModel):
    """정제된 DataFrame을 QTableView로 보여주는 모델"""

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
            return format_value(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and self._df.columns[index.column()].startswith(("전년대비", "자연증가")):
            if not pd.isna(value) and value != 0:
                return QColor(UP_COLOR if value > 0 else DOWN_COLOR)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return str(self._df.index[section])


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


def fill_table(table: QTableWidget, rows: list[tuple], color_cols: tuple[int, ...] = ()):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(format_value(value))
            if isinstance(value, Number):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c in color_cols and not pd.isna(value) and value != 0:
                    item.setForeground(QColor(UP_COLOR if value > 0 else DOWN_COLOR))
            table.setItem(r, c, item)


def titled(title: str, widget: QWidget) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel(title)
    label.setStyleSheet("font-weight: bold; padding: 4px 0")
    layout.addWidget(label)
    layout.addWidget(widget)
    return box


class MainWindow(QMainWindow):
    def __init__(self, xlsx_path: Path | None = None):
        super().__init__()
        self.setWindowTitle("대한민국 출생아수 데이터 분석기")
        self.resize(1400, 880)
        self.df: pd.DataFrame | None = None

        # ---- 상단 컨트롤 바
        self.open_btn = QPushButton("엑셀 열기")
        self.open_btn.clicked.connect(self.open_xlsx)
        self.file_label = QLabel("파일을 불러오세요")
        self.file_label.setStyleSheet("color: gray")

        self.start_spin = QSpinBox()
        self.end_spin = QSpinBox()
        for spin in (self.start_spin, self.end_spin):
            spin.setRange(1900, 2100)
            spin.setSuffix("년")
        self.start_spin.setValue(DEFAULT_START)
        self.end_spin.setValue(DEFAULT_END)
        self.apply_btn = QPushButton("적용")
        self.apply_btn.clicked.connect(self.refresh)
        self.reset_btn = QPushButton("전체 기간")
        self.reset_btn.clicked.connect(self.select_full_range)

        self.ma_check = QCheckBox("5년 이동평균")
        self.marker_check = QCheckBox("마커 표시")
        self.marker_check.setChecked(True)
        for check in (self.ma_check, self.marker_check):
            check.toggled.connect(self.draw_line_chart)

        self.save_btn = QPushButton("그래프 PNG 저장")
        self.save_btn.clicked.connect(self.save_charts)
        self.csv_btn = QPushButton("정제 데이터 CSV 저장")
        self.csv_btn.clicked.connect(self.save_csv)

        bar = QHBoxLayout()
        bar.addWidget(self.open_btn)
        bar.addWidget(self.file_label, 1)
        bar.addWidget(QLabel("기간"))
        bar.addWidget(self.start_spin)
        bar.addWidget(QLabel("~"))
        bar.addWidget(self.end_spin)
        bar.addWidget(self.apply_btn)
        bar.addWidget(self.reset_btn)
        bar.addSpacing(16)
        bar.addWidget(self.ma_check)
        bar.addWidget(self.marker_check)
        bar.addSpacing(16)
        bar.addWidget(self.save_btn)
        bar.addWidget(self.csv_btn)

        # ---- 탭
        self.line_chart = ChartPanel((13, 6.5))
        self.dash_chart = ChartPanel((15, 9))

        self.summary_table = make_table(["항목", "값"])
        self.describe_table = make_table(["통계", "출생아수", "사망자수", "자연증가", "조출생률", "합계출산율", "출생성비"])
        self.decade_table = make_table(["연대", "평균출생아수", "평균사망자수", "평균합계출산율", "평균출생성비", "연도수", "직전연대대비(%)"])
        self.cagr_table = make_table(["구간", "연평균 증감률(%)", "시작 출생아수", "종료 출생아수"])
        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(titled("핵심 지표 · 마일스톤", self.summary_table))
        left.addWidget(titled("기술통계", self.describe_table))
        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(titled("연대별 평균", self.decade_table))
        right.addWidget(titled("구간별 연평균 증감률(CAGR)", self.cagr_table))
        stats_tab = QSplitter(Qt.Orientation.Horizontal)
        stats_tab.addWidget(left)
        stats_tab.addWidget(right)
        stats_tab.setSizes([550, 850])

        self.change_table = make_table(["감소 연도", "증감(명)", "증감률(%)", "증가 연도", "증감(명)", "증감률(%)"])
        self.corr_table = make_table(["", "출생아수", "사망자수", "조출생률", "합계출산율", "출생성비"])
        change_tab = QSplitter(Qt.Orientation.Vertical)
        change_tab.addWidget(titled("전년 대비 증감 TOP 10", self.change_table))
        change_tab.addWidget(titled("상관관계 (피어슨)", self.corr_table))

        self.data_model = DataFrameModel()
        data_view = QTableView()
        data_view.setModel(self.data_model)
        data_view.setAlternatingRowColors(True)
        data_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.log_view = QPlainTextEdit(readOnly=True)
        self.log_view.setFont(QFont("Consolas", 10))

        self.tabs = QTabWidget()
        self.tabs.addTab(self.line_chart, "출생아수 추이")
        self.tabs.addTab(self.dash_chart, "분석 대시보드")
        self.tabs.addTab(stats_tab, "통계 요약")
        self.tabs.addTab(change_tab, "증감 · 상관관계")
        self.tabs.addTab(data_view, "정제 데이터")
        self.tabs.addTab(self.log_view, "클렌징 로그")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(bar)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)
        self.set_controls_enabled(False)

        if xlsx_path and xlsx_path.exists():
            self.load(xlsx_path)

    # ---- 동작
    def set_controls_enabled(self, enabled: bool):
        for w in (self.start_spin, self.end_spin, self.apply_btn, self.reset_btn,
                  self.ma_check, self.marker_check, self.save_btn, self.csv_btn):
            w.setEnabled(enabled)

    def open_xlsx(self):
        path, _ = QFileDialog.getOpenFileName(self, "출생아수 엑셀 열기", str(Path.cwd()),
                                              "엑셀 파일 (*.xlsx *.xls);;모든 파일 (*)")
        if path:
            self.load(Path(path))

    def load(self, path: Path):
        try:
            df, log = load_and_clean(path)
        except Exception as e:
            QMessageBox.critical(self, "불러오기 실패", f"{path.name}\n\n{e}")
            return
        self.df = df
        self.file_label.setText(f"{path.name}  ({len(df)}개 연도)")
        self.file_label.setStyleSheet("")
        self.log_view.setPlainText("\n".join(log))
        self.data_model.set_frame(df)

        lo, hi = int(df.index.min()), int(df.index.max())
        for spin in (self.start_spin, self.end_spin):
            spin.setRange(lo, hi)
        self.start_spin.setValue(max(lo, DEFAULT_START))
        self.end_spin.setValue(min(hi, DEFAULT_END))
        self.set_controls_enabled(True)
        self.refresh()

    def select_full_range(self):
        self.start_spin.setValue(int(self.df.index.min()))
        self.end_spin.setValue(int(self.df.index.max()))
        self.refresh()

    def period(self) -> pd.DataFrame:
        return self.df.loc[self.start_spin.value():self.end_spin.value()]

    def refresh(self):
        if self.df is None:
            return
        sub = self.period()
        if len(sub) < 2:
            QMessageBox.warning(self, "기간 오류", "시작 연도가 종료 연도보다 앞서야 하며, 2개 연도 이상이어야 합니다.")
            return
        self.result = analyze(sub)
        self.draw_line_chart()
        draw_dashboard(self.dash_chart.figure, sub)
        self.dash_chart.canvas.draw()
        self.fill_stats()
        self.statusBar().showMessage(f"분석 기간: {sub.index[0]}~{sub.index[-1]}년 ({len(sub)}개 연도)")

    def draw_line_chart(self):
        if self.df is None:
            return
        draw_births_line(self.line_chart.figure, self.result["df"],
                         self.ma_check.isChecked(), self.marker_check.isChecked())
        self.line_chart.canvas.draw()

    def fill_stats(self):
        r = self.result
        fill_table(self.summary_table, r["summary"])

        desc = r["describe"]
        fill_table(self.describe_table, [(name, *map(float, desc.loc[name])) for name in desc.index])

        dec = r["decade"]
        fill_table(self.decade_table,
                   [(name, *(float(v) for v in row[:4]), int(row.iloc[4]), float(row.iloc[5]))
                    for name, row in dec.iterrows()], color_cols=(6,))

        fill_table(self.cagr_table, r["cagr"], color_cols=(1,))

        fill_table(self.change_table,
                   [(f"{dy}년", int(dv["전년대비증감"]), float(dv["전년대비증감률(%)"]),
                     f"{uy}년", int(uv["전년대비증감"]), float(uv["전년대비증감률(%)"]))
                    for (dy, dv), (uy, uv) in zip(r["top_down"].iterrows(), r["top_up"].iterrows())],
                   color_cols=(1, 2, 4, 5))

        corr = r["corr"]
        fill_table(self.corr_table, [(name, *map(float, corr.loc[name])) for name in corr.index])
        for row in range(corr.shape[0]):
            for col in range(corr.shape[1]):
                v = corr.iat[row, col]
                base = QColor(UP_COLOR if v >= 0 else DOWN_COLOR)
                base.setAlphaF(min(abs(v), 1) * 0.45)
                self.corr_table.item(row, col + 1).setBackground(base)

    def save_charts(self):
        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택", str(Path.cwd()))
        if not folder:
            return
        span = f"{self.start_spin.value()}_{self.end_spin.value()}"
        paths = [Path(folder) / f"births_line_{span}.png", Path(folder) / f"analysis_dashboard_{span}.png"]
        self.line_chart.figure.savefig(paths[0], dpi=150)
        self.dash_chart.figure.savefig(paths[1], dpi=130)
        QMessageBox.information(self, "저장 완료", "\n".join(str(p) for p in paths))

    def save_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "정제 데이터 저장", str(Path.cwd() / "births_cleaned.csv"),
                                              "CSV 파일 (*.csv)")
        if path:
            self.df.to_csv(path, encoding="utf-8-sig")
            QMessageBox.information(self, "저장 완료", path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 9))
    window = MainWindow(Path(sys.argv[1]) if len(sys.argv) > 1 else default_xlsx())
    window.show()
    sys.exit(app.exec())
