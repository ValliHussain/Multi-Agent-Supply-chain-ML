# database.py
import sqlite3
from datetime import datetime

DB_NAME = "supply_chain.db"

def init_db():
    """Initializes SQLite database tables including multi-session chat threads and user authentication."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
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
    
    # 4. Suppliers inventory catalog table
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

    # 5. Bidding contracts table for procurement optimization
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

    # 6. Users table for authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'Procurement Manager'
        )
    ''')

    # 7. Chat sessions table (Enables multiple chat threads per user)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            username TEXT,
            title TEXT,
            created_at TEXT
        )
    ''')

    # 8. Chat history table linked to session_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            username TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )
    ''')
    
    # Seed default parts catalog if empty
    cursor.execute("SELECT COUNT(*) FROM parts")
    if cursor.fetchone()[0] == 0:
        default_parts = [
            ("Microcontroller Chip V2", "electronics", 0.15, 45.00),
            ("OLED Display Module", "electronics", 0.35, 28.00),
            ("High-Tensile Steel Rod", "raw_materials", 5.20, 12.50),
            ("Aluminum Extrusion Bar", "raw_materials", 3.80, 19.00)
        ]
        cursor.executemany('''
            INSERT INTO parts (part_name, category, unit_weight_kg, unit_cost)
            VALUES (?, ?, ?, ?)
        ''', default_parts)
        
    # Seed default suppliers if empty
    cursor.execute("SELECT COUNT(*) FROM suppliers")
    if cursor.fetchone()[0] == 0:
        default_suppliers = [
            ("Apex Microparts", "electronics", 5400, 3, 0.92),
            ("Nova Tech Components", "electronics", 8200, 2, 0.95),
            ("Vanguard Logistics & Metals", "raw_materials", 12000, 5, 0.88),
            ("Delta Industrial Supplies", "raw_materials", 15000, 4, 0.85)
        ]
        cursor.executemany('''
            INSERT INTO suppliers (supplier_name, category, stock_available, lead_time_days, reliability_score)
            VALUES (?, ?, ?, ?, ?)
        ''', default_suppliers)

    # Seed default procurement bidding contracts if empty
    cursor.execute("SELECT COUNT(*) FROM bidding_contracts")
    if cursor.fetchone()[0] == 0:
        default_bids = [
            ("PO-2026-001", "Apex Microparts (Road Express)", "Bangalore, India", "Chennai, India", 14200.0, 185.5, 2),
            ("PO-2026-001", "GreenLine Logistics (Rail/Electric)", "Bangalore, India", "Chennai, India", 15500.0, 72.0, 4),
            ("PO-2026-001", "SwiftAir Freight (Air Cargo)", "Bangalore, India", "Chennai, India", 24000.0, 650.0, 1),
            ("PO-2026-002", "Vanguard Heavy Haul", "Mumbai, India", "Delhi, India", 38000.0, 1420.0, 5),
            ("PO-2026-002", "EcoFreight Rail Corridors", "Mumbai, India", "Delhi, India", 34500.0, 490.0, 7),
            ("PO-2026-002", "Titan Express Roadways", "Mumbai, India", "Delhi, India", 41000.0, 1350.0, 4)
        ]
        cursor.executemany('''
            INSERT INTO bidding_contracts (po_id, supplier_name, origin, destination, bid_cost, carbon_emission_kg, transit_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
        ''', default_bids)

    # Seed default admin user if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", 
                       ("admin", "admin123", "Supply Chain Director"))
        
    conn.commit()
    conn.close()

def get_part_details(part_name: str):
    """Retrieves weight and unit cost for a specific part."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT category, unit_weight_kg, unit_cost FROM parts WHERE part_name = ?", (part_name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"category": row[0], "unit_weight_kg": row[1], "unit_cost": row[2]}
    return {"category": "electronics", "unit_weight_kg": 0.2, "unit_cost": 30.0}

def get_best_supplier(category: str, required_qty: int):
    """Queries SQLite to find a backup supplier with enough stock for the category."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT supplier_name, stock_available, lead_time_days, reliability_score 
        FROM suppliers 
        WHERE category = ? AND stock_available >= ? 
        ORDER BY lead_time_days ASC, stock_available DESC 
        LIMIT 1
    ''', (category, required_qty))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute('''
            SELECT supplier_name, stock_available, lead_time_days, reliability_score 
            FROM suppliers WHERE category = ? ORDER BY stock_available DESC LIMIT 1
        ''', (category,))
        row = cursor.fetchone()
        
    conn.close()
    
    if row:
        status_note = "Sufficient Stock" if row[1] >= required_qty else "⚠️ Partial Stock Warning"
        return f"{row[0]} | Status: {status_note} (Available: {row[1]:,} units for required {required_qty:,}, Lead Time: {row[2]} days)"
    return "Standard backup vendor on standby."

def log_evaluation(data: dict):
    """Saves evaluation audit logs including part details, weight, and cost impact."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO evaluations (
            shipment_id, part_name, order_quantity, total_weight_kg,
            route_congestion, weather_severity, supplier_reliability, 
            risk_score, delay_days, cost_impact, status, 
            backup_supplier_info, mitigation_plan, timestamp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get("shipment_id"),
        data.get("part_name"),
        data.get("order_quantity"),
        data.get("total_weight_kg"),
        data.get("route_congestion"),
        data.get("weather_severity"),
        data.get("supplier_reliability"),
        data.get("risk_score"),
        data.get("delay_days"),
        data.get("cost_impact"),
        data.get("status"),
        data.get("backup_supplier_info"),
        data.get("mitigation_plan"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()