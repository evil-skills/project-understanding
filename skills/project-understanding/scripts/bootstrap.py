#!/usr/bin/env python3
"""
Bootstrap script for Project Understanding Skill.

Sets up a local virtual environment under .pui/venv/ and installs
pinned dependencies from requirements.txt.

Usage:
    python scripts/bootstrap.py [--offline]

Options:
    --offline    Skip network operations, use pre-downloaded packages only
"""

import argparse
import subprocess
import sys
from pathlib import Path


# Constants
PUI_DIR = Path(".pui")
VENV_DIR = PUI_DIR / "venv"
REQUIREMENTS_FILE = Path(__file__).parent.parent / "requirements.txt"


def normalize_package_name(name: str) -> str:
    """Normalize package names for comparison."""
    return name.strip().lower().replace("-", "_")


def parse_requirements() -> list[str]:
    """Parse requirements.txt and return normalized package names."""
    if not REQUIREMENTS_FILE.exists():
        return []

    requirements: list[str] = []
    version_separators = ["==", ">=", "<=", "~=", ">", "<"]

    for line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-"):
            continue

        name = line
        for sep in version_separators:
            if sep in name:
                name = name.split(sep, 1)[0].strip()
                break

        if name:
            requirements.append(normalize_package_name(name))

    return requirements


def get_installed_packages(pip_path: Path) -> set[str]:
    """Return normalized installed package names from pip."""
    try:
        result = subprocess.run(
            [str(pip_path), "list", "--format=freeze"],
            capture_output=True,
            text=True,
            timeout=30
        )
    except Exception:
        return set()

    if result.returncode != 0:
        return set()

    installed: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if "==" in line:
            name = line.split("==", 1)[0].strip()
        elif " @ " in line:
            name = line.split(" @ ", 1)[0].strip()
        else:
            name = line
        if name:
            installed.add(normalize_package_name(name))

    return installed


def extract_distribution_name(filename: str) -> str:
    """Extract distribution name from wheel or sdist filename."""
    if filename.endswith(".whl"):
        base = filename[:-4]
        dist = base.split("-", 1)[0]
        return normalize_package_name(dist)

    if filename.endswith(".tar.gz"):
        base = filename[:-7]
        parts = base.split("-")
        version_index = None
        for index in range(len(parts) - 1, -1, -1):
            if parts[index][:1].isdigit():
                version_index = index
                break
        if version_index is None:
            dist = parts[0]
        else:
            dist = "-".join(parts[:version_index])
        return normalize_package_name(dist)

    return ""


def check_python_version() -> bool:
    """Check if Python version is 3.10 or higher."""
    if sys.version_info < (3, 10):
        print(f"Error: Python 3.10+ required, found {sys.version_info.major}.{sys.version_info.minor}")
        return False
    return True


def check_offline_availability(offline: bool) -> bool:
    """Check if offline mode is possible (requirements already satisfied or packages available)."""
    if not offline:
        return True

    requirements = parse_requirements()
    if not requirements:
        print(f"Error: Requirements file not found at {REQUIREMENTS_FILE}")
        return False

    installed: set[str] = set()
    if VENV_DIR.exists():
        pip_path = VENV_DIR / "bin" / "pip"
        if not pip_path.exists():
            pip_path = VENV_DIR / "Scripts" / "pip.exe"  # Windows

        if pip_path.exists():
            installed = get_installed_packages(pip_path)

    available: set[str] = set()
    packages_dir = PUI_DIR / "packages"
    if packages_dir.exists():
        for package_file in packages_dir.glob("*.whl"):
            dist = extract_distribution_name(package_file.name)
            if dist:
                available.add(dist)
        for package_file in packages_dir.glob("*.tar.gz"):
            dist = extract_distribution_name(package_file.name)
            if dist:
                available.add(dist)

    combined = installed | available
    missing = [name for name in requirements if name not in combined]
    if not missing:
        if installed and not available:
            print("Offline mode: Virtual environment already has required packages.")
        elif available and not installed:
            print("Offline mode: Found all required packages in .pui/packages.")
        else:
            print("Offline mode: Found required packages across venv and .pui/packages.")
        return True

    if combined:
        print("Offline mode: Missing required packages for offline use:")
        for name in missing:
            print(f"  - {name}")
        return False

    print("Warning: Offline mode requested but packages not available.")
    print("You may need to:")
    print("  1. Run bootstrap with network first: python scripts/bootstrap.py")
    print("  2. Or download packages to .pui/packages (wheels or tar.gz files)")
    return False


