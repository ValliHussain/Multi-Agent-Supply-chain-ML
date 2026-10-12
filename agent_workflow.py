# agent_workflow.py
import os
from typing import Annotated, TypedDict
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
from ml_model import predict_shipment_risk
from database import get_best_supplier

# 1. Define the Expanded Shared State for our Agents
class SupplyChainState(TypedDict):
    messages: list[BaseMessage]
    shipment_id: str
    part_name: str
    order_quantity: int
    route_congestion: float
    weather_severity: int
    supplier_reliability: float
    risk_score: float
    delay_days: int
    cost_impact: float
    total_weight_kg: float
    category: str
    status: str
    backup_supplier_info: str
    mitigation_plan: str

# Initialize the Groq LLM
llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)

# 2. Define Agent Nodes

def monitor_agent_node(state: SupplyChainState):
    """Monitor Agent: Evaluates risk, delay, freight weight, and cost impact via ML model."""
    print("\n--- [Monitor Agent] Analyzing part shipment & freight metrics via ML Model... ---")
    
    prediction = predict_shipment_risk(
        route_congestion_index=state["route_congestion"],
        weather_severity=state["weather_severity"],
        supplier_reliability=state["supplier_reliability"],
        part_name=state["part_name"],
        order_quantity=state["order_quantity"]
    )
    
    state["risk_score"] = prediction["risk_score"]
    state["delay_days"] = prediction["predicted_delay_days"]
    state["cost_impact"] = prediction["cost_impact"]
    state["total_weight_kg"] = prediction["total_weight_kg"]
    state["category"] = prediction["category"]
    state["status"] = prediction["status"]
    
    analysis_msg = (
        f"ML Assessment Complete for {state['order_quantity']}x {state['part_name']}:\n"
        f"- Risk Score: {state['risk_score']}/100\n"
        f"- Predicted Delay: {state['delay_days']} days\n"
        f"- Total Freight Weight: {state['total_weight_kg']} kg\n"
        f"- Projected Cost Impact: ${state['cost_impact']:,.2f}\n"
        f"- Status: {state['status']}"
    )
    
    state["messages"].append(AIMessage(content=analysis_msg))
    return state


def sourcing_logistics_agent_node(state: SupplyChainState):
    """Sourcing & Logistics Agent: Queries SQLite inventory for the optimal category backup supplier."""
    print("\n--- [Sourcing & Logistics Agent] Checking supplier stock against order quantity... ---")
    
    if state["risk_score"] > 40:
        # Query SQLite matching the part category and required quantity
        backup_info = get_best_supplier(state["category"], state["order_quantity"])
    else:
        backup_info = "No backup sourcing required. Shipment is within normal parameters."
        
    state["backup_supplier_info"] = backup_info
    state["messages"].append(AIMessage(content=f"Logistics Scan Result: {backup_info}"))
    return state


def finance_approval_agent_node(state: SupplyChainState):
    """Finance Agent: Synthesizes freight weight costs, inventory risks, and drafts mitigation plans."""
    print("\n--- [Finance Agent] Formulating financial & logistics mitigation strategy... ---")
    
    prompt = f"""
    You are an expert supply chain financial controller. 
    Review the following incident details:
    - Part Name: {state['part_name']} (Category: {state['category']})
    - Order Quantity: {state['order_quantity']:,} units
    - Total Freight Weight: {state['total_weight_kg']:,.2f} kg
    - Risk Score: {state['risk_score']}
    - Delay Days: {state['delay_days']}
    - Total Financial Cost Impact (including carrier freight weight surcharges & holding costs): ${state['cost_impact']:,.2f}
    - Status: {state['status']}
    - Selected Backup Supplier Stock Verification: {state['backup_supplier_info']}
    
    Draft a concise, high-level action plan addressing carrier freight surcharges, whether to reroute or expedite sourcing, and how to absorb or recover the estimated financial cost impact. Use Markdown formatting.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    state["mitigation_plan"] = response.content
    state["messages"].append(AIMessage(content=f"Final Mitigation Plan:\n{response.content}"))
    return state


# 3. Define Conditional Routing Logic
should_mitigate = lambda state: "mitigate" if state["risk_score"] > 40 else "proceed"


# 4. Construct the LangGraph Workflow
workflow = StateGraph(SupplyChainState)

workflow.add_node("monitor", monitor_agent_node)
workflow.add_node("sourcing_logistics", sourcing_logistics_agent_node)
workflow.add_node("finance_approval", finance_approval_agent_node)

workflow.set_entry_point("monitor")

workflow.add_conditional_edges(
    "monitor",
    should_mitigate,
    {
        "mitigate": "sourcing_logistics",
        "proceed": END
    }
)

workflow.add_edge("sourcing_logistics", "finance_approval")
workflow.add_edge("finance_approval", END)

app = workflow.compile()