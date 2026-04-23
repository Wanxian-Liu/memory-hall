"""
Mimir-Core 模块清单查询 API (Module Registry)
=============================================

基于 M1.1-M1.3 模块扫描结果，提供可查询的模块清单 API。

参考 claw-code TaskRegistry 设计：
- 线程安全的注册表
- 按状态/类型过滤
- 输出累积模式

使用方式:
    # ModuleRegistry and get_registry are defined in this file — no import needed

    reg = get_registry()

    # 按名称精确查询
    reg.get_by_name("gateway.gateway")

    # 按前缀查询
    reg.get_by_prefix("agent.")

    # 按顶层类型查询
    reg.get_by_type("health")

    # 搜索模块（类名/函数名/docstring）
    reg.search("circuit")

    # 获取模块详情
    reg.get_details("health.circuit_breaker")

    # 获取依赖链
    reg.get_dependency_chain("gateway.gateway")

    # 累积输出模式
    reg.find_modules_accumulating(
        lambda m: len(m.get("classes", [])) > 5,
        limit=10
    )
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
)

# ---------------------------------------------------------------------------
# 内部数据（由 M1.1-M1.3 扫描生成）
# ---------------------------------------------------------------------------

_MODULE_DATA: Dict[str, Dict[str, Any]] = {
    "agent": {
        "path": "agent/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["lifecycle_manager", "role_registry", "task_dispatcher"],
    },
    "agent.lifecycle_manager": {
        "path": "agent/lifecycle_manager.py",
        "classes": ["LifecycleConfig", "AgentLifecycleManager"],
        "functions": ["get_global_lifecycle_manager"],
        "imports": ["dataclasses", "datetime", "models", "role_registry", "threading", "time", "typing", "uuid"],
    },
    "agent.models": {
        "path": "agent/models.py",
        "classes": ["RoleType", "AgentState", "TaskStatus", "Role", "Agent", "Task", "TaskResult"],
        "functions": [],
        "imports": ["dataclasses", "datetime", "enum", "typing"],
    },
    "agent.role_registry": {
        "path": "agent/role_registry.py",
        "classes": ["RegistryInner", "RoleRegistry"],
        "functions": ["get_global_registry"],
        "imports": ["dataclasses", "models", "threading", "typing"],
    },
    "agent.task_dispatcher": {
        "path": "agent/task_dispatcher.py",
        "classes": ["DispatcherConfig", "TaskDispatcher"],
        "functions": ["get_global_dispatcher"],
        "imports": ["dataclasses", "datetime", "heapq", "lifecycle_manager", "models", "role_registry", "threading", "time", "typing", "uuid"],
    },
    "agent.test_agent": {
        "path": "agent/test_agent.py",
        "classes": [],
        "functions": ["test_role_registry", "test_lifecycle_manager", "test_task_dispatcher", "test_integration", "main"],
        "imports": ["agent", "datetime", "os", "sys", "time", "traceback"],
    },
    "audit": {
        "path": "audit/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["audit"],
    },
    "audit.audit": {
        "path": "audit/audit.py",
        "classes": ["AuditLevel", "AuditCategory", "RiskLevel", "AuditEntry", "_AuditDB", "_TextLogWriter", "AuditLogger"],
        "functions": ["get_audit_logger", "log_operation", "log_high_risk_operation", "query_logs"],
        "imports": ["datetime", "enum", "json", "os", "pathlib", "sqlite3", "threading", "traceback", "typing"],
    },
    "base_wal": {
        "path": "base_wal/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["wal"],
    },
    "base_wal.wal": {
        "path": "base_wal/wal.py",
        "classes": ["WALPhase", "WALEntryType", "WALEntry", "Transaction", "WALManager"],
        "functions": ["get_default_wal_manager", "begin", "prepare_write", "execute_write", "commit", "rollback", "wal_write", "wal_delete", "compact", "recover", "status"],
        "imports": ["dataclasses", "enum", "hashlib", "json", "os", "pathlib", "struct", "threading", "time", "typing", "uuid"],
    },
    "benchmark": {
        "path": "benchmark.py",
        "classes": [],
        "functions": ["random_string", "random_record", "measure_time", "bench_gateway_read_write", "bench_wal_write", "bench_search", "bench_extractor_compression", "main"],
        "imports": ["extractor", "gateway", "json", "os", "pathlib", "random", "sensory", "statistics", "string", "sys", "tempfile", "time", "tracemalloc", "typing", "wal"],
    },
    "capsule_generator": {
        "path": "capsule_generator.py",
        "classes": ["GeneType", "Capsule", "GeneSignal", "GeneMatch", "GeneMapper", "CapsuleGenerator"],
        "functions": ["get_generator", "generate_capsule"],
        "imports": ["dataclasses", "enum", "evomap_validator", "gdi_scorer", "hashlib", "json", "re", "time", "typing"],
    },
    "classifier": {
        "path": "classifier/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["classifier"],
    },
    "classifier.classifier": {
        "path": "classifier/classifier.py",
        "classes": ["TaskStatus", "ClassificationResult", "ClassificationTask", "TaskRegistry", "TaxonomyClassifier", "KnowledgeTypeClassifier", "AutoTagger", "ClassificationEngine"],
        "functions": ["get_engine", "classify", "classify_dual", "register_task", "get_task", "get_stats"],
        "imports": ["collections", "dataclasses", "enum", "hashlib", "json", "re", "sys", "time", "typing", "uuid"],
    },
    "classifier.monitor": {
        "path": "classifier/monitor.py",
        "classes": ["ClassificationStats", "LatencyStats", "ClassificationMonitor"],
        "functions": ["get_monitor"],
        "imports": ["dataclasses", "datetime", "threading", "typing"],
    },
    "cli": {
        "path": "cli/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["router"],
    },
    "cli.commands": {
        "path": "cli/commands.py",
        "classes": ["MemoryStore", "MemoryCommands"],
        "functions": ["main"],
        "imports": ["argparse", "base_wal", "hashlib", "health", "interfaces", "json", "os", "sensory", "sys", "typing"],
    },
    "cli.router": {
        "path": "cli/router.py",
        "classes": ["ArgType", "Arg", "Command", "ParsedArgs", "Router"],
        "functions": ["get_router", "parse_and_run"],
        "imports": ["dataclasses", "enum", "re", "shlex", "typing"],
    },
    "cli.tui": {
        "path": "cli/tui.py",
        "classes": ["Colors", "Column", "Table", "ProgressBar", "Spinner", "Pager"],
        "functions": ["colorize", "has_color_support", "print_header", "print_success", "print_error", "print_warning", "print_info", "confirm", "input_with_default"],
        "imports": ["dataclasses", "shutil", "sys", "termios", "threading", "time", "tty", "typing"],
    },
    "config": {
        "path": "config/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["loader"],
    },
    "config.loader": {
        "path": "config/loader.py",
        "classes": ["ConfigLoader"],
        "functions": ["get_loader", "load_config", "get_config"],
        "imports": ["os", "pathlib", "typing", "yaml"],
    },
    "evolve": {
        "path": "evolve/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["evolve"],
    },
    "evolve.self_evolution": {
        "path": "evolve/self_evolution.py",
        "classes": ["ConfidenceLevel", "GenerationItem", "VerificationResult", "CorrectionResult", "Intent", "RootCauseAnalysis", "FixExecutionResult", "ProactiveKnowledgeCorrector", "IntentPredictor", "AutonomousRepairExecutor", "AutomatedRootCauseFixer"],
        "functions": [],
        "imports": ["asyncio", "dataclasses", "enum", "logging", "time", "typing"],
    },
    "evolve.three_ring_architecture": {
        "path": "evolve/three_ring_architecture.py",
        "classes": ["RingStatus", "AnomalyType", "MonitorEvent", "DecisionOutput", "ExecutionOutput", "MonitorRing", "DecisionRing", "ExecutionRing", "ThreeRingClosedLoop"],
        "functions": [],
        "imports": ["asyncio", "dataclasses", "enum", "logging", "time", "typing"],
    },
    "evomap_validator": {
        "path": "evomap_validator.py",
        "classes": ["EvoMapStatus", "EvoMapCheck", "EvoMapValidationResult", "EvoMapValidator"],
        "functions": ["get_validator", "validate_for_evomap", "validate_batch_for_evomap", "filter_evomap_ready"],
        "imports": ["dataclasses", "enum", "re", "time", "typing"],
    },
    "extractor": {
        "path": "extractor/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["adaptive_compression", "extractor"],
    },
    "extractor.adaptive_compression": {
        "path": "extractor/adaptive_compression.py",
        "classes": ["CompressionLevel", "AdaptiveThresholds", "CompressionContext", "AdaptiveCompressionController", "AdaptiveExtractionPipeline"],
        "functions": [],
        "imports": ["dataclasses", "enum", "re", "threading", "time", "typing"],
    },
    "extractor.extractor": {
        "path": "extractor/extractor.py",
        "classes": ["MemoryType", "CompressionResult", "Extractor", "SimpleLLMClient"],
        "functions": [],
        "imports": ["dataclasses", "enum", "hashlib", "json", "re", "typing"],
    },
    "fence": {
        "path": "fence/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["fence"],
    },
    "fence.fence": {
        "path": "fence/fence.py",
        "classes": ["SpaceType", "Permission", "SpaceBoundary", "ViolationEvent", "FenceAlert", "MemoryPalaceFence"],
        "functions": ["get_fence", "check_boundary", "validate_access"],
        "imports": ["dataclasses", "enum", "hashlib", "json", "os", "pathlib", "time", "typing"],
    },
    "gateway": {
        "path": "gateway/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["gateway"],
    },
    "gateway.gateway": {
        "path": "gateway/gateway.py",
        "classes": ["Config", "LRUCache", "Gateway"],
        "functions": ["_get_vault_adapter", "_expand_path", "_get_vault_dir", "_get_log_dir", "_get_audit_file", "_get_cache_file", "audit_log", "_sanitize_string", "_validate_path", "_validate_record_type", "read_record", "write_record", "generate_id", "fence_checkpoint", "notify_coordinator", "write", "read", "search", "delete", "get_audit_logs", "get_cache_stats", "clear_cache"],
        "imports": ["asyncio", "collections", "datetime", "hashlib", "interfaces", "json", "os", "pathlib", "re", "subprocess", "sys", "time", "typing", "urllib", "yaml"],
    },
    "gdi_scorer": {
        "path": "gdi_scorer.py",
        "classes": ["CapsuleType", "GDIResult", "GDIScorer"],
        "functions": ["get_scorer", "score_capsule", "score_capsules", "filter_publishable"],
        "imports": ["dataclasses", "enum", "hashlib", "time", "typing"],
    },
    "gene_mapper": {
        "path": "gene_mapper.py",
        "classes": ["GeneType", "CapsuleType", "GeneSignal", "GeneMatch", "GeneMapper"],
        "functions": ["get_mapper", "match_gene", "select_capsule_type", "analyze_signals"],
        "imports": ["dataclasses", "enum", "re", "time", "typing"],
    },
    "health": {
        "path": "health/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["checker", "circuit_breaker", "data_classes", "diagnostic", "enums", "metrics", "panel", "threshold"],
    },
    "health.checker": {
        "path": "health/checker.py",
        "classes": ["HealthChecker"],
        "functions": [],
        "imports": ["data_classes", "diagnostic", "enums", "metrics", "panel", "typing"],
    },
    "health.circuit_breaker": {
        "path": "health/circuit_breaker.py",
        "classes": ["CircuitBreaker"],
        "functions": [],
        "imports": ["data_classes", "enums", "json", "os", "threading", "time", "typing"],
    },
    "health.data_classes": {
        "path": "health/data_classes.py",
        "classes": ["SixDimensionData", "CircuitBreakerInfo", "DiagnosisResult"],
        "functions": [],
        "imports": ["dataclasses", "enums", "typing"],
    },
    "health.diagnostic": {
        "path": "health/diagnostic.py",
        "classes": ["DiagnosticEngine"],
        "functions": [],
        "imports": ["data_classes", "datetime", "enums", "json", "os", "threshold", "typing"],
    },
    "health.enums": {
        "path": "health/enums.py",
        "classes": ["HealthStatus", "CircuitState"],
        "functions": [],
        "imports": ["enum"],
    },
    "health.health_check": {
        "path": "health/health_check.py",
        "classes": [],
        "functions": ["main"],
        "imports": ["health", "json", "sys"],
    },
    "health.metrics": {
        "path": "health/metrics.py",
        "classes": ["SixDimensionMetrics"],
        "functions": [],
        "imports": ["data_classes", "datetime", "json", "os", "time", "typing"],
    },
    "health.panel": {
        "path": "health/panel.py",
        "classes": ["CircuitBreakerPanel"],
        "functions": [],
        "imports": ["circuit_breaker", "typing"],
    },
    "health.threshold": {
        "path": "health/threshold.py",
        "classes": ["AdaptiveThresholdCalculator"],
        "functions": [],
        "imports": ["typing"],
    },
    "integrate": {
        "path": "integrate/__init__.py",
        "classes": ["MemoryPalaceIntegration"],
        "functions": ["create_integration"],
        "imports": ["asyncio", "config", "dataclasses", "evolve", "extractor", "logging", "memory_layer", "optimize", "repair", "sensory", "stats", "time", "typing"],
    },
    "integrate.config": {
        "path": "integrate/config.py",
        "classes": ["IntegrationConfig"],
        "functions": [],
        "imports": ["dataclasses", "typing"],
    },
    "integrate.stats": {
        "path": "integrate/stats.py",
        "classes": ["MemoryStats"],
        "functions": [],
        "imports": ["dataclasses"],
    },
    "interfaces": {
        "path": "interfaces/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["adapters", "imemory_vault"],
    },
    "interfaces.adapters": {
        "path": "interfaces/adapters/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["file_system_adapter"],
    },
    "interfaces.adapters.file_system_adapter": {
        "path": "interfaces/adapters/file_system_adapter.py",
        "classes": ["FileSystemAdapter"],
        "functions": [],
        "imports": ["config", "hashlib", "imemory_vault", "json", "os", "pathlib", "typing"],
    },
    "interfaces.imemory_vault": {
        "path": "interfaces/imemory_vault.py",
        "classes": ["SearchResult", "IMemoryVault"],
        "functions": [],
        "imports": ["abc", "dataclasses", "typing"],
    },
    "interfaces.verify_interface": {
        "path": "interfaces/verify_interface.py",
        "classes": [],
        "functions": ["verify_interface"],
        "imports": ["asyncio", "interfaces", "os", "sys", "tempfile"],
    },
    "introspection": {
        "path": "introspection/__init__.py",
        "classes": [],
        "functions": [],
        "imports": [],
    },
    "introspection.dependency_graph": {
        "path": "introspection/dependency_graph.py",
        "classes": ["DependencyEdge", "DependencyGraph"],
        "functions": ["main"],
        "imports": ["ast", "collections", "dataclasses", "pathlib", "sys", "typing"],
    },
    "introspection.module_map_generator": {
        "path": "introspection/module_map_generator.py",
        "classes": ["ModuleInterface", "ModuleMapGenerator"],
        "functions": ["main"],
        "imports": ["ast", "dataclasses", "datetime", "json", "pathlib", "sys", "typing"],
    },
    "introspection.problem_detector": {
        "path": "introspection/problem_detector.py",
        "classes": ["ProblemSeverity", "ProblemCategory", "Problem", "ProblemReport", "ProblemDetector"],
        "functions": ["main"],
        "imports": ["collections", "dataclasses", "datetime", "enum", "json", "pathlib", "re", "sys", "traceback", "typing"],
    },
    "introspection.status_api": {
        "path": "introspection/status_api.py",
        "classes": ["ModuleStatus", "HealthCheckResult", "StatusAPI"],
        "functions": ["main"],
        "imports": ["agent", "collections", "dataclasses", "datetime", "enum", "gateway", "health", "importlib", "memory_layer", "pathlib", "sys", "time", "typing"],
    },
    "memory_layer": {
        "path": "memory_layer/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["rl_access"],
    },
    "memory_layer.rl_access": {
        "path": "memory_layer/rl_access.py",
        "classes": ["MemoryTier", "MemoryAccessAction", "MemoryAccessState", "MemoryBlock", "SimplePolicyNetwork", "RLMemoryLayerManager"],
        "functions": [],
        "imports": ["collections", "dataclasses", "enum", "random", "threading", "time", "typing"],
    },
    "mini_agent": {
        "path": "mini_agent/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["compact", "hooks", "registry"],
    },
    "mini_agent.compact": {
        "path": "mini_agent/compact.py",
        "classes": ["CompactionConfig", "CompactionResult", "Message"],
        "functions": ["estimate_message_tokens", "estimate_session_tokens", "should_compact", "_get_compactable_start", "_has_existing_summary", "summarize_messages", "merge_compact_summaries", "format_compact_summary", "compress_summary_text", "compact_session", "_extract_summary_content", "_build_continuation_message"],
        "imports": ["dataclasses", "datetime", "re", "typing"],
    },
    "mini_agent.hooks": {
        "path": "mini_agent/hooks.py",
        "classes": ["TimeoutError", "timeout", "HookEvent", "HookResult", "ToolCall", "ToolResult", "HookContext", "BeforeToolCallHook", "ToolResultPersistHook", "DefaultBeforeToolCallHook", "DefaultToolResultPersistHook", "HookManager"],
        "functions": ["create_default_hook_manager"],
        "imports": ["dataclasses", "datetime", "enum", "json", "signal", "threading", "typing"],
    },
    "mini_agent.registry": {
        "path": "mini_agent/registry.py",
        "classes": ["TaskStatus", "TaskPriority", "Task", "TaskRegistry"],
        "functions": ["create_task_registry"],
        "imports": ["__future__", "dataclasses", "datetime", "enum", "json", "typing", "uuid"],
    },
    "mini_agent.test_mini_agent": {
        "path": "mini_agent/test_mini_agent.py",
        "classes": ["TestRunner", "SimpleHook"],
        "functions": ["test_compact_config", "test_message_creation", "test_should_compact", "test_compact_session", "test_hooks_basic", "test_default_before_tool_hook", "test_hook_manager", "test_task_creation", "test_task_status_transitions", "test_task_dependencies", "test_task_queue", "test_task_registry_stats", "test_export_import", "main"],
        "imports": ["compact", "hooks", "json", "os", "registry", "sys"],
    },
    "normalizer": {
        "path": "normalizer/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["deduplicator"],
    },
    "normalizer.deduplicator": {
        "path": "normalizer/deduplicator.py",
        "classes": ["SimHash", "TaskStatus", "TaskRecord", "LLMSemanticDeduplicator", "TaskRegistry", "Deduplicator"],
        "functions": [],
        "imports": ["dataclasses", "datetime", "enum", "hashlib", "json", "os", "pathlib", "re", "time", "typing"],
    },
    "optimize": {
        "path": "optimize/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["optimize"],
    },
    "optimize.adaptive_compression": {
        "path": "optimize/adaptive_compression.py",
        "classes": ["CompressionLevel", "CompressionTask", "MemoryEntry", "CompressionResult", "IndexSearchResult", "AdaptiveCompressionScheduler", "IncrementalMemoryIndex", "PredictiveCompressor"],
        "functions": [],
        "imports": ["asyncio", "bisect", "collections", "dataclasses", "enum", "hashlib", "logging", "time", "typing"],
    },
    "permission": {
        "path": "permission/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["engine"],
    },
    "permission.engine": {
        "path": "permission/engine.py",
        "classes": ["PermissionLevel", "RuleAction", "Rule", "PermissionContext", "PermissionResult", "PermissionEngine"],
        "functions": ["get_engine", "check_permission"],
        "imports": ["dataclasses", "enum", "re", "typing", "urllib"],
    },
    "pipeline": {
        "path": "pipeline/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["cross_reference"],
    },
    "pipeline.cross_reference": {
        "path": "pipeline/cross_reference.py",
        "classes": ["SimilarityMethod", "Capsule", "CrossReferenceResult", "CrossReferenceEngine"],
        "functions": ["get_engine", "compute_cross_references"],
        "imports": ["dataclasses", "enum", "hashlib", "re", "time", "typing"],
    },
    "plugin": {
        "path": "plugin/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["__future__", "plugin"],
    },
    "plugin.plugin": {
        "path": "plugin/plugin.py",
        "classes": ["PluginState", "PluginMetadata", "PluginInterface", "PluginRegistry", "_PluginEntry", "PluginLoader"],
        "functions": ["plugin_metadata"],
        "imports": ["__future__", "abc", "dataclasses", "enum", "importlib", "logging", "os", "pathlib", "sys", "typing"],
    },
    "plugin.test_plugins.test_dummy": {
        "path": "plugin/test_plugins/test_dummy.py",
        "classes": ["DummyPlugin"],
        "functions": [],
        "imports": ["plugin"],
    },
    "repair": {
        "path": "repair/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["repair"],
    },
    "repair.backup_manager": {
        "path": "repair/backup_manager.py",
        "classes": ["VerificationStatus", "ImportanceLevel", "BackupSnapshot", "RestorationResult", "RAGVerificationResult", "CompressedItem", "MemoryBackupManager", "ImportanceAwareCompressor"],
        "functions": ["_simple_similarity"],
        "imports": ["asyncio", "collections", "dataclasses", "enum", "hashlib", "json", "logging", "os", "re", "time", "typing"],
    },
    "run": {
        "path": "run.py",
        "classes": ["TestBeforeHook", "TestPlugin"],
        "functions": ["get_role_registry", "get_lifecycle_manager", "get_hook_manager", "get_task_registry", "log", "result_test", "result_error", "test_agent", "test_mini_agent", "test_gateway", "test_wal", "test_cli", "test_plugin", "main"],
        "imports": ["agent", "argparse", "base_wal", "cli", "gateway", "json", "mini_agent", "os", "pathlib", "plugin", "subprocess", "sys", "time", "traceback", "typing"],
    },
    "sensory": {
        "path": "sensory/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["cache_invalidation", "semantic_search"],
    },
    "sensory.cache_invalidation": {
        "path": "sensory/cache_invalidation.py",
        "classes": ["CacheEntry", "HybridCacheInvalidator", "MemorySensoryIndex"],
        "functions": [],
        "imports": ["collections", "dataclasses", "fnmatch", "threading", "time", "typing"],
    },
    "sensory.semantic_search": {
        "path": "sensory/semantic_search.py",
        "classes": ["GatewayConfig", "TaskStatus", "SearchQuery", "SearchResult", "QueryTask", "TaskRegistry", "VectorIndex", "SemanticSearchEngine"],
        "functions": ["get_task_registry", "create_engine"],
        "imports": ["asyncio", "collections", "dataclasses", "enum", "hashlib", "json", "os", "pathlib", "re", "struct", "sys", "threading", "time", "typing", "uuid"],
    },
    "task": {
        "path": "task/__init__.py",
        "classes": [],
        "functions": [],
        "imports": ["task_manager"],
    },
    "task.task_manager": {
        "path": "task/task_manager.py",
        "classes": ["TaskStatus", "PhaseType", "CircuitState", "TaskContext", "CircuitBreaker", "TaskManager", "CircuitOpenError", "TaskNotFoundError"],
        "functions": ["get_default_manager", "create_task"],
        "imports": ["asyncio", "collections", "dataclasses", "enum", "time", "typing", "uuid"],
    },
    "test_gdi_gene": {
        "path": "test_gdi_gene.py",
        "classes": [],
        "functions": ["test_gdi_scorer", "test_gene_mapper", "test_capsule_generator", "test_integration", "main"],
        "imports": ["capsule_generator", "gdi_scorer", "gene_mapper", "sys", "time", "traceback"],
    },
    "tests": {
        "path": "tests/__init__.py",
        "classes": [],
        "functions": [],
        "imports": [],
    },
    "tests.conftest": {
        "path": "tests/conftest.py",
        "classes": [],
        "functions": ["temp_dir", "wal_dir", "vault_dir", "metadata_dir", "plugin_dir", "sample_content", "sample_contents"],
        "imports": ["os", "pathlib", "pytest", "shutil", "sys", "tempfile"],
    },
    "tests.integration": {
        "path": "tests/integration/__init__.py",
        "classes": ["BaseIntegrationTest"],
        "functions": ["setup_test_vault", "cleanup_test_vault"],
        "imports": ["json", "os", "pathlib", "shutil", "sys", "tempfile", "time", "typing", "unittest"],
    },
    "tests.integration.conftest": {
        "path": "tests/integration/conftest.py",
        "classes": [],
        "functions": ["project_root", "test_vault_dir", "test_wal_dir", "clean_registry", "pytest_configure", "pytest_collection_modifyitems"],
        "imports": ["os", "pathlib", "plugin", "pytest", "shutil", "sys", "tempfile"],
    },
    "tests.integration.integration_test_cli_modules": {
        "path": "tests/integration/integration_test_cli_modules.py",
        "classes": ["TestCLICommands", "TestCLIWithGateway", "TestCLIWithPermission", "TestCLIRunner"],
        "functions": [],
        "imports": ["base_wal", "cli", "gateway", "health", "json", "os", "pathlib", "permission", "pytest", "shutil", "subprocess", "sys", "tempfile", "tests", "time", "typing"],
    },
    "tests.integration.integration_test_gateway_permission": {
        "path": "tests/integration/integration_test_gateway_permission.py",
        "classes": ["TestGatewayPermissionCollaboration", "TestPermissionEngineStandalone"],
        "functions": [],
        "imports": ["gateway", "json", "os", "pathlib", "permission", "pytest", "shutil", "sys", "tempfile", "tests", "time", "typing"],
    },
    "tests.integration.integration_test_gateway_wal": {
        "path": "tests/integration/integration_test_gateway_wal.py",
        "classes": ["TestGatewayWALCollaboration", "TestWALWithGatewayCache"],
        "functions": [],
        "imports": ["base_wal", "gateway", "json", "os", "pathlib", "pytest", "shutil", "sys", "tempfile", "tests", "threading", "time", "typing"],
    },
    "tests.integration.integration_test_plugin_modules": {
        "path": "tests/integration/integration_test_plugin_modules.py",
        "classes": ["TestPluginA", "TestPluginB", "TestPluginLifecycle", "TestPluginGatewayIntegration", "TestPluginPermissionIntegration", "TestPluginWALIntegration", "TestPluginRegistryAdvanced", "TestPluginLoader"],
        "functions": [],
        "imports": ["base_wal", "gateway", "importlib", "json", "os", "pathlib", "permission", "plugin", "pytest", "shutil", "sys", "tempfile", "tests", "time", "typing"],
    },
    "tests.integration.run_tests": {
        "path": "tests/integration/run_tests.py",
        "classes": [],
        "functions": ["run_tests", "main"],
        "imports": ["argparse", "importlib", "os", "sys", "unittest"],
    },
    "tests.test_audit": {
        "path": "tests/test_audit.py",
        "classes": ["TestAuditLevel", "TestAuditCategory", "TestRiskLevel", "TestAuditEntry", "TestInferRisk", "TestTextLogWriter", "TestAuditDB", "TestAuditLogger", "TestGlobalFunctions"],
        "functions": [],
        "imports": ["audit", "datetime", "os", "pytest", "sys", "tempfile", "time"],
    },
    "tests.test_base_wal": {
        "path": "tests/test_base_wal.py",
        "classes": ["TestWALEntryType", "TestWALPhase", "TestWALEntry", "TestTransaction", "TestWALManager", "TestWALGlobalFunctions", "TestWALCompaction", "TestWALChecksum"],
        "functions": [],
        "imports": ["base_wal", "os", "pathlib", "pytest", "sys", "uuid"],
    },
    "tests.test_classifier": {
        "path": "tests/test_classifier.py",
        "classes": ["TestTaskStatus", "TestClassificationResult", "TestClassificationTask", "TestTaskRegistry", "TestTaxonomyClassifier", "TestKnowledgeTypeClassifier", "TestAutoTagger", "TestClassificationEngine", "TestGlobalFunctions", "TestClassificationResultAdvanced", "TestClassificationTaskAdvanced", "TestTaskRegistryAdvanced", "TestTaxonomyClassifierAdvanced", "TestKnowledgeTypeClassifierAdvanced", "TestAutoTaggerAdvanced", "TestClassificationEngineAdvanced", "TestGlobalFunctionsAdvanced"],
        "functions": [],
        "imports": ["classifier", "os", "pytest", "sys"],
    },
    "tests.test_cli_commands": {
        "path": "tests/test_cli_commands.py",
        "classes": ["TestMemoryStore", "TestMain"],
        "functions": [],
        "imports": ["cli", "io", "json", "os", "pytest", "shutil", "sys", "tempfile"],
    },
    "tests.test_cli_router": {
        "path": "tests/test_cli_router.py",
        "classes": ["TestArgType", "TestArg", "TestParsedArgs", "TestCommand", "TestRouter", "TestGlobalFunctions"],
        "functions": [],
        "imports": ["cli", "os", "pytest", "sys"],
    },
    "tests.test_extractor": {
        "path": "tests/test_extractor.py",
        "classes": ["TestMemoryType", "TestCompressionResult", "TestExtractor", "TestSimpleLLMClient", "TestExtractorAdvanced"],
        "functions": [],
        "imports": ["extractor", "os", "pytest", "sys"],
    },
    "tests.test_fence": {
        "path": "tests/test_fence.py",
        "classes": ["TestSpaceType", "TestPermission", "TestSpaceBoundary", "TestViolationEvent", "TestFenceAlert", "TestMemoryPalaceFence", "TestFenceGlobalFunctions"],
        "functions": [],
        "imports": ["fence", "os", "pytest", "sys", "time"],
    },
    "tests.test_gateway": {
        "path": "tests/test_gateway.py",
        "classes": ["TestConfig", "TestLRUCache", "TestGateway", "TestFenceCheckpoint", "TestNotifyCoordinator", "TestAuditLog", "TestGetAuditLogs", "TestGetCacheStats", "TestClearCache", "TestSecurityFunctions", "TestReadWriteRecord", "TestSearch", "TestWriteWithMetadata"],
        "functions": [],
        "imports": ["gateway", "os", "pytest", "sys", "tempfile"],
    },
    "tests.test_health": {
        "path": "tests/test_health.py",
        "classes": ["TestHealthStatus", "TestCircuitState", "TestSixDimensionData", "TestCircuitBreakerInfo", "TestDiagnosisResult", "TestAdaptiveThresholdCalculator", "TestCircuitBreaker", "TestSixDimensionMetrics", "TestCircuitBreakerPanel", "TestDiagnosticEngine", "TestHealthChecker"],
        "functions": [],
        "imports": ["health", "os", "pytest", "sys", "time"],
    },
    "tests.test_normalizer": {
        "path": "tests/test_normalizer.py",
        "classes": ["TestSimHash", "TestTaskStatus", "TestTaskRecord", "TestLLMSemanticDeduplicator", "TestTaskRegistry", "TestDeduplicator", "TestSimHashAdvanced", "TestTaskRecordAdvanced", "TestTaskRegistryAdvanced", "TestDeduplicatorAdvanced", "TestLLMSemanticDeduplicatorAdvanced"],
        "functions": [],
        "imports": ["asyncio", "normalizer", "os", "pytest", "sys"],
    },
    "tests.test_permission": {
        "path": "tests/test_permission.py",
        "classes": ["TestPermissionLevel", "TestRuleAction", "TestRule", "TestPermissionContext", "TestPermissionResult", "TestPermissionEngine"],
        "functions": [],
        "imports": ["os", "permission", "pytest", "sys"],
    },
    "tests.test_plugin": {
        "path": "tests/test_plugin.py",
        "classes": ["TestPlugin", "AnotherTestPlugin", "FailingPlugin", "TestPluginMetadata", "TestPluginState", "TestPluginInterface", "TestPluginRegistry", "TestPluginLoader", "TestPluginMetadataDecorator", "Test_PluginEntry", "PluginA", "PluginB", "DecoratedPlugin"],
        "functions": ["fresh_registry", "plugin_a", "plugin_b"],
        "imports": ["os", "pathlib", "plugin", "pytest", "shutil", "sys", "tempfile"],
    },
    "tests.test_sensory": {
        "path": "tests/test_sensory.py",
        "classes": ["TestGatewayConfig", "TestTaskStatus", "TestSearchQuery", "TestSearchResult", "TestQueryTask", "TestTaskRegistry", "TestVectorIndex", "TestSemanticSearchEngine", "TestCreateEngine"],
        "functions": [],
        "imports": ["numpy", "os", "pytest", "sensory", "sys"],
    },
    "tests.test_task": {
        "path": "tests/test_task.py",
        "classes": ["TestTaskStatus", "TestPhaseType", "TestCircuitStateEnum", "TestTaskContext", "TestTaskManager", "TestTaskManagerAsync", "TestGlobalFunctions"],
        "functions": [],
        "imports": ["asyncio", "os", "pytest", "sys", "task", "time"],
    },
    "utils": {
        "path": "utils/__init__.py",
        "classes": [],
        "functions": [],
        "imports": [],
    },
    "utils.deepseek_client": {
        "path": "utils/deepseek_client.py",
        "classes": ["LLMConfig", "RateLimiter", "DeepSeekClient"],
        "functions": ["get_client"],
        "imports": ["dataclasses", "json", "openai", "os", "queue", "threading", "time", "traceback", "typing", "yaml"],
    },
    "verify_tool_invocation": {
        "path": "verify_tool_invocation.py",
        "classes": ["RealExecutionPlugin"],
        "functions": ["test_gateway_file_io", "test_wal_real_persistence", "test_plugin_real_execution", "test_agent_lifecycle_real", "main"],
        "imports": ["agent", "gateway", "hashlib", "os", "pathlib", "plugin", "sys", "time", "wal"],
    },
}

# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


class ModuleType(Enum):
    """模块顶层类型"""
    AGENT = "agent"
    AUDIT = "audit"
    BASE_WAL = "base_wal"
    BENCHMARK = "benchmark"
    CAPSULE = "capsule"
    CLASSIFIER = "classifier"
    CLI = "cli"
    CONFIG = "config"
    EVOLVE = "evolve"
    EVOMAP = "evomap"
    EXTRACTOR = "extractor"
    FENCE = "fence"
    GATEWAY = "gateway"
    GDI = "gdi"
    GENE = "gene"
    HEALTH = "health"
    INTEGRATE = "integrate"
    INTERFACES = "interfaces"
    INTROSPECTION = "introspection"
    MEMORY_LAYER = "memory_layer"
    MINI_AGENT = "mini_agent"
    NORMALIZER = "normalizer"
    OPTIMIZE = "optimize"
    PERMISSION = "permission"
    PIPELINE = "pipeline"
    PLUGIN = "plugin"
    REPAIR = "repair"
    RUN = "run"
    SENSORY = "sensory"
    TASK = "task"
    TESTS = "tests"
    UTILS = "utils"
    VERIFY = "verify"
    UNKNOWN = "unknown"


@dataclass
class ModuleDetail:
    """模块详细信息"""
    id: str
    path: str
    top_type: str
    classes: List[str]
    functions: List[str]
    imports: List[str]
    # 反向依赖：哪些模块依赖此模块
    dependents: List[str] = field(default_factory=list)
    # 正向依赖：此模块依赖的外部模块
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ModuleSummary:
    """模块摘要（轻量）"""
    id: str
    path: str
    top_type: str
    class_count: int
    function_count: int
    import_count: int


@dataclass
class ModuleQueryResult:
    """查询结果"""
    total: int
    modules: List[Dict[str, Any]]
    query_type: str
    query_value: str


# ---------------------------------------------------------------------------
# 线程安全的模块注册表
# ---------------------------------------------------------------------------

class ModuleRegistry:
    """
    线程安全的模块清单注册表。

    参考 TaskRegistry 设计模式：
    - RLock 保证读写并发安全
    - 内置索引加速常见查询
    - 累积输出模式支持增量发现
    """

    # 顶层类型 -> 模块ID前缀映射
    _TYPE_PREFIXES: Dict[ModuleType, Tuple[str, ...]] = {
        ModuleType.AGENT: ("agent",),
        ModuleType.AUDIT: ("audit",),
        ModuleType.BASE_WAL: ("base_wal",),
        ModuleType.BENCHMARK: ("benchmark",),
        ModuleType.CAPSULE: ("capsule_generator",),
        ModuleType.CLASSIFIER: ("classifier",),
        ModuleType.CLI: ("cli",),
        ModuleType.CONFIG: ("config",),
        ModuleType.EVOLVE: ("evolve",),
        ModuleType.EVOMAP: ("evomap_validator",),
        ModuleType.EXTRACTOR: ("extractor",),
        ModuleType.FENCE: ("fence",),
        ModuleType.GATEWAY: ("gateway",),
        ModuleType.GDI: ("gdi_scorer",),
        ModuleType.GENE: ("gene_mapper",),
        ModuleType.HEALTH: ("health",),
        ModuleType.INTEGRATE: ("integrate",),
        ModuleType.INTERFACES: ("interfaces",),
        ModuleType.INTROSPECTION: ("introspection",),
        ModuleType.MEMORY_LAYER: ("memory_layer",),
        ModuleType.MINI_AGENT: ("mini_agent",),
        ModuleType.NORMALIZER: ("normalizer",),
        ModuleType.OPTIMIZE: ("optimize",),
        ModuleType.PERMISSION: ("permission",),
        ModuleType.PIPELINE: ("pipeline",),
        ModuleType.PLUGIN: ("plugin",),
        ModuleType.REPAIR: ("repair",),
        ModuleType.RUN: ("run",),
        ModuleType.SENSORY: ("sensory",),
        ModuleType.TASK: ("task",),
        ModuleType.TESTS: ("tests",),
        ModuleType.UTILS: ("utils",),
        ModuleType.VERIFY: ("verify_tool_invocation",),
    }

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, Dict[str, Any]] = _MODULE_DATA
        # 索引缓存（按需构建）
        self._type_index: Optional[Dict[str, List[str]]] = None
        self._prefix_index: Optional[Dict[str, List[str]]] = None
        self._class_index: Optional[Dict[str, List[str]]] = None
        self._function_index: Optional[Dict[str, List[str]]] = None
        self._reverse_deps: Optional[Dict[str, List[str]]] = None

    # -------------------------------------------------------------------------
    # 索引构建
    # -------------------------------------------------------------------------

    def _ensure_type_index(self) -> None:
        if self._type_index is None:
            with self._lock:
                if self._type_index is None:
                    index: Dict[str, List[str]] = {}
                    for mid in self._data:
                        top = self._get_top_type(mid)
                        index.setdefault(top, []).append(mid)
                    self._type_index = index

    def _ensure_reverse_deps(self) -> None:
        if self._reverse_deps is None:
            with self._lock:
                if self._reverse_deps is None:
                    rev: Dict[str, List[str]] = {mid: [] for mid in self._data}
                    for mid, mdata in self._data.items():
                        for imp in mdata.get("imports", []):
                            # imp 可能是简短的模块名，尝试匹配
                            matched = self._match_import_to_module(imp)
                            for m in matched:
                                if m in rev:
                                    rev[m].append(mid)
                    self._reverse_deps = rev

    def _ensure_class_index(self) -> None:
        if self._class_index is None:
            with self._lock:
                if self._class_index is None:
                    index: Dict[str, List[str]] = {}
                    for mid, mdata in self._data.items():
                        for cls in mdata.get("classes", []):
                            index.setdefault(cls.lower(), []).append(mid)
                    self._class_index = index

    def _ensure_function_index(self) -> None:
        if self._function_index is None:
            with self._lock:
                if self._function_index is None:
                    index: Dict[str, List[str]] = {}
                    for mid, mdata in self._data.items():
                        for fn in mdata.get("functions", []):
                            index.setdefault(fn.lower(), []).append(mid)
                    self._function_index = index

    def _match_import_to_module(self, imp: str) -> List[str]:
        """将 import 语句匹配到模块 ID"""
        candidates = []
        # 精确匹配
        if imp in self._data:
            candidates.append(imp)
        # 前缀匹配
        for mid in self._data:
            if mid.startswith(imp + ".") or mid == imp:
                if mid not in candidates:
                    candidates.append(mid)
        return candidates

    # -------------------------------------------------------------------------
    # 顶层类型判断
    # -------------------------------------------------------------------------

    def _get_top_type(self, module_id: str) -> str:
        """获取模块的顶层类型"""
        top = module_id.split(".")[0]
        return top

    def get_top_type(self, module_id: str) -> str:
        """公开：获取模块的顶层类型"""
        with self._lock:
            return self._get_top_type(module_id)

    # -------------------------------------------------------------------------
    # 基础查询
    # -------------------------------------------------------------------------

    def all_modules(self) -> List[str]:
        """返回所有模块 ID（排序）"""
        with self._lock:
            return sorted(self._data.keys())

    def count(self) -> int:
        """返回模块总数"""
        with self._lock:
            return len(self._data)

    def get(self, module_id: str) -> Optional[Dict[str, Any]]:
        """精确获取单个模块数据"""
        with self._lock:
            return self._data.get(module_id)

    # -------------------------------------------------------------------------
    # 按名称查询
    # -------------------------------------------------------------------------

    def get_by_name(self, module_id: str) -> Optional[Dict[str, Any]]:
        """
        按精确名称查询模块。

        Example:
            reg.get_by_name("health.circuit_breaker")
        """
        with self._lock:
            return self._data.get(module_id)

    def get_by_prefix(self, prefix: str) -> List[Dict[str, Any]]:
        """
        按前缀查询模块。

        Example:
            reg.get_by_prefix("health.")      # health 下所有子模块
            reg.get_by_prefix("agent.role")  # agent.role_* 模块
        """
        with self._lock:
            results = []
            for mid in self._data:
                if mid.startswith(prefix):
                    results.append({"id": mid, **self._data[mid]})
            return sorted(results, key=lambda x: x["id"])

    # -------------------------------------------------------------------------
    # 按类型查询
    # -------------------------------------------------------------------------

    def get_by_type(self, top_type: str) -> List[Dict[str, Any]]:
        """
        按顶层类型查询所有子模块。

        Example:
            reg.get_by_type("health")
            reg.get_by_type("agent")
            reg.get_by_type("extractor")
        """
        with self._lock:
            self._ensure_type_index()
            matched_ids = self._type_index.get(top_type, [])
            return [{"id": mid, **self._data[mid]} for mid in sorted(matched_ids)]

    def get_types(self) -> Dict[str, int]:
        """返回所有顶层类型及每个类型的模块数量"""
        with self._lock:
            self._ensure_type_index()
            return {t: len(mids) for t, mids in self._type_index.items()}

    # -------------------------------------------------------------------------
    # 按类名/函数名查询
    # -------------------------------------------------------------------------

    def get_by_class(self, class_name: str) -> List[Dict[str, Any]]:
        """
        按类名查询所在模块（不区分大小写）。

        Example:
            reg.get_by_class("CircuitBreaker")  # -> [health.circuit_breaker, ...]
        """
        with self._lock:
            self._ensure_class_index()
            key = class_name.lower()
            matched_ids = self._class_index.get(key, [])
            return [{"id": mid, **self._data[mid]} for mid in sorted(matched_ids)]

    def get_by_function(self, func_name: str) -> List[Dict[str, Any]]:
        """
        按函数名查询所在模块（不区分大小写）。

        Example:
            reg.get_by_function("create_engine")
        """
        with self._lock:
            self._ensure_function_index()
            key = func_name.lower()
            matched_ids = self._function_index.get(key, [])
            return [{"id": mid, **self._data[mid]} for mid in sorted(matched_ids)]

    # -------------------------------------------------------------------------
    # 搜索
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        case_sensitive: bool = False,
        include_docstring: bool = False,
    ) -> ModuleQueryResult:
        """
        模糊搜索模块，匹配名称、类名、函数名。

        Example:
            reg.search("circuit")       # 匹配 circuit_breaker, CircuitBreaker, ...
            reg.search("Circuit", case_sensitive=True)
        """
        with self._lock:
            q = query if case_sensitive else query.lower()
            results = []

            for mid, mdata in self._data.items():
                matched = False
                match_field = []

                # 匹配模块 ID
                target = mid if case_sensitive else mid.lower()
                if q in target:
                    matched = True
                    match_field.append("name")

                # 匹配类名
                for cls in mdata.get("classes", []):
                    t = cls if case_sensitive else cls.lower()
                    if q in t:
                        matched = True
                        match_field.append("class")
                        break

                # 匹配函数名
                for fn in mdata.get("functions", []):
                    t = fn if case_sensitive else fn.lower()
                    if q in t:
                        matched = True
                        match_field.append("function")
                        break

                if matched:
                    results.append({
                        "id": mid,
                        "match_fields": list(set(match_field)),
                        **mdata,
                    })

            results.sort(key=lambda x: x["id"])
            return ModuleQueryResult(
                total=len(results),
                modules=results,
                query_type="search",
                query_value=query,
            )

    # -------------------------------------------------------------------------
    # 模块详情
    # -------------------------------------------------------------------------

    def get_details(self, module_id: str) -> Optional[ModuleDetail]:
        """
        获取模块完整详情，包含正向和反向依赖。

        Example:
            detail = reg.get_details("gateway.gateway")
            print(detail.dependents)   # 谁依赖 gateway.gateway
            print(detail.dependencies) # gateway.gateway 依赖谁
        """
        with self._lock:
            mdata = self._data.get(module_id)
            if not mdata:
                return None

            self._ensure_reverse_deps()

            # 解析 imports 为实际模块 ID
            deps = []
            for imp in mdata.get("imports", []):
                matched = self._match_import_to_module(imp)
                deps.extend(matched)

            return ModuleDetail(
                id=module_id,
                path=mdata.get("path", ""),
                top_type=self._get_top_type(module_id),
                classes=mdata.get("classes", []),
                functions=mdata.get("functions", []),
                imports=mdata.get("imports", []),
                dependents=sorted(set(self._reverse_deps.get(module_id, []))),
                dependencies=sorted(set(deps)),
            )

    def get_summary(self, module_id: str) -> Optional[ModuleSummary]:
        """获取模块摘要（轻量）"""
        with self._lock:
            mdata = self._data.get(module_id)
            if not mdata:
                return None
            return ModuleSummary(
                id=module_id,
                path=mdata.get("path", ""),
                top_type=self._get_top_type(module_id),
                class_count=len(mdata.get("classes", [])),
                function_count=len(mdata.get("functions", [])),
                import_count=len(mdata.get("imports", [])),
            )

    # -------------------------------------------------------------------------
    # 依赖链
    # -------------------------------------------------------------------------

    def get_dependency_chain(
        self,
        module_id: str,
        depth: int = 3,
        direction: str = "both",
    ) -> Dict[str, Any]:
        """
        获取模块依赖链。

        Args:
            module_id: 起始模块
            depth: 最大深度
            direction: "forward"(此模块依赖谁), "reverse"(谁依赖此模块), "both"
        """
        with self._lock:
            visited: Set[str] = set()
            forward: Dict[str, List[str]] = {}
            reverse: Dict[str, List[str]] = {}

            def _resolve_forward(mid: str, d: int) -> None:
                if d <= 0 or mid in visited:
                    return
                visited.add(mid)
                mdata = self._data.get(mid)
                if not mdata:
                    return
                deps = []
                for imp in mdata.get("imports", []):
                    matched = self._match_import_to_module(imp)
                    deps.extend(matched)
                if deps:
                    forward[mid] = sorted(set(deps))
                    for dep in deps:
                        if dep not in visited:
                            _resolve_forward(dep, d - 1)

            def _resolve_reverse(mid: str, d: int) -> None:
                if d <= 0 or mid in visited:
                    return
                visited.add(mid)
                self._ensure_reverse_deps()
                deps = self._reverse_deps.get(mid, [])
                if deps:
                    reverse[mid] = sorted(set(deps))
                    for dep in deps:
                        if dep not in visited:
                            _resolve_reverse(dep, d - 1)

            if direction in ("forward", "both"):
                _resolve_forward(module_id, depth)
            if direction in ("reverse", "both"):
                visited.clear()
                _resolve_reverse(module_id, depth)

            return {
                "module": module_id,
                "depth": depth,
                "direction": direction,
                "forward_dependencies": forward,
                "reverse_dependents": reverse,
            }

    # -------------------------------------------------------------------------
    # 累积输出模式（Accumulating Output）
    # -------------------------------------------------------------------------

    def find_modules_accumulating(
        self,
        predicate: Callable[[Dict[str, Any]], bool],
        limit: Optional[int] = None,
        sort_by: str = "name",
    ) -> List[Dict[str, Any]]:
        """
        累积模式：找出所有满足条件的模块，可指定排序和数量上限。

        Example:
            # 找出所有包含超过5个类的模块
            reg.find_modules_accumulating(
                lambda m: len(m.get("classes", [])) > 5,
                sort_by="class_count",
                limit=10
            )
        """
        with self._lock:
            results = []
            for mid, mdata in self._data.items():
                entry = {"id": mid, **mdata}
                if predicate(entry):
                    results.append(entry)

            # 排序
            def sort_key(x: Dict[str, Any]) -> Any:
                if sort_by == "name":
                    return x["id"]
                elif sort_by == "class_count":
                    return len(x.get("classes", []))
                elif sort_by == "function_count":
                    return len(x.get("functions", []))
                elif sort_by == "import_count":
                    return len(x.get("imports", []))
                return x["id"]

            results.sort(key=sort_key)
            if limit:
                results = results[:limit]
            return results

    def iter_accumulating(
        self,
        predicate: Callable[[Dict[str, Any]], bool],
    ) -> Iterator[Dict[str, Any]]:
        """
        累积模式迭代器：惰性返回满足条件的模块。

        Example:
            for module in reg.iter_accumulating(lambda m: "circuit" in m["id"]):
                print(module["id"])
        """
        with self._lock:
            for mid, mdata in self._data.items():
                entry = {"id": mid, **mdata}
                if predicate(entry):
                    yield entry

    # -------------------------------------------------------------------------
    # 统计
    # -------------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """返回全局统计信息"""
        with self._lock:
            total_classes = sum(len(m.get("classes", [])) for m in self._data.values())
            total_functions = sum(len(m.get("functions", [])) for m in self._data.values())
            self._ensure_type_index()
            return {
                "total_modules": len(self._data),
                "total_classes": total_classes,
                "total_functions": total_functions,
                "modules_by_type": {t: len(mids) for t, mids in self._type_index.items()},
                "indexed_types": list(self._type_index.keys()),
            }

    def type_distribution(self) -> Dict[str, int]:
        """返回各类型的模块数量分布"""
        with self._lock:
            self._ensure_type_index()
            return dict(sorted(
                ((t, len(mids)) for t, mids in self._type_index.items()),
                key=lambda x: -x[1],
            ))

    # -------------------------------------------------------------------------
    # 导出
    # -------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """返回完整数据字典（深拷贝）"""
        with self._lock:
            import copy
            return copy.deepcopy(self._data)

    def filter(
        self,
        top_type: Optional[str] = None,
        has_classes: bool = False,
        has_functions: bool = False,
        min_classes: int = 0,
        min_functions: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        组合过滤器查询。

        Example:
            # 查找 health 下所有包含类的模块
            reg.filter(top_type="health", has_classes=True)

            # 查找函数数>=3的所有模块
            reg.filter(min_functions=3)
        """
        with self._lock:
            results = []
            for mid, mdata in self._data.items():
                # 类型过滤
                if top_type and not mid.startswith(top_type + ".") and mid != top_type:
                    continue
                # 类过滤
                classes = mdata.get("classes", [])
                if has_classes and not classes:
                    continue
                if len(classes) < min_classes:
                    continue
                # 函数过滤
                functions = mdata.get("functions", [])
                if has_functions and not functions:
                    continue
                if len(functions) < min_functions:
                    continue

                results.append({"id": mid, **mdata})

            return sorted(results, key=lambda x: x["id"])


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_registry: Optional[ModuleRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> ModuleRegistry:
    """获取全局模块注册表（单例）"""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ModuleRegistry()
    return _registry


# ---------------------------------------------------------------------------
# 兼容旧 API（直接函数调用）
# ---------------------------------------------------------------------------

def get_modules() -> List[str]:
    """Return all module IDs."""
    return get_registry().all_modules()


def get_module(module_id: str) -> Optional[Dict[str, Any]]:
    """Return info for a specific module."""
    return get_registry().get(module_id)


def get_dependencies(module_id: str) -> List[str]:
    """Return import dependencies for a module."""
    detail = get_registry().get_details(module_id)
    if not detail:
        return []
    return detail.dependencies


def get_stats() -> Dict[str, int]:
    """Return summary statistics."""
    reg = get_registry()
    s = reg.stats()
    return {
        "modules": s["total_modules"],
        "classes": s["total_classes"],
        "functions": s["total_functions"],
    }
