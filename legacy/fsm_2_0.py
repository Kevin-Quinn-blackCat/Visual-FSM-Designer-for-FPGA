import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt
import graphviz

class FSMVisualizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPGA 状态机逻辑设计工具 - V0.2")
        self.resize(1200, 700)

        # 1. 核心数据存储
        self.output_filename = "live_fsm"
        
        # 2. 构建 UI
        self.init_ui()
        
        # 3. 初始填充
        self.add_default_rows()
        self.refresh_graph()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # --- 左侧面板：表格输入 ---
        left_panel = QVBoxLayout()
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["当前状态", "下一状态", "跳转条件", "输出动作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(self.refresh_graph) # 关键：实时更新
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加跳转 (+)")
        del_btn = QPushButton("删除选中 (-)")
        add_btn.clicked.connect(self.add_row)
        del_btn.clicked.connect(self.remove_row)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)

        left_panel.addWidget(QLabel("状态转移逻辑表:"))
        left_panel.addWidget(self.table)
        left_panel.addLayout(btn_layout)

        # --- 右侧面板：图形显示 ---
        right_panel = QVBoxLayout()
        self.graph_label = QLabel("等待输入逻辑...")
        self.graph_label.setAlignment(Qt.AlignCenter)
        self.graph_label.setStyleSheet("border: 1px solid #ccc; background: white;")
        
        right_panel.addWidget(QLabel("实时状态转移图:"))
        right_panel.addWidget(self.graph_label, 1) # 权重 1 以填充空间

        # 组装
        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 1)

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        # 阻止触发刷新直到用户输入
        self.table.blockSignals(True)
        self.table.setItem(row, 0, QTableWidgetItem(f"S{row}"))
        self.table.setItem(row, 1, QTableWidgetItem(f"S{row+1}"))
        self.table.blockSignals(False)
        self.refresh_graph()

    def remove_row(self):
        curr_row = self.table.currentRow()
        if curr_row >= 0:
            self.table.removeRow(curr_row)
            self.refresh_graph()

    def add_default_rows(self):
        # 预设一些初始逻辑
        default_data = [
            ("IDLE", "WORK", "start == 1", "en = 1"),
            ("WORK", "IDLE", "done == 1", "en = 0")
        ]
        for s, n, c, a in default_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(s))
            self.table.setItem(row, 1, QTableWidgetItem(n))
            self.table.setItem(row, 2, QTableWidgetItem(c))
            self.table.setItem(row, 3, QTableWidgetItem(a))

    def refresh_graph(self):
        """核心算法：从表格提取数据并调用 Graphviz"""
        dot = graphviz.Digraph(format='png')
        dot.attr(rankdir='LR', fontname='Microsoft YaHei')
        dot.attr('node', fontname='Microsoft YaHei', shape='circle', style='filled', color='lightblue')
        dot.attr('edge', fontname='Microsoft YaHei')

        states_found = set()

        for i in range(self.table.rowCount()):
            curr_s = self.table.item(i, 0).text() if self.table.item(i, 0) else ""
            next_s = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
            cond = self.table.item(i, 2).text() if self.table.item(i, 2) else ""
            act = self.table.item(i, 3).text() if self.table.item(i, 3) else ""

            if curr_s and next_s:
                # 标注转移条件和输出
                label = cond
                if act:
                    label += f"\n/ {act}"
                
                dot.edge(curr_s, next_s, label=label)
                states_found.add(curr_s)
                states_found.add(next_s)

        # 渲染
        try:
            # 渲染临时文件
            dot.render(self.output_filename, cleanup=True)
            pixmap = QPixmap(f"{self.output_filename}.png")
            
            # 自适应缩放显示
            scaled_pixmap = pixmap.scaled(self.graph_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.graph_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"渲染错误: {e}")

    def resizeEvent(self, event):
        # 窗口大小改变时重新缩放图片
        super().resizeEvent(event)
        self.refresh_graph()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FSMVisualizerApp()
    window.show()
    sys.exit(app.exec())