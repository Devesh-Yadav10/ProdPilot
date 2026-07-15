from __future__ import annotations
from typing import Any


def get_context(finding: dict) -> dict[str, Any]:
    '''
    Optional light context lookup for a finding.
    
    Could be extended to:
    - Look up related files
    - Check for similar patterns in codebase
    - Fetch recent incidents
    - Get team ownership info
    
    Currently returns minimal context.
    '''
    return {
        'file': finding.get('file'),
        'pattern_type': finding.get('pattern_type'),
        'team': 'backend-team',  # Placeholder
        'related_incidents': [],
    }
