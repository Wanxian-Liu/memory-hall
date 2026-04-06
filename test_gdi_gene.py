#!/usr/bin/env python3
"""
记忆殿堂v2.0 GDI评分与基因图谱测试
验证: gdi_scorer.py, gene_mapper.py, capsule_generator.py
"""

import sys
import time


def test_gdi_scorer():
    """测试GDI评分器"""
    from gdi_scorer import GDIScorer, GDIResult, CapsuleType
    
    print("=" * 60)
    print("测试 GDI评分器")
    print("=" * 60)
    
    scorer = GDIScorer()
    
    # 测试用例1: 正常胶囊
    capsule1 = {
        "id": "test_001",
        "content": """
## Python装饰器使用指南

### 功能特点
1. 函数增强
2. 链式调用
3. 参数传递

### 用法示例
```python
def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"耗时: {time.time() - start}")
        return result
    return wrapper
```

### 注意事项
- 装饰器顺序很重要
- 被装饰的函数签名可能改变
""",
        "taxonomy_tags": ["python", "decorator", "best-practice"],
        "knowledge_type": {"type": "skill", "confidence": 0.9},
        "memory_type": "long_term",
        "related_capsules": [{"id": "ref_001"}, {"id": "ref_002"}],
        "metadata": {
            "created_at": time.time() - 3600,  # 1小时前
            "retrieval_count": 50,
            "task_usage_count": 10,
            "update_count": 3
        }
    }
    
    result1 = scorer.score(capsule1)
    print(f"\n[测试1] 正常胶囊评分")
    print(f"  GDI_intrinsic: {result1.intrinsic:.3f}")
    print(f"  GDI_usage: {result1.usage:.3f}")
    print(f"  GDI_social: {result1.social:.3f}")
    print(f"  GDI_freshness: {result1.freshness:.3f}")
    print(f"  GDI_total: {result1.total:.3f}")
    print(f"  should_publish: {result1.should_publish()}")
    
    assert result1.total > 0, "总分应该大于0"
    assert result1.should_publish(), "正常胶囊应该发布"
    
    # 测试用例2: 短内容胶囊
    capsule2 = {
        "id": "test_002",
        "content": "短内容",
        "taxonomy_tags": [],
        "knowledge_type": {},
        "memory_type": "unknown",
        "related_capsules": [],
        "metadata": {
            "created_at": time.time() - 86400 * 60  # 60天前
        }
    }
    
    result2 = scorer.score(capsule2)
    print(f"\n[测试2] 短内容胶囊评分")
    print(f"  GDI_total: {result2.total:.3f}")
    print(f"  should_publish: {result2.should_publish()}")
    
    assert result2.total < result1.total, "短内容分数应低于正常内容"
    
    # 测试用例3: 批量评分
    results = scorer.score_batch([capsule1, capsule2])
    print(f"\n[测试3] 批量评分: {len(results)} 个胶囊")
    assert len(results) == 2, "批量评分应该返回2个结果"
    
    # 测试用例4: 阈值过滤
    filtered = scorer.filter_by_threshold([capsule1, capsule2], threshold=0.5)
    print(f"\n[测试4] 阈值过滤: 通过 {len(filtered)}/{2} 个胶囊")
    
    print("\n✅ GDI评分器测试通过!")
    return True


def test_gene_mapper():
    """测试基因图谱映射器"""
    from gene_mapper import GeneMapper, GeneType, CapsuleType
    
    print("\n" + "=" * 60)
    print("测试 基因图谱映射器")
    print("=" * 60)
    
    mapper = GeneMapper()
    
    # 测试用例1: 问题信号
    print("\n[测试1] 问题信号提取")
    signals1 = mapper.extract_signals("程序报错了，错误信息是 KeyError")
    print(f"  检测到 {len(signals1)} 个信号")
    for s in signals1[:3]:
        print(f"    - {s.signal_type}: {s.raw_signal} (置信度: {s.confidence})")
    
    result1 = mapper.match_gene("程序报错了，错误信息是 KeyError")
    print(f"  匹配基因: {result1.gene_type.value}")
    print(f"  置信度: {result1.confidence:.2f}")
    print(f"  推理: {result1.reasoning}")
    assert result1.gene_type == GeneType.REPAIR, "应该匹配REPAIR基因"
    
    # 测试用例2: 优化信号
    print("\n[测试2] 优化信号提取")
    result2 = mapper.match_gene("需要优化性能，提升处理速度")
    print(f"  匹配基因: {result2.gene_type.value}")
    print(f"  推理: {result2.reasoning}")
    assert result2.gene_type == GeneType.OPTIMIZE, "应该匹配OPTIMIZE基因"
    
    # 测试用例3: 创新信号
    print("\n[测试3] 创新信号提取")
    result3 = mapper.match_gene("需要设计一个新功能，实现自动化")
    print(f"  匹配基因: {result3.gene_type.value}")
    print(f"  推理: {result3.reasoning}")
    assert result3.gene_type == GeneType.INNOVATE, "应该匹配INNOVATE基因"
    
    # 测试用例4: 胶囊类型选择
    print("\n[测试4] 胶囊类型选择")
    cap_type, gene_match = mapper.select_capsule_type("数据库连接失败，需要修复")
    print(f"  选择胶囊: {cap_type.value}")
    assert cap_type == CapsuleType.REPAIR, "应该选择REPAIR胶囊"
    
    # 测试用例5: 无信号默认
    print("\n[测试5] 无信号情况")
    result5 = mapper.match_gene("今天天气不错")
    print(f"  匹配基因: {result5.gene_type.value} (默认)")
    assert result5.gene_type == GeneType.INNOVATE, "无信号应使用默认INNOVATE"
    
    print("\n✅ 基因图谱映射器测试通过!")
    return True


