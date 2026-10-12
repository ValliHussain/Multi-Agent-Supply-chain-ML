# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent_workflow import app as agent_workflow_app
from database import init_db, log_evaluation
from route_service import get_realtime_telemetry

app = FastAPI(title="Autonomous Supply Chain Telemetry & Part Manager", version="4.0")

@app.on_event("startup")
def startup_event():
    init_db()

class ShipmentRequest(BaseModel):
    shipment_id: str
    origin: str
    destination: str
    part_name: str
    order_quantity: int
    supplier_reliability: float

@app.post("/evaluate-shipment")
def evaluate_shipment(request: ShipmentRequest):
    try:
        # AUTOMATED TELEMETRY: Fetch live weather and traffic/congestion for the route
        telemetry = get_realtime_telemetry(request.origin, request.destination)
        
        initial_state = {
            "messages": [],
            "shipment_id": request.shipment_id,
            "origin": request.origin,
            "destination": request.destination,
            "part_name": request.part_name,
            "order_quantity": request.order_quantity,
            "route_congestion": telemetry["route_congestion"],
            "weather_severity": telemetry["weather_severity"],
            "supplier_reliability": request.supplier_reliability,
            "risk_score": 0.0,
            "delay_days": 0,
            "cost_impact": 0.0,
            "total_weight_kg": 0.0,
            "category": "",
            "status": "",
            "backup_supplier_info": "",
            "mitigation_plan": ""
        }
        
        # Run LangGraph multi-agent pipeline
        final_state = agent_workflow_app.invoke(initial_state)
        
        response_payload = {
            "shipment_id": final_state["shipment_id"],
            "origin": request.origin,
            "destination": request.destination,
            "part_name": final_state["part_name"],
            "order_quantity": final_state["order_quantity"],
            "route_congestion": telemetry["route_congestion"],
            "weather_severity": telemetry["weather_severity"],
            "total_weight_kg": final_state["total_weight_kg"],
            "risk_score": final_state["risk_score"],
            "delay_days": final_state["delay_days"],
            "cost_impact": final_state["cost_impact"],
            "status": final_state["status"],
            "backup_supplier_info": final_state["backup_supplier_info"],
            "mitigation_plan": final_state["mitigation_plan"] if final_state["mitigation_plan"] else "Shipment normal. No mitigation required."
        }
        
        # Save to SQLite database audit log including origin/destination
        log_evaluation({
            "shipment_id": request.shipment_id,
            "part_name": request.part_name,
            "order_quantity": request.order_quantity,
            "total_weight_kg": final_state["total_weight_kg"],
            "route_congestion": telemetry["route_congestion"],
            "weather_severity": telemetry["weather_severity"],
            "supplier_reliability": request.supplier_reliability,
            "risk_score": final_state["risk_score"],
            "delay_days": final_state["delay_days"],
            "cost_impact": final_state["cost_impact"],
            "status": final_state["status"],
            "backup_supplier_info": final_state["backup_supplier_info"],
            "mitigation_plan": final_state["mitigation_plan"] if final_state["mitigation_plan"] else "Shipment normal. No mitigation required."
        })
        
        return response_payload
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)