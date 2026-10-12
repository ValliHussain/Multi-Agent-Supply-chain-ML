# ml_model.py
import sqlite3
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from database import get_part_details

DB_NAME = "supply_chain.db"

def seed_historical_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM historical_shipments")
    if cursor.fetchone()[0] < 1000:
        cursor.execute("DELETE FROM historical_shipments")
        conn.commit()
        
        np.random.seed(42)
        n_samples = 1500
        
        congestion = np.random.uniform(1.0, 10.0, n_samples)
        weather = np.random.randint(1, 11, n_samples)
        reliability = np.random.uniform(0.1, 1.0, n_samples)
        
        delays = np.maximum(0, (congestion * 0.85) + (weather * 0.55) - (reliability * 3.5) + np.random.normal(0, 0.8, n_samples)).astype(int)
        cost_impacts = (delays * 1200) + ((1.0 - reliability) * 8500) + (congestion * 400) + np.random.normal(0, 300, n_samples)
        cost_impacts = np.maximum(150.0, cost_impacts)
        
        history_df = pd.DataFrame({
            'route_congestion': congestion,
            'weather_severity': weather,
            'supplier_reliability': reliability,
            'actual_delay_days': delays,
            'cost_impact': cost_impacts
        })
        history_df.to_sql('historical_shipments', conn, if_exists='append', index=False)
    conn.close()

def train_ml_models():
    seed_historical_data()
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT * FROM historical_shipments", conn)
    conn.close()
    
    X = df[['route_congestion', 'weather_severity', 'supplier_reliability']]
    
    delay_model = RandomForestRegressor(n_estimators=100, random_state=42)
    delay_model.fit(X, df['actual_delay_days'])
    
    cost_model = RandomForestRegressor(n_estimators=100, random_state=42)
    cost_model.fit(X, df['cost_impact'])
    
    return delay_model, cost_model

def predict_shipment_risk(route_congestion_index: float, weather_severity: int, supplier_reliability: float, part_name: str, order_quantity: int):
    delay_model, cost_model = train_ml_models()
    
    input_features = pd.DataFrame([[route_congestion_index, weather_severity, supplier_reliability]],
                                  columns=['route_congestion', 'weather_severity', 'supplier_reliability'])
    
    predicted_delay = int(round(delay_model.predict(input_features)[0]))
    base_cost = float(cost_model.predict(input_features)[0])
    
    # Fetch part specs (weight and unit cost) from database
    part_info = get_part_details(part_name)
    total_weight = order_quantity * part_info["unit_weight_kg"]
    
    # Advanced Cost Calculation: Factor in weight carrier surcharges + part inventory value tied up
    freight_surcharge = total_weight * route_congestion_index * 3.5  # Weight & congestion carrier fee
    inventory_holding_cost = predicted_delay * (order_quantity * part_info["unit_cost"] * 0.015) # Capital tied up cost
    
    adjusted_cost_impact = float(round(base_cost + freight_surcharge + inventory_holding_cost, 2))
    
    risk_score = min(100.0, max(0.0, (predicted_delay * 5) + ((1.0 - supplier_reliability) * 40) + (route_congestion_index * 2)))
    risk_score = round(risk_score, 1)
    
    status = "NORMAL_OPERATION"
    if risk_score > 70:
        status = "CRITICAL_DISRUPTION_PREDICTED"
    elif risk_score > 40:
        status = "MODERATE_DELAY_WARNING"
        
    return {
        "risk_score": risk_score,
        "predicted_delay_days": predicted_delay,
        "cost_impact": adjusted_cost_impact,
        "total_weight_kg": round(total_weight, 2),
        "category": part_info["category"],
        "status": status
    }