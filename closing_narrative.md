# Closing Slide — What Happens After Deployment

**Known N+1 scenario: 15 queries per request, 100,000 projected QPS, and
75,000% projected connection-pool utilization.**

> Deploy → peak traffic reaches the affected endpoint → each request performs
> 15 product lookups → projected query volume reaches 100,000 QPS → the
> connection pool saturates at 75,000% of capacity → queries queue and latency
> spikes → customers see slow pages, timeouts, or errors → eager-load or batch
> product records before deployment.

**Takeaway:** the deterministic calculator quantifies the risk; the agents turn
those fixed numbers into an actionable engineering decision.
