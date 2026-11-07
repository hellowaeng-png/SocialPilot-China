from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QLineEdit, QMessageBox, QFileDialog, QTextEdit, QInputDialog,
)

APP_DIR = Path.home() / "AppData" / "Local" / "SocialPilotChina"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB = APP_DIR / "socialpilot.db"


def normalize_body(value: str) -> str:
    return re.sub(r"\\s+", " ", value).strip().casefold()


def parse_txt(text: str, mode: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    if mode == "每行一条":
        return [line.strip() for line in text.split("\n") if line.strip()]
    return [part.strip() for part in re.split(r"\n[ \t]*\n+", text) if part.strip()]


class Store:
    def __init__(self):
        with sqlite3.connect(DB) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY, name TEXT NOT NULL, platform TEXT NOT NULL DEFAULT 'Weibo', note TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS content(id INTEGER PRIMARY KEY, title TEXT DEFAULT '', body TEXT NOT NULL, category TEXT DEFAULT '', enabled INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS ads(id INTEGER PRIMARY KEY, title TEXT DEFAULT '', body TEXT NOT NULL, url TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY, name TEXT NOT NULL, account TEXT DEFAULT '', daily_limit INTEGER DEFAULT 1, note TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, plan TEXT, scheduled_at TEXT, status TEXT DEFAULT 'Pending');
            CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, message TEXT);
            """)

    def rows(self, table):
        with sqlite3.connect(DB) as c:
            return c.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()

    def add(self, table, cols, values):
        with sqlite3.connect(DB) as c:
            c.execute(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' for _ in values)})", values)

    def import_bodies(self, table: str, bodies: list[str]) -> tuple[int, int]:
        if table not in ("content", "ads"):
            raise ValueError("Unsupported import table")
        imported = skipped = 0
        with sqlite3.connect(DB) as c:
            existing = {
                normalize_body(row[0])
                for row in c.execute(f"SELECT body FROM {table}").fetchall()
            }
            for body in bodies:
                key = normalize_body(body)
                if not key or key in existing:
                    skipped += 1
                    continue
                if table == "content":
                    c.execute(
                        "INSERT INTO content (title, body, category, enabled) VALUES (?, ?, ?, 1)",
                        ("", body, ""),
                    )
                else:
                    c.execute(
                        "INSERT INTO ads (title, body, url) VALUES (?, ?, ?)",
                        ("", body, ""),
                    )
                existing.add(key)
                imported += 1
        return imported, skipped


class TablePage(QWidget):
    def __init__(self, store, table, headers, cols, prompt):
        super().__init__()
        self.store = store
        self.table = table
        self.cols = cols
        root = QVBoxLayout(self)
        self.grid = QTableWidget()
        self.grid.setColumnCount(len(headers))
        self.grid.setHorizontalHeaderLabels(headers)
        self.grid.setEditTriggers(QTableWidget.NoEditTriggers)
        self.grid.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.grid)

        bar = QHBoxLayout()
        self.fields = []
        for label in prompt:
            edit = QLineEdit()
            edit.setPlaceholderText(label)
            self.fields.append(edit)
            bar.addWidget(edit)

        add = QPushButton("添加")
        add.clicked.connect(self.add_row)
        bar.addWidget(add)

        if table in ("content", "ads"):
            import_btn = QPushButton("TXT 批量导入")
            import_btn.clicked.connect(self.import_txt)
            bar.addWidget(import_btn)

        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        root.addLayout(bar)
        self.refresh()

    def refresh(self):
        rows = self.store.rows(self.table)
        self.grid.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row[:self.grid.columnCount()]):
                self.grid.setItem(r, c, QTableWidgetItem(str(val)))

    def add_row(self):
        vals = [e.text().strip() for e in self.fields]
        required_index = 1 if self.table in ("content", "ads") else 0
        if len(vals) <= required_index or not vals[required_index]:
            QMessageBox.warning(self, "需要内容", "请填写必填内容后再添加。")
            return
        self.store.add(self.table, self.cols, vals)
        for e in self.fields:
            e.clear()
        self.refresh()

    def import_txt(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 TXT 文本文件", "", "Text Files (*.txt);;All Files (*.*)"
        )
        if not path:
            return

        try:
            raw = Path(path).read_bytes()
            try:
                content = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = raw.decode("gb18030")
        except Exception as exc:
            QMessageBox.critical(self, "读取失败", f"无法读取该文件：\n{exc}")
            return

        mode, ok = QInputDialog.getItem(
            self,
            "选择 TXT 内容格式",
            "请选择文件中每条内容的分隔方式：",
            ["空行分隔（适合多段长文案）", "每行一条（适合短文案列表）"],
            0,
            False,
        )
        if not ok:
            return

        parser_mode = "每行一条" if mode.startswith("每行") else "空行分隔"
        bodies = parse_txt(content, parser_mode)
        if not bodies:
            QMessageBox.information(self, "没有可导入内容", "这个 TXT 文件中没有识别到有效文本。")
            return

        imported, skipped = self.store.import_bodies(self.table, bodies) if False else (0, 0)
        # Preview duplicates before writing, including duplicates already in the database.
        existing = {
            normalize_body(row[0])
            for row in self._existing_bodies()
        }
        unique = []
        seen = set(existing)
        duplicate_count = 0
        for body in bodies:
            key = normalize_body(body)
            if not key or key in seen:
                duplicate_count += 1
                continue
            seen.add(key)
            unique.append(body)

        target_name = "内容库" if self.table == "content" else "广告库"
        confirm = QMessageBox.question(
            self,
            "确认批量导入",
            f"文件：{Path(path).name}\n识别到：{len(bodies)} 条\n"
            f"可新增：{len(unique)} 条\n重复/空白跳过：{duplicate_count} 条\n\n"
            f"是否导入到{target_name}？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if confirm != QMessageBox.Yes:
            return

        imported, skipped = self.store.import_bodies(self.table, unique)
        self.refresh()
        QMessageBox.information(
            self,
            "导入完成",
            f"成功导入：{imported} 条\n跳过：{skipped + duplicate_count} 条",
        )

    def _existing_bodies(self):
        with sqlite3.connect(DB) as c:
            return c.execute(f"SELECT body FROM {self.table}").fetchall()


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SocialPilot China")
        self.resize(1150, 700)
        self.store = Store()
        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        tabs.addTab(
            TablePage(self.store, "accounts", ["ID", "账号名称", "平台", "备注"],
                      "name,platform,note", ["账号名称", "平台（Weibo）", "备注"]),
            "账号管理",
        )
        tabs.addTab(
            TablePage(self.store, "content", ["ID", "标题", "正文", "分类", "启用"],
                      "title,body,category,enabled", ["标题（可空）", "正文内容（必填）", "分类", "1=启用/0=停用"]),
            "内容库",
        )
        tabs.addTab(
            TablePage(self.store, "ads", ["ID", "广告标题", "广告正文", "链接"],
                      "title,body,url", ["广告标题（可空）", "广告正文（必填）", "链接（可空）"]),
            "广告库",
        )
        tabs.addTab(
            TablePage(self.store, "plans", ["ID", "计划名称", "账号", "每日数量", "备注"],
                      "name,account,daily_limit,note", ["计划名称", "账号", "每日数量", "备注"]),
            "发布计划",
        )

        queue = QWidget()
        ql = QVBoxLayout(queue)
        ql.addWidget(QLabel("任务队列目前仅展示本地任务数据；尚未连接微博发布服务。"))
        ql.addWidget(QLabel("电脑关机或软件关闭时，本地程序不会执行发布。"))
        tabs.addTab(queue, "任务队列")

        log = QWidget()
        ll = QVBoxLayout(log)
        self.logtext = QTextEdit()
        self.logtext.setReadOnly(True)
        ll.addWidget(self.logtext)
        button = QPushButton("刷新记录")
        button.clicked.connect(self.refresh_logs)
        ll.addWidget(button)
        tabs.addTab(log, "发布记录")

        settings = QWidget()
        sl = QVBoxLayout(settings)
        sl.addWidget(QLabel(f"本地数据库：{DB}"))
        backup = QPushButton("备份数据库")
        backup.clicked.connect(self.backup)
        sl.addWidget(backup)
        sl.addWidget(QLabel("当前版本为本地数据管理框架。微博登录、自动发布和任务调度尚未实现。"))
        tabs.addTab(settings, "设置")

    def backup(self):
        target, _ = QFileDialog.getSaveFileName(
            self, "备份数据库", "SocialPilotChina-backup.db", "SQLite Database (*.db)"
        )
        if target:
            import shutil
            shutil.copy2(DB, target)
            QMessageBox.information(self, "完成", "数据库备份已保存。")

    def refresh_logs(self):
        self.logtext.setPlainText(
            "\n".join(" | ".join(map(str, r)) for r in self.store.rows("logs")) or "暂无记录。"
        )


def main():
    app = QApplication(sys.argv)
    win = Main()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
