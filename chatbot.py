# chatbot.py
import os
import time
import uuid
import sqlite3
import tempfile
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from typing import TypedDict, List

# --- COMPATIBILITY PATCH FOR DEPRECATED st.cache ---
if not hasattr(st, "cache"):
    st.cache = st.cache_resource

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

# Mapping & Forecasting Imports
import pydeck as pdk
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Cookie Manager for Persistent Sessions across Refreshes
from streamlit_cookies_manager import EncryptedCookieManager

# RAG & Document Processing Imports
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# Import existing backend modules & guardrails safely
from database import get_best_supplier, get_part_details, init_db
from route_service import get_realtime_telemetry
from ml_model import predict_shipment_risk
from guardrails import detect_prompt_injection, sanitize_pii, enforce_role_permission

# Ensure DB tables are initialized
init_db()

st.set_page_config(page_title="Enterprise Supply Chain Intelligence Platform", page_icon="🌐", layout="wide")

# --- Initialize Cookie Manager ---
cookies = EncryptedCookieManager(prefix="enterprise_supply_chain/", password="supply_chain_secret_cookie_key")
if not cookies.ready():
    st.stop()

# --- 1. Vector Store & RAG Initialization ---
PERSIST_DIRECTORY = "./chroma_db"

@st.cache_resource
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_vector_store():
    embeddings = get_embedding_model()
    return Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=embeddings)

def process_and_store_pdf(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        loader = PyPDFLoader(tmp_path)
        docs = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=60)
        chunks = text_splitter.split_documents(docs)

        vector_store = get_vector_store()
        vector_store.add_documents(chunks)
        
        os.unlink(tmp_path)
        return True, len(chunks)
    except Exception as e:
        return False, str(e)


# --- 2. Database Helper Functions for Sessions & Auth ---

