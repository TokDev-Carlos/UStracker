import ast
from pathlib import Path


def test_uvicorn_startup_does_not_require_console_streams():
    source = Path('src/ustracker/server.py').read_text(encoding='utf-8')
    tree = ast.parse(source)

    config_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == 'uvicorn'
        and node.func.attr == 'Config'
    ]
    assert config_calls, 'uvicorn.Config call not found'

    assert any(
        kw.arg == 'log_config'
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is None
        for call in config_calls
        for kw in call.keywords
    ), 'GUI backend must use log_config=None so pythonw startup does not depend on console stderr/stdout'
