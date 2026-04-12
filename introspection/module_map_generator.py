"""
模块地图生成器 - Mimir-Core自我感知层 Phase 0
=================================================
扫描所有Python模块，提取模块名称、路径、接口（函数/类/公共API）
"""

import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class ModuleInterface:
    """模块接口信息"""
    name: str
    path: str
    relative_path: str
    classes: List[str]
    functions: List[str]
    public_api: List[str]
    imports: List[str]
    docstring: str


class ModuleMapGenerator:
    """模块地图生成器"""
    
    def __init__(self, project_root: str = None):
        if project_root is None:
            self.project_root = Path(__file__).parent.parent.resolve()
        else:
            self.project_root = Path(project_root)
        self.modules: Dict[str, ModuleInterface] = {}
    
    def scan(self) -> Dict[str, Any]:
        """扫描所有Python模块并生成地图"""
        self.modules.clear()
        
        for py_file in self.project_root.rglob("*.py"):
            # 跳过__pycache__、.git等
            if "__pycache__" in str(py_file) or ".git" in str(py_file):
                continue
            # 跳过introspection自己
            if "introspection" in str(py_file):
                continue
            
            try:
                module_info = self._analyze_module(py_file)
                if module_info:
                    self.modules[module_info.relative_path] = module_info
            except Exception as e:
                print(f"Warning: Failed to analyze {py_file}: {e}", file=sys.stderr)
        
        return self._build_map()
    
    def _analyze_module(self, py_file: Path) -> Optional[ModuleInterface]:
        """分析单个Python模块"""
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            return None
        
        relative_path = py_file.relative_to(self.project_root)
        
        try:
            tree = ast.parse(content, filename=str(py_file))
        except SyntaxError:
            return None
        
        classes = []
        functions = []
        public_api = []
        imports = []
        docstring = ast.get_docstring(tree) or ""
        
        for node in ast.iter_child_nodes(tree):
            # 类定义
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
                # 公共方法（不含下划线开头）
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                        public_api.append(f"{node.name}.{item.name}")
            
            # 函数定义
            elif isinstance(node, ast.FunctionDef):
                functions.append(node.name)
                if not node.name.startswith("_"):
                    public_api.append(node.name)
            
            # 导入语句
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        
        # 构建模块名（从路径）
        module_name = self._path_to_module_name(relative_path)
        
        return ModuleInterface(
            name=module_name,
            path=str(py_file),
            relative_path=str(relative_path),
            classes=classes,
            functions=functions,
            public_api=public_api,
            imports=imports,
            docstring=docstring[:200]  # 截取前200字符
        )
    
    def _path_to_module_name(self, path: Path) -> str:
        """将路径转换为模块名"""
        parts = list(path.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        elif parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        return ".".join(parts)
    
    def _build_map(self) -> Dict[str, Any]:
        """构建完整地图"""
        return {
            "version": "1.0.0",
            "generated_at": self._timestamp(),
            "project_root": str(self.project_root),
            "total_modules": len(self.modules),
            "modules": {k: asdict(v) for k, v in self.modules.items()},
            "summary": {
                "total_classes": sum(len(v.classes) for v in self.modules.values()),
                "total_functions": sum(len(v.functions) for v in self.modules.values()),
                "total_public_api": sum(len(v.public_api) for v in self.modules.values()),
            }
        }
    
    def _timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()
    
    def save_json(self, output_path: str = None) -> str:
        """保存为JSON文件"""
        if output_path is None:
            output_path = self.project_root / "introspection" / "module_map.json"
        else:
            output_path = Path(output_path)
        
        result = self.scan()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(output_path)


def main():
    """CLI入口"""
    generator = ModuleMapGenerator()
    output_path = generator.save_json()
    result = generator.scan()
    
    print(f"✅ 模块地图生成完成")
    print(f"   总模块数: {result['total_modules']}")
    print(f"   总类数: {result['summary']['total_classes']}")
    print(f"   总函数数: {result['summary']['total_functions']}")
    print(f"   公共API数: {result['summary']['total_public_api']}")
    print(f"   输出: {output_path}")
    
    return result


if __name__ == "__main__":
    main()