def create_venv() -> bool:
    """Create virtual environment under .pui/venv/."""
    print(f"Creating virtual environment at {VENV_DIR}...")

    try:
        # Create the .pui directory if it doesn't exist
        PUI_DIR.mkdir(parents=True, exist_ok=True)

        # Create virtual environment
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
            capture_output=True
        )
        print(f"✓ Virtual environment created at {VENV_DIR}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating virtual environment: {e}")
        if e.stderr:
            print(f"Details: {e.stderr.decode()}")
        return False
    except Exception as e:
        print(f"Error creating virtual environment: {e}")
        return False


def get_pip_path() -> Path:
    """Get the path to pip in the virtual environment."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "pip.exe"
    else:
        return VENV_DIR / "bin" / "pip"


def get_python_path() -> Path:
    """Get the path to python in the virtual environment."""
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    else:
        return VENV_DIR / "bin" / "python"


def install_dependencies(offline: bool = False) -> bool:
    """Install dependencies from requirements.txt."""
    pip_path = get_pip_path()

    if not REQUIREMENTS_FILE.exists():
        print(f"Error: Requirements file not found at {REQUIREMENTS_FILE}")
        return False

    print(f"Installing dependencies from {REQUIREMENTS_FILE}...")

    cmd = [str(pip_path), "install"]

    if offline:
        cmd.append("--no-index")
        cmd.append("--find-links")
        cmd.append(str(PUI_DIR / "packages"))
        print("(Offline mode: using local packages only)")

    cmd.extend(["-r", str(REQUIREMENTS_FILE)])

    try:
        subprocess.run(cmd, check=True, capture_output=False)
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        if offline:
            print("\nOffline mode failed. To prepare for offline use:")
            print("  1. First run with network: python scripts/bootstrap.py")
            print("  2. Download packages: pip download -r requirements.txt -d .pui/packages")
        return False
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        return False


def verify_installation() -> bool:
    """Verify that the installation works by importing key packages."""
    python_path = get_python_path()

    test_script = """
import sys
try:
    import tree_sitter
    print("✓ tree-sitter imported successfully")
except ImportError as e:
    print(f"✗ Failed to import tree-sitter: {e}")
    sys.exit(1)

try:
    from tree_sitter_languages import get_language, get_parser
    print("✓ tree-sitter-languages imported successfully")
except ImportError as e:
    print(f"✗ Failed to import tree-sitter-languages: {e}")
    sys.exit(1)

print("All dependencies verified!")
"""

    try:
        result = subprocess.run(
            [str(python_path), "-c", test_script],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(result.stdout)

        if result.returncode != 0:
            if result.stderr:
                print(f"Verification errors:\n{result.stderr}")
            return False

        return True
    except Exception as e:
        print(f"Error verifying installation: {e}")
        return False


def print_next_steps():
    """Print instructions for the next command to run."""
    print("\n" + "=" * 60)
    print("Bootstrap complete!")
    print("=" * 60)
    print("\nNext step:")
    print("  python skills/project-understanding/scripts/pui.py index")

    print("\n" + "=" * 60)


def main(argv: list[str] | None = None) -> int:
    """Main entrypoint for bootstrap script."""
    parser = argparse.ArgumentParser(
        description="Bootstrap Project Understanding Skill dependencies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/bootstrap.py           # Install with network
  python scripts/bootstrap.py --offline # Install from local packages only
        """
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip network operations, use pre-downloaded packages only"
    )

    args = parser.parse_args(argv)

    print("Project Understanding Skill Bootstrap")
    print("=" * 60)

    # Check Python version
    if not check_python_version():
        return 1

    # Check offline availability if requested
    if args.offline and not check_offline_availability(args.offline):
        print("\nCannot proceed in offline mode.")
        return 1

    # Check if venv already exists
    if VENV_DIR.exists():
        print(f"Virtual environment already exists at {VENV_DIR}")
        response = input("Re-create? [y/N]: ").strip().lower()
        if response == 'y':
            import shutil
            shutil.rmtree(VENV_DIR)
            if not create_venv():
                return 1
        else:
            print("Using existing virtual environment.")
    else:
        if not create_venv():
            return 1

    # Install dependencies
    if not install_dependencies(offline=args.offline):
        return 1

    # Verify installation
    if not verify_installation():
        print("\nInstallation verification failed.")
        return 1

    # Print next steps
    print_next_steps()

    return 0


if __name__ == "__main__":
    sys.exit(main())
