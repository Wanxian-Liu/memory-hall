#!/usr/bin/env python3
"""
记忆殿堂-观自在 V3.0.0 - CLI入口
"""

import sys
import json

from health import HealthChecker


def main():
    checker = HealthChecker()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--circuit":
            result = checker.circuit_panel.get_panel_status()
        elif sys.argv[1] == "--metrics":
            result = checker.metrics.get_current_metrics()
        elif sys.argv[1] == "--diagnose":
            current = checker.metrics.get_current_metrics()
            history = checker.metrics.get_history_for_adaptive()
            diagnoses = checker.diagnostics.diagnose(current, history)
            result = {"diagnoses": [d.__dict__ for d in diagnoses]}
        elif sys.argv[1] == "--reset" and len(sys.argv) > 2:
            result = checker.circuit_panel.reset_breaker(sys.argv[2])
        elif sys.argv[1] == "--reset-all":
            result = checker.circuit_panel.reset_breaker()
        else:
            result = checker.get_full_report()
    else:
        result = checker.get_full_report()
    
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
