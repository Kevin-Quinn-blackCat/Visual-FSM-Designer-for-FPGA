import sys
import json
import math
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView, QComboBox, 
                             QFileDialog, QCompleter, QStyledItemDelegate, QLineEdit, QTextEdit, QTabWidget)
from PySide6.QtGui import QPixmap, QColor, QFont
from PySide6.QtCore import Qt
import graphviz

# --- 1. 修复 Tab 补全逻辑：强制选中首项 ---
class TabLineEdit(QLineEdit):
    def keyPressEvent(self, event):
        popup = self.completer().popup() if self.completer() else None
        if popup and popup.isVisible():
            if event.key() in (Qt.Key_Tab, Qt.Key_Enter, Qt.Key_Return):
                # 如果没有手动选择项，强制指向第一行
                index = popup.currentIndex()
                if not index.isValid():
                    index = self.completer().completionModel().index(0, 0)
                
                res = self.completer().completionModel().data(index)
                self.setText(res)
                self.completer().popup().hide()
                return # 拦截，防止焦点跳转
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
            completer.setCompletionMode(QCompleter.PopupCompletion)
            editor.setCompleter(completer)
            return editor
        return super().createEditor(parent, option, index)

# --- 2. 主程序 ---
class FSMVisualizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPGA 状态机逻辑设计工具 - V0.6")
        self.resize(1500, 950)
        
        self.output_filename = "fsm_render_v06"
        self.state_list = []
        self.delegate = AutocompleteDelegate()
        
        self.init_ui()
        self.add_default_rows()
        self.refresh_logic()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- 左侧：设计区 ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 顶部工具栏
        toolbar = QHBoxLayout()
        btn_save = QPushButton("保存工程")
        btn_load = QPushButton("读取工程")
        btn_gen = QPushButton("生成 Verilog")
        btn_gen.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 5px;")
        btn_save.clicked.connect(self.save_project)
        btn_load.clicked.connect(self.load_project)
        btn_gen.clicked.connect(self.generate_verilog)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_load)
        toolbar.addWidget(btn_gen)
        left_layout.addLayout(toolbar)

        # 选项卡切换逻辑设计与参数定义
        self.design_tabs = QTabWidget()
        
        # Tab 1: 状态转移
        trans_page = QWidget()
        trans_layout = QVBoxLayout(trans_page)
        
        reset_box = QHBoxLayout()
        reset_box.addWidget(QLabel("复位状态:"))
        self.reset_selector = QComboBox()
        self.reset_selector.currentIndexChanged.connect(self.draw_fsm)
        reset_box.addWidget(self.reset_selector, 1)
        trans_layout.addLayout(reset_box)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["当前状态", "下一状态", "跳转条件", "输出动作"])
        self.table.setItemDelegate(self.delegate)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(self.refresh_logic)
        
        row_ctrl = QHBoxLayout()
        add_row_btn = QPushButton("添加跳转 (+)")
        del_row_btn = QPushButton("删除选中 (-)")
        add_row_btn.clicked.connect(lambda: self.add_row())
        del_row_btn.clicked.connect(self.remove_row)
        row_ctrl.addWidget(add_row_btn)
        row_ctrl.addWidget(del_row_btn)
        
        trans_layout.addWidget(self.table)
        trans_layout.addLayout(row_ctrl)
        
        # Tab 2: 参数定义 (Input/Output Parameters)
        param_page = QWidget()
        param_layout = QVBoxLayout(param_page)
        self.param_table = QTableWidget(0, 3)
        self.param_table.setHorizontalHeaderLabels(["参数名", "位宽/值 (如 2'b01)", "备注描述"])
        self.param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        add_param_btn = QPushButton("添加参数 (+)")
        add_param_btn.clicked.connect(self.add_param_row)
        param_layout.addWidget(QLabel("在这里定义输入/输出逻辑中使用的常量参数:"))
        param_layout.addWidget(self.param_table)
        param_layout.addWidget(add_param_btn)

        self.design_tabs.addTab(trans_page, "状态转移逻辑")
        self.design_tabs.addTab(param_page, "信号参数定义")
        left_layout.addWidget(self.design_tabs)

        # --- 右侧：预览区 ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.graph_label = QLabel("正在生成状态图...")
        self.graph_label.setAlignment(Qt.AlignCenter)
        self.graph_label.setStyleSheet("border: 2px solid #ddd; background: white; border-radius: 5px;")
        
        self.code_preview = QTextEdit()
        self.code_preview.setFont(QFont("Consolas", 10))
        self.code_preview.setReadOnly(True)
        self.code_preview.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc;")

        right_layout.addWidget(QLabel("实时预览:"))
        right_layout.addWidget(self.graph_label, 3)
        right_layout.addWidget(QLabel("Verilog 代码预览:"))
        right_layout.addWidget(self.code_preview, 2)

        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(right_widget, 1)

    # --- 逻辑控制 ---
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

    def add_param_row(self, name="PARAM_NAME", val="2'b00", note=""):
        row = self.param_table.rowCount()
        self.param_table.insertRow(row)
        self.param_table.setItem(row, 0, QTableWidgetItem(name))
        self.param_table.setItem(row, 1, QTableWidgetItem(val))
        self.param_table.setItem(row, 2, QTableWidgetItem(note))

    def refresh_logic(self):
        self.table.blockSignals(True)
        try:
            states = set()
            for i in range(self.table.rowCount()):
                s = self.table.item(i,0).text() if self.table.item(i,0) else ""
                n = self.table.item(i,1).text() if self.table.item(i,1) else ""
                if s: states.add(s)
                if n: states.add(n)
            
            self.state_list = sorted(list(states))
            self.delegate.set_words(self.state_list)
            
            cur_reset = self.reset_selector.currentText()
            self.reset_selector.blockSignals(True)
            self.reset_selector.clear()
            self.reset_selector.addItems(self.state_list)
            if cur_reset in self.state_list: self.reset_selector.setCurrentText(cur_reset)
            self.reset_selector.blockSignals(False)
            
            self.check_conflicts()
            self.draw_fsm()
        finally:
            self.table.blockSignals(False)

    def check_conflicts(self):
        for i in range(self.table.rowCount()):
            for j in range(4):
                item = self.table.item(i,j)
                if item: item.setBackground(QColor(255,255,255))
        
        cmap = {}
        for i in range(self.table.rowCount()):
            src = self.table.item(i, 0).text() if self.table.item(i,0) else ""
            cond = self.table.item(i, 2).text() if self.table.item(i,2) else ""
            if src and cond:
                key = (src, cond)
                if key not in cmap: cmap[key] = []
                cmap[key].append(i)
        for rows in cmap.values():
            if len(rows) > 1:
                for r in rows:
                    for c in range(4): self.table.item(r,c).setBackground(QColor(255,200,200))

    def draw_fsm(self):
        dot = graphviz.Digraph(format='png')
        dot.attr(rankdir='LR', fontname='Microsoft YaHei')
        reset_state = self.reset_selector.currentText()
        
        has_content = False
        for i in range(self.table.rowCount()):
            s = self.table.item(i, 0).text() if self.table.item(i,0) else ""
            n = self.table.item(i, 1).text() if self.table.item(i,1) else ""
            c = self.table.item(i, 2).text() if self.table.item(i,2) else ""
            a = self.table.item(i, 3).text() if self.table.item(i,3) else ""
            if s and n:
                label = c
                if a: label += f"\n/ {a}"
                dot.edge(s, n, label=label, fontname='Microsoft YaHei')
                has_content = True

        for state in self.state_list:
            if state == reset_state:
                dot.node(state, shape='doublecircle', color='darkgreen', style='filled', fillcolor='honeydew')
            else:
                dot.node(state, shape='circle', style='filled', fillcolor='lightblue')

        if not has_content: return

        try:
            dot.render(self.output_filename, cleanup=True)
            pixmap = QPixmap(f"{self.output_filename}.png")
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.graph_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.graph_label.setPixmap(scaled)
        except: pass

    # --- 3. Verilog 生成引擎 (完全遵循用户提供的时序块风格) ---
    def generate_verilog(self):
        if not self.state_list: return
        reset_state = self.reset_selector.currentText()
        num_states = len(self.state_list)
        width = max(1, math.ceil(math.log2(num_states)))
        
        code = ["/*================================================================================*/"]
        code.append("/*===================================== FSM ======================================*/")
        code.append("/*================================================================================*/\n")

        # A. Encoding Section
        code.append("/*== Encoding ==*/")
        # 用户定义的参数
        code.append("// Input/Output Signals Parameters")
        for i in range(self.param_table.rowCount()):
            p_name = self.param_table.item(i,0).text() if self.param_table.item(i,0) else ""
            p_val  = self.param_table.item(i,1).text() if self.param_table.item(i,1) else ""
            if p_name:
                code.append(f"parameter   {p_name.ljust(15)} = {p_val};")
        
        # 状态参数
        code.append("\n// State Parameters")
        for i, name in enumerate(self.state_list):
            code.append(f"parameter   {name.upper().ljust(15)} = {width}'d{i};")
        code.append(f"reg [{width-1}:0] state;\n")

        # B. State Transition Section
        code.append("/*================================== State Transition ==================================*/")
        code.append("always@(posedge sys_clk or negedge sys_rst_n) begin")
        code.append("    if(sys_rst_n == 1'b0)")
        code.append(f"        state <= {reset_state.upper()};")
        code.append("    else case(state)")
        
        for state in self.state_list:
            code.append(f"        {state.upper()}: begin")
            first = True
            for i in range(self.table.rowCount()):
                if self.table.item(i,0).text() == state:
                    nxt = self.table.item(i,1).text()
                    cond = self.table.item(i,2).text()
                    prefix = "if" if first else "else if"
                    code.append(f"            {prefix}({cond})")
                    code.append(f"                state <= {nxt.upper()};")
                    first = False
            if not first: code.append(f"            else\n                state <= {state.upper()};")
            code.append("        end")
        code.append("        default: state <= IDLE;")
        code.append("    endcase\nend\n")

        # C. Output Section
        output_logic = {} # {sig: [(state, cond, val)]}
        for i in range(self.table.rowCount()):
            act_raw = self.table.item(i,3).text()
            if '=' not in act_raw: continue
            s, c = self.table.item(i,0).text(), self.table.item(i,2).text()
            for a in act_raw.replace(';', ',').split(','):
                if '=' in a:
                    sig, val = a.split('=')[0].strip(), a.split('=')[1].strip()
                    if sig not in output_logic: output_logic[sig] = []
                    output_logic[sig].append((s, c, val))

        code.append("/*================================== FSM Output ==================================*/")
        for sig, rules in output_logic.items():
            code.append(f"// {sig} output logic")
            code.append(f"always@(posedge sys_clk or negedge sys_rst_n) begin")
            code.append(f"    if(sys_rst_n == 1'b0)")
            code.append(f"        {sig} <= 'b0;")
            for rs, rc, rv in rules:
                code.append(f"    else if((state == {rs.upper()}) && ({rc}))")
                code.append(f"        {sig} <= {rv};")
            code.append(f"    else")
            code.append(f"        {sig} <= {sig};")
            code.append(f"end\n")

        self.code_preview.setText("\n".join(code))

    # --- 4. 存取与工程管理 ---
    def save_project(self):
        f_data = []
        for i in range(self.table.rowCount()):
            f_data.append([self.table.item(i,j).text() if self.table.item(i,j) else "" for j in range(4)])
        p_data = []
        for i in range(self.param_table.rowCount()):
            p_data.append([self.param_table.item(i,j).text() if self.param_table.item(i,j) else "" for j in range(3)])
        
        path, _ = QFileDialog.getSaveFileName(self, "保存工程", "", "FSM JSON (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({"reset": self.reset_selector.currentText(), "fsm": f_data, "params": p_data}, f, indent=4)

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "读取工程", "", "FSM JSON (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                self.table.blockSignals(True)
                self.table.setRowCount(0)
                for r in conf.get("fsm", []): self.add_row(*r)
                self.param_table.setRowCount(0)
                for p in conf.get("params", []): self.add_param_row(*p)
                self.table.blockSignals(False)
                self.refresh_logic()
                self.reset_selector.setCurrentText(conf.get("reset", ""))

    def add_default_rows(self):
        # 初始化一些示例数据
        self.add_param_row("MONEY_HALF", "2'b01", "Input constant")
        self.add_param_row("COLA_AND_NOMONEY", "2'b10", "Output constant")
        self.add_row("IDLE", "HALF", "pi_money == MONEY_HALF", "po_cola=0")
        self.add_row("HALF", "IDLE", "pi_money == MONEY_HALF", "{po_cola,po_money}=COLA_AND_NOMONEY")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.draw_fsm()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FSMVisualizerApp()
    window.show()
    sys.exit(app.exec())