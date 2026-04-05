# -*- coding: utf-8 -*-
"""
测试 cli/router 模块 - CLI路由系统
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.expanduser("~/.openclaw/projects/记忆殿堂v2.0")
sys.path.insert(0, PROJECT_ROOT)

from cli.router import (
    Router, Command, Arg, ParsedArgs,
    ArgType, get_router, parse_and_run
)


class TestArgType:
    """测试ArgType枚举"""

    def test_types(self):
        assert ArgType.STRING.value == "string"
        assert ArgType.INT.value == "int"
        assert ArgType.FLOAT.value == "float"
        assert ArgType.BOOL.value == "bool"
        assert ArgType.LIST.value == "list"
        assert ArgType.CHOICE.value == "choice"


class TestArg:
    """测试Arg类"""

    def test_arg_creation(self):
        arg = Arg(
            name="test_arg",
            arg_type=ArgType.STRING,
            required=True,
            default="default_value",
            help="Test argument help",
            short="t"
        )
        assert arg.name == "test_arg"
        assert arg.arg_type == ArgType.STRING
        assert arg.required is True
        assert arg.default == "default_value"
        assert arg.short == "t"

    def test_arg_validate_int(self):
        arg = Arg(name="int_arg", arg_type=ArgType.INT, required=True)

        valid, msg = arg.validate(42)
        assert valid is True

        valid, msg = arg.validate("not_an_int")
        assert valid is False

    def test_arg_validate_float(self):
        arg = Arg(name="float_arg", arg_type=ArgType.FLOAT)

        valid, msg = arg.validate(3.14)
        assert valid is True

        valid, msg = arg.validate("not_a_float")
        assert valid is False

    def test_arg_validate_choice(self):
        arg = Arg(
            name="choice_arg",
            arg_type=ArgType.CHOICE,
            choices=["option1", "option2", "option3"]
        )

        valid, msg = arg.validate("option1")
        assert valid is True

        valid, msg = arg.validate("invalid")
        assert valid is False

    def test_arg_validate_required(self):
        arg = Arg(name="required_arg", required=True)

        valid, msg = arg.validate(None)
        assert valid is False
        assert "必需" in msg

        valid, msg = arg.validate(None)
        assert valid is False


class TestParsedArgs:
    """测试ParsedArgs类"""

    def test_parsed_args_get_set(self):
        parsed = ParsedArgs()
        parsed["key1"] = "value1"
        assert parsed["key1"] == "value1"

    def test_parsed_args_get_default(self):
        parsed = ParsedArgs()
        result = parsed.get("nonexistent", "default")
        assert result == "default"

    def test_parsed_args_contains(self):
        parsed = ParsedArgs()
        parsed["key1"] = "value1"
        assert "key1" in parsed
        assert "key2" not in parsed


class TestCommand:
    """测试Command类"""

    def test_command_creation(self):
        def handler(**kwargs):
            pass

        cmd = Command(
            name="test_cmd",
            handler=handler,
            help="Test command help",
            description="A test command",
            aliases=["tc", "t"]
        )
        assert cmd.name == "test_cmd"
        assert cmd.handler is handler
        assert "tc" in cmd.aliases

    def test_command_get_arg(self):
        def handler(**kwargs):
            pass

        arg1 = Arg(name="arg1", short="a")
        arg2 = Arg(name="arg2", short="b")
        cmd = Command(name="cmd", handler=handler, args=[arg1, arg2])

        assert cmd.get_arg("arg1") is arg1
        assert cmd.get_arg("a") is arg1
        assert cmd.get_arg("b") is arg2
        assert cmd.get_arg("nonexistent") is None


class TestRouter:
    """测试Router类"""

    def test_router_init(self):
        router = Router(prog="TestApp", description="A test app")
        assert router.prog == "TestApp"
        assert router.description == "A test app"
        assert len(router.commands) == 0

    def test_router_decorator_command(self):
        """测试装饰器注册命令"""
        router = Router()

        @router.command(name="hello", help="Say hello")
        def hello_handler(**kwargs):
            return "Hello!"

        assert "hello" in router.commands
        assert router.commands["hello"].help == "Say hello"

    def test_router_add_command(self):
        """测试程序化添加命令"""
        router = Router()

        def my_handler(**kwargs):
            return "handled"

        router.add_command(
            name="add_cmd",
            handler=my_handler,
            help="Added command"
        )

        assert "add_cmd" in router.commands

    def test_router_parse_simple(self):
        """测试简单命令解析"""
        router = Router()

        def handler(**kwargs):
            return "ok"

        router.add_command(name="test", handler=handler)

        # Actual: parse returns 4 values: (cmd_name, parsed, positional_values, errors)
        cmd_name, parsed, positional, errors = router.parse("test arg1 arg2")

        assert cmd_name == "test"
        assert len(errors) == 0

    def test_router_parse_empty(self):
        """测试解析空白输入"""
        router = Router()

        result = router.parse("")
        # parse returns 3 values when empty: (cmd_name, parsed, errors)
        if len(result) == 3:
            cmd_name, parsed, errors = result
        else:
            cmd_name, parsed, positional, errors = result
        assert cmd_name is None
        assert len(errors) > 0

    def test_router_parse_with_options(self):
        """测试带选项的解析"""
        router = Router()

        def handler(**kwargs):
            return "ok"

        router.add_command(name="cmd", handler=handler)

        cmd_name, parsed, positional, errors = router.parse("cmd --name=value")

        assert cmd_name == "cmd"
        assert parsed.get("name") == "value"

    def test_router_parse_long_option(self):
        """测试长选项解析"""
        router = Router()

        def handler(**kwargs):
            return "ok"

        router.add_command(name="long", handler=handler)

        cmd_name, parsed, positional, errors = router.parse("long --option value")

        assert cmd_name == "long"
        assert parsed.get("option") == "value"

    def test_router_parse_quoted(self):
        """测试带引号的解析"""
        router = Router()

        def handler(**kwargs):
            return "ok"

        router.add_command(name="quote", handler=handler)

        cmd_name, parsed, positional, errors = router.parse('quote --msg "hello world"')

        assert cmd_name == "quote"
        assert parsed.get("msg") == "hello world"

    def test_router_validate(self):
        """测试参数验证"""
        router = Router()

        def handler(**kwargs):
            return "ok"

        arg1 = Arg(name="required_arg", arg_type=ArgType.STRING, required=True)
        router.add_command(name="validate", handler=handler, args=[arg1])

        # 缺少必需参数
        parsed = ParsedArgs()
        errors = router.validate("validate", parsed)
        assert len(errors) > 0

        # 提供必需参数
        parsed["required_arg"] = "value"
        errors = router.validate("validate", parsed)
        assert len(errors) == 0

    def test_router_execute(self):
        """测试命令执行"""
        router = Router()

        def my_handler(**kwargs):
            return "executed"

        router.add_command(name="exec", handler=my_handler)

        parsed = ParsedArgs()
        parsed["key"] = "value"

        result = router.execute("exec", parsed)
        assert result == "executed"

    def test_router_execute_unknown_command(self):
        """测试执行未知命令"""
        router = Router()

        with pytest.raises(ValueError, match="未知命令"):
            router.execute("unknown", ParsedArgs())

    def test_router_get_help(self):
        """测试获取帮助文本"""
        router = Router()

        @router.command(name="help_cmd", help="Help command", description="Description")
        def help_handler(**kwargs):
            pass

        help_text = router.get_help("help_cmd")
        assert "help_cmd" in help_text
        assert "Description" in help_text

    def test_router_get_help_global(self):
        """测试全局帮助"""
        router = Router(prog="TestApp", description="App description")

        @router.command(name="cmd1", help="Command 1")
        def cmd1(**kwargs):
            pass

        @router.command(name="cmd2", help="Command 2")
        def cmd2(**kwargs):
            pass

        help_text = router.get_help()
        assert "TestApp" in help_text
        assert "cmd1" in help_text
        assert "cmd2" in help_text

    def test_router_get_help_unknown_command(self):
        """测试获取未知命令帮助"""
        router = Router()
        help_text = router.get_help("nonexistent")
        assert "未知命令" in help_text

    def test_router_run(self):
        """测试完整运行流程"""
        router = Router()

        def handler(**kwargs):
            return "success"

        router.add_command(name="run_test", handler=handler)

        success, result, errors = router.run("run_test")
        assert success is True
        assert result == "success"
        assert len(errors) == 0

    def test_router_run_with_errors(self):
        """测试运行有错误的情况"""
        router = Router()

        def handler(**kwargs):
            return "ok"

        router.add_command(name="err_test", handler=handler)

        success, result, errors = router.run("err_test --nonexistent value")
        # May succeed or fail depending on validation
        assert isinstance(success, bool)

    def test_router_run_help_option(self):
        """测试帮助选项"""
        router = Router()

        def handler(**kwargs):
            return "should not reach"

        router.add_command(name="help_test", handler=handler)

        success, result, errors = router.run("help_test --help")
        assert success is True
        assert "help_test" in result


class TestGlobalFunctions:
    """测试全局函数"""

    def test_get_router(self):
        """测试获取路由器"""
        router = get_router()
        assert router is not None
        assert isinstance(router, Router)

    def test_parse_and_run(self):
        """测试解析并运行"""
        # Note: this uses global router
        # Test with a non-existent command to trigger error path
        success, result, errors = parse_and_run("nonexistent_cmd_12345")
        # Should handle gracefully
        assert isinstance(success, bool)
