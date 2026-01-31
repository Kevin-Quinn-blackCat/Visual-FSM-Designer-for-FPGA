import sys
import json
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QHeaderView, QComboBox, 
                             QFileDialog, QCompleter, QStyledItemDelegate, QLineEdit, QTextEdit, QTabWidget, QMessageBox)
from PySide6.QtGui import QPixmap, QColor, QFont
from PySide6.QtCore import Qt
import graphviz

# --- 1. UI 组件：支持 Tab 补全的 LineEdit ---
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

# --- 2. 主程序 ---
class FSMVisualizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FPGA 状态机逻辑设计工具 - V0.7")
        self.resize(1500, 950)
        
        self.output_filename = "fsm_render_v07"
        self.state_list = []
        self.delegate = AutocompleteDelegate()
        
        self.init_ui()
        self.load_official_example() # 加载官方例程
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
        self.btn_help = QPushButton("[?]")
        self.btn_help.setFixedWidth(40)
        self.btn_help.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold;")
        
        btn_gen = QPushButton("生成 Verilog")
        btn_gen.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 5px;")
        
        btn_save.clicked.connect(self.save_project)
        btn_load.clicked.connect(self.load_project)
        btn_gen.clicked.connect(self.generate_verilog)
        self.btn_help.clicked.connect(self.show_help)

        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_load)
        toolbar.addWidget(btn_gen)
        toolbar.addWidget(self.btn_help)
        left_layout.addLayout(toolbar)

        # 设计选项卡
        self.design_tabs = QTabWidget()
        
        # Tab 1: 状态转移
        trans_page = QWidget()
        trans_layout = QVBoxLayout(trans_page)
        
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
        add_row_btn = QPushButton("添加跳转 (+)")
        del_row_btn = QPushButton("删除选中 (-)")
        add_row_btn.clicked.connect(lambda: self.add_row())
        del_row_btn.clicked.connect(self.remove_row)
        row_ctrl.addWidget(add_row_btn)
        row_ctrl.addWidget(del_row_btn)
        
        trans_layout.addWidget(self.table)
        trans_layout.addLayout(row_ctrl)
        
        # Tab 2: 参数定义
        param_page = QWidget()
        param_layout = QVBoxLayout(param_page)
        self.param_table = QTableWidget(0, 3)
        self.param_table.setHorizontalHeaderLabels(["参数名", "数值/位宽", "备注"])
        self.param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        add_param_btn = QPushButton("添加参数 (+)")
        add_param_btn.clicked.connect(self.add_param_row)
        param_layout.addWidget(QLabel("预定义常量参数 (用于代码生成):"))
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
        self.graph_label.setStyleSheet("border: 1px solid #ddd; background: white;")
        
        self.code_preview = QTextEdit()
        self.code_preview.setFont(QFont("Consolas", 10))
        self.code_preview.setStyleSheet("background-color: #1e1e1e; color: #dcdcdc;")

        right_layout.addWidget(QLabel("可视化状态转移图:"))
        right_layout.addWidget(self.graph_label, 3)
        right_layout.addWidget(QLabel("Verilog 代码预览:"))
        right_layout.addWidget(self.code_preview, 2)

        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(right_widget, 1)

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
            <li>目前 Verilog 代码基于硬编码输出，并且是基于用户输入的条件生成判断条件，结果仅供参考</li>
            <li>图像生成基于Graphviz开源的图形可视化软件处理有向无环图和有向循环图</li>
        </ul>
        """
        QMessageBox.information(self, "功能说明", help_text)

    def load_official_example(self):
        """预加载 101 序列检测器官方例程"""
        self.table.setRowCount(0)
        self.param_table.setRowCount(0)
        # 默认参数
        self.add_param_row("DIN_ZERO", "1'b0", "Input 0")
        self.add_param_row("DIN_ONE",  "1'b1", "Input 1")
        # 默认转移逻辑 (101 检测)
        example_logic = [
            ("S_IDLE", "S_ONE",  "pi_data == DIN_ONE",  "po_match=0"),
            ("S_IDLE", "S_IDLE", "pi_data == DIN_ZERO", "po_match=0"),
            ("S_ONE",  "S_TEN",  "pi_data == DIN_ZERO", "po_match=0"),
            ("S_ONE",  "S_ONE",  "pi_data == DIN_ONE",  "po_match=0"),
            ("S_TEN",  "S_IDLE", "pi_data == DIN_ONE",  "po_match=1"),
            ("S_TEN",  "S_IDLE", "pi_data == DIN_ZERO", "po_match=0"),
        ]
        self.table.blockSignals(True)
        for s, n, c, a in example_logic:
            self.add_row(s, n, c, a)
        self.table.blockSignals(False)
        self.refresh_logic()

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

    def add_param_row(self, name="NAME", val="0", note=""):
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
                dot.edge(s, n, label=f"{c}\n/ {a}" if a else c, fontname='Microsoft YaHei')
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
                self.graph_label.setPixmap(pixmap.scaled(self.graph_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except: pass

    # --- 3. Verilog 代码生成 (支持 Binary, One-hot, Gray) ---
    def generate_verilog(self):
        if not self.state_list: return
        mode = self.encoding_selector.currentText()
        num = len(self.state_list)
        
        # 计算位宽和数值
        enc_vals = []
        if mode == "Binary":
            width = max(1, math.ceil(math.log2(num)))
            enc_vals = [f"{width}'d{i}" for i in range(num)]
        elif mode == "One-hot":
            width = num
            enc_vals = [f"{width}'b" + ("0"*num)[:num-1-i] + "1" + "0"*i for i in range(num)]
        else: # Gray
            width = max(1, math.ceil(math.log2(num)))
            for i in range(num):
                g = (i >> 1) ^ i
                enc_vals.append(f"{width}'d{g}")

        code = ["/*===================================== FSM ======================================*/\n"]
        code.append("/*== Encoding ==*/")
        # 信号参数
        for i in range(self.param_table.rowCount()):
            n = self.param_table.item(i,0).text()
            v = self.param_table.item(i,1).text()
            if n: code.append(f"parameter   {n.ljust(15)} = {v};")
        # 状态参数
        code.append("")
        for name, val in zip(self.state_list, enc_vals):
            code.append(f"parameter   {name.upper().ljust(15)} = {val};")
        code.append(f"reg [{width-1}:0] state;\n")

        # 状态转移
        reset_s = self.reset_selector.currentText()
        code.append("/*== State Transition ==*/")
        code.append("always@(posedge sys_clk or negedge sys_rst_n) begin")
        code.append(f"    if(sys_rst_n == 1'b0)\n        state <= {reset_s.upper() if reset_s else 'IDLE'};")
        code.append("    else case(state)")
        for state in self.state_list:
            code.append(f"        {state.upper()}: begin")
            rows = [i for i in range(self.table.rowCount()) if self.table.item(i,0).text()==state]
            for idx, r in enumerate(rows):
                prefix = "if" if idx==0 else "else if"
                code.append(f"            {prefix}({self.table.item(r,2).text()})")
                code.append(f"                state <= {self.table.item(r,1).text().upper()};")
            if rows: code.append(f"            else\n                state <= {state.upper()};")
            code.append("        end")
        code.append("        default: state <= IDLE;\n    endcase\nend\n")

        # 输出动作
        outputs = {}
        for i in range(self.table.rowCount()):
            a_raw = self.table.item(i,3).text()
            if '=' not in a_raw: continue
            for a in a_raw.replace(';',',').split(','):
                sig, val = a.split('=')[0].strip(), a.split('=')[1].strip()
                if sig not in outputs: outputs[sig] = []
                outputs[sig].append((self.table.item(i,0).text(), self.table.item(i,2).text(), val))

        for sig, rules in outputs.items():
            code.append(f"// Output: {sig}")
            code.append(f"always@(posedge sys_clk or negedge sys_rst_n) begin")
            code.append(f"    if(sys_rst_n == 1'b0)\n        {sig} <= 'b0;")
            for s, c, v in rules:
                code.append(f"    else if((state == {s.upper()}) && ({c}))\n        {sig} <= {v};")
            code.append(f"    else\n        {sig} <= {sig};")
            code.append(f"end\n")

        self.code_preview.setText("\n".join(code))

    def save_project(self):
        f_data = [[self.table.item(i,j).text() if self.table.item(i,j) else "" for j in range(4)] for i in range(self.table.rowCount())]
        p_data = [[self.param_table.item(i,j).text() if self.param_table.item(i,j) else "" for j in range(3)] for i in range(self.param_table.rowCount())]
        path, _ = QFileDialog.getSaveFileName(self, "保存", "", "*.json")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({"reset": self.reset_selector.currentText(), "enc": self.encoding_selector.currentText(), "fsm": f_data, "params": p_data}, f, indent=4)

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "读取", "", "*.json")
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                conf = json.load(f)
                self.table.setRowCount(0); self.param_table.setRowCount(0)
                for r in conf.get("fsm", []): self.add_row(*r)
                for p in conf.get("params", []): self.add_param_row(*p)
                self.encoding_selector.setCurrentText(conf.get("enc", "Binary"))
                self.refresh_logic()
                self.reset_selector.setCurrentText(conf.get("reset", ""))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.draw_fsm()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FSMVisualizerApp()
    window.show()
    sys.exit(app.exec())