import sys
import json
import math
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView, QComboBox, 
                             QFileDialog, QCompleter, QStyledItemDelegate, QLineEdit, QTextEdit, QTabWidget, QMessageBox)
from PySide6.QtGui import QPixmap, QColor, QFont
from PySide6.QtCore import Qt
import graphviz

# --- 1. UI 组件：增强型补全输入框 ---
class TabLineEdit(QLineEdit):
    def keyPressEvent(self, event):
        popup = self.completer().popup() if self.completer() else None
        if popup and popup.isVisible():
            if event.key() in (Qt.Key_Tab, Qt.Key_Enter, Qt.Key_Return):
                index = popup.currentIndex()
                if not index.isValid():
                    index = self.completer().completionModel().index(0, 0)
                res = self.completer().completionModel().data(index)
                self.setText(res)
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
            completer.setCompletionMode(QCompleter.PopupCompletion)
            editor.setCompleter(completer)
            return editor
        return super().createEditor(parent, option, index)

# --- 2. 主窗口 ---
class FSMVisualizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPGA 状态机逻辑设计工具 - V1.0.1 (Stable)")
        self.resize(1500, 950)
        
        self.output_filename = "fsm_render_final"
        self.state_list = []
        self.delegate = AutocompleteDelegate()
        
        self.init_ui()
        self.load_official_example() 
        self.refresh_logic()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # --- 左侧：设计区 ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        toolbar = QHBoxLayout()
        btn_save = QPushButton("保存工程")
        btn_load = QPushButton("读取工程")
        self.btn_help = QPushButton("[?]")
        self.btn_info = QPushButton("[i]")
        for b in [self.btn_help, self.btn_info]: b.setFixedWidth(40)
        self.btn_help.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold;")
        self.btn_info.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold;")
        
        btn_gen = QPushButton("生成 Verilog")
        btn_gen.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 5px;")
        
        btn_save.clicked.connect(self.save_project)
        btn_load.clicked.connect(self.load_project)
        btn_gen.clicked.connect(self.generate_verilog)
        self.btn_help.clicked.connect(self.show_help)
        self.btn_info.clicked.connect(self.show_info)

        toolbar.addWidget(btn_save); toolbar.addWidget(btn_load); toolbar.addWidget(btn_gen)
        toolbar.addWidget(self.btn_help); toolbar.addWidget(self.btn_info)
        left_layout.addLayout(toolbar)

        self.design_tabs = QTabWidget()
        
        # Tab 1: 状态转移
        trans_page = QWidget(); trans_layout = QVBoxLayout(trans_page)
        cfg_row = QHBoxLayout()
        cfg_row.addWidget(QLabel("复位状态:"))
        self.reset_selector = QComboBox()
        self.reset_selector.currentIndexChanged.connect(self.draw_fsm)
        cfg_row.addWidget(self.reset_selector, 1)
        cfg_row.addWidget(QLabel("状态编码:"))
        self.encoding_selector = QComboBox()
        self.encoding_selector.addItems(["Binary", "One-hot", "Gray"])
        cfg_row.addWidget(self.encoding_selector, 1)
        trans_layout.addLayout(cfg_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["当前状态", "下一状态", "跳转条件", "输出动作"])
        self.table.setItemDelegate(self.delegate)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(self.refresh_logic)
        
        row_ctrl = QHBoxLayout()
        add_btn = QPushButton("添加跳转 (+)"); del_btn = QPushButton("删除选中 (-)")
        add_btn.clicked.connect(lambda: self.add_row())
        del_btn.clicked.connect(self.remove_row)
        row_ctrl.addWidget(add_btn); row_ctrl.addWidget(del_btn)
        trans_layout.addWidget(self.table); trans_layout.addLayout(row_ctrl)
        
        # Tab 2: 参数定义
        param_page = QWidget(); param_layout = QVBoxLayout(param_page)
        self.param_table = QTableWidget(0, 3)
        self.param_table.setHorizontalHeaderLabels(["参数名", "数值/位宽", "备注"])
        self.param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        add_p_btn = QPushButton("添加参数 (+)"); add_p_btn.clicked.connect(self.add_param_row)
        param_layout.addWidget(QLabel("预定义常量参数:")); param_layout.addWidget(self.param_table); param_layout.addWidget(add_p_btn)

        self.design_tabs.addTab(trans_page, "状态转移逻辑"); self.design_tabs.addTab(param_page, "信号参数定义")
        left_layout.addWidget(self.design_tabs)

        # --- 右侧：预览区 ---
        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget)
        self.graph_label = QLabel("正在生成状态图..."); self.graph_label.setAlignment(Qt.AlignCenter)
        self.graph_label.setStyleSheet("border: 1px solid #ddd; background: white;")
        self.code_preview = QTextEdit(); self.code_preview.setFont(QFont("Consolas", 10))
        self.code_preview.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc;")

        right_layout.addWidget(QLabel("可视化状态转移图:")); right_layout.addWidget(self.graph_label, 3)
        right_layout.addWidget(QLabel("Verilog 代码预览:")); right_layout.addWidget(self.code_preview, 2)
        main_layout.addWidget(left_widget, 1); main_layout.addWidget(right_widget, 1)

    # --- 安全获取表格文本 ---
    def safe_get_text(self, table, row, col):
        item = table.item(row, col)
        return item.text() if item else ""

    # --- 功能函数 ---
    def show_help(self):
        help_text = """
        <h3>FSM 工具使用帮助</h3>
        <b>1. 逻辑输入:</b>
        <ul>
            <li><b>当前/下一状态:</b> 直接输入状态名，或在此基础上点击键盘上下选中，按 <b>Tab</b> 自动补全。</li>
            <li><b>跳转条件:</b> 输入 Verilog 语法条件，如 <i>pi_data == 1'b1</i>。</li>
            <li><b>输出动作:</b> 格式为 <i>变量名=值</i>，多个动作逗号隔开，如 <i>po_vld=1, po_data=8'hFF</i>。</li>
        </ul>
        <b>2. 状态编码:</b>
        <ul>
            <li><b>Binary:</b> 普通二进制编码。</li>
            <li><b>One-hot:</b> 独热码（每个状态一位）。</li>
            <li><b>Gray:</b> 格雷码（相邻状态仅一位变化）。</li>
        </ul>
        <b>3. 技巧:</b>
        <ul>
            <li>同一状态下相同跳转条件会显示为<span style='color:red;'>红色</span>表示冲突。</li>
            <li>生成的 Verilog 采用全时序打拍输出，不是经典的三段式状态机</li>
        </ul>
        <b>4. 注意:</b>
        <ul>
            <li>目前 Verilog 代码基于硬编码输出，并且是基于用户输入的条件生成判断条件，结果仅供参考，可作为单纯的状态机绘图工具使用</li>
            <li>图像生成基于 Graphviz 开源的图形可视化软件处理有向无环图和有向循环图</li>
        </ul>
        """
        QMessageBox.information(self, "使用说明", help_text)

    def show_info(self):
        QMessageBox.about(self, "项目信息", "<b>名称:</b> FPGA 可视化状态机设计工具<br><b>版本:</b> V1.0.0 (正式版)<br><b>开发者:</b> Gemini (Google) & Kevin_Quinn_Cat<br><b>年份:</b> 2026.2<br><b>维护:</b> Kevin_Quinn_Cat@outlook.com")

    def load_official_example(self):
        self.table.setRowCount(0); self.param_table.setRowCount(0)
        self.add_param_row("DIN_ZERO", "1'b0", "Input 0"); self.add_param_row("DIN_ONE", "1'b1", "Input 1")
        ex = [("S_IDLE", "S_ONE", "pi_data == DIN_ONE", "po_match=0"),
              ("S_IDLE", "S_IDLE", "pi_data == DIN_ZERO", "po_match=0"),
              ("S_ONE", "S_TEN", "pi_data == DIN_ZERO", "po_match=0"),
              ("S_ONE", "S_ONE", "pi_data == DIN_ONE", "po_match=0"),
              ("S_TEN", "S_IDLE", "pi_data == DIN_ONE", "po_match=1"),
              ("S_TEN", "S_IDLE", "pi_data == DIN_ZERO", "po_match=0")]
        self.table.blockSignals(True)
        for s, n, c, a in ex: self.add_row(s, n, c, a)
        self.table.blockSignals(False)

    def add_row(self, s="IDLE", n="IDLE", c="1", a=""):
        self.table.blockSignals(True)
        r = self.table.rowCount(); self.table.insertRow(r)
        self.table.setItem(r,0,QTableWidgetItem(s)); self.table.setItem(r,1,QTableWidgetItem(n))
        self.table.setItem(r,2,QTableWidgetItem(c)); self.table.setItem(r,3,QTableWidgetItem(a))
        self.table.blockSignals(False); self.refresh_logic()

    def remove_row(self):
        curr = self.table.currentRow()
        if curr >= 0: self.table.removeRow(curr); self.refresh_logic()

    def add_param_row(self, name="NAME", val="0", note=""):
        r = self.param_table.rowCount(); self.param_table.insertRow(r)
        self.param_table.setItem(r,0,QTableWidgetItem(name))
        self.param_table.setItem(r,1,QTableWidgetItem(val))
        self.param_table.setItem(r,2,QTableWidgetItem(note))

    def refresh_logic(self):
        self.table.blockSignals(True)
        try:
            states = set()
            for i in range(self.table.rowCount()):
                s, n = self.safe_get_text(self.table, i, 0), self.safe_get_text(self.table, i, 1)
                if s: states.add(s)
                if n: states.add(n)
            self.state_list = sorted(list(states))
            self.delegate.set_words(self.state_list)
            cur_reset = self.reset_selector.currentText()
            self.reset_selector.blockSignals(True); self.reset_selector.clear(); self.reset_selector.addItems(self.state_list)
            if cur_reset in self.state_list: self.reset_selector.setCurrentText(cur_reset)
            self.reset_selector.blockSignals(False)
            self.check_conflicts(); self.draw_fsm()
        finally: self.table.blockSignals(False)

    def check_conflicts(self):
        cmap = {}
        for i in range(self.table.rowCount()):
            for j in range(4): 
                it = self.table.item(i,j)
                if it: it.setBackground(QColor(255,255,255))
            s, c = self.safe_get_text(self.table, i, 0), self.safe_get_text(self.table, i, 2)
            if s and c:
                key = (s, c); cmap.setdefault(key, []).append(i)
        for rows in cmap.values():
            if len(rows) > 1:
                for r in rows:
                    for col in range(4): 
                        item = self.table.item(r,col)
                        if item: item.setBackground(QColor(255,200,200))

    def draw_fsm(self):
        dot = graphviz.Digraph(format='png'); dot.attr(rankdir='LR', fontname='Microsoft YaHei')
        res = self.reset_selector.currentText(); has_content = False
        for i in range(self.table.rowCount()):
            s, n = self.safe_get_text(self.table, i, 0), self.safe_get_text(self.table, i, 1)
            c, a = self.safe_get_text(self.table, i, 2), self.safe_get_text(self.table, i, 3)
            if s and n:
                dot.edge(s, n, label=f"{c}\n/ {a}" if a else c, fontname='Microsoft YaHei')
                has_content = True
        for state in self.state_list:
            if state == res: dot.node(state, shape='doublecircle', color='darkgreen', style='filled', fillcolor='honeydew')
            else: dot.node(state, shape='circle', style='filled', fillcolor='lightblue')
        if not has_content: return
        try:
            dot.render(self.output_filename, cleanup=True)
            pix = QPixmap(f"{self.output_filename}.png")
            if not pix.isNull(): self.graph_label.setPixmap(pix.scaled(self.graph_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except: pass

    def generate_verilog(self):
        if not self.state_list: return
        mode = self.encoding_selector.currentText(); num = len(self.state_list)
        if mode == "Binary":
            w = max(1, math.ceil(math.log2(num))); ev = [f"{w}'d{i}" for i in range(num)]
        elif mode == "One-hot":
            w = num; ev = [f"{w}'b" + ("0"*num)[:num-1-i] + "1" + "0"*i for i in range(num)]
        else:
            w = max(1, math.ceil(math.log2(num))); ev = [f"{w}'d{(i >> 1) ^ i}" for i in range(num)]

        code = ["/*===================================== FSM ======================================*/\n"]
        code.append("/*== Encoding ==*/")
        for i in range(self.param_table.rowCount()):
            n, v = self.safe_get_text(self.param_table, i, 0), self.safe_get_text(self.param_table, i, 1)
            if n: code.append(f"parameter   {n.ljust(15)} = {v};")
        code.append("")
        for n, v in zip(self.state_list, ev): code.append(f"parameter   {n.upper().ljust(15)} = {v};")
        code.append(f"reg [{w-1}:0] state;\n")

        rs = self.reset_selector.currentText()
        code.append("/*== State Transition ==*/\nalways@(posedge sys_clk or negedge sys_rst_n) begin")
        code.append(f"    if(sys_rst_n == 1'b0)\n        state <= {rs.upper() if rs else 'IDLE'};\n    else case(state)")
        for st in self.state_list:
            code.append(f"        {st.upper()}: begin")
            first = True
            for i in range(self.table.rowCount()):
                if self.safe_get_text(self.table, i, 0) == st:
                    nxt, cond = self.safe_get_text(self.table, i, 1), self.safe_get_text(self.table, i, 2)
                    p = "if" if first else "else if"; code.append(f"            {p}({cond})\n                state <= {nxt.upper()};")
                    first = False
            if not first: code.append(f"            else\n                state <= {st.upper()};")
            code.append("        end")
        code.append("        default: state <= IDLE;\n    endcase\nend\n")

        outs = {}
        for i in range(self.table.rowCount()):
            a_raw = self.safe_get_text(self.table, i, 3)
            if '=' not in a_raw: continue
            for a in a_raw.replace(';',',').split(','):
                if '=' in a:
                    k, v = a.split('=')[0].strip(), a.split('=')[1].strip()
                    outs.setdefault(k, []).append((self.safe_get_text(self.table, i, 0), self.safe_get_text(self.table, i, 2), v))
        for k, rules in outs.items():
            code.append(f"// Output: {k}\nalways@(posedge sys_clk or negedge sys_rst_n) begin\n    if(sys_rst_n == 1'b0)\n        {k} <= 'b0;")
            for s, c, v in rules: code.append(f"    else if((state == {s.upper()}) && ({c}))\n        {k} <= {v};")
            code.append(f"    else\n        {k} <= {k};\nend\n")
        self.code_preview.setText("\n".join(code))

    def save_project(self):
        f = [[self.safe_get_text(self.table, i, j) for j in range(4)] for i in range(self.table.rowCount())]
        p = [[self.safe_get_text(self.param_table, i, j) for j in range(3)] for i in range(self.param_table.rowCount())]
        path, _ = QFileDialog.getSaveFileName(self, "保存工程", "", "*.json")
        if path:
            with open(path, 'w', encoding='utf-8') as f_out:
                json.dump({"reset": self.reset_selector.currentText(), "enc": self.encoding_selector.currentText(), "fsm": f, "params": p}, f_out, indent=4)

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "读取工程", "", "*.json")
        if path:
            with open(path, 'r', encoding='utf-8') as f_in:
                c = json.load(f_in); self.table.setRowCount(0); self.param_table.setRowCount(0)
                self.table.blockSignals(True)
                for r_data in c.get("fsm", []): self.add_row(*r_data)
                for pr in c.get("params", []): self.add_param_row(*pr)
                self.table.blockSignals(False); self.encoding_selector.setCurrentText(c.get("enc", "Binary"))
                self.refresh_logic(); self.reset_selector.setCurrentText(c.get("reset", ""))

    def resizeEvent(self, event): super().resizeEvent(event); self.draw_fsm()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FSMVisualizerApp(); window.show(); sys.exit(app.exec())