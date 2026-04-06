"""
上下文压缩模块 - 精简自Claude Code compact.rs

实现5层压缩体系：
- L1: Tool Result Budget (限制工具结果大小)
- L2: Snip Compact (删除旧对话历史)
- L3: Microcompact (缓存工具结果到磁盘)
- L4: Context Collapse (将消息组归档为摘要)
- L5: Autocompact (LLM全量摘要)
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import re


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class CompactionConfig:
    """压缩配置"""
    preserve_recent_messages: int = 4  # 保留最近消息数
    max_estimated_tokens: int = 10000  # 最大token阈值
    max_summary_chars: int = 1200      # 摘要最大字符数
    max_summary_lines: int = 24        # 摘要最大行数


@dataclass
class CompactionResult:
    """压缩结果"""
    summary: str
    formatted_summary: str
    compacted_messages: list
    removed_message_count: int


@dataclass
class Message:
    """简化的消息结构"""
    role: str  # system, user, assistant
    content: str
    tool_calls: Optional[list] = None
    tool_results: Optional[list] = None
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================================================
# 核心函数
# ============================================================================

def estimate_message_tokens(message: Message) -> int:
    """估算单条消息的token数（粗略估算：中文约2字符=1token，英文约4字符=1token）"""
    content = message.content or ""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    other_chars = len(content) - chinese_chars
    return chinese_chars // 2 + other_chars // 4 + 10  # 基础开销10


def estimate_session_tokens(messages: list) -> int:
    """估算会话的总token数"""
    return sum(estimate_message_tokens(msg) for msg in messages)


def should_compact(messages: list, config: CompactionConfig) -> bool:
    """判断是否需要压缩"""
    if len(messages) <= config.preserve_recent_messages:
        return False
    
    # 计算可压缩的部分（排除已有摘要和最近保留消息）
    start = _get_compactable_start(messages)
    # 排除最近保留的消息
    keep_from = max(len(messages) - config.preserve_recent_messages, start)
    compactable = messages[start:keep_from]
    
    return estimate_session_tokens(compactable) >= config.max_estimated_tokens


def _get_compactable_start(messages: list) -> int:
    """获取可压缩消息的起始位置"""
    # 检查首条消息是否已包含摘要
    if messages and _has_existing_summary(messages[0]):
        return 1  # 跳过摘要消息
    return 0


def _has_existing_summary(message: Message) -> bool:
    """检查消息是否包含已有摘要"""
    content = message.content or ""
    return "<summary>" in content and "</summary>" in content


# ============================================================================
# 摘要生成
# ============================================================================

def summarize_messages(messages: list) -> str:
    """生成消息摘要"""
    if not messages:
        return ""
    
    # 统计消息类型
    tool_names = set()
    user_requests = []
    key_files = set()
    decisions = []
    
    for msg in messages:
        content = msg.content or ""
        role = msg.role
        
        # 提取工具调用
        if msg.tool_calls:
            for tc in msg.tool_calls:
                if isinstance(tc, dict) and 'name' in tc:
                    tool_names.add(tc['name'])
                elif hasattr(tc, 'name'):
                    tool_names.add(tc.name)
        
        # 提取用户请求
        if role == "user" and content:
            # 取前100字符作为请求摘要
            user_requests.append(content[:100])
        
        # 提取关键文件引用
        for match in re.finditer(r'[\w./]+\.(py|rs|js|ts|md|txt)', content):
            key_files.add(match.group())
        
        # 提取决策（以"决定"、"选择"、"采用"开头的句子）
        for line in content.split('\n'):
            if any(line.startswith(p) for p in ["决定", "选择", "采用", "选用"]):
                decisions.append(line[:80])
    
    # 构建摘要
    summary_parts = []
    
    if tool_names:
        summary_parts.append(f"使用的工具: {', '.join(sorted(tool_names))}")
    
    if user_requests:
        summary_parts.append(f"用户请求: {'; '.join(user_requests[-3:])}")
    
    if key_files:
        summary_parts.append(f"关键文件: {', '.join(sorted(key_files)[:10])}")
    
    if decisions:
        summary_parts.append(f"决策: {'; '.join(decisions[-3:])}")
    
    summary_parts.append(f"消息数: {len(messages)}")
    
    return "\n".join(summary_parts)


def merge_compact_summaries(existing: Optional[str], new: str) -> str:
    """合并新旧摘要"""
    if not existing:
        return new
    
    # 提取现有摘要的关键信息
    lines = existing.split('\n')
    merged = []
    
    for line in lines:
        # 保留范围和关键文件信息
        if any(line.startswith(p) for p in ["使用的工具", "关键文件", "范围"]):
            continue  # 这些会被新摘要替换
        merged.append(line)
    
    # 添加新摘要（去重）
    for line in new.split('\n'):
        if line not in merged:
            merged.append(line)
    
    return "\n".join(merged)


# ============================================================================
# 格式化与压缩
# ============================================================================

def format_compact_summary(summary: str) -> str:
    """格式化压缩摘要为用户可读形式"""
    if not summary:
        return ""
    
    # 移除analysis标签块
    content = re.sub(r'<analysis>.*?</analysis>', '', summary, flags=re.DOTALL)
    
    # 提取summary标签内容
    match = re.search(r'<summary>(.*?)</summary>', content, re.DOTALL)
    if match:
        content = match.group(1).strip()
        return f"Summary:\n{content}"
    
    return content.strip()


def compress_summary_text(text: str, budget: CompactionConfig) -> str:
    """
    文本摘要压缩 - 基于Claude Code summary_compression.rs
    
    策略:
    1. 行内空白折叠
    2. 去重（相同内容忽略大小写）
    3. 优先级选择: P0>核心详情 > P1>标题 > P2>列表项 > P3>其他
    4. 截断超长行
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    
    # P0: 核心详情行
    P0_PATTERNS = ["Scope:", "Current work:", "Pending work:", "使用的工具:", "关键文件:"]
    # P1: 章节标题
    P1_PATTERNS = ["##", "###", "**"]
    # P2: 列表项
    P2_PATTERNS = ["- ", "* ", "1. ", "2. ", "3. "]
    
    def line_priority(line: str) -> int:
        stripped = line.strip()
        if any(stripped.startswith(p) for p in P0_PATTERNS):
            return 0
        if any(stripped.startswith(p) for p in P1_PATTERNS):
            return 1
        if any(stripped.startswith(p) for p in P2_PATTERNS):
            return 2
        return 3
    
    # 折叠空白
    normalized = []
    seen = set()
    for line in lines:
        # 折叠连续空白
        collapsed = re.sub(r'\s+', ' ', line)
        # 去重
        lower = collapsed.lower()
        if lower not in seen:
            seen.add(lower)
            normalized.append(collapsed)
    
    # 按优先级选择
    selected = []
    total_chars = 0
    
    for priority in range(4):
        for line in normalized:
            p = line_priority(line)
            if p != priority:
                continue
            if line in selected:
                continue
            
            line_chars = len(line)
            # 检查是否超出预算
            if (len(selected) + 1 <= budget.max_lines and 
                total_chars + line_chars + 1 <= budget.max_chars):
                selected.append(line)
                total_chars += line_chars + 1
    
    # 截断超长行
    result = []
    for line in selected:
        if len(line) > budget.max_summary_chars:
            line = line[:budget.max_summary_chars - 3] + "..."
        result.append(line)
    
    return "\n".join(result)


