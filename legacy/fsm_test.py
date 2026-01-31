import graphviz
import os

# 版本报告
print("""
-------------------
VERSION REPORT V0.1
STATUS: ENVIRONMENT TEST
FEATURES: GRAPHVIZ INTEGRATION CHECK
-------------------
""")

def test_fsm_render():
    # 创建一个有向图
    fsm = graphviz.Digraph('Finite_State_Machine', format='png')
    fsm.attr(rankdir='LR', size='8,5')

    # 定义状态样式
    fsm.attr('node', shape='circle', style='filled', color='lightblue')
    
    # 添加状态和跳转逻辑 (模拟数据)
    # 格式: 源状态, 目标状态, 触发条件
    transitions = [
        ('IDLE', 'SETUP', 'rst_n == 1'),
        ('SETUP', 'WORK', 'cfg_done'),
        ('WORK', 'WORK', 'data_vld'),
        ('WORK', 'IDLE', 'error'),
    ]

    for src, dst, cond in transitions:
        fsm.edge(src, dst, label=cond)

    # 渲染并保存
    try:
        output_path = fsm.render('test_fsm_output', view=True)
        print(f"成功! 状态机图已生成至: {output_path}")
    except Exception as e:
        print(f"失败! 错误原因: {e}")
        print("\n提示: 请确保 Graphviz/bin 路径已加入系统环境变量 PATH。")

if __name__ == "__main__":
    test_fsm_render()