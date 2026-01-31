import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView, QComboBox)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt
import graphviz

class FSMVisualizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPGA 状态机逻辑设计工具 - V0.3")
        self.resize(1300, 800)

        self.output_filename = "live_fsm_v03"
        self.init_ui()
        self.add_default_rows()
        self.refresh_logic()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # --- 左侧面板 ---
        left_panel = QVBoxLayout()
        
        # 复位状态选择区
        reset_layout = QHBoxLayout()
        reset_layout.addWidget(QLabel("复位(初始)状态:"))
        self.reset_selector = QComboBox()
        self.reset_selector.currentIndexChanged.connect(self.refresh_graph)
        reset_layout.addWidget(self.reset_selector, 1)
        left_panel.addLayout(reset_layout)

        # 表格
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["当前状态", "下一状态", "跳转条件", "输出动作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(self.refresh_logic) # 触发逻辑检查和绘图
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加跳转 (+)")
        del_btn = QPushButton("删除选中 (-)")
        add_btn.clicked.connect(self.add_row)
        del_btn.clicked.connect(self.remove_row)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)

        left_panel.addWidget(QLabel("状态转移逻辑表 (同状态同条件将标红):"))
        left_panel.addWidget(self.table)
        left_panel.addLayout(btn_layout)

        # --- 右侧面板 ---
        right_panel = QVBoxLayout()
        self.graph_label = QLabel("等待输入逻辑...")
        self.graph_label.setAlignment(Qt.AlignCenter)
        self.graph_label.setStyleSheet("border: 1px solid #ccc; background: #f9f9f9;")
        
        right_panel.addWidget(QLabel("实时状态转移图 (Green=Reset State):"))
        right_panel.addWidget(self.graph_label, 1)

        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 1)

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.blockSignals(True)
        self.table.setItem(row, 0, QTableWidgetItem("IDLE"))
        self.table.setItem(row, 1, QTableWidgetItem("NEXT"))
        self.table.blockSignals(False)
        self.refresh_logic()

    def remove_row(self):
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            self.table.removeRow(curr_row)
            self.refresh_logic()

    def add_default_rows(self):
        default_data = [
            ("IDLE", "SETUP", "rst_n == 0", "out=0"),
            ("IDLE", "WORK", "start == 1", "out=1"),
            ("WORK", "IDLE", "done == 1", "out=0")
        ]
        self.table.blockSignals(True)
        for s, n, c, a in default_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(s))
            self.table.setItem(row, 1, QTableWidgetItem(n))
            self.table.setItem(row, 2, QTableWidgetItem(c))
            self.table.setItem(row, 3, QTableWidgetItem(a))
        self.table.blockSignals(False)

    def refresh_logic(self):
        """逻辑检查总控：更显下拉框 -> 检查冲突 -> 绘图"""
        self.update_reset_selector()
        self.check_conflicts()
        self.refresh_graph()

    def update_reset_selector(self):
        """提取所有状态名并更新下拉框"""
        states = set()
        for i in range(self.table.rowCount()):
            s = self.table.item(i, 0).text() if self.table.item(i, 0) else ""
            n = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
            if s: states.add(s)
            if n: states.add(n)
        
        current_reset = self.reset_selector.currentText()
        self.reset_selector.blockSignals(True)
        self.reset_selector.clear()
        self.reset_selector.addItems(sorted(list(states)))
        if current_reset in states:
            self.reset_selector.setCurrentText(current_reset)
        self.reset_selector.blockSignals(False)

    def check_conflicts(self):
        """检测多驱动冲突并标红"""
        conflict_map = {} # (src, cond) -> list of row indices
        
        # 重置背景色
        for i in range(self.table.rowCount()):
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                if item: item.setBackground(QColor(255, 255, 255))

        # 扫描冲突
        for i in range(self.table.rowCount()):
            src = self.table.item(i, 0).text() if self.table.item(i, 0) else ""
            cond = self.table.item(i, 2).text() if self.table.item(i, 2) else ""
            if src and cond:
                key = (src, cond)
                if key not in conflict_map: conflict_map[key] = []
                conflict_map[key].append(i)
        
        # 标记冲突行
        for key, rows in conflict_map.items():
            if len(rows) > 1:
                for row_idx in rows:
                    for col_idx in range(4):
                        item = self.table.item(row_idx, col_idx)
                        if item: item.setBackground(QColor(255, 200, 200)) # 浅红色

    def refresh_graph(self):
        """渲染图形"""
        dot = graphviz.Digraph(format='png')
        dot.attr(rankdir='LR', fontname='Microsoft YaHei')
        
        reset_state = self.reset_selector.currentText()
        states_in_graph = set()

        # 收集所有跳转
        for i in range(self.table.rowCount()):
            curr_s = self.table.item(i, 0).text() if self.table.item(i, 0) else ""
            next_s = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
            cond = self.table.item(i, 2).text() if self.table.item(i, 2) else ""
            act = self.table.item(i, 3).text() if self.table.item(i, 3) else ""

            if curr_s and next_s:
                label = cond
                if act: label += f"\n/ {act}"
                dot.edge(curr_s, next_s, label=label, fontname='Microsoft YaHei')
                states_in_graph.add(curr_s)
                states_in_graph.add(next_s)

        # 设置节点样式
        for state in states_in_graph:
            if state == reset_state:
                dot.node(state, shape='doublecircle', color='darkgreen', 
                         style='filled', fillcolor='honeydew', fontname='Microsoft YaHei')
            else:
                dot.node(state, shape='circle', style='filled', 
                         fillcolor='lightblue', fontname='Microsoft YaHei')

        try:
            dot.render(self.output_filename, cleanup=True)
            pixmap = QPixmap(f"{self.output_filename}.png")
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.graph_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.graph_label.setPixmap(scaled)
        except Exception as e:
            print(f"Graphviz Error: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_graph()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FSMVisualizerApp()
    window.show()
    sys.exit(app.exec())