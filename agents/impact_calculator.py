"""Deterministic impact calculator - pure Python math, no LLMs."""
from dataclasses import dataclass
from typing import TypedDict


class ImpactResultDict(TypedDict):
    projected_query_count: int
    projected_qps: float
    pool_utilization_pct: float
    threshold_breached: bool
    threshold_details: dict


@dataclass
class ImpactResult:
    projected_query_count: int
    projected_qps: float
    pool_utilization_pct: float
    threshold_breached: bool
    threshold_details: dict

    def to_dict(self):
        return {
            'projected_query_count': self.projected_query_count,
            'projected_qps': self.projected_qps,
            'pool_utilization_pct': self.pool_utilization_pct,
            'threshold_breached': self.threshold_breached,
            'threshold_details': self.threshold_details,
        }


def calculate_impact(findings, metrics):
    avg_orders = metrics.get('avg_orders_per_user', 5)
    avg_items = metrics.get('avg_items_per_order', 3)
    pool_size = metrics.get('connection_pool_size', 20)
    avg_query_ms = metrics.get('avg_query_time_ms', 5)
    peak_users = metrics.get('peak_concurrent_users', 1000)
    max_pool_pct = metrics.get('max_pool_utilization_pct', 80)
    avg_req_dur_s = metrics.get('avg_request_duration_seconds', 0.5)

    total_nested_queries = 0
    for finding in findings:
        depth = finding.get('nesting_depth', 1)
        if depth == 1:
            multiplier = avg_orders
        elif depth >= 2:
            multiplier = avg_orders * avg_items
            for _ in range(depth - 2):
                multiplier *= avg_items
        else:
            multiplier = 1
        total_nested_queries += multiplier

    projected_query_count = total_nested_queries
    rps = peak_users / avg_req_dur_s if avg_req_dur_s > 0 else 0
    projected_qps = projected_query_count * rps
    query_duration_s = avg_query_ms / 1000.0
    concurrent_queries = projected_qps * query_duration_s
    pool_utilization_pct = (concurrent_queries / pool_size * 100) if pool_size > 0 else 0
    threshold_breached = pool_utilization_pct > max_pool_pct

    threshold_details = {
        'max_pool_utilization_pct': max_pool_pct,
        'pool_size': pool_size,
        'avg_query_time_ms': avg_query_ms,
        'avg_request_duration_s': avg_req_dur_s,
        'peak_concurrent_users': peak_users,
        'avg_orders_per_user': avg_orders,
        'avg_items_per_order': avg_items,
    }

    return ImpactResult(
        projected_query_count=projected_query_count,
        projected_qps=round(projected_qps, 2),
        pool_utilization_pct=round(pool_utilization_pct, 2),
        threshold_breached=threshold_breached,
        threshold_details=threshold_details,
    )


if __name__ == '__main__':
    test_findings = [
        {'file': 'test.py', 'line': 3, 'pattern_type': 'nested_query', 'nesting_depth': 2, 'snippet': '...'}
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
    result = calculate_impact(test_findings, test_metrics)
    print(f'Projected query count: {result.projected_query_count}')
    print(f'Projected QPS: {result.projected_qps}')
    print(f'Pool utilization: {result.pool_utilization_pct}%')
    print(f'Threshold breached: {result.threshold_breached}')
    assert result.projected_query_count == 15
    assert result.projected_qps == 30000.0
    assert result.pool_utilization_pct == 750.0
    assert result.threshold_breached == True
    print('All assertions passed!')
