from pathlib import Path


def test_shell_starts_maximized_with_normal_resizable_border():
    text = Path('host/Shell/MainWindow.xaml').read_text(encoding='utf-8')
    assert 'WindowState="Maximized"' in text
    assert 'WindowStyle="SingleBorderWindow"' in text
    assert 'ResizeMode="CanResize"' in text
