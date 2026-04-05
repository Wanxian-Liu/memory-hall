
"""测试插件模块"""
from plugin.plugin import PluginInterface

class DummyPlugin(PluginInterface):
    def activate(self) -> bool:
        return True
    
    def deactivate(self) -> bool:
        return True
    
    def get_metadata(self):
        from plugin.plugin import PluginMetadata
        return PluginMetadata(id="记忆殿堂.test", name="测试插件", version="1.0.0")
    
    def execute(self, context: dict) -> dict:
        return {"status": "ok", "plugin": "test"}
