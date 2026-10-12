# seed_data.py
import sqlite3
import random
from datetime import datetime, timedelta

DB_NAME = "supply_chain.db"

def populate_massive_mock_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("Ensuring all database tables exist...")
    
    # 1. Evaluations audit log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id TEXT,
            part_name TEXT,
            order_quantity INTEGER,
            total_weight_kg REAL,
            route_congestion REAL,
            weather_severity INTEGER,
            supplier_reliability REAL,
            risk_score REAL,
            delay_days INTEGER,
            cost_impact REAL,
            status TEXT,
            backup_supplier_info TEXT,
            mitigation_plan TEXT,
            timestamp TEXT
        )
    ''')
    
    # 2. Historical training table for ML model
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historical_shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_congestion REAL,
            weather_severity INTEGER,
            supplier_reliability REAL,
            actual_delay_days INTEGER,
            cost_impact REAL
        )
    ''')
    
    # 3. Parts catalog table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_name TEXT UNIQUE,
            category TEXT,
            unit_weight_kg REAL,
            unit_cost REAL
        )
    ''')
    
    # 4. Suppliers inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT,
            category TEXT,
            stock_available INTEGER,
            lead_time_days INTEGER,
            reliability_score REAL
        )
    ''')

    # 5. Bidding contracts table for procurement
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bidding_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id TEXT,
            supplier_name TEXT,
            origin TEXT,
            destination TEXT,
            bid_cost REAL,
            carbon_emission_kg REAL,
            transit_days INTEGER,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    
    categories = ["electronics", "raw_materials", "packaging", "assembly", "chemicals", "hydraulics"]

    # --- 1. GENERATE 1,200+ PARTS ---
    print("Generating 1,200+ parts catalog...")
    part_adjectives = ["High-Density", "Ultra", "Precision", "Industrial", "Heavy-Duty", "Compact", "Advanced", "Modular", "Smart", "Reinforced"]
    part_nouns = ["Circuit Board", "Valve Assembly", "Steel Alloy Rod", "Sensor Module", "Connector Pin", "Lithium Cell", "Cooling Heatsink", "Actuator Unit", "Bearing Assembly", "Gasket Seal"]
    
    parts_set = set()
    while len(parts_set) < 1200:
        p_name = f"{random.choice(part_adjectives)} {random.choice(part_nouns)} #{random.randint(10000, 99999)}"
        cat = random.choice(categories)
        weight = round(random.uniform(0.01, 25.0), 2)
        cost = round(random.uniform(5.0, 500.0), 2)
        parts_set.add((p_name, cat, weight, cost))
        
    cursor.executemany("INSERT OR IGNORE INTO parts (part_name, category, unit_weight_kg, unit_cost) VALUES (?, ?, ?, ?)", list(parts_set))
    
    # --- 2. GENERATE 1,200+ SUPPLIERS ---
    print("Generating 1,200+ suppliers inventory...")
    sup_prefixes = ["Apex", "Global", "Nova", "Titan", "Vanguard", "Delta", "Omni", "Prime", "Summit", "Nexus", "Pioneer", "Zenith"]
    sup_suffixes = ["Logistics", "Components", "Industries", "Foundry", "Supply Co.", "Materials Group", "Enterprise", "Global Sourcing", "Distribution Hub"]
    
    suppliers_set = set()
    while len(suppliers_set) < 1200:
        s_name = f"{random.choice(sup_prefixes)} {random.choice(sup_suffixes)} {random.randint(100, 9999)}"
        cat = random.choice(categories)
        stock = random.randint(1000, 100000)
        lead_time = random.randint(1, 14)
        reliability = round(random.uniform(0.70, 0.99), 2)
        suppliers_set.add((s_name, cat, stock, lead_time, reliability))
        
    cursor.executemany("INSERT OR IGNORE INTO suppliers (supplier_name, category, stock_available, lead_time_days, reliability_score) VALUES (?, ?, ?, ?, ?)", list(suppliers_set))

    # --- 3. GENERATE 1,200+ BIDDING CONTRACTS ---
    print("Generating 1,200+ procurement bidding contracts across hundreds of POs...")
    cities = [
        ("Bangalore, India", "Chennai, India", 350),
        ("Mumbai, India", "Delhi, India", 1400),
        ("Hyderabad, India", "Pune, India", 560),
        ("Kolkata, India", "Bangalore, India", 1550),
        ("Ahmedabad, India", "Mumbai, India", 520),
        ("Chennai, India", "Kochi, India", 700),
        ("Pune, India", "Bengaluru, India", 850),
        ("Delhi, India", "Kolkata, India", 1300)
    ]
    carrier_types = [
        ("Express Roadways", 0.062, 1.0),
        ("GreenLine Rail Corridors", 0.022, 1.8),
        ("AirFreight Express Cargo", 0.602, 0.4),
        ("EcoCargo Multimodal", 0.035, 1.4)
    ]
    
    bids = []
    for i in range(1, 320): # 319 POs * 4 carrier bids = ~1,276 contracts
        po_id = f"PO-2026-{i:04d}"
        origin, dest, base_dist = random.choice(cities)
        for carrier_name, carbon_factor, time_multiplier in carrier_types:
            base_cost = random.randint(8000, 65000)
            weight_dummy = random.randint(1000, 15000)
            carbon = round((weight_dummy / 1000.0) * base_dist * carbon_factor, 1)
            transit_days = max(1, int((base_dist / 75.0 / 24.0) * time_multiplier * random.uniform(0.8, 1.3)))
            status = random.choice(['Pending', 'Pending', 'Pending', 'Rejected'])
            bids.append((po_id, f"{carrier_name} ({origin.split(',')[0]})", origin, dest, float(base_cost), carbon, transit_days, status))
            
    cursor.executemany("INSERT INTO bidding_contracts (po_id, supplier_name, origin, destination, bid_cost, carbon_emission_kg, transit_days, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", bids)

    # --- 4. GENERATE 1,200+ HISTORICAL SHIPMENTS ---
    print("Generating 1,200+ historical shipment training logs...")
    history = []
    for _ in range(1200):
        rc = round(random.uniform(1.0, 10.0), 1)
        ws = random.randint(1, 10)
        sr = round(random.uniform(0.40, 1.0), 2)
        delay = int(rc * 0.3 + ws * 0.4 + (1.0 - sr) * 5 + random.uniform(-1, 3))
        cost = round(delay * random.uniform(400, 2000) + random.uniform(100, 5000), 2)
        history.append((rc, ws, sr, max(0, delay), max(0.0, cost)))
        
    cursor.executemany("INSERT INTO historical_shipments (route_congestion, weather_severity, supplier_reliability, actual_delay_days, cost_impact) VALUES (?, ?, ?, ?, ?)", history)

    # --- 5. GENERATE 1,200+ EVALUATION AUDIT LOGS ---
    print("Generating 1,200+ evaluation audit logs...")
    evals = []
    part_names_list = [row[0] for row in parts_set]
    for i in range(1200):
        shipment_id = f"SH-2026-{i:04d}"
        p_name = random.choice(part_names_list)
        qty = random.randint(100, 20000)
        weight = round(qty * random.uniform(0.1, 5.0), 2)
        rc = round(random.uniform(1.0, 9.5), 1)
        ws = random.randint(1, 10)
        sr = round(random.uniform(0.5, 1.0), 2)
        risk = round(rc * 4.5 + ws * 3.2 + (1.0 - sr) * 20 + random.uniform(-5, 5), 1)
        risk = min(100.0, max(0.0, risk))
        delay = int(risk / 15.0)
        cost_imp = round(risk * 350.0 + random.uniform(500, 10000), 2)
        status = "Normal" if risk < 50 else ("Warning - Potential Delay" if risk < 80 else "Critical - Action Required")
        backup = "Apex Microparts | Status: Sufficient Stock"
        plan = "Standard route execution." if risk < 50 else "Dynamic rerouting and backup supplier engagement initiated."
        ts = (datetime.now() - timedelta(days=random.randint(0, 180), hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M:%S")
        
        evals.append((shipment_id, p_name, qty, weight, rc, ws, sr, risk, delay, cost_imp, status, backup, plan, ts))
        
    cursor.executemany('''
        INSERT INTO evaluations (shipment_id, part_name, order_quantity, total_weight_kg, route_congestion, weather_severity, supplier_reliability, risk_score, delay_days, cost_impact, status, backup_supplier_info, mitigation_plan, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', evals)

    conn.commit()
    conn.close()
    print("✨ Massive Data Injection Complete! Every table now contains over 1,000+ records.")

if __name__ == "__main__":
    populate_massive_mock_data()