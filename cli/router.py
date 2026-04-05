"""
记忆殿堂v2.0 - CLI路由系统
命令解析、参数验证、帮助系统
"""

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class ArgType(Enum):
    """参数类型枚举"""
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIST = "list"
    CHOICE = "choice"


@dataclass
class Arg:
    """CLI参数定义"""
    name: str
    arg_type: ArgType = ArgType.STRING
    required: bool = False
    default: Any = None
    choices: Optional[list] = None
    help: str = ""
    short: Optional[str] = None  # 短选项如 -n

    def validate(self, value: Any) -> tuple[bool, str]:
        """验证参数值"""
        if value is None:
            if self.required:
                return False, f"缺少必需参数: {self.name}"
            return True, ""

        if self.arg_type == ArgType.INT:
            try:
                int(value)
            except (ValueError, TypeError):
                return False, f"{self.name} 需要整数类型，实际: {type(value).__name__}"
        elif self.arg_type == ArgType.FLOAT:
            try:
                float(value)
            except (ValueError, TypeError):
                return False, f"{self.name} 需要浮点数类型，实际: {type(value).__name__}"
        elif self.arg_type == ArgType.CHOICE:
            if self.choices and value not in self.choices:
                return False, f"{self.name} 必须是 {[str(c) for c in self.choices]} 之一，实际: {value}"

        return True, ""


@dataclass
class Command:
    """CLI命令定义"""
    name: str
    handler: Callable
    args: list[Arg] = field(default_factory=list)
    help: str = ""
    description: str = ""
    aliases: list[str] = field(default_factory=list)

    def get_arg(self, name: str) -> Optional[Arg]:
        for arg in self.args:
            if arg.name == name or arg.short == name:
                return arg
        return None


