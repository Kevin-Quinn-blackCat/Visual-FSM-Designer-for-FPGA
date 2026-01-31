import sys
import json
import math
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView, QComboBox, 
                             QFileDialog, QCompleter, QStyledItemDelegate, QLineEdit, QTextEdit)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt
import graphviz

# --- 1. 修复 Tab 补全的 LineEdit ---
class TabLineEdit(QLineEdit):
    def keyPressEvent(self, event):
        # 如果补全窗口可见，按下 Tab 或 Enter 键则选中当前项
        if self.completer() and self.completer().popup().isVisible():
            if event.key() in (Qt.Key_Tab, Qt.Key_Enter, Qt.Key_Return):
                index = self.completer().popup().currentIndex()
                if not index.isValid():
                    index = self.completer().completionModel().index(0, 0)
                self.completer().activated.emit(index)
                return # 拦截事件，不让表格跳到下一个单元格
        super().keyPressEvent(event)

class AutocompleteDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words = []

    def set_words(self, words):
        self.words = words

    def createEditor(self, parent, option, index):
        if index.column() < 2: # 仅前两列（状态名）启用补全
            editor = TabLineEdit(parent)
            completer = QCompleter(self.words, editor)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            editor.setCompleter(completer)
            return editor
        return super().createEditor(parent, option, index)

