"""
记忆殿堂 萃取模块 V3.2
智能摘要系统 - 4层压缩流水线

层级：
  L1: Token预算检查 + 快速裁剪
  L2: 结构化记忆提取（episodic/short_term/long_term分类）
  L3: 链式语义摘要merge算法
  L4: 格式化注入 + WAL协议兼容
"""

import re
import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class MemoryType(Enum):
    """记忆类型枚举"""
    EPISODIC = "episodic"       # 情景记忆 - 具体事件、对话、经历
    SHORT_TERM = "short_term"   # 短期记忆 - 当前上下文、工作记忆
    LONG_TERM = "long_term"     # 长期记忆 - 持久知识、概念、规则


@dataclass
class CompressionResult:
    """压缩结果"""
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    memory_type: MemoryType
    summary: str
    key_points: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)


class Extractor:
    """
    萃取器 V3.2
    4层压缩流水线 + LLM摘要
    """

    # 各记忆类型的压缩目标比例
    TARGET_RATIOS = {
        MemoryType.EPISODIC: 0.3,     # 情景记忆压缩到30%
        MemoryType.SHORT_TERM: 0.5,   # 短期记忆压缩到50%
        MemoryType.LONG_TERM: 0.2,    # 长期记忆压缩到20%
    }

    # 简单token估算（中文按字符计，英文按单词计）
    def estimate_tokens(self, text: str) -> int:
        """估算token数量（简单方法）"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words

    # ============ L1: Token预算检查 + 快速裁剪 ============
    def _l1_fast_prune(self, text: str, max_tokens: int) -> str:
        """L1层：快速裁剪过长的文本"""
        tokens = self.estimate_tokens(text)
        if tokens <= max_tokens:
            return text

        # 简单策略：按比例裁剪
        ratio = max_tokens / tokens
        lines = text.split('\n')
        keep_count = max(1, int(len(lines) * ratio))

        # 保留开头和关键段落
        result_lines = []
        for i, line in enumerate(lines[:keep_count]):
            result_lines.append(line)

        return '\n'.join(result_lines)

    # ============ L2: 结构化记忆提取 ============
    def _l2_structured_extract(self, text: str) -> tuple[str, MemoryType, list[str]]:
        """L2层：识别记忆类型并提取结构化信息"""
        memory_type = self._classify_memory(text)
        key_points = self._extract_key_points(text, memory_type)

        # 结构化重组
        structured = self._reconstruct_structured(text, memory_type, key_points)
        return structured, memory_type, key_points

    def _classify_memory(self, text: str) -> MemoryType:
        """根据内容特征分类记忆类型"""
        # 情景记忆特征：时间词、具体事件、对话
        episodic_patterns = [
            r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}',
            r'昨天|今天|明天|上周|下周|刚才|刚刚|刚才',
            r'说|告诉|问|答|对话|聊|谈',
            r'做了|发生|出现|遇到|见到',
        ]

        # 长期记忆特征：概念、定义、规则、原理
        long_term_patterns = [
            r'^定义：|^概念：|^原理：|^规则：',
            r'是.*的|属于|包括|分为',
            r'总是|通常|一般来说|原则上',
        ]

        episodic_score = sum(1 for p in episodic_patterns if re.search(p, text))
        long_term_score = sum(1 for p in long_term_patterns if re.search(p, text))

        if episodic_score > long_term_score:
            return MemoryType.EPISODIC
        elif long_term_score > episodic_score:
            return MemoryType.LONG_TERM
        else:
            return MemoryType.SHORT_TERM

    def _extract_key_points(self, text: str, memory_type: MemoryType) -> list[str]:
        """提取关键点"""
        key_points = []
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # 按记忆类型选择关键行
        for line in lines:
            tokens = self.estimate_tokens(line)
            if tokens < 10:  # 太短的行跳过
                continue

            if memory_type == MemoryType.EPISODIC:
                # 情景记忆：保留含时间/动作/结果的句子
                if any(k in line for k in ['做', '发生', '完成', '开始', '结束', '去了', '见了']):
                    key_points.append(line)
            elif memory_type == MemoryType.LONG_TERM:
                # 长期记忆：保留定义/规则类句子
                if any(k in line for k in ['是', '定义', '规则', '包括', '属于', '用于']):
                    key_points.append(line)
            else:
                # 短期记忆：保留中间段落
                key_points.append(line)

        return key_points[:10]  # 最多10个关键点

    def _reconstruct_structured(self, text: str, memory_type: MemoryType, key_points: list[str]) -> str:
        """重构为结构化文本"""
        lines = text.split('\n')
        non_empty = [l.strip() for l in lines if l.strip()]

        if not non_empty:
            return ""

        # 取前几段作为主体
        body = non_empty[:5]
        body_text = '\n'.join(body)

        # 添加关键点摘要
        if key_points:
            kp_section = "【要点】\n" + '\n'.join(f"- {kp}" for kp in key_points[:5])
            return f"{body_text}\n\n{kp_section}"

        return body_text

    # ============ L3: 链式语义摘要Merge ============
    def _l3_semantic_merge(self, structured_text: str, memory_type: MemoryType, 
                           original_tokens: int) -> str:
        """L3层：语义合并摘要（模拟LLM摘要）"""
        target_tokens = int(original_tokens * self.TARGET_RATIOS[memory_type])

        # 简单merge策略：分段+重组
        sentences = re.split(r'[。！？\n]+', structured_text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return structured_text

        # 按重要性排序（长度作为代理指标）
        scored = [(s, self.estimate_tokens(s)) for s in sentences]
        scored.sort(key=lambda x: -x[1])  # 长的优先

        # 选择最重要的句子
        result = []
        current_tokens = 0
        for sent, tokens in scored:
            if current_tokens + tokens <= target_tokens:
                result.append(sent)
                current_tokens += tokens
            if current_tokens >= target_tokens * 0.8:
                break

        # 重组
        summary = '。'.join(result)
        if summary and not summary.endswith('。'):
            summary += '。'

        return summary if summary else structured_text[:target_tokens*2]

    # ============ L4: 格式化注入 + WAL协议兼容 ============
    def _l4_format_inject(self, summary: str, memory_type: MemoryType,
                          key_points: list[str], metadata: dict) -> str:
        """L4层：格式化输出，注入WAL协议元数据"""
        # 生成ID
        content_hash = hashlib.md5(summary.encode()).hexdigest()[:8]

        # 构建输出
        output_parts = [
            f"# 萃取摘要 [{memory_type.value}]",
            f"ID: {content_hash}",
            "",
            "## 摘要",
            summary,
            "",
        ]

        if key_points:
            output_parts.extend([
                "## 关键点",
                *[f"- {kp}" for kp in key_points[:5]],
                "",
            ])

        # WAL协议元数据
        wal_meta = {
            "type": memory_type.value,
            "version": "3.2.0",
            "timestamp": metadata.get("timestamp", ""),
            "source": metadata.get("source", "unknown"),
        }
        output_parts.extend([
            "## WAL元数据",
            "```json",
            json.dumps(wal_meta, ensure_ascii=False, indent=2),
            "```",
        ])

        return '\n'.join(output_parts)

    # ============ 主萃取流程 ============
    def extract(self, text: str, max_tokens: int = 4000,
                use_llm: bool = False, llm_client: Optional[object] = None,
                metadata: dict = None) -> CompressionResult:
        """
        执行4层萃取流程

        Args:
            text: 待萃取文本
            max_tokens: 最大token数限制
            use_llm: 是否使用LLM进行摘要（需要提供llm_client）
            llm_client: LLM客户端（需实现 call(prompt) -> str）
            metadata: 附加元数据

        Returns:
            CompressionResult: 萃取结果
        """
        metadata = metadata or {}
        original_tokens = self.estimate_tokens(text)

        # L1: 快速裁剪
        pruned = self._l1_fast_prune(text, max_tokens)

        # L2: 结构化提取
        structured, memory_type, key_points = self._l2_structured_extract(pruned)

        # L3: 语义合并
        if use_llm and llm_client:
            # 真实LLM调用
            prompt = self._build_llm_prompt(structured, memory_type)
            summary = llm_client.call(prompt)
        else:
            # 本地merge
            summary = self._l3_semantic_merge(structured, memory_type, original_tokens)

        # L4: 格式化输出
        final_output = self._l4_format_inject(summary, memory_type, key_points, metadata)

        compressed_tokens = self.estimate_tokens(final_output)

        return CompressionResult(
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 1.0,
            memory_type=memory_type,
            summary=summary,
            key_points=key_points,
            confidence=0.85 if not use_llm else 0.95,
            metadata={
                **metadata,
                "memory_type": memory_type.value,
                "layers_used": ["L1", "L2", "L3", "L4"],
            }
        )

    def _build_llm_prompt(self, text: str, memory_type: MemoryType) -> str:
        """构建LLM摘要提示词"""
        type_hints = {
            MemoryType.EPISODIC: "提取事件、动作、结果等关键情节",
            MemoryType.SHORT_TERM: "保留核心信息和上下文",
            MemoryType.LONG_TERM: "保留定义、规则、核心概念",
        }

        return f"""请对以下{memory_type.value}类型记忆进行精简摘要：

要求：{type_hints[memory_type]}
输出格式：简洁的摘要段落

内容：
{text}

摘要："""

    # ============ 批量处理 ============
    def extract_batch(self, texts: list[str], max_tokens: int = 4000,
                      use_llm: bool = False, llm_client: Optional[object] = None,
                      metadata: dict = None) -> list[CompressionResult]:
        """
        批量萃取多个文本

        Args:
            texts: 文本列表
            max_tokens: 每个文本的最大token数
            use_llm: 是否使用LLM
            llm_client: LLM客户端
            metadata: 附加元数据

        Returns:
            list[CompressionResult]: 萃取结果列表
        """
        results = []
        for i, text in enumerate(texts):
            item_meta = {**(metadata or {}), "batch_index": i}
            result = self.extract(
                text, max_tokens, use_llm, llm_client, item_meta
            )
            results.append(result)

        return results

    # ============ 便捷方法 ============
    def extract_episodic(self, text: str, **kwargs) -> CompressionResult:
        """快速萃取情景记忆"""
        return self.extract(text, memory_type=MemoryType.EPISODIC, **kwargs)

    def extract_short_term(self, text: str, **kwargs) -> CompressionResult:
        """快速萃取短期记忆"""
        return self.extract(text, memory_type=MemoryType.SHORT_TERM, **kwargs)

    def extract_long_term(self, text: str, **kwargs) -> CompressionResult:
        """快速萃取长期记忆"""
        return self.extract(text, memory_type=MemoryType.LONG_TERM, **kwargs)


# ============ LLM客户端示例 ============
class SimpleLLMClient:
    """简单的LLM客户端封装（需根据实际API实现）"""

    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.model = model

    def call(self, prompt: str) -> str:
        """
        调用LLM API
        实际实现需要接入具体API（如OpenAI、Claude等）
        """
        # 占位实现
        raise NotImplementedError(
            "请实现具体的LLM API调用逻辑，"
            "或使用本地merge模式（use_llm=False）"
        )


# ============ 直接执行入口 ============
if __name__ == "__main__":
    # 测试代码
    extractor = Extractor()

    test_text = """
    2024年3月15日，我去了深圳出差。

    上午10点，我到了客户公司，见了王总。
    王总说他们公司今年要上线新系统，需要我们的数据库优化服务。
    中午和王总一起吃了饭，聊了很多技术细节。

    下午2点，我给客户的技术团队做了一个技术分享。
    介绍了我们最新的分布式数据库方案。
    客户很感兴趣，说下周安排测试环境。

    下午5点，我离开了客户公司。
    这次出差收获很大，王总表示会考虑和我们长期合作。
    """

    print("=" * 60)
    print("测试萃取模块 V3.2")
    print("=" * 60)

    result = extractor.extract(test_text, max_tokens=500)

    print(f"\n原始Token数: {result.original_tokens}")
    print(f"压缩后Token数: {result.compressed_tokens}")
    print(f"压缩比: {result.compression_ratio:.2%}")
    print(f"记忆类型: {result.memory_type.value}")
    print(f"置信度: {result.confidence}")
    print(f"\n摘要:\n{result.summary}")
    print(f"\n关键点:")
    for kp in result.key_points:
        print(f"  - {kp}")

    print("\n" + "=" * 60)
    print("批量处理测试")
    print("=" * 60)

    batch_results = extractor.extract_batch(
        [test_text, test_text.replace("深圳", "广州")],
        max_tokens=500
    )

    for i, r in enumerate(batch_results):
        print(f"\n[批次 {i}] {r.memory_type.value} | 压缩比: {r.compression_ratio:.2%}")