@dataclass
class ParsedArgs:
    """解析后的参数容器"""
    _values: dict = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return self._values.get(key)

    def __setitem__(self, key: str, value: Any):
        self._values[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._values


class Router:
    """CLI路由器"""

    def __init__(self, prog: str = "记忆殿堂", description: str = ""):
        self.prog = prog
        self.description = description
        self.commands: dict[str, Command] = {}
        self._global_args: list[Arg] = []

    def arg(self, name: str, arg_type: ArgType = ArgType.STRING,
            required: bool = False, default: Any = None,
            choices: Optional[list] = None, help: str = "", short: Optional[str] = None):
        """装饰器：添加全局参数"""
        def decorator(func: Callable):
            arg_def = Arg(name=name, arg_type=arg_type, required=required,
                          default=default, choices=choices, help=help, short=short)
            self._global_args.append(arg_def)
            return func
        return decorator

    def command(self, name: str, help: str = "", description: str = "", aliases: list[str] = None):
        """装饰器：注册命令"""
        def decorator(func: Callable):
            cmd = Command(name=name, handler=func, help=help,
                         description=description, aliases=aliases or [])
            self.commands[name] = cmd
            # 注册别名
            for alias in cmd.aliases:
                self.commands[alias] = cmd
            return func
        return decorator

    def add_command(self, name: str, handler: Callable, args: list[Arg] = None,
                    help: str = "", description: str = "", aliases: list[str] = None):
        """程序化添加命令"""
        cmd = Command(name=name, handler=handler, args=args or [], help=help,
                     description=description, aliases=aliases or [])
        self.commands[name] = cmd
        for alias in cmd.aliases:
            self.commands[alias] = cmd

    def parse(self, raw_input: str) -> tuple[Optional[str], ParsedArgs, list[str]]:
        """
        解析CLI输入
        返回: (命令名, 解析参数, 错误列表)
        """
        errors = []
        parsed = ParsedArgs()

        # 处理空白输入
        if not raw_input.strip():
            errors.append("请输入命令")
            return None, parsed, errors

        try:
            # 使用shlex正确处理引号和转义
            tokens = shlex.split(raw_input)
        except ValueError as e:
            errors.append(f"命令解析错误: {e}")
            return None, parsed, errors

        if not tokens:
            errors.append("请输入命令")
            return None, parsed, errors

        # 第一个token是命令
        cmd_name = tokens[0]

        # 检查是否是全局选项（以--开头）
        if cmd_name.startswith("--"):
            # 全局选项模式，命令在选项之后
            pass

        # 解析参数
        i = 1
        positional_values = []
        while i < len(tokens):
            token = tokens[i]

            if token.startswith("-"):
                # 选项
                if token.startswith("--"):
                    # 长选项 --name=value 或 --name value
                    if "=" in token:
                        name, value = token[2:].split("=", 1)
                    else:
                        name = token[2:]
                        value = tokens[i + 1] if i + 1 < len(tokens) and not tokens[i + 1].startswith("-") else None
                        if value is None:
                            parsed[name] = True
                            i += 1
                            continue
                        i += 1
                    parsed[name] = self._convert_value(value)
                elif token.startswith("-"):
                    # 短选项 -n value
                    name = token[1:]
                    value = tokens[i + 1] if i + 1 < len(tokens) and not tokens[i + 1].startswith("-") else None
                    if value is None:
                        parsed[name] = True
                    else:
                        parsed[name] = self._convert_value(value)
                    i += 1
            else:
                # 位置参数
                positional_values.append(token)
            i += 1

        return cmd_name, parsed, positional_values, errors

    def _convert_value(self, value: str) -> Any:
        """转换参数值为适当类型"""
        # 布尔值
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # 整数
        try:
            return int(value)
        except (ValueError, TypeError):
            pass

        # 浮点数
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

        return value

    def validate(self, cmd_name: str, parsed: ParsedArgs) -> list[str]:
        """验证参数是否符合命令定义"""
        errors = []

        cmd = self.commands.get(cmd_name)
        if not cmd:
            return [f"未知命令: {cmd_name}"]

        # 验证必需参数
        for arg in cmd.args:
            value = parsed.get(arg.name) or parsed.get(arg.short, parsed.get(arg.name))
            if arg.required and value is None:
                errors.append(f"缺少必需参数: {arg.name}")
            elif value is not None:
                valid, msg = arg.validate(value)
                if not valid:
                    errors.append(msg)

        return errors

    def execute(self, cmd_name: str, parsed: ParsedArgs) -> Any:
        """执行命令"""
        cmd = self.commands.get(cmd_name)
        if not cmd:
            raise ValueError(f"未知命令: {cmd_name}")

        # 构建传递给handler的kwargs
        kwargs = dict(parsed._values)
        return cmd.handler(**kwargs)

    def get_help(self, cmd_name: Optional[str] = None) -> str:
        """生成帮助文本"""
        lines = []

        if cmd_name:
            # 特定命令帮助
            cmd = self.commands.get(cmd_name)
            if not cmd:
                return f"未知命令: {cmd_name}"

            lines.append(f"命令: {cmd.name}")
            if cmd.aliases:
                lines.append(f"别名: {', '.join(cmd.aliases)}")
            if cmd.description:
                lines.append(f"\n描述: {cmd.description}")
            if cmd.help:
                lines.append(f"\n用法: {cmd.help}")

            if cmd.args:
                lines.append("\n参数:")
                for arg in cmd.args:
                    required = "[必需]" if arg.required else "[可选]"
                    default = f" (默认: {arg.default})" if arg.default is not None else ""
                    choices = f" {{{', '.join(str(c) for c in arg.choices)}}}" if arg.choices else ""
                    lines.append(f"  --{arg.name} {required}{default}{choices}")
                    lines.append(f"    {arg.help}")
        else:
            # 全局帮助
            lines.append(f"{self.prog}")
            if self.description:
                lines.append(f"{self.description}")
            lines.append("\n可用命令:")

            for name, cmd in sorted(self.commands.items()):
                # 只显示主命令，不显示别名
                if name in cmd.aliases:
                    continue
                help_text = cmd.help or cmd.description or "无描述"
                lines.append(f"  {name:15} {help_text}")

            lines.append("\n使用 --help 查看特定命令帮助")
            lines.append(f"例如: {self.prog} <命令> --help")

        return "\n".join(lines)

    def run(self, raw_input: str) -> tuple[bool, Any, list[str]]:
        """
        完整运行流程：解析→验证→执行
        返回: (成功标志, 结果, 错误列表)
        """
        errors = []

        # 解析
        cmd_name, parsed, positional_values, parse_errors = self.parse(raw_input)
        errors.extend(parse_errors)

        if not cmd_name:
            return False, None, errors

        # 帮助选项
        if parsed.get("help") or parsed.get("h"):
            return True, self.get_help(cmd_name), []

        # 验证
        validate_errors = self.validate(cmd_name, parsed)
        errors.extend(validate_errors)

        if errors:
            return False, None, errors

        # 执行
        try:
            result = self.execute(cmd_name, parsed)
            return True, result, []
        except Exception as e:
            return False, None, [f"执行错误: {e}"]


# 全局路由器实例
_default_router: Optional[Router] = None


def get_router() -> Router:
    """获取全局路由器实例"""
    global _default_router
    if _default_router is None:
        _default_router = Router(prog="记忆殿堂", description="记忆殿堂v2.0 CLI")
    return _default_router


def parse_and_run(raw_input: str) -> tuple[bool, Any, list[str]]:
    """快捷函数：解析并运行命令"""
    router = get_router()
    return router.run(raw_input)