def verify_user(username, password):
    conn = sqlite3.connect("supply_chain.db")
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username = ? AND password = ?", (username, password))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def register_user(username, password, role="Procurement Manager"):
    try:
        conn = sqlite3.connect("supply_chain.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def get_user_sessions(username):
    conn = sqlite3.connect("supply_chain.db")
    cursor = conn.cursor()
    cursor.execute("SELECT session_id, title, created_at FROM chat_sessions WHERE username = ? ORDER BY created_at DESC", (username,))
    rows = cursor.fetchall()
    conn.close()
    return [{"session_id": r[0], "title": r[1], "created_at": r[2]} for r in rows]

def create_new_session(username, title="Enterprise Supply Chain Hub"):
    session_id = str(uuid.uuid4())[:8]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("supply_chain.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_sessions (session_id, username, title, created_at) VALUES (?, ?, ?, ?)",
                   (session_id, username, title, created_at))
    conn.commit()
    conn.close()
    return session_id

def save_chat_message(session_id, username, role, content):
    conn = sqlite3.connect("supply_chain.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (session_id, username, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                   (session_id, username, role, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def load_chat_history(session_id):
    conn = sqlite3.connect("supply_chain.db")
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_history WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]


# --- 3. Persistent Authentication & Cookie Sync ---

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.user_role = ""

if not st.session_state.authenticated and cookies.get("authenticated") == "true":
    st.session_state.authenticated = True
    st.session_state.username = cookies.get("username", "")
    st.session_state.user_role = cookies.get("user_role", "")

if not st.session_state.authenticated:
    st.title("🔐 Enterprise Supply Chain Login & Security Gate")
    st.markdown("Please sign in or register to access the platform. Sessions persist securely across page refreshes.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Sign In")
        with st.form("login_form"):
            login_user = st.text_input("Username", value="admin")
            login_pass = st.text_input("Password", type="password", value="admin123")
            submit_login = st.form_submit_button("Login")
            if submit_login:
                role = verify_user(login_user, login_pass)
                if role:
                    st.session_state.authenticated = True
                    st.session_state.username = login_user
                    st.session_state.user_role = role
                    
                    cookies["authenticated"] = "true"
                    cookies["username"] = login_user
                    cookies["user_role"] = role
                    cookies.save()
                    
                    st.success(f"Welcome back, {login_user}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
    with col2:
        st.subheader("Register New Account")
        with st.form("register_form"):
            reg_user = st.text_input("Choose Username")
            reg_pass = st.text_input("Choose Password", type="password")
            reg_role = st.selectbox("Role", ["Procurement Manager", "Logistics Coordinator", "Supply Chain Director"])
            submit_reg = st.form_submit_button("Register")
            if submit_reg:
                if reg_user and reg_pass:
                    success = register_user(reg_user, reg_pass, reg_role)
                    if success:
                        st.success("Account created successfully! You can now log in.")
                    else:
                        st.error("Username already exists.")
                else:
                    st.warning("Please fill out all fields.")
    st.stop()


# --- 4. Multi-Session Sidebar & Controls ---

st.sidebar.title(f"👤 User: {st.session_state.username}")
st.sidebar.markdown(f"**Role:** `{st.session_state.user_role}`")
st.sidebar.markdown("---")

groq_api_key = os.environ.get("GROQ_API_KEY")
try:
    if not groq_api_key and "GROQ_API_KEY" in st.secrets:
        groq_api_key = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

if not groq_api_key:
    groq_api_key = st.sidebar.text_input("🔑 Enter Groq API Key", type="password")

st.sidebar.subheader("📁 Contract & Doc Intelligence")
uploaded_pdfs = st.sidebar.file_uploader("Upload Vendor MSAs / Bills of Lading (PDF)", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    if st.sidebar.button("📥 Process & Index Documents"):
        with st.spinner("Embedding documents into vector database..."):
            success_count = 0
            for pdf in uploaded_pdfs:
                success, info = process_and_store_pdf(pdf)
                if success:
                    success_count += 1
            st.sidebar.success(f"Successfully indexed {success_count} document(s) into ChromaDB!")

st.sidebar.markdown("---")
st.sidebar.subheader("💬 Chat Sessions")
user_sessions = get_user_sessions(st.session_state.username)
if not user_sessions:
    initial_sid = create_new_session(st.session_state.username, title="Supply Chain Intelligence Chat")
    user_sessions = get_user_sessions(st.session_state.username)

if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = user_sessions[0]["session_id"]

if st.sidebar.button("➕ Start New Chat", use_container_width=True):
    new_sid = create_new_session(st.session_state.username, title=f"Session {datetime.now().strftime('%b %d, %H:%M')}")
    st.session_state.current_session_id = new_sid
    st.rerun()

session_options = {f"{s['title']} ({s['created_at']})": s['session_id'] for s in user_sessions}
selected_label = st.sidebar.selectbox("Select Chat Thread", options=list(session_options.keys()))
new_sid_choice = session_options[selected_label]
if new_sid_choice != st.session_state.current_session_id:
    st.session_state.current_session_id = new_sid_choice
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("🌐 GIS Mapping, Time-Series Forecasting & Multi-Agent RAG Active")

if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.user_role = ""
    
    cookies["authenticated"] = "false"
    cookies["username"] = ""
    cookies["user_role"] = ""
    cookies.save()
    st.rerun()


# --- 5. RAG Retrieval & Advanced Tools ---

@tool
def query_uploaded_contracts(query: str) -> str:
    """Searches uploaded vendor agreements, MSAs, insurance certificates, and bills of lading in ChromaDB."""
    try:
        vector_store = get_vector_store()
        results = vector_store.similarity_search(query, k=2)
        if not results:
            return "No relevant information found in uploaded documents."
        context = "\n\n---\n\n".join([doc.page_content for doc in results])
        st.session_state.last_retrieved_chunks = context
        return f"Relevant Excerpts from Uploaded Contracts:\n{context}"
    except Exception as e:
        return f"Error querying vector database: {e}"


# --- 6. Rate-Limit Resilient Multi-Agent Network ---

def safe_llm_invoke(llm, messages, max_retries=3):
    for attempt in range(max_retries):
        try:
            return llm.invoke(messages)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit_exceeded" in error_str:
                if attempt < max_retries - 1:
                    time.sleep(6 * (attempt + 1))
                    continue
            raise e

class SupplyChainState(TypedDict):
    messages: List
    po_id: str
    rag_context: str
    bidding_data: str
    procurement_review: str
    risk_review: str
    finance_review: str
    final_output: str

def init_multi_agent_network(api_key: str):
    llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0, groq_api_key=api_key)
    workflow = StateGraph(SupplyChainState)

    def rag_agent_node(state: SupplyChainState):
        prompt_text = state["messages"][-1].content
        rag_data = query_uploaded_contracts.invoke({"query": prompt_text})
        po_id = "PO-2026-001"
        for word in prompt_text.split():
            if "PO-2026-" in word:
                po_id = word.strip(".,!?")
        return {"po_id": po_id, "rag_context": rag_data}

    def procurement_agent_node(state: SupplyChainState):
        po_id = state["po_id"]
        try:
            conn = sqlite3.connect("supply_chain.db")
            df = pd.read_sql("SELECT * FROM bidding_contracts WHERE po_id = ?", conn, params=(po_id,))
            conn.close()
            bids_str = df.to_string() if not df.empty else "No bids found."
        except Exception as e:
            bids_str = f"Error fetching bids: {e}"
            
        system_msg = SystemMessage(content="You are the Procurement Agent. Focus on cost efficiency and contract terms.")
        messages = [system_msg, HumanMessage(content=f"Analyze procurement bids for {po_id}:\n{bids_str}\n\nContract Excerpts:\n{state['rag_context']}")]
        response = safe_llm_invoke(llm, messages)
        return {"bidding_data": bids_str, "procurement_review": response.content}

    def risk_agent_node(state: SupplyChainState):
        po_id = state["po_id"]
        telemetry = get_realtime_telemetry("Bangalore, India", "Chennai, India")
        risk_pred = predict_shipment_risk(4.0, 2, 0.92, "Microcontroller Chip V2", 5000)
        
        system_msg = SystemMessage(content="You are the Risk Agent. Focus on delivery penalties, force majeure, and weather delays.")
        messages = [system_msg, HumanMessage(content=f"Evaluate risk for {po_id}. Telemetry: {telemetry}. ML Risk: {risk_pred.get('risk_score', 35)}/100.\nContract Excerpts:\n{state['rag_context']}")]
        response = safe_llm_invoke(llm, messages)
        return {"risk_review": response.content}

    def finance_agent_node(state: SupplyChainState):
        po_id = state["po_id"]
        system_msg = SystemMessage(content="You are the Finance Agent. Review payment terms and budget impact.")
        messages = [system_msg, HumanMessage(content=f"Review financial impact and payment terms for {po_id}.\nContract Excerpts:\n{state['rag_context']}")]
        response = safe_llm_invoke(llm, messages)
        return {"finance_review": response.content}

    def synthesizer_node(state: SupplyChainState):
        p_review = state.get("procurement_review", "")
        r_review = state.get("risk_review", "")
        f_review = state.get("finance_review", "")
        rag_info = state.get("rag_context", "")
        user_role = st.session_state.user_role
        
        system_msg = SystemMessage(content=f"You are the Lead Synthesizer Agent. User role is '{user_role}'. Synthesize reviews into an executive recommendation.")
        synthesis_prompt = f"Document Excerpts: {rag_info}\n\nProcurement: {p_review}\nRisk: {r_review}\nFinance: {f_review}\nProvide final recommendation."
        messages = [system_msg, HumanMessage(content=synthesis_prompt)]
        response = safe_llm_invoke(llm, messages)
        return {"final_output": response.content}

    workflow.add_node("rag_agent", rag_agent_node)
    workflow.add_node("procurement_agent", procurement_agent_node)
    workflow.add_node("risk_agent", risk_agent_node)
    workflow.add_node("finance_agent", finance_agent_node)
    workflow.add_node("synthesizer", synthesizer_node)

    workflow.add_edge(START, "rag_agent")
    workflow.add_edge("rag_agent", "procurement_agent")
    workflow.add_edge("procurement_agent", "risk_agent")
    workflow.add_edge("risk_agent", "finance_agent")
    workflow.add_edge("finance_agent", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()


# --- 7. Main Dashboard Interface with Tabs ---

st.title("🌐 Enterprise Supply Chain Intelligence Platform")
st.markdown(f"**Active Session:** `{st.session_state.current_session_id}` | **User Role:** `{st.session_state.user_role}`")

tab1, tab2, tab3 = st.tabs(["💬 Multi-Agent Chat & RAG", "🗺️ Interactive GIS Route Map", "📈 Time-Series Demand Forecasting"])

# --- TAB 1: Chat & RAG Interface ---
with tab1:
    current_sid = st.session_state.current_session_id
    session_messages = load_chat_history(current_sid)

    if not session_messages:
        initial_msg = f"Hello {st.session_state.username}! Multi-Agent RAG active. Ask questions about contracts, POs, or supplier bids."
        session_messages = [{"role": "assistant", "content": initial_msg}]
        save_chat_message(current_sid, st.session_state.username, "assistant", initial_msg)

    # Render message history
    for msg in session_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if "last_retrieved_chunks" in st.session_state and st.session_state.last_retrieved_chunks:
        with st.expander("🔍 Debug: Inspect Last RAG Retrieved Chunks"):
            st.text(st.session_state.last_retrieved_chunks)


# --- TAB 2: Interactive GIS Route Mapping (PyDeck) ---
with tab2:
    st.subheader("🗺️ Live Freight Transit & Telemetry GIS Map")
    st.markdown("Visualizing active freight corridors, live weather severity zones, and traffic congestion bottlenecks.")

    hubs = {
        "Bangalore (Origin Hub)": [77.5946, 12.9716],
        "Chennai (Destination Hub)": [80.2707, 13.0827],
        "Mumbai (Regional DC)": [72.8777, 19.0760],
        "Delhi (Central Hub)": [77.1025, 28.7041]
    }

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        origin_hub = st.selectbox("Select Origin Hub", list(hubs.keys()), index=0)
    with col_m2:
        dest_hub = st.selectbox("Select Destination Hub", list(hubs.keys()), index=1)

    orig_coords = hubs[origin_hub]
    dest_coords = hubs[dest_hub]

    arc_data = pd.DataFrame({
        "from_name": [origin_hub],
        "from_lon": [orig_coords[0]],
        "from_lat": [orig_coords[1]],
        "to_name": [dest_hub],
        "to_lon": [dest_coords[0]],
        "to_lat": [dest_coords[1]],
        "status": ["Active Transit"]
    })

    mid_lon = (orig_coords[0] + dest_coords[0]) / 2
    mid_lat = (orig_coords[1] + dest_coords[1]) / 2

    pin_data = pd.DataFrame({
        "name": [origin_hub, dest_hub, "Route Congestion Bottleneck", "Weather Severity Zone"],
        "lon": [orig_coords[0], dest_coords[0], mid_lon + 0.2, mid_lon - 0.3],
        "lat": [orig_coords[1], dest_coords[1], mid_lat + 0.1, mid_lat - 0.15],
        "type": ["Hub", "Hub", "Bottleneck", "Weather"],
        "color": [[0, 128, 255], [0, 255, 128], [255, 165, 0], [255, 0, 0]],
        "radius": [50000, 50000, 30000, 40000]
    })

    arc_layer = pdk.Layer(
        "ArcLayer",
        data=arc_data,
        get_source_position="[from_lon, from_lat]",
        get_target_position="[to_lon, to_lat]",
        get_source_color=[0, 128, 255],
        get_target_color=[0, 255, 128],
        get_width=5,
        pickable=True
    )

    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=pin_data,
        get_position="[lon, lat]",
        get_color="color",
        get_radius="radius",
        pickable=True,
        opacity=0.8
    )

    view_state = pdk.ViewState(
        longitude=mid_lon,
        latitude=mid_lat,
        zoom=6,
        pitch=40,
    )

    r = pdk.Deck(
        layers=[arc_layer, scatter_layer],
        initial_view_state=view_state,
        tooltip={"text": "{name}\nType: {type}"}
    )

    st.pydeck_chart(r)
    st.info("💡 **Legend:** 🔵 Origin Hub | 🟢 Destination Hub | 🟠 Traffic Congestion Bottleneck | 🔴 Severe Weather Zone")


# --- TAB 3: Time-Series Demand Forecasting ---
with tab3:
    st.subheader("📈 Time-Series Demand Forecasting & Preemptive POs")
    st.markdown("Predicting upcoming seasonal spikes using Exponential Smoothing to suggest automated purchase orders weeks before stockouts.")

    part_selected = st.selectbox("Select Component for Forecasting", ["Microcontroller Chip V2", "High-Performance Sensor X1", "Industrial Servo Motor"])

    np.random.seed(42)
    dates = pd.date_range(start="2025-01-01", end="2026-09-01", freq="MS")
    base_demand = 4500 if part_selected == "Microcontroller Chip V2" else 2800
    seasonal_spike = np.sin(np.linspace(0, 3 * np.pi, len(dates))) * 800
    noise = np.random.normal(0, 200, len(dates))
    historical_demand = np.clip(base_demand + seasonal_spike + noise, 1000, 8000).astype(int)

    df_forecast = pd.DataFrame({"ds": dates, "demand": historical_demand})
    df_forecast.set_index("ds", inplace=True)

    model = ExponentialSmoothing(df_forecast["demand"], trend="add", seasonal="add", seasonal_periods=6).fit()
    forecast_values = model.forecast(4)

    future_dates = pd.date_range(start="2026-10-01", periods=4, freq="MS")
    df_future = pd.DataFrame({"Forecasted Demand": forecast_values}, index=future_dates)

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown("### Historical Consumption")
        st.line_chart(df_forecast)
    with col_f2:
        st.markdown("### 4-Month AI Demand Forecast")
        st.line_chart(df_future)

    st.markdown("---")
    st.subheader("📋 Preemptive Purchase Order Recommendation")
    next_month_forecast = int(forecast_values.iloc[0])
    recommended_buffer = int(next_month_forecast * 0.25)
    
    st.warning(f"⚠️ **Stockout Risk Alert:** Projected demand for **{part_selected}** next month is **{next_month_forecast:,} units**. Recommended safety buffer: **{recommended_buffer:,} units**.")
    
    if st.button("🚀 Generate Preemptive Purchase Order"):
        new_po_id = f"PO-2026-{np.random.randint(100, 999)}"
        st.success(f"✅ Successfully created preemptive Purchase Order `{new_po_id}` for {next_month_forecast + recommended_buffer:,} units of {part_selected} to prevent stockouts!")


# --- MAIN LEVEL STICKY CHAT INPUT ---
# Rendered outside tabs so it remains natively pinned to the bottom of the viewport
if prompt := st.chat_input("Ask about supplier contracts, penalties, or purchase orders..."):
    current_sid = st.session_state.current_session_id

    if not groq_api_key:
        st.error("⚠️ Please enter your Groq API Key in the sidebar.")
        st.stop()

    if detect_prompt_injection(prompt):
        warning_msg = "🚨 Security Guardrail Triggered: Injection pattern detected."
        save_chat_message(current_sid, st.session_state.username, "user", prompt)
        save_chat_message(current_sid, st.session_state.username, "assistant", warning_msg)
        st.error(warning_msg)
        st.rerun()

    is_allowed, rbac_message = enforce_role_permission(st.session_state.user_role, prompt)
    if not is_allowed:
        save_chat_message(current_sid, st.session_state.username, "user", prompt)
        save_chat_message(current_sid, st.session_state.username, "assistant", rbac_message)
        st.warning(rbac_message)
        st.rerun()

    sanitized_prompt = sanitize_pii(prompt)
    save_chat_message(current_sid, st.session_state.username, "user", sanitized_prompt)

    with tab1:
        with st.chat_message("user"):
            st.markdown(sanitized_prompt)

        with st.chat_message("assistant"):
            with st.status("📁 Running Multi-Agent RAG Pipeline...", expanded=True) as status:
                st.write("🔍 Querying ChromaDB vector store...")
                st.write("🛒 Procurement, Risk & Finance agents analyzing...")
                st.write("🧠 Synthesizing final recommendation...")
                
                try:
                    network = init_multi_agent_network(groq_api_key)
                    initial_state = {"messages": [HumanMessage(content=sanitized_prompt)]}
                    result = network.invoke(initial_state)
                    
                    ai_response = sanitize_pii(result["final_output"])
                    status.update(label="✅ Review Complete!", state="complete", expanded=False)
                    st.markdown(ai_response)
                    save_chat_message(current_sid, st.session_state.username, "assistant", ai_response)
                except Exception as e:
                    err = f"Execution error: {e}"
                    st.error(err)
                    save_chat_message(current_sid, st.session_state.username, "assistant", err)
    st.rerun()