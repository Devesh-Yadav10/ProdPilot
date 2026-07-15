import pytest
import sys
sys.path.insert(0, r'C:\Users\deves\pr-risk-agent')

from agents.risk_agent import assess_risk, _fallback_assessment
from agents.recommendation_agent import suggest_fix, _fallback_recommendation
from agents.impact_agent import assess_business_impact, _fallback_impact


class TestRiskAgent:
    '''Tests for the Risk Agent (LLM-based).'''

    def test_fallback_assessment_threshold_breached(self):
        '''Test fallback when threshold is breached.'''
        findings = [
            {'file': 'test.py', 'line': 3, 'pattern_type': 'nested_query', 'nesting_depth': 2}
        ]
        impact = {
            'projected_query_count': 15,
            'projected_qps': 30000.0,
            'pool_utilization_pct': 750.0,
            'threshold_breached': True,
        }

        result = _fallback_assessment(findings, impact)

        assert result['threshold_breached'] is True
        assert result['severity'] == 'critical'
        assert '750' in result['risk_summary']
        assert 'BREACHES' in result['risk_summary']
        assert len(result['key_factors']) >= 3

    def test_fallback_assessment_high_not_critical(self):
        '''Test fallback with high but not critical utilization.'''
        findings = [{'nesting_depth': 1}]
        impact = {
            'projected_query_count': 5,
            'projected_qps': 10000.0,
            'pool_utilization_pct': 250.0,
            'threshold_breached': True,
        }

        result = _fallback_assessment(findings, impact)

        assert result['severity'] == 'high'

    def test_fallback_assessment_medium(self):
        '''Test fallback with medium utilization.'''
        findings = [{'nesting_depth': 1}]
        impact = {
            'projected_query_count': 2,
            'projected_qps': 100.0,
            'pool_utilization_pct': 150.0,
            'threshold_breached': True,
        }

        result = _fallback_assessment(findings, impact)

        assert result['severity'] == 'medium'

    def test_fallback_assessment_low_no_breach(self):
        '''Test fallback when threshold not breached.'''
        findings = [{'nesting_depth': 1}]
        impact = {
            'projected_query_count': 1,
            'projected_qps': 10.0,
            'pool_utilization_pct': 50.0,
            'threshold_breached': False,
        }

        result = _fallback_assessment(findings, impact)

        assert result['severity'] == 'low'
        assert result['threshold_breached'] is False
        assert 'within' in result['risk_summary']

    def test_assess_risk_structure(self):
        '''Test that assess_risk returns correct structure.'''
        findings = [{'file': 'test.py', 'line': 3, 'pattern_type': 'nested_query', 'nesting_depth': 2}]
        metrics = {
            'avg_orders_per_user': 5,
            'avg_items_per_order': 3,
            'connection_pool_size': 20,
            'avg_query_time_ms': 5,
            'peak_concurrent_users': 1000,
            'max_pool_utilization_pct': 80,
            'avg_request_duration_seconds': 0.5,
        }
        impact = {
            'projected_query_count': 15,
            'projected_qps': 30000.0,
            'pool_utilization_pct': 750.0,
            'threshold_breached': True,
        }

        result = assess_risk(findings, metrics, impact)

        # Check structure
        assert 'severity' in result
        assert 'threshold_breached' in result
        assert 'risk_summary' in result
        assert 'reasoning' in result
        assert 'key_factors' in result

        # Check types
        assert isinstance(result['severity'], str)
        assert isinstance(result['threshold_breached'], bool)
        assert isinstance(result['risk_summary'], str)
        assert isinstance(result['reasoning'], str)
        assert isinstance(result['key_factors'], list)
        assert len(result['key_factors']) > 0

    def test_fallback_includes_all_required_keys(self):
        '''Test fallback includes all required fields.'''
        findings = [{'nesting_depth': 2}]
        impact = {
            'projected_query_count': 15,
            'projected_qps': 30000.0,
            'pool_utilization_pct': 750.0,
            'threshold_breached': True,
        }

        result = _fallback_assessment(findings, impact)

        required_keys = ['severity', 'threshold_breached', 'risk_summary', 'reasoning', 'key_factors']
        for key in required_keys:
            assert key in result, f'Missing key: {key}'


class TestRecommendationAgent:
    '''Tests for the Recommendation Agent (LLM-based).'''

    def test_fallback_recommendation_orm_pattern(self):
        '''Test fallback for SQLAlchemy/Django ORM pattern.'''
        finding = {
            'file': 'orders.py',
            'line': 10,
            'pattern_type': 'nested_query',
            'nesting_depth': 2,
            'snippet': 'product = Product.query.get(item.product_id)',
        }

        result = _fallback_recommendation(finding)

        assert 'suggested_fix' in result
        assert 'fix_code_snippet' in result
        assert 'explanation' in result
        assert 'confidence' in result
        assert result['confidence'] > 0.5
        assert 'joinedload' in result['fix_code_snippet'] or 'prefetch' in result['fix_code_snippet'].lower()

    def test_fallback_recommendation_cursor_execute(self):
        '''Test fallback for raw cursor.execute pattern.'''
        finding = {
            'file': 'repo.py',
            'line': 5,
            'pattern_type': 'nested_query',
            'nesting_depth': 1,
            'snippet': 'cursor.execute("SELECT * FROM products WHERE id = %s", (item_id,))',
        }

        result = _fallback_recommendation(finding)

        assert result['confidence'] >= 0.5
        assert 'IN clause' in result['suggested_fix'] or 'batch' in result['explanation'].lower()

    def test_fallback_recommendation_generic(self):
        '''Test fallback for unknown pattern.'''
        finding = {
            'file': 'unknown.py',
            'line': 1,
            'pattern_type': 'nested_query',
            'nesting_depth': 1,
            'snippet': 'some.unknown.pattern()',
        }

        result = _fallback_recommendation(finding)

        assert result['confidence'] >= 0.1
        assert len(result['suggested_fix']) > 10
        assert len(result['fix_code_snippet']) > 10

    def test_suggest_fix_structure(self):
        '''Test that suggest_fix returns correct structure.'''
        risk_summary = '2 nested query patterns detected (max depth: 2). Projected pool utilization: 750.0% (BREACHES threshold).'
        finding = {
            'file': 'orders.py',
            'line': 10,
            'pattern_type': 'nested_query',
            'nesting_depth': 2,
            'snippet': 'product = Product.query.get(item.product_id)',
        }
        file_content = 'from models import Order, Item, Product\n\ndef get_user_products(user):\n    for order in user.orders:\n        for item in order.items:\n            product = Product.query.get(item.product_id)\n            print(product.name)'

        result = suggest_fix(risk_summary, finding, file_content)

        required_keys = ['suggested_fix', 'fix_code_snippet', 'explanation', 'confidence']
        for key in required_keys:
            assert key in result, f'Missing key: {key}'

        assert isinstance(result['suggested_fix'], str)
        assert isinstance(result['fix_code_snippet'], str)
        assert isinstance(result['explanation'], str)
        assert isinstance(result['confidence'], (int, float))
        assert 0 <= result['confidence'] <= 1


class TestImpactAgent:
    '''Tests for the Business Impact Agent (LLM-based).'''

    def test_fallback_impact_critical_breach(self):
        '''Test fallback for critical severity with breach.'''
        risk_summary = ('2 nested query patterns detected (max depth: 2). '
                       'Projected pool utilization: 750.0% (BREACHES threshold). '
                       'Projected QPS: 30000.0. Severity: critical.')

        result = _fallback_impact(risk_summary)

        assert 'user_facing_impact' in result
        assert 'cost_estimate' in result
        assert 'narrative' in result
        assert 'timeout' in result['user_facing_impact'].lower()
        assert '' in result['cost_estimate'] or '' in result['cost_estimate']
        assert 'deploy' in result['narrative'].lower()
        assert '->' in result['narrative']

    def test_fallback_impact_high_breach(self):
        '''Test fallback for high severity with breach.'''
        risk_summary = ('1 nested query patterns detected (max depth: 1). '
                       'Projected pool utilization: 250.0% (BREACHES threshold). '
                       'Projected QPS: 10000.0. Severity: high.')

        result = _fallback_impact(risk_summary)

        assert 'slow' in result['user_facing_impact'].lower() or 'latency' in result['user_facing_impact'].lower()
        assert '' in result['cost_estimate'] or '' in result['cost_estimate']
        assert 'deploy' in result['narrative'].lower()

    def test_fallback_impact_no_breach(self):
        '''Test fallback when threshold not breached.'''
        risk_summary = ('1 nested query patterns detected (max depth: 1). '
                       'Projected pool utilization: 50.0% (within threshold). '
                       'Projected QPS: 10.0. Severity: low.')

        result = _fallback_impact(risk_summary)

        assert 'no user-facing impact' in result['user_facing_impact'].lower() or 'no user' in result['user_facing_impact'].lower()
        assert '' in result['cost_estimate'] or '0' in result['cost_estimate']
        assert 'deploy' in result['narrative'].lower()
        assert 'headroom' in result['narrative'].lower()

    def test_assess_business_impact_structure(self):
        '''Test that assess_business_impact returns correct structure.'''
        risk_summary = ('2 nested query patterns detected (max depth: 2). '
                       'Projected pool utilization: 750.0% (BREACHES threshold). '
                       'Projected QPS: 30000.0. Severity: critical.')

        result = assess_business_impact(risk_summary)

        required_keys = ['user_facing_impact', 'cost_estimate', 'narrative']
        for key in required_keys:
            assert key in result, f'Missing key: {key}'

        assert isinstance(result['user_facing_impact'], str)
        assert isinstance(result['cost_estimate'], str)
        assert isinstance(result['narrative'], str)
        assert len(result['narrative']) > 50  # Should be a substantial narrative

    def test_narrative_contains_causal_chain(self):
        '''Test that narrative follows deploy -> traffic -> queries -> saturation -> latency -> impact format.'''
        risk_summary = ('2 nested query patterns detected (max depth: 2). '
                       'Projected pool utilization: 750.0% (BREACHES threshold). '
                       'Projected QPS: 30000.0. Severity: critical.')

        result = _fallback_impact(risk_summary)
        narrative = result['narrative'].lower()

        # Check for causal chain elements
        assert 'deploy' in narrative
        assert ('traffic' in narrative or 'concurrent' in narrative)
        assert ('query' in narrative or 'qps' in narrative)
        assert ('pool' in narrative or 'saturat' in narrative or 'utilization' in narrative)
        assert ('latency' in narrative or 'slow' in narrative or 'timeout' in narrative)
        assert ('user' in narrative or 'customer' in narrative or 'impact' in narrative)
