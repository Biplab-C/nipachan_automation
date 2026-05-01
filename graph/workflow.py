from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import TestWorkflowState
from graph.nodes import (
    launch_browser_node,
    inspect_page_node,
    generate_page_object_node,
    analyze_step_node,
    execute_step_node,
    finalize_node,
)
from graph.edges import route_after_execute, route_after_inspect


def build_workflow():
    graph = StateGraph(TestWorkflowState)

    graph.add_node("launch_browser", launch_browser_node)
    graph.add_node("inspect_page", inspect_page_node)
    graph.add_node("generate_page_object", generate_page_object_node)
    graph.add_node("analyze_step", analyze_step_node)
    graph.add_node("execute_step", execute_step_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("launch_browser")
    graph.add_edge("launch_browser", "inspect_page")
    graph.add_conditional_edges(
        "inspect_page",
        route_after_inspect,
        {"generate_page_object": "generate_page_object", "finalize": "finalize"},
    )
    graph.add_edge("generate_page_object", "analyze_step")
    graph.add_edge("analyze_step", "execute_step")
    graph.add_conditional_edges(
        "execute_step",
        route_after_execute,
        {
            "inspect_page": "inspect_page",
            "analyze_step": "analyze_step",
            "finalize": "finalize",
        },
    )
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=MemorySaver())


workflow = build_workflow()