def test_capsule_generator():
    """测试胶囊生成器"""
    from capsule_generator import CapsuleGenerator, CapsuleType
    
    print("\n" + "=" * 60)
    print("测试 胶囊生成器")
    print("=" * 60)
    
    generator = CapsuleGenerator()
    
    # 测试用例1: 自动判断胶囊类型
    print("\n[测试1] 自动判断胶囊类型")
    result1 = generator.generate_and_evaluate(
        "程序崩溃了，显示 Segmentation Fault",
        auto_publish=True
    )
    print(f"  胶囊ID: {result1['capsule'].id}")
    print(f"  胶囊类型: {result1['capsule'].capsule_type}")
    print(f"  基因类型: {result1['capsule'].gene_type}")
    print(f"  GDI总分: {result1['gdi_score'].total:.3f}")
    print(f"  应发布: {result1['should_publish']}")
    print(f"  原因: {result1['reason']}")
    assert result1['capsule'].capsule_type == "repair", "应该生成repair胶囊"
    
    # 测试用例2: 优化胶囊
    print("\n[测试2] 优化胶囊生成")
    result2 = generator.generate_and_evaluate(
        "需要优化API响应速度",
        auto_publish=True
    )
    print(f"  胶囊类型: {result2['capsule'].capsule_type}")
    assert result2['capsule'].capsule_type == "optimize", "应该生成optimize胶囊"
    
    # 测试用例3: 创新胶囊
    print("\n[测试3] 创新胶囊生成")
    result3 = generator.generate_and_evaluate(
        "探索新的机器学习方案",
        auto_publish=True
    )
    print(f"  胶囊类型: {result3['capsule'].capsule_type}")
    assert result3['capsule'].capsule_type == "innovate", "应该生成innovate胶囊"
    
    # 测试用例4: 指定胶囊类型
    print("\n[测试4] 指定胶囊类型")
    result4 = generator.generate(
        "随便输入一些内容",
        capsule_type=CapsuleType.REPAIR
    )
    print(f"  指定类型: {result4.capsule_type}")
    assert result4.capsule_type == "repair", "应该使用指定的repair类型"
    
    # 测试用例5: 胶囊转字典
    print("\n[测试5] 胶囊序列化")
    capsule_dict = result1['capsule'].to_dict()
    print(f"  序列化键: {list(capsule_dict.keys())}")
    assert "id" in capsule_dict, "应该包含id字段"
    assert "content" in capsule_dict, "应该包含content字段"
    assert "gdi_score" in capsule_dict, "应该包含gdi_score字段"
    
    print("\n✅ 胶囊生成器测试通过!")
    return True


def test_integration():
    """集成测试"""
    from gdi_scorer import GDIScorer
    from gene_mapper import GeneMapper
    from capsule_generator import CapsuleGenerator
    
    print("\n" + "=" * 60)
    print("测试 集成流程")
    print("=" * 60)
    
    # 创建组件
    scorer = GDIScorer()
    mapper = GeneMapper()
    generator = CapsuleGenerator(gene_mapper=mapper, gdi_scorer=scorer)
    
    # 完整流程
    print("\n[集成] 完整流程测试")
    input_text = "优化数据库查询性能，减少响应时间"
    
    # 1. 基因匹配
    gene_match = mapper.match_gene(input_text)
    print(f"  1. 基因匹配: {gene_match.gene_type.value} (置信度: {gene_match.confidence:.2f})")
    
    # 2. 胶囊生成
    capsule = generator.generate(input_text)
    print(f"  2. 胶囊生成: {capsule.id}")
    print(f"     类型: {capsule.capsule_type}")
    print(f"     基因: {capsule.gene_type}")
    
    # 3. GDI评分
    gdi_result = scorer.score(capsule.to_dict())
    print(f"  3. GDI评分: {gdi_result.total:.3f} (发布: {gdi_result.should_publish()})")
    
    print("\n✅ 集成测试通过!")
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("记忆殿堂v2.0 GDI评分与基因图谱模块测试")
    print("=" * 60)
    
    try:
        test_gdi_scorer()
        test_gene_mapper()
        test_capsule_generator()
        test_integration()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 异常错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
