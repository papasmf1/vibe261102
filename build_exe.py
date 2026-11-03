"""
크롤러 앱들을 PyInstaller로 윈도우 실행파일(.exe)로 만드는 빌드 스크립트

설치:  pip install pyinstaller
실행:  python build_exe.py            (전체 빌드)
       python build_exe.py news       (네이버 뉴스 크롤러만)
       python build_exe.py kospi200   (코스피200 크롤러만)
       python build_exe.py sp500      (S&P 500 분석기만)
결과:  dist/<앱이름>.exe  (파이썬이 없는 PC에서도 실행 가능)
       dist/<앱이름>.zip  (배포용 압축 파일)
"""

import os
import shutil
import sys
import zipfile

import PyInstaller.__main__

# 빌드 대상: 키 -> (exe 이름, 스크립트, 아이콘 파일, 아이콘 글자)
APPS = {
    "news": ("NaverNewsCrawler", "naver_news_crawler.py", "app.ico", "N"),
    "kospi200": ("Kospi200Crawler", "kospi200_crawler.py", "kospi200.ico", "K"),
    "sp500": ("SP500Analyzer", "sp500_analysis.py", "sp500.ico", "S"),
}

# 앱별 추가 포함 파일 (exe 안에 함께 묶임, 없으면 건너뜀)
EXTRA_DATA = {
    "sp500": ["S&P 500 과거 데이터.csv"],  # 실행 시 바로 보여줄 샘플 데이터
}

# 앱별 추가 옵션
EXTRA_ARGS = {
    # matplotlib이 다른 Qt 바인딩까지 끌어오면 빌드가 중단되므로 PyQt6만 남기고 제외
    "sp500": [arg for mod in ("PySide6", "PySide2", "PyQt5", "tkinter")
              for arg in ("--exclude-module", mod)],
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def make_icon(path, letter):
    """앱 아이콘(.ico)이 없으면 PyQt6로 그려서 만듦"""
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QColor, QFont, QGuiApplication, QLinearGradient, QPainter, QPixmap

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    size = 256
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor("#03c75a"))
    gradient.setColorAt(0.5, QColor("#0ea5e9"))
    gradient.setColorAt(1, QColor("#8b5cf6"))
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(8, 8, size - 16, size - 16), 56, 56)

    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("Segoe UI", 120, QFont.Weight.Black))
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, letter)
    painter.end()

    if not pixmap.save(path, "ICO"):
        raise RuntimeError("아이콘 파일을 만들지 못했습니다.")
    print(f"아이콘 생성: {path}")


def build(key):
    app_name, script, icon, letter = APPS[key]
    os.chdir(BASE_DIR)
    if not os.path.exists(icon):
        make_icon(icon, letter)

    extra = []
    for data in EXTRA_DATA.get(key, []):
        if os.path.exists(data):
            extra += ["--add-data", f"{data}{os.pathsep}."]
        else:
            print(f"경고: {data} 파일이 없어 포함하지 않습니다.")

    PyInstaller.__main__.run([
        script,
        "--name", app_name,
        "--onefile",          # 실행파일 하나로 묶기
        "--windowed",         # 콘솔(검은 창) 없이 실행
        "--icon", icon,       # exe 파일 아이콘
        "--add-data", f"{icon}{os.pathsep}.",  # 실행 중 창 아이콘으로도 사용
        "--noconfirm",
        "--clean",
        *extra,
        *EXTRA_ARGS.get(key, []),
    ])

    exe_path = os.path.join("dist", f"{app_name}.exe")
    zip_path = os.path.join("dist", f"{app_name}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, f"{app_name}.exe")

    # 빌드 중간 파일 정리
    shutil.rmtree("build", ignore_errors=True)

    size_mb = os.path.getsize(exe_path) / 1024 / 1024
    print(f"\n완료: {exe_path} ({size_mb:.1f} MB)")
    print(f"배포용 압축 파일: {zip_path}")


if __name__ == "__main__":
    targets = sys.argv[1:] or list(APPS)
    unknown = [t for t in targets if t not in APPS]
    if unknown:
        sys.exit(f"알 수 없는 대상: {', '.join(unknown)} (사용 가능: {', '.join(APPS)})")
    for target in targets:
        build(target)
