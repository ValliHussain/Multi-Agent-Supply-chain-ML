# guardrails.py
import re

def detect_prompt_injection(user_prompt: str) -> bool:
    """Scans incoming user queries for common jailbreak or prompt injection patterns."""
    injection_patterns = [
        r"ignore previous instructions",
        r"disregard all rules",
        r"drop table",
        r"delete from",
        r"system prompt",
        r"reveal passwords"
    ]
    prompt_lower = user_prompt.lower()
    for pattern in injection_patterns:
        if re.search(pattern, prompt_lower):
            return True
    return False

def sanitize_pii(text: str) -> str:
    """Masks potential sensitive codes, internal IDs, or mock credentials found in text."""
    # Mask potential token/password strings matching simple patterns
    masked_text = re.sub(r'password\s*=\s*[\'"][^\'"]+[\'"]', 'password=********', text, flags=re.IGNORECASE)
    return masked_text

def enforce_role_permission(user_role: str, requested_action: str) -> tuple[bool, str]:
    """Enforces Role-Based Access Control (RBAC) for sensitive supply chain actions."""
    high_impact_actions = ["approve", "delete", "modify_contract"]
    
    # Check if user is attempting a high-impact action
    is_high_impact = any(action in requested_action.lower() for action in high_impact_actions)
    
    if is_high_impact:
        # Only Directors or Managers are allowed
        authorized_roles = ["Supply Chain Director", "Procurement Manager"]
        if user_role not in authorized_roles:
            return False, f"❌ **Guardrail Block:** Role '{user_role}' is not authorized to execute high-impact procurement approvals. Director or Manager clearance required."
            
    return True, "Authorized"