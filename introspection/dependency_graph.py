"""
依赖关系图生成器 - Mimir-Core自我感知层 Phase 0
=====================================================
分析模块间导入关系，生成graph.dot格式的依赖图
"""

import ast
import sys
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class DependencyEdge:
    """依赖边"""
    from_module: str
    to_module: str
    import_type: str  # "import" | "from_import"


class DependencyGraph:
    """依赖关系图生成器"""
    
    def __init__(self, project_root: str = None):
        if project_root is None:
            self.project_root = Path(__file__).parent.parent.resolve()
        else:
            self.project_root = Path(project_root)
        
        self.nodes: Set[str] = set()
        self.edges: List[DependencyEdge] = []
        self.module_paths: Dict[str, Path] = {}  # 模块名 -> 文件路径
        self._internal_modules: Set[str] = set()
    
    def scan(self) -> "DependencyGraph":
        """扫描所有模块的依赖关系"""
        self.nodes.clear()
        self.edges.clear()
        self.module_paths.clear()
        self._internal_modules.clear()
        
        # 第一遍：建立所有模块路径映射
        for py_file in self.project_root.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".git" in str(py_file):
                continue
            if "introspection" in str(py_file):
                continue
            
            module_name = self._path_to_module(py_file)
            self.module_paths[module_name] = py_file
            self._internal_modules.add(module_name)
        
        # 第二遍：分析每个模块的导入
        for py_file in self.project_root.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".git" in str(py_file):
                continue
            if "introspection" in str(py_file):
                continue
            
            self._analyze_file(py_file)
        
        return self
    
    def _path_to_module(self, path: Path) -> str:
        """将文件路径转换为模块名"""
        parts = list(path.relative_to(self.project_root).parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        elif parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        return ".".join(parts)
    
    def _analyze_file(self, py_file: Path):
        """分析单个文件的导入关系"""
        current_module = self._path_to_module(py_file)
        self.nodes.add(current_module)
        
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
        except Exception:
            return
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name.split(".")[0]  # 取第一级
                    if imported in self._internal_modules:
                        self.nodes.add(imported)
                        self.edges.append(DependencyEdge(
                            from_module=current_module,
                            to_module=imported,
                            import_type="import"
                        ))
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported = node.module.split(".")[0]
                    if imported in self._internal_modules:
                        self.nodes.add(imported)
                        self.edges.append(DependencyEdge(
                            from_module=current_module,
                            to_module=imported,
                            import_type="from_import"
                        ))
    
    def to_dot(self) -> str:
        """生成graph.dot格式"""
        lines = [
            'digraph MimirCore {',
            '    rankdir=LR;',
            '    node [shape=box, style=filled, fillcolor=lightyellow];',
            '    edge [color=gray40];',
            '',
        ]
        
        # 按模块前缀分组（用于子图）
        packages: Dict[str, List[str]] = defaultdict(list)
        for node in sorted(self.nodes):
            parts = node.split(".")
            if len(parts) > 1:
                packages[parts[0]].append(node)
            else:
                packages["_root"].append(node)
        
        # 生成子图
        for package, members in sorted(packages.items()):
            if package != "_root":
                lines.append(f'    subgraph cluster_{package} {{')
                lines.append(f'        label="{package}";')
                lines.append(f'        color=lightblue;')
                for member in sorted(members):
                    safe_name = member.replace(".", "_")
                    lines.append(f'        "{member}" [label="{member}"];')
                lines.append('    }')
            else:
                for member in sorted(members):
                    lines.append(f'    "{member}" [label="{member}"];')
        
        lines.append('')
        
        # 生成边
        for edge in self.edges:
            from_safe = edge.from_module.replace(".", "_")
            to_safe = edge.to_module.replace(".", "_")
            style = 'solid' if edge.import_type == 'from_import' else 'dashed'
            lines.append(f'    "{edge.from_module}" -> "{edge.to_module}" [style={style}];')
        
        lines.append('}')
        return '\n'.join(lines)
    
    def to_mermaid(self) -> str:
        """生成Mermaid格式"""
        lines = ['erDiagram']
        
        # 按包组织
        packages: Dict[str, List[str]] = defaultdict(list)
        for node in sorted(self.nodes):
            parts = node.split(".")
            pkg = parts[0] if len(parts) > 1 else "_root"
            packages[pkg].append(node)
        
        for pkg, members in sorted(packages.items()):
            if len(members) > 1:
                lines.append(f'    {pkg} {{')
                for m in members:
                    lines.append(f'        string {m}')
                lines.append('    }')
        
        return '\n'.join(lines)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        # 计算入度和出度
        in_degree: Dict[str, int] = {n: 0 for n in self.nodes}
        out_degree: Dict[str, int] = {n: 0 for n in self.nodes}
        
        for edge in self.edges:
            out_degree[edge.from_module] = out_degree.get(edge.from_module, 0) + 1
            in_degree[edge.to_module] = in_degree.get(edge.to_module, 0) + 1
        
        # 找出核心模块（入度最高的模块）
        sorted_in = sorted(in_degree.items(), key=lambda x: -x[1])
        sorted_out = sorted(out_degree.items(), key=lambda x: -x[1])
        
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "top_depended": sorted_in[:5],  # 被依赖最多
            "top_dependent": sorted_out[:5],  # 依赖最多
        }
    
    def save_dot(self, output_path: str = None) -> str:
        """保存为.dot文件"""
        if output_path is None:
            output_path = self.project_root / "introspection" / "dependency_graph.dot"
        else:
            output_path = Path(output_path)
        
        self.scan()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_dot(), encoding="utf-8")
        return str(output_path)


def main():
    """CLI入口"""
    graph = DependencyGraph()
    dot_path = graph.save_dot()
    stats = graph.get_stats()
    
    print(f"✅ 依赖关系图生成完成")
    print(f"   总节点数: {stats['total_nodes']}")
    print(f"   总边数: {stats['total_edges']}")
    print(f"   最被依赖: {stats['top_depended'][:3]}")
    print(f"   输出: {dot_path}")
    
    return graph


if __name__ == "__main__":
    main()
