from langgraph.graph import StateGraph, END
from models.schemas import AgentState
from agents.nodes import plan, search, evaluate, archive

def create_mining_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    workflow.add_node("plan", plan)
    workflow.add_node("search", search)
    workflow.add_node("evaluate", evaluate)
    workflow.add_node("archive", archive)
    
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "search")
    workflow.add_edge("search", "evaluate")
    workflow.add_edge("evaluate", "archive")
    workflow.add_edge("archive", END)
    
    return workflow.compile()