# --- 2. 主程序 ---
class FSMVisualizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPGA 状态机逻辑设计工具 - V0.5.1")
        self.resize(1400, 900)
        
        self.output_filename = "live_fsm_render"
        self.state_list = []
        self.delegate = AutocompleteDelegate()
        
        self.init_ui()
        self.add_default_rows()
        self.refresh_logic()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # 左侧逻辑面板
        left_panel = QVBoxLayout()
        
        file_tool = QHBoxLayout()
        save_btn = QPushButton("保存工程 (JSON)")
        load_btn = QPushButton("读取工程 (JSON)")
        gen_verilog_btn = QPushButton("生成 Verilog 代码")
        gen_verilog_btn.setStyleSheet("background-color: #d4edda; font-weight: bold; color: #155724;")
        save_btn.clicked.connect(self.save_project)
        load_btn.clicked.connect(self.load_project)
        gen_verilog_btn.clicked.connect(self.generate_verilog)
        file_tool.addWidget(save_btn)
        file_tool.addWidget(load_btn)
        file_tool.addWidget(gen_verilog_btn)
        left_panel.addLayout(file_tool)

        reset_layout = QHBoxLayout()
        reset_layout.addWidget(QLabel("复位状态:"))
        self.reset_selector = QComboBox()
        self.reset_selector.currentIndexChanged.connect(self.draw_fsm) # 仅手动切换时重绘
        reset_layout.addWidget(self.reset_selector, 1)
        left_panel.addLayout(reset_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["当前状态", "下一状态", "跳转条件", "输出动作"])
        self.table.setItemDelegate(self.delegate)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(self.refresh_logic)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加跳转 (+)")
        del_btn = QPushButton("删除选中 (-)")
        add_btn.clicked.connect(self.add_row)
        del_btn.clicked.connect(self.remove_row)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)

        left_panel.addWidget(self.table)
        left_panel.addLayout(btn_layout)

        # 右侧预览面板
        right_panel = QVBoxLayout()
        self.graph_label = QLabel("正在初始化绘图...")
        self.graph_label.setAlignment(Qt.AlignCenter)
        self.graph_label.setStyleSheet("border: 1px solid #ccc; background: white;")
        
        self.code_preview = QTextEdit()
        self.code_preview.setPlaceholderText("Verilog 代码区...")
        self.code_preview.setReadOnly(True)
        self.code_preview.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10pt; background-color: #f8f9fa;")

        right_panel.addWidget(QLabel("实时状态图:"))
        right_panel.addWidget(self.graph_label, 3)
        right_panel.addWidget(QLabel("Verilog 代码预览:"))
        right_panel.addWidget(self.code_preview, 2)

        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 1)

    # --- 基础操作 ---
    def add_row(self, s="IDLE", n="IDLE", c="1", a=""):
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
        curr = self.table.currentRow()
        if curr >= 0: 
            self.table.removeRow(curr)
            self.refresh_logic()

    def refresh_logic(self):
        """核心逻辑控制：防冲突、更显词库、绘图"""
        self.table.blockSignals(True)
        try:
            # 1. 提取所有状态名
            states = set()
            for i in range(self.table.rowCount()):
                s = self.table.item(i,0).text() if self.table.item(i,0) else ""
                n = self.table.item(i,1).text() if self.table.item(i,1) else ""
                if s: states.add(s)
                if n: states.add(n)
            
            self.state_list = sorted(list(states))
            self.delegate.set_words(self.state_list)
            
            # 2. 更新复位选择下拉框
            cur_reset = self.reset_selector.currentText()
            self.reset_selector.blockSignals(True)
            self.reset_selector.clear()
            self.reset_selector.addItems(self.state_list)
            if cur_reset in self.state_list:
                self.reset_selector.setCurrentText(cur_reset)
            self.reset_selector.blockSignals(False)
            
            # 3. 冲突检查
            self.check_conflicts()
            # 4. 绘图
            self.draw_fsm()
        finally:
            self.table.blockSignals(False)

    def check_conflicts(self):
        # 重置颜色
        for i in range(self.table.rowCount()):
            for j in range(4):
                item = self.table.item(i, j)
                if item: item.setBackground(QColor(255, 255, 255))
        
        conflict_map = {}
        for i in range(self.table.rowCount()):
            src = self.table.item(i, 0).text() if self.table.item(i, 0) else ""
            cond = self.table.item(i, 2).text() if self.table.item(i, 2) else ""
            if src and cond:
                key = (src, cond)
                if key not in conflict_map: conflict_map[key] = []
                conflict_map[key].append(i)
        
        for rows in conflict_map.values():
            if len(rows) > 1:
                for r in rows:
                    for c in range(4): self.table.item(r, c).setBackground(QColor(255, 200, 200))

    def draw_fsm(self):
        """恢复绘图逻辑"""
        dot = graphviz.Digraph(format='png')
        dot.attr(rankdir='LR', fontname='Microsoft YaHei')
        reset_state = self.reset_selector.currentText()
        
        edges_added = False
        for i in range(self.table.rowCount()):
            s = self.table.item(i, 0).text() if self.table.item(i, 0) else ""
            n = self.table.item(i, 1).text() if self.table.item(i, 1) else ""
            c = self.table.item(i, 2).text() if self.table.item(i, 2) else ""
            a = self.table.item(i, 3).text() if self.table.item(i, 3) else ""
            if s and n:
                label = c
                if a: label += f"\n/ {a}"
                dot.edge(s, n, label=label, fontname='Microsoft YaHei')
                edges_added = True

        for state in self.state_list:
            if state == reset_state:
                dot.node(state, shape='doublecircle', color='darkgreen', style='filled', fillcolor='honeydew')
            else:
                dot.node(state, shape='circle', style='filled', fillcolor='lightblue')

        if not edges_added and not self.state_list:
            self.graph_label.setText("请在表格中输入逻辑...")
            return

        try:
            dot.render(self.output_filename, cleanup=True)
            pixmap = QPixmap(f"{self.output_filename}.png")
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.graph_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.graph_label.setPixmap(scaled)
        except Exception as e:
            self.graph_label.setText(f"绘图引擎未就绪: {e}")

    # --- 3. Verilog 生成逻辑 ---
    def generate_verilog(self):
        if not self.state_list: return
        reset_state = self.reset_selector.currentText()
        num_states = len(self.state_list)
        width = max(1, math.ceil(math.log2(num_states)))
        
        code = [f"// FSM Generated by Python Tool\n"]
        
        # Encoding
        code.append("/*== state_encoding ==*/")
        for i, name in enumerate(self.state_list):
            code.append(f"parameter   {name.upper().ljust(15)} = {width}'d{i};")
        code.append(f"reg [{width-1}:0] state;\n")

        # Transition
        code.append("/*================== State Transition ==================*/")
        code.append("always@(posedge sys_clk or negedge sys_rst_n) begin")
        code.append("    if(sys_rst_n == 1'b0)")
        code.append(f"        state <= {reset_state.upper() if reset_state else 'IDLE'};")
        code.append("    else case(state)")
        
        for state in self.state_list:
            code.append(f"        {state.upper()}: begin")
            first = True
            for i in range(self.table.rowCount()):
                if self.table.item(i, 0).text() == state:
                    nxt = self.table.item(i, 1).text()
                    cond = self.table.item(i, 2).text()
                    prefix = "if" if first else "else if"
                    code.append(f"            {prefix}({cond})")
                    code.append(f"                state <= {nxt.upper()};")
                    first = False
            if not first: 
                code.append(f"            else\n                state <= {state.upper()};")
            code.append("        end")
        code.append("        default: state <= IDLE;")
        code.append("    endcase\nend\n")

        # Outputs
        output_logic = {}
        for i in range(self.table.rowCount()):
            act_raw = self.table.item(i, 3).text()
            if '=' not in act_raw: continue
            state = self.table.item(i, 0).text()
            cond = self.table.item(i, 2).text()
            acts = act_raw.replace(';', ',').split(',')
            for a in acts:
                if '=' in a:
                    sig, val = a.split('=')
                    sig = sig.strip(); val = val.strip()
                    if sig not in output_logic: output_logic[sig] = []
                    output_logic[sig].append((state, cond, val))

        code.append("/*================== FSM Output ==================*/")
        for sig, rules in output_logic.items():
            code.append(f"always@(posedge sys_clk or negedge sys_rst_n) begin")
            code.append(f"    if(sys_rst_n == 1'b0)")
            code.append(f"        {sig} <= 'b0;")
            for r_state, r_cond, r_val in rules:
                code.append(f"    else if((state == {r_state.upper()}) && ({r_cond}))")
                code.append(f"        {sig} <= {r_val};")
            code.append(f"    else")
            code.append(f"        {sig} <= {sig};")
            code.append(f"end\n")

        self.code_preview.setText("\n".join(code))

    # --- 4. 存取功能修复 ---
    def save_project(self):
        data = []
        for i in range(self.table.rowCount()):
            row = [self.table.item(i, j).text() if self.table.item(i, j) else "" for j in range(4)]
            data.append(row)
        
        path, _ = QFileDialog.getSaveFileName(self, "保存工程", "", "FSM Files (*.json)")
        if path:
            with open(path, 'w') as f:
                json.dump({"reset": self.reset_selector.currentText(), "data": data}, f)

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "读取工程", "", "FSM Files (*.json)")
        if path:
            with open(path, 'r') as f:
                content = json.load(f)
                self.table.blockSignals(True)
                self.table.setRowCount(0)
                for row_data in content["data"]:
                    self.add_row(*row_data)
                self.table.blockSignals(False)
                self.refresh_logic()
                self.reset_selector.setCurrentText(content.get("reset", ""))

    def add_default_rows(self):
        self.add_row("IDLE", "WORK", "start==1", "po_en=1")
        self.add_row("WORK", "IDLE", "done==1", "po_en=0")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.draw_fsm()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FSMVisualizerApp()
    window.show()
    sys.exit(app.exec())