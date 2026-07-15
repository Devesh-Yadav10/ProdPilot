import os
import json
from dotenv import load_dotenv

from agents.risk_agent import assess_risk

load_dotenv()

# We know the API key is set, but we are out of quota, so we expect the fallback to be used.
test_findings = [
    {'file': 'orders.py', 'line': 10, 'pattern_type': 'nested_query', 'nesting_depth': 2, 'snippet': 'product = Product.query.get(item.product_id)'}
]
test_metrics = {
    'avg_orders_per_user': 5,
    'avg_items_per_order': 3,
    'connection_pool_size': 20,
    'avg_query_time_ms': 5,
    'peak_concurrent_users': 1000,
    'max_pool_utilization_pct': 80,
    'avg_request_duration_seconds': 0.5,
}
test_impact = {
    'projected_query_count': 15,
    'projected_qps': 30000.0,
    'pool_utilization_pct': 750.0,
    'threshold_breached': True,
    'threshold_details': {'max_pool_utilization_pct': 80, 'pool_size': 20},
}

print("Testing Risk Agent with API key set (expecting fallback due to quota)...")
result = assess_risk(test_findings, test_impact)
print("Result:")
print(json.dumps(result, indent=2))

# Check that we got a fallback result (we can check for the presence of the fallback string in the risk_summary)
if 'Deterministic analysis' in result.get('reasoning', ''):
    print("\nSUCCESS: Fell back to deterministic assessment as expected due to quota/error.")
else:
    print("\nWARNING: Did not get the expected fallback reasoning. Might have used LLM (if quota available) or an error.")
