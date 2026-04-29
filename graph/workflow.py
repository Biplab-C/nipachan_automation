from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import TestWorkflowState
from graph.nodes import parse_node, generate_node, execute_node, analyze_error_node, finalize_node
from graph.edges import route_after_execution, route_after_analysis


def build_workflow():
    graph = StateGraph(TestWorkflowState)

    graph.add_node("parse", parse_node)
    graph.add_node("generate", generate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("analyze_error", analyze_error_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("parse")

    graph.add_edge("parse", "generate")
    graph.add_edge("generate", "execute")
    graph.add_conditional_edges(
        "execute",
        route_after_execution,
        {"finalize": "finalize", "analyze_error": "analyze_error"},
    )
    graph.add_conditional_edges(
        "analyze_error",
        route_after_analysis,
        {"generate": "generate", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


workflow = build_workflow()
