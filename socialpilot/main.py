from __future__ import annotations
import csv, sqlite3, sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QLineEdit, QMessageBox,
    QFileDialog, QTextEdit)
from PySide6.QtCore import Qt

APP_DIR = Path.home() / "AppData" / "Local" / "SocialPilotChina"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB = APP_DIR / "socialpilot.db"

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

class TablePage(QWidget):
    def __init__(self, store, table, headers, cols, prompt):
        super().__init__(); self.store=store; self.table=table; self.cols=cols
        root=QVBoxLayout(self); self.grid=QTableWidget(); self.grid.setColumnCount(len(headers)); self.grid.setHorizontalHeaderLabels(headers); self.grid.setEditTriggers(QTableWidget.NoEditTriggers); self.grid.horizontalHeader().setStretchLastSection(True); root.addWidget(self.grid)
        bar=QHBoxLayout(); self.fields=[]
        for label in prompt:
            edit=QLineEdit(); edit.setPlaceholderText(label); self.fields.append(edit); bar.addWidget(edit)
        add=QPushButton("添加"); add.clicked.connect(self.add_row); bar.addWidget(add)
        refresh=QPushButton("刷新"); refresh.clicked.connect(self.refresh); bar.addWidget(refresh); root.addLayout(bar)
        self.refresh()
    def refresh(self):
        rows=self.store.rows(self.table); self.grid.setRowCount(len(rows))
        for r,row in enumerate(rows):
            for c,val in enumerate(row[:self.grid.columnCount()]): self.grid.setItem(r,c,QTableWidgetItem(str(val)))
    def add_row(self):
        vals=[e.text().strip() for e in self.fields]
        if not vals or not vals[-1]:
            QMessageBox.warning(self,"需要内容","请至少填写最后一个必填字段。"); return
        self.store.add(self.table,self.cols,vals)
        for e in self.fields: e.clear()
        self.refresh()

class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("SocialPilot China"); self.resize(1050,680); self.store=Store()
        tabs=QTabWidget(); self.setCentralWidget(tabs)
        tabs.addTab(TablePage(self.store,"accounts",["ID","账号名称","平台","备注"],"name,platform,note",["账号名称","平台（Weibo）","备注"]),"账号管理")
        tabs.addTab(TablePage(self.store,"content",["ID","标题","正文","分类","启用"],"title,body,category,enabled",["标题","正文内容（必填）","分类","1=启用/0=停用"]),"内容库")
        tabs.addTab(TablePage(self.store,"ads",["ID","广告标题","广告正文","链接"],"title,body,url",["广告标题","广告正文（必填）","链接"]),"广告库")
        tabs.addTab(TablePage(self.store,"plans",["ID","计划名称","账号","每日数量","备注"],"name,account,daily_limit,note",["计划名称","账号","每日数量","备注"]),"发布计划")
        queue=QWidget(); ql=QVBoxLayout(queue); ql.addWidget(QLabel("任务队列目前仅展示本地任务数据；尚未连接微博发布服务。")); ql.addWidget(QLabel("电脑关机或软件关闭时，本地程序不会执行发布。")); tabs.addTab(queue,"任务队列")
        log=QWidget(); ll=QVBoxLayout(log); self.logtext=QTextEdit(); self.logtext.setReadOnly(True); ll.addWidget(self.logtext); b=QPushButton("刷新记录"); b.clicked.connect(self.refresh_logs); ll.addWidget(b); tabs.addTab(log,"发布记录")
        settings=QWidget(); sl=QVBoxLayout(settings); sl.addWidget(QLabel(f"本地数据库：{DB}")); backup=QPushButton("备份数据库"); backup.clicked.connect(self.backup); sl.addWidget(backup); sl.addWidget(QLabel("当前版本为本地数据管理框架。微博登录、自动发布和任务调度尚未实现。")); tabs.addTab(settings,"设置")
    def backup(self):
        target,_=QFileDialog.getSaveFileName(self,"备份数据库","SocialPilotChina-backup.db","SQLite Database (*.db)")
        if target:
            import shutil; shutil.copy2(DB,target); QMessageBox.information(self,"完成","数据库备份已保存。")
    def refresh_logs(self):
        self.logtext.setPlainText("\n".join(" | ".join(map(str,r)) for r in self.store.rows("logs")) or "暂无记录。")

def main():
    app=QApplication(sys.argv); win=Main(); win.show(); sys.exit(app.exec())
if __name__=="__main__": main()