# ============================================================================
# 会话压缩
# ============================================================================

def compact_session(messages: list, config: Optional[CompactionConfig] = None) -> CompactionResult:
    """压缩会话：保留摘要和最近消息"""
    if config is None:
        config = CompactionConfig()
    
    if not should_compact(messages, config):
        return CompactionResult(
            summary="",
            formatted_summary="",
            compacted_messages=messages.copy(),
            removed_message_count=0,
        )
    
    # 获取已有摘要
    existing_summary = None
    compacted_prefix_len = 0
    if messages and _has_existing_summary(messages[0]):
        existing_summary = _extract_summary_content(messages[0])
        compacted_prefix_len = 1
    
    # 确定保留范围
    keep_from = max(len(messages) - config.preserve_recent_messages, compacted_prefix_len)
    removed = messages[compacted_prefix_len:keep_from]
    preserved = messages[keep_from:]
    
    # 生成新摘要
    new_summary = summarize_messages(removed)
    summary = merge_compact_summaries(existing_summary, new_summary)
    formatted_summary = format_compact_summary(summary)
    
    # 构建压缩后的系统消息
    continuation = _build_continuation_message(summary, bool(preserved))
    
    # 构建新的消息列表
    compacted = [Message(role="system", content=continuation)] + preserved
    
    return CompactionResult(
        summary=summary,
        formatted_summary=formatted_summary,
        compacted_messages=compacted,
        removed_message_count=len(removed),
    )


def _extract_summary_content(message: Message) -> str:
    """从系统消息中提取摘要内容"""
    content = message.content or ""
    match = re.search(r'Summary:\n(.*?)(?:\n\n|$)', content, re.DOTALL)
    if match:
        return match.group(1)
    return content


def _build_continuation_message(summary: str, recent_preserved: bool) -> str:
    """构建压缩后的继续消息"""
    preamble = ("This session is being continued from a previous conversation "
                "that ran out of context. The summary below covers the earlier "
                "portion of the conversation.\n\n")
    
    formatted = format_compact_summary(summary)
    
    parts = [preamble, formatted]
    
    if recent_preserved:
        parts.append("\n\nRecent messages are preserved verbatim.")
    
    parts.append("\n\nContinue the conversation from where it left off without "
                 "asking the user any further questions. Resume directly.")
    
    return "".join(parts)
