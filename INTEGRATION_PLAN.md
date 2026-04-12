# 记忆殿堂v2.0 胶囊集成计划
## Phase: 第16章执行流程

## 📋 Clarify 结果

### 待集成胶囊清单

| ID | 胶囊 | 核心功能 | GDI | 优先级 |
|----|------|----------|-----|--------|
| CAP-01 | 01-repair-memory-palace-v2 | RAG验证、备份恢复、重要性压缩 | 67.6 | P0 |
| CAP-02 | 01-optimize-memory-palace-v2 | 自适应压缩、增量索引、预测压缩 | 65.7 | P1 |
| CAP-03 | 01-innovate-memory-palace-v2 | 自进化闭环、主动纠错、意图预测 | 66.7 | P2 |

---

## 📐 Plan: 集成架构

### 文件映射

| 来源 | 类/函数 | 目标路径 | 说明 |
|------|---------|----------|------|
| CAP-01 | verify_rag_source | pipeline/rag_verifier.py | 新建 - RAG源码验证 |
| CAP-01 | MemoryBackupManager | library/backup_manager.py | 新建 - 备份恢复管理 |
| CAP-01 | ImportanceAwareCompressor | library/importance_compressor.py | 新建 - 重要性压缩 |
| CAP-02 | AdaptiveCompressionScheduler | library/adaptive_scheduler.py | 新建 - 自适应压缩调度 |
| CAP-02 | IncrementalMemoryIndex | library/incremental_index.py | 新建 - 增量索引 |
| CAP-02 | PredictiveCompressor | library/predictive_compressor.py | 新建 - 预测压缩 |
| CAP-03 | ProactiveKnowledgeCorrector | pipeline/proactive_corrector.py | 新建 - 主动纠错 |
| CAP-03 | IntentPredictor | pipeline/intent_predictor.py | 新建 - 意图预测 |
| CAP-03 | AutomatedRootCauseFixer | agent/root_cause_fixer.py | 新建 - 自动根因修复 |
| CAP-03 | SelfEvolutionLoop | agent/self_evolution_loop.py | 新建 - 自进化闭环 |

---

## 🔧 SubAgent 分派任务

### Round 1: P0 修复胶囊 (CAP-01)

**engineering_ai_engineer 任务：**
1. 创建 `pipeline/rag_verifier.py` - RAG源码验证
2. 创建 `library/backup_manager.py` - 备份恢复管理
3. 创建 `library/importance_compressor.py` - 重要性压缩

### Round 2: P1 优化胶囊 (CAP-02)

**engineering_ai_engineer 任务：**
1. 创建 `library/adaptive_scheduler.py` - 自适应压缩调度
2. 创建 `library/incremental_index.py` - 增量索引
3. 创建 `library/predictive_compressor.py` - 预测压缩

### Round 3: P2 创新胶囊 (CAP-03)

**engineering_ai_engineer 任务：**
1. 创建 `pipeline/proactive_corrector.py` - 主动纠错
2. 创建 `pipeline/intent_predictor.py` - 意图预测
3. 创建 `agent/root_cause_fixer.py` - 自动根因修复
4. 创建 `agent/self_evolution_loop.py` - 自进化闭环

### Round 4: Evaluator 审查

**testing_performance_benchmarker 任务：**
1. 验证所有新文件的语法正确性
2. 验证模块导入正确性
3. 执行基本单元测试

### Round 5: Git Commit

---

## ⏱️ 预计工时

- CAP-01 (P0): 4h
- CAP-02 (P1): 6h
- CAP-03 (P2): 8h
- 审查: 2h
- **总计: 20h**

---

## ✅ 验收标准

1. 所有新创建文件语法正确
2. 模块可正常导入
3. 基础单元测试通过
4. Git 提交成功

---

*Created: 2026-04-07 02:38 GMT+8*
*Status: IN_PROGRESS*
