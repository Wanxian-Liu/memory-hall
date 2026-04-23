"""
记忆殿堂v2.0 - DeepSeek LLM 共享客户端
单例模式 + 线程安全 + 请求队列 + 重试逻辑
"""

import os
import time
import threading
import queue
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
import json

# 延迟导入openai，避免未安装时出错
try:
    from openai import OpenAI
    from openai import APIError, RateLimitError, Timeout
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class LLMConfig:
    """LLM配置数据类"""
    provider: str = "deepseek"
    api_key_env: str = "DEEPSEEK_API_KEY"
    model: str = "kimi-k2.5"  # Moonshot Kimi K2.5
    base_url: str = "https://api.moonshot.cn/v1"  # Moonshot Kimi K2.5
    timeout: int = 30
    max_retries: int = 3
    retry_backoff: float = 1.5
    rate_limit: int = 60


class RateLimiter:
    """简单的令牌桶限流器"""
    def __init__(self, rate: int):
        self.rate = rate
        self.interval = 60.0 / rate  # 每分钟rate个请求
        self.lock = threading.Lock()
        self.last_request = 0.0

    def acquire(self):
        """获取令牌，阻塞直到可用"""
        with self.lock:
            now = time.time()
            wait_time = self.last_request + self.interval - now
            if wait_time > 0:
                time.sleep(wait_time)
            self.last_request = time.time()


class DeepSeekClient:
    """
    DeepSeek LLM 单例客户端
    
    特性:
    - 单例模式：全局唯一实例
    - 线程安全：使用锁保护并发访问
    - 环境变量读取API Key
    - 请求队列和限流
    - 自动重试（指数退避）
    """
    
    _instance: Optional['DeepSeekClient'] = None
    _lock = threading.Lock()
    
    def __new__(cls, config: Optional[LLMConfig] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config: Optional[LLMConfig] = None):
        if self._initialized:
            return
        
        self._initialized = True
        self._config = config or self._load_config()
        self._client: Optional[OpenAI] = None
        self._client_lock = threading.Lock()
        
        # 清除代理设置（避免代理干扰）
        for var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
            os.environ.pop(var, None)
        
        # 初始化限流器
        self._rate_limiter = RateLimiter(self._config.rate_limit)
        
        # 请求队列（用于批量处理）
        self._request_queue: queue.Queue = queue.Queue()
        self._queue_worker: Optional[threading.Thread] = None
        self._worker_running = False
    
    def _load_config(self) -> LLMConfig:
        """从YAML配置文件加载配置"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "llm_config.yaml"
        )
        
        if os.path.exists(config_path):
            try:
                import yaml
                with open(config_path, 'r') as f:
                    data = yaml.safe_load(f)
                llm_data = data.get('llm', {})
                return LLMConfig(
                    provider=llm_data.get('provider', 'deepseek'),
                    api_key_env=llm_data.get('api_key_env', 'DEEPSEEK_API_KEY'),
                    model=llm_data.get('model', 'deepseek-chat'),
                    base_url=llm_data.get('base_url', 'https://api.deepseek.com/v1'),
                    timeout=llm_data.get('timeout', 30),
                    max_retries=llm_data.get('max_retries', 3),
                    retry_backoff=llm_data.get('retry_backoff', 1.5),
                    rate_limit=llm_data.get('rate_limit', 60),
                )
            except ImportError:
                # 没有yaml库，使用默认值
                pass
        
        return LLMConfig()
    
    def _get_client(self) -> Any:
        """获取或创建OpenAI客户端（懒加载）"""
        if not OPENAI_AVAILABLE:
            return None
        
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    api_key = os.environ.get(self._config.api_key_env)
                    if not api_key:
                        # 尝试从配置文件读取（仅作为后备）
                        raise ValueError(f"API Key not found in environment variable {self._config.api_key_env}. Please set it before using.")
                    
                    self._client = OpenAI(
                        api_key=api_key,
                        base_url=self._config.base_url,
                        timeout=self._config.timeout,
                    )
        return self._client
    
    def _retry_with_backoff(self, func, *args, **kwargs) -> Any:
        """带指数退避的重试逻辑"""
        last_exception = None
        for attempt in range(self._config.max_retries):
            try:
                return func(*args, **kwargs)
            except (APIError, RateLimitError, Timeout) as e:
                last_exception = e
                if attempt < self._config.max_retries - 1:
                    wait_time = self._config.retry_backoff ** attempt
                    time.sleep(wait_time)
                    continue
                raise
        
        if last_exception:
            raise last_exception
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送chat请求
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model: 模型名称（默认使用配置中的模型）
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他OpenAI参数
        
        Returns:
            API响应字典
        """
        self._rate_limiter.acquire()
        
        client = self._get_client()
        if client is None:
            return {
                "error": "OpenAI client not available. Install with: pip install openai"
            }
        
        def _do_chat():
            return client.chat.completions.create(
                model=model or self._config.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        
        response = self._retry_with_backoff(_do_chat)
        return response.model_dump() if hasattr(response, 'model_dump') else response
    
    def completion(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送completion请求（兼容旧接口）
        
        Args:
            prompt: 提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
        
        Returns:
            API响应字典
        """
        messages = [{"role": "user", "content": prompt}]
        return self.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    @property
    def config(self) -> LLMConfig:
        """获取当前配置"""
        return self._config
    
    def set_api_key(self, api_key: str):
        """手动设置API Key（会覆盖环境变量）"""
        with self._client_lock:
            self._client = OpenAI(
                api_key=api_key,
                base_url=self._config.base_url,
                timeout=self._config.timeout,
            )


def get_client() -> DeepSeekClient:
    """获取DeepSeek客户端单例"""
    return DeepSeekClient()


# ==================== 测试代码 ====================
if __name__ == "__main__":
    print("🧪 记忆殿堂v2.0 - DeepSeek LLM 客户端测试")
    print("=" * 50)
    
    # 从环境变量读取API Key
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set")
    
    client = get_client()
    print(f"配置: {client.config}")
    print()
    
    # 测试chat调用
    print("📤 发送测试请求...")
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": "你是记忆殿堂的AI助手"},
                {"role": "user", "content": "你好，简单介绍一下自己"}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        if "error" in response:
            print(f"❌ 错误: {response['error']}")
        else:
            print("✅ API调用成功!")
            print(f"📥 响应: {response}")
            # 提取回复内容
            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]
                print(f"\n💬 AI回复: {content}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
