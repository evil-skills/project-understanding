"""
Cross-platform support utilities.

Provides:
- OS detection
- Platform-specific error messages
- Python-only install path support
- Binary release detection
"""

import os
import sys
import platform
from enum import Enum
from typing import Optional, Dict, Any, List
from pathlib import Path


class Platform(Enum):
    """Supported platforms."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "darwin"
    UNKNOWN = "unknown"


def get_platform() -> Platform:
    """Detect current platform."""
    system = platform.system().lower()
    
    if system == "windows" or system == "win32":
        return Platform.WINDOWS
    elif system == "linux":
        return Platform.LINUX
    elif system == "darwin":
        return Platform.MACOS
    else:
        return Platform.UNKNOWN


def is_windows() -> bool:
    """Check if running on Windows."""
    return get_platform() == Platform.WINDOWS


def is_linux() -> bool:
    """Check if running on Linux."""
    return get_platform() == Platform.LINUX


def is_macos() -> bool:
    """Check if running on macOS."""
    return get_platform() == Platform.MACOS


def get_platform_message(platform: Optional[Platform] = None) -> str:
    """
    Get platform-specific message.
    
    Returns helpful error messages and instructions for the platform.
    """
    if platform is None:
        platform = get_platform()
    
    messages = {
        Platform.WINDOWS: """
Windows detected. For best experience:
  1. Use PowerShell: scripts/pui.ps1
  2. Or use Git Bash: scripts/pui
  3. Or run directly: python -m scripts.pui

Note: Some features may require Windows Subsystem for Linux (WSL).
""",
        Platform.LINUX: """
Linux detected. Installation options:
  1. Use the shell script: ./scripts/pui
  2. Run with Python: python3 -m scripts.pui
  3. Install globally: pip install -e .

All features are fully supported on Linux.
""",
        Platform.MACOS: """
macOS detected. Installation options:
  1. Use the shell script: ./scripts/pui
  2. Run with Python: python3 -m scripts.pui
  3. Install globally: pip install -e .

Note: You may need to install Xcode Command Line Tools for some features.
""",
        Platform.UNKNOWN: """
Unknown platform detected. PUI should work but may have limitations.
Try running directly with Python: python -m scripts.pui
""",
    }
    
    return messages.get(platform, messages[Platform.UNKNOWN])


def check_python_version() -> tuple[bool, str]:
    """
    Check if Python version is supported.
    
    Returns:
        Tuple of (is_supported, message)
    """
    version = sys.version_info
    
    if version < (3, 9):
        return False, f"Python {version.major}.{version.minor} is not supported. Please use Python 3.9 or later."
    
    return True, f"Python {version.major}.{version.minor}.{version.micro}"


def check_dependencies() -> Dict[str, Any]:
    """
    Check if required dependencies are installed.
    
    Returns:
        Dict with dependency status
    """
    results = {}
    
    # Core dependencies
    optional_deps = [
        ("watchdog", "File watching (pui watch)"),
        ("tree_sitter", "Advanced parsing"),
        ("tree_sitter_languages", "Multi-language support"),
    ]
    
    for module, description in optional_deps:
        try:
            __import__(module)
            results[module] = {"available": True, "description": description}
        except ImportError:
            results[module] = {
                "available": False,
                "description": description,
                "install": f"pip install {module}"
            }
    
    return results


def get_install_path() -> Path:
    """
    Get the installation path for PUI.
    
    Returns:
        Path to the PUI installation
    """
    # Check for PyInstaller bundle
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    
    # Development/install path
    return Path(__file__).parent.parent.parent


def is_pyinstaller_bundle() -> bool:
    """Check if running as a PyInstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_data_dir() -> Path:
    """
    Get the data directory for PUI.
    
    This handles both regular Python and PyInstaller bundles.
    """
    if is_pyinstaller_bundle():
        return Path(sys._MEIPASS)
    else:
        return get_install_path()


class PlatformSupport:
    """Platform support checker and reporter."""
    
    def __init__(self):
        self.platform = get_platform()
        self.python_ok, self.python_version = check_python_version()
        self.dependencies = check_dependencies()
        self.is_bundle = is_pyinstaller_bundle()
    
    def is_supported(self) -> bool:
        """Check if current platform is fully supported."""
        if not self.python_ok:
            return False
        
        # All platforms are supported, but with varying capabilities
        return True
    
    def get_status_report(self) -> str:
        """Get a status report as a string."""
        lines = [
            "Platform Support Status",
            "=" * 50,
            f"Platform: {self.platform.value}",
            f"Python: {self.python_version}",
            f"Bundle mode: {self.is_bundle}",
            "",
            "Dependencies:",
        ]
        
        for name, info in self.dependencies.items():
            status = "✓" if info["available"] else "✗"
            lines.append(f"  {status} {name}: {info['description']}")
            if not info["available"]:
                lines.append(f"      Install: {info['install']}")
        
        lines.extend([
            "",
            get_platform_message(self.platform),
        ])
        
        return '\n'.join(lines)
    
    def print_report(self) -> None:
        """Print the status report."""
        print(self.get_status_report())


def require_dependency(module: str, feature: str) -> None:
    """
    Require a dependency or raise an error.
    
    Args:
        module: Module name to check
        feature: Feature description for error message
    
    Raises:
        RuntimeError: If dependency is not available
    """
    try:
        __import__(module)
    except ImportError:
        raise RuntimeError(
            f"'{module}' is required for {feature}. "
            f"Install with: pip install {module}"
        )


def get_shell_extension() -> str:
    """Get the shell script extension for the current platform."""
    if is_windows():
        return ".ps1"
    return ""


def get_python_executable() -> str:
    """Get the Python executable path."""
    return sys.executable


def install_signal_handlers() -> None:
    """
    Install platform-appropriate signal handlers.
    
    This ensures clean shutdown on Ctrl+C across all platforms.
    """
    import signal
    
    def signal_handler(signum, frame):
        print("\nInterrupted by user")
        sys.exit(0)
    
    # Handle SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    
    # On Windows, also handle SIGBREAK
    if is_windows() and hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)
