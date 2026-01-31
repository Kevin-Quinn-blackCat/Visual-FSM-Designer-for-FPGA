import sys
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView, QComboBox, 
                             QFileDialog, QCompleter, QStyledItemDelegate, QLineEdit)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt, QStringListModel
import graphviz

# --- 补全器委托 ---
class AutocompleteDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words = []

    def set_words(self, words):
        self.words = words

    def createEditor(self, parent, option, index):
        # 仅在前两列（状态名列）启用补全
        if index.column() < 2:
            editor = QLineEdit(parent)
            completer = QCompleter(self.words, editor)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            editor.setCompleter(completer)
            return editor
        return super().createEditor(parent, option, index)

class FSMVisualizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPGA 状态机逻辑设计工具 - V0.4")
        self.resize(1300, 850)

        self.output_filename = "live_fsm_v04"
        self.state_list = []
        
        # 初始化补全器委托
        self.delegate = AutocompleteDelegate()
        
        self.init_ui()
        self.add_default_rows()
        self.refresh_logic()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # --- 左侧面板 ---
        left_panel = QVBoxLayout()
        
        # 工具栏：保存/加载
        file_tool_layout = QHBoxLayout()
        save_btn = QPushButton("保存工程 (JSON)")
        load_btn = QPushButton("读取工程")
        save_btn.clicked.connect(self.save_project)
        load_btn.clicked.connect(self.load_project)
        file_tool_layout.addWidget(save_btn)
        file_tool_layout.addWidget(load_btn)
        left_panel.addLayout(file_tool_layout)

        # 复位状态选择
        reset_layout = QHBoxLayout()
        reset_layout.addWidget(QLabel("复位(初始)状态:"))
        self.reset_selector = QComboBox()
        self.reset_selector.currentIndexChanged.connect(self.refresh_graph)
        reset_layout.addWidget(self.reset_selector, 1)
        left_panel.addLayout(reset_layout)

        # 表格配置
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["当前状态", "下一状态", "跳转条件", "输出动作"])
        self.table.setItemDelegate(self.delegate) # 安装补全委托
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(self.refresh_logic)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加跳转 (+)")
        del_btn = QPushButton("删除选中 (-)")
        add_btn.clicked.connect(self.add_row)
        del_btn.clicked.connect(self.remove_row)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)

        left_panel.addWidget(QLabel("状态转移逻辑表 (Tab补全已启用):"))
        left_panel.addWidget(self.table)
        left_panel.addLayout(btn_layout)

        # --- 右侧面板 ---
        right_panel = QVBoxLayout()
        self.graph_label = QLabel("等待输入逻辑...")
        self.graph_label.setAlignment(Qt.AlignCenter)
        self.graph_label.setStyleSheet("border: 1px solid #ccc; background: #f9f9f9;")
        
        # 底部 Verilog 选项占位
        verilog_opt_layout = QHBoxLayout()
        verilog_opt_layout.addWidget(QLabel("状态编码:"))
        self.enc_combo = QComboBox()
        self.enc_combo.addItems(["Binary", "One-hot", "Gray"])
        verilog_opt_layout.addWidget(self.enc_combo)
        verilog_opt_layout.addWidget(QLabel(" 风格:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["三段式 (Recommended)", "两段式"])
        verilog_opt_layout.addWidget(self.style_combo)
        
        right_panel.addWidget(QLabel("实时状态转移图:"))
        right_panel.addWidget(self.graph_label, 1)
        right_panel.addLayout(verilog_opt_layout)

        layout.addLayout(left_panel, 2)
        layout.addLayout(right_panel, 3)

    def add_row(self, s="NEW_S", n="NEXT_S", c="", a=""):
        row = self.table.rowCount()
        self.table.blockSignals(True)
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(s))
        self.table.setItem(row, 1, QTableWidgetItem(n))
        self.table.setItem(row, 2, QTableWidgetItem(c))
        self.table.setItem(row, 3, QTableWidgetItem(a))
        self.table.blockSignals(False)
        self.refresh_logic()

    def remove_row(self):
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            self.table.removeRow(curr_row)
            self.refresh_logic()

    def refresh_logic(self):
        """核心：增加信号屏蔽防止递归崩溃"""
        self.table.blockSignals(True) # 屏蔽开始
        try:
            self.update_state_list()
            self.check_conflicts()
            self.refresh_graph()
        finally:
            self.table.blockSignals(False) # 屏蔽结束

    def update_state_list(self):
        states = set()
        for i in range(self.table.rowCount()):
            s = self.table.item(i, 0).text() if self.table.item(i, 0) else ""
            n = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
            if s: states.add(s)
            if n: states.add(n)
        
        self.state_list = sorted(list(states))
        self.delegate.set_words(self.state_list) # 更新补全词库
        
        # 更新复位选择器
        current_reset = self.reset_selector.currentText()
        self.reset_selector.blockSignals(True)
        self.reset_selector.clear()
        self.reset_selector.addItems(self.state_list)
        if current_reset in states:
            self.reset_selector.setCurrentText(current_reset)
        self.reset_selector.blockSignals(False)

    def check_conflicts(self):
        conflict_map = {}
        # 重置背景
        for i in range(self.table.rowCount()):
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                if item: item.setBackground(QColor(255, 255, 255))

        for i in range(self.table.rowCount()):
            src = self.table.item(i, 0).text() if self.table.item(i, 0) else ""
            cond = self.table.item(i, 2).text() if self.table.item(i, 2) else ""
            if src and cond:
                key = (src, cond)
                if key not in conflict_map: conflict_map[key] = []
                conflict_map[key].append(i)
        
        for key, rows in conflict_map.items():
            if len(rows) > 1:
                for row_idx in rows:
                    for col_idx in range(4):
                        item = self.table.item(row_idx, col_idx)
                        if item: item.setBackground(QColor(255, 200, 200))

    def refresh_graph(self):
        dot = graphviz.Digraph(format='png')
        dot.attr(rankdir='LR', fontname='Microsoft YaHei')
        reset_state = self.reset_selector.currentText()
        
        for i in range(self.table.rowCount()):
            curr_s = self.table.item(i, 0).text() if self.table.item(i, 0) else ""
            next_s = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
            cond = self.table.item(i, 2).text() if self.table.item(i, 2) else ""
            act = self.table.item(i, 3).text() if self.table.item(i, 3) else ""

            if curr_s and next_s:
                label = cond
                if act: label += f"\n/ {act}"
                dot.edge(curr_s, next_s, label=label, fontname='Microsoft YaHei')

        for state in self.state_list:
            if state == reset_state:
                dot.node(state, shape='doublecircle', color='darkgreen', style='filled', fillcolor='honeydew')
            else:
                dot.node(state, shape='circle', style='filled', fillcolor='lightblue')

        try:
            dot.render(self.output_filename, cleanup=True)
            pixmap = QPixmap(f"{self.output_filename}.png")
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.graph_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.graph_label.setPixmap(scaled)
        except: pass

    def save_project(self):
        data = []
        for i in range(self.table.rowCount()):
            row = [self.table.item(i, j).text() if self.table.item(i, j) else "" for j in range(4)]
            data.append(row)
        
        file_path, _ = QFileDialog.getSaveFileName(self, "保存工程", "", "FSM Files (*.json)")
        if file_path:
            with open(file_path, 'w') as f:
                json.dump({"reset": self.reset_selector.currentText(), "data": data}, f)

    def load_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "读取工程", "", "FSM Files (*.json)")
        if file_path:
            with open(file_path, 'r') as f:
                content = json.load(f)
                self.table.setRowCount(0)
                for row_data in content["data"]:
                    self.add_row(*row_data)
                self.reset_selector.setCurrentText(content.get("reset", ""))

    def add_default_rows(self):
        self.add_row("IDLE", "WORK", "start==1", "en=1")
        self.add_row("WORK", "IDLE", "done==1", "en=0")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_graph()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FSMVisualizerApp()
    window.show()
    sys.exit(app.exec())