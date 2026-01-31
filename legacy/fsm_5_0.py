import sys
import json
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView, QComboBox, 
                             QFileDialog, QCompleter, QStyledItemDelegate, QLineEdit, QTextEdit)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt

# --- 1. 自定义 LineEdit 支持 Tab 补全 ---
class TabLineEdit(QLineEdit):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab and self.completer() and self.completer().popup().isVisible():
            self.completer().setCurrentRow(0)
            self.setText(self.completer().currentCompletion())
            self.completer().popup().hide()
            return
        super().keyPressEvent(event)

class AutocompleteDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words = []

    def set_words(self, words):
        self.words = words

    def createEditor(self, parent, option, index):
        if index.column() < 2:
            editor = TabLineEdit(parent)
            completer = QCompleter(self.words, editor)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            editor.setCompleter(completer)
            return editor
        return super().createEditor(parent, option, index)

# --- 2. 核心逻辑与 UI ---
class FSMVisualizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPGA 状态机逻辑设计工具 - V0.5")
        self.resize(1400, 900)
        self.state_list = []
        self.delegate = AutocompleteDelegate()
        self.init_ui()
        self.add_default_rows()
        self.refresh_logic()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # 左侧面板
        left_panel = QVBoxLayout()
        
        file_tool = QHBoxLayout()
        save_btn = QPushButton("保存 (JSON)")
        load_btn = QPushButton("读取 (JSON)")
        gen_verilog_btn = QPushButton("生成 Verilog 代码")
        gen_verilog_btn.setStyleSheet("background-color: #d4edda; font-weight: bold;")
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
        reset_layout.addWidget(self.reset_selector, 1)
        left_panel.addLayout(reset_layout)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["当前状态", "下一状态", "跳转条件", "输出动作 (如 out=1)"])
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

        # 右侧面板 (图形 + 代码预览)
        right_panel = QVBoxLayout()
        self.graph_label = QLabel("绘图区")
        self.graph_label.setAlignment(Qt.AlignCenter)
        self.graph_label.setStyleSheet("border: 1px solid #ccc; background: white;")
        
        self.code_preview = QTextEdit()
        self.code_preview.setPlaceholderText("Verilog 代码将生成在这里...")
        self.code_preview.setReadOnly(True)
        self.code_preview.setStyleSheet("font-family: 'Consolas'; background-color: #f8f9fa;")

        right_panel.addWidget(QLabel("实时状态图:"))
        right_panel.addWidget(self.graph_label, 3)
        right_panel.addWidget(QLabel("Verilog 代码预览:"))
        right_panel.addWidget(self.code_preview, 2)

        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 1)

    # --- 逻辑处理 (同 V0.4, 略作精简) ---
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
        if curr >= 0: self.table.removeRow(curr); self.refresh_logic()

    def refresh_logic(self):
        self.table.blockSignals(True)
        try:
            states = set()
            for i in range(self.table.rowCount()):
                s = self.table.item(i,0).text(); n = self.table.item(i,1).text()
                if s: states.add(s)
                if n: states.add(n)
            self.state_list = sorted(list(states))
            self.delegate.set_words(self.state_list)
            
            cur_reset = self.reset_selector.currentText()
            self.reset_selector.clear()
            self.reset_selector.addItems(self.state_list)
            if cur_reset in self.state_list: self.reset_selector.setCurrentText(cur_reset)
            
            # 绘图逻辑 (调用 graphviz)
            self.draw_fsm()
        finally:
            self.table.blockSignals(False)

    def draw_fsm(self):
        # 此处省略具体的 graphviz 渲染代码 (同 V0.3)，假设已渲染并显示在 graph_label
        pass

    # --- 3. Verilog 代码生成引擎 (重点) ---
    def generate_verilog(self):
        if not self.state_list: return
        
        reset_state = self.reset_selector.currentText()
        num_states = len(self.state_list)
        width = max(1, math.ceil(math.log2(num_states)))
        
        code = []
        code.append("/*===================================== FSM Generated ======================================*/")
        
        # 1. State Encoding
        code.append("\n/*== state_encoding ==*/")
        for i, name in enumerate(self.state_list):
            val = f"{width}'d{i}"
            code.append(f"parameter   {name.upper().ljust(12)} = {val};")
        code.append(f"reg [{width-1}:0] state;")

        # 2. State Transition (Case Style)
        code.append("\n/*================================== State Transition ==================================*/")
        code.append("always@(posedge sys_clk or negedge sys_rst_n) begin")
        code.append("    if(sys_rst_n == 1'b0)")
        code.append(f"        state <= {reset_state.upper()};")
        code.append("    else case(state)")
        
        # 遍历每个状态的跳转逻辑
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
            if not first: code.append(f"            else\n                state <= {state.upper()};")
            code.append("        end")
        
        code.append("        default: state <= IDLE;")
        code.append("    endcase\nend")

        # 3. FSM Output (拆分不同信号)
        # 先解析出有哪些输出变量
        output_logic = {} # { signal_name: [(state, cond, value), ...] }
        for i in range(self.table.rowCount()):
            act_raw = self.table.item(i, 3).text()
            if not act_raw: continue
            
            state = self.table.item(i, 0).text()
            cond = self.table.item(i, 2).text()
            
            # 解析 "po_cola=1, po_money=0"
            acts = act_raw.replace(';', ',').split(',')
            for a in acts:
                if '=' in a:
                    sig, val = a.split('=')
                    sig = sig.strip(); val = val.strip()
                    if sig not in output_logic: output_logic[sig] = []
                    output_logic[sig].append((state, cond, val))

        code.append("\n/*================================== FSM Output ==================================*/")
        for sig, rules in output_logic.items():
            code.append(f"// Output: {sig}")
            code.append(f"always@(posedge sys_clk or negedge sys_rst_n) begin")
            code.append(f"    if(sys_rst_n == 1'b0)")
            code.append(f"        {sig} <= 'b0; // Default Reset Value")
            
            for r_state, r_cond, r_val in rules:
                code.append(f"    else if((state == {r_state.upper()}) && ({r_cond}))")
                code.append(f"        {sig} <= {r_val};")
            
            code.append(f"    else")
            code.append(f"        {sig} <= {sig}; // Keep previous or set default")
            code.append(f"end\n")

        self.code_preview.setText("\n".join(code))

    # --- 存取功能 ---
    def save_project(self):
        # 同 V0.4
        pass
    def load_project(self):
        # 同 V0.4
        pass

    def add_default_rows(self):
        self.add_row("IDLE", "HALF", "pi_money == MONEY_HALF", "po_cola=0")
        self.add_row("IDLE", "ONE",  "pi_money == MONEY_ONE", "po_cola=0")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FSMVisualizerApp()
    window.show()
    sys.exit(app.exec())