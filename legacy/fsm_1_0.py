import graphviz

class FSMNode:
    def __init__(self, name, output=""):
        self.name = name
        self.output = output

class FSMEdge:
    def __init__(self, src, dst, condition=""):
        self.src = src
        self.dst = dst
        self.condition = condition

class FSMGenerator:
    def __init__(self, name="FSM_Project"):
        self.name = name
        self.states = {} # Name -> FSMNode
        self.transitions = []

    def add_transition(self, src_name, dst_name, cond=""):
        if src_name not in self.states:
            self.states[src_name] = FSMNode(src_name)
        if dst_name not in self.states:
            self.states[dst_name] = FSMNode(dst_name)
        
        edge = FSMEdge(src_name, dst_name, cond)
        self.transitions.append(edge)

    def draw(self):
        # 使用 Graphviz 的 dot 引擎进行自动布局
        dot = graphviz.Digraph(self.name, comment='Generated FSM')
        dot.attr(rankdir='LR') # 从左向右布局，减少重叠
        
        # 添加节点
        for name, node in self.states.items():
            label = f"{name}"
            if node.output:
                label += f"\n({node.output})"
            dot.node(name, label, shape='circle')

        # 添加连线
        for edge in self.transitions:
            dot.edge(edge.src, edge.dst, label=edge.condition)

        return dot

# 示例使用
if __name__ == "__main__":
    fsm = FSMGenerator("Serial_Receiver")
    
    # 模拟用户只需关注逻辑设计
    fsm.add_transition("IDLE", "START", "rx_start == 0")
    fsm.add_transition("START", "DATA", "tick == 1")
    fsm.add_transition("DATA", "DATA", "bit_cnt < 8")
    fsm.add_transition("DATA", "STOP", "bit_cnt == 8")
    fsm.add_transition("STOP", "IDLE", "rx_stop == 1")
    
    # 自动生成图
    # dot_graph = fsm.draw()
    # dot_graph.render('fsm_output', format='png', view=True)
    print("V0.1 逻辑原型构建完成。图形渲染已准备就绪。")