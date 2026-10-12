# dashboard.py
import streamlit as st
import requests
import pandas as pd
import sqlite3

st.set_page_config(page_title="Autonomous Supply Chain Telemetry", page_icon="🚢", layout="wide")

API_URL = "http://localhost:8000"
try:
    if "API_URL" in st.secrets:
        API_URL = st.secrets["API_URL"]
except Exception:
    pass

st.title("🚢 Autonomous Supply Chain Telemetry & Live Routing Engine")
st.markdown("Enter shipment origin, destination, and part details. The system automatically queries live weather and traffic routing APIs to compute ML risk scores.")

tab1, tab2 = st.tabs(["🚀 Live Route Simulation", "📊 Historical Audit Logs"])

with tab1:
    st.subheader("Live Telemetry & Shipment Parameters")
    
    try:
        conn = sqlite3.connect("supply_chain.db")
        parts_df = pd.read_sql("SELECT part_name FROM parts", conn)
        conn.close()
        part_options = parts_df['part_name'].tolist() if not parts_df.empty else ["Microcontroller Chip V2"]
    except Exception:
        part_options = ["Microcontroller Chip V2"]

    with st.form("shipment_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            shipment_id = st.text_input("Shipment ID", value="SH-2026-LIVE")
        with c2:
            origin = st.text_input("Origin City / Port", value="Bangalore, India")
        with c3:
            destination = st.text_input("Destination City / Port", value="Chennai, India")
            
        st.markdown("---")
        c4, c5, c6 = st.columns(3)
        with c4:
            part_name = st.selectbox("Select Part", part_options)
        with c5:
            order_quantity = st.number_input("Order Quantity", min_value=10, max_value=50000, value=2000, step=100)
        with c6:
            supplier_reliability = st.slider("Supplier Base Reliability", 0.0, 1.0, 0.85)
        
        submitted = st.form_submit_button("Fetch Live Weather/Traffic & Evaluate Risk")
        
        if submitted:
            with st.spinner("Connecting to live weather and routing telemetry APIs, running ML models, and executing agents..."):
                payload = {
                    "shipment_id": shipment_id,
                    "origin": origin,
                    "destination": destination,
                    "part_name": part_name,
                    "order_quantity": order_quantity,
                    "supplier_reliability": supplier_reliability
                }
                try:
                    response = requests.post(f"{API_URL}/evaluate-shipment", json=payload)
                    if response.status_code == 200:
                        res = response.json()
                        st.success("Telemetry fetched and evaluation complete!")
                        
                        # Live telemetry metrics display
                        st.markdown(f"### 🌐 Live Telemetry Feed (`{origin}` ➔ `{destination}`)")
                        t1, t2 = st.columns(2)
                        t1.metric("Live Route Congestion Index", f"{res.get('route_congestion', 0)} / 10")
                        t2.metric("Live Destination Weather Severity", f"{res.get('weather_severity', 0)} / 10")
                        
                        st.markdown("### 📈 ML Impact Predictions")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Risk Score", f"{res.get('risk_score')}/100")
                        m2.metric("Predicted Delay", f"{res.get('delay_days')} Days")
                        m3.metric("Freight Weight", f"{res.get('total_weight_kg', 0):,.2f} kg")
                        m4.metric("Cost Impact", f"${res.get('cost_impact', 0):,.2f}")
                        
                        st.info(f"**Status:** {res.get('status')}")
                        
                        st.markdown("### 📋 Sourcing & Inventory Stock Verification")
                        st.info(res.get('backup_supplier_info'))
                        
                        st.markdown("### 📑 Autonomous Mitigation Plan")
                        st.markdown(res.get('mitigation_plan'))
                    else:
                        st.error(f"API Error: {response.text}")
                except Exception as e:
                    st.error(f"Could not connect to backend at `{API_URL}`: {e}")

with tab2:
    st.subheader("Database Audit Trail")
    if st.button("🔄 Refresh Logs"):
        st.rerun()
        
    try:
        conn = sqlite3.connect("supply_chain.db")
        df = pd.read_sql("SELECT * FROM evaluations ORDER BY id DESC", conn)
        conn.close()
        
        if not df.empty:
            display_cols = [c for c in ['id', 'timestamp', 'shipment_id', 'part_name', 'order_quantity', 'route_congestion', 'weather_severity', 'risk_score', 'delay_days', 'cost_impact', 'status'] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True)
        else:
            st.info("No evaluations logged yet.")
    except Exception as e:
        st.warning(f"Database not initialized yet: {e}")