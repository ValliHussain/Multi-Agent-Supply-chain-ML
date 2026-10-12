# mcp_server.py
from mcp.server.fastmcp import FastMCP
from ml_model import predict_shipment_risk

# Initialize the FastMCP server
mcp = FastMCP("Supply Chain Intelligence Server")

@mcp.tool()
def evaluate_shipment_risk(
    route_congestion_index: float, 
    weather_severity: int, 
    supplier_reliability: float
) -> str:
    """
    Analyzes shipment parameters using the ML model to return a disruption risk score and estimated delay.
    """
    result = predict_shipment_risk(route_congestion_index, weather_severity, supplier_reliability)
    return (
        f"ML Model Prediction Result:\n"
        f"- Risk Score: {result['risk_score']}/100\n"
        f"- Estimated Delay: {result['predicted_delay_days']} days\n"
        f"- Status: {result['status']}"
    )

@mcp.tool()
def query_backup_suppliers(component_category: str) -> str:
    """
    Queries the enterprise database for verified alternative suppliers with active inventory.
    """
    # Mock database lookup
    suppliers = {
        "electronics": "Apex Microparts (Stock Available: 5,400 units, Avg Lead Time: 3 days)",
        "raw_materials": "Vanguard Logistics & Metals (Stock Available: 12,000 tons, Avg Lead Time: 5 days)",
        "packaging": "EcoPack Solutions (Stock Available: 50,000 units, Avg Lead Time: 1 day)"
    }
    
    return suppliers.get(
        component_category.lower(), 
        "No direct backup supplier found. Recommended to run broader market scan."
    )

if __name__ == "__main__":
    # Run the MCP server over standard input/output (stdio)
    mcp.run()