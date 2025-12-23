from __future__ import annotations

import shutil
from argparse import ArgumentParser
from os import name as OSNAME
from subprocess import CalledProcessError, run as subprun
from sys import exit as sysexit
from pathlib import Path

from src.util.context import Context, Platform


def _ensure_pyinstaller() -> str:
    exe = shutil.which("pyinstaller")
    if not exe:
        raise RuntimeError(
            "PyInstaller not found in PATH. Install it in your Pipenv:\n"
            "  pipenv install pyinstaller\n"
        )
    return exe

def _sep() -> str:
    return ":" if OSNAME != "nt" else ";"

def _add_data_arg(src: Path, dest: str) -> list[str]:
    # Bundle 'src' into the app at relative path 'dest'
    return ["--add-data", f"{src}{_sep()}{dest}"]

def _icon_args(platform: Platform, assets_dir: Path) -> list[str]:
    if platform == Platform.MACOS:
        icon = assets_dir / "icons" / "app.icns"
        return ["--icon", str(icon)] if icon.exists() else []
    if platform == Platform.WINDOWS:
        icon = assets_dir / "icons" / "app.ico"
        return ["--icon", str(icon)] if icon.exists() else []
    return []



def _create_zip_windows(exe_path: Path, out_zip: Path) -> None:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    base = out_zip.with_suffix("")  # shutil adds .zip automatically
    # Package just the exe; extend as needed
    tmp_dir = out_zip.parent / "_zip_tmp"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe_path, tmp_dir / exe_path.name)
    print(f"Packaging (zip): {out_zip}")
    shutil.make_archive(str(base), "zip", root_dir=tmp_dir)
    shutil.rmtree(tmp_dir, ignore_errors=True)

def _create_dmg(app_path: Path, out_dmg: Path) -> None:
    # Requires hdiutil (macOS)
    out_dmg.parent.mkdir(parents=True, exist_ok=True)
    volname = app_path.stem
    cmd = [
        "hdiutil", "create",
        "-volname", volname,
        "-srcfolder", str(app_path),
        "-ov",
        "-format", "UDZO",
        str(out_dmg),
    ]
    print("Packaging (dmg):", " ".join(cmd))
    subprun(cmd, check=True)

def _handle_packaging(platform: Platform, app_name: str, dist_dir: Path, build_root: Path, package: bool) -> None:
    """Handle post-build packaging if requested."""
    if not package:
        return

    if platform == Platform.MACOS:
        app_path = dist_dir / f"{app_name}.app"
        if not app_path.exists():
            raise SystemExit(f"Expected app at {app_path}, but it was not found.")

        out_dmg = build_root / f"{app_name}.dmg"
        _create_dmg(app_path, out_dmg)
        print(f"[build] DMG: {out_dmg}")

    elif platform == Platform.WINDOWS:
        exe_path = dist_dir / f"{app_name}.exe"
        if not exe_path.exists():
            # one-dir build puts exe inside a folder named app_name
            exe_path = dist_dir / app_name / f"{app_name}.exe"
        if not exe_path.exists():
            raise SystemExit(f"Expected exe at {exe_path}, but it was not found.")

        out_zip = build_root / f"{app_name}-win.zip"
        _create_zip_windows(exe_path, out_zip)
        print(f"[build] ZIP: {out_zip}")



def build(debug: bool = False, package: bool = False, use_spec: bool = True) -> None:
    """
    Build the application with PyInstaller.

    Args:
        debug: If True, builds in debug mode (onedir, console, no clean).
               If False, builds for production (onefile, windowed, clean).
        package: If True, creates a distributable package (zip for all, dmg for macOS).
        use_spec: If True, generates/uses a .spec file for the build (recommended).
    """
    platform = Context.platform

    # Determine build options based on debug mode
    if debug:
        onefile = False
        windowed = False
        clean = False
        print("Building in DEBUG mode (onedir, with console)")
    else:
        onefile = True
        windowed = True
        clean = True
        print("Building in PRODUCTION mode (onefile, windowed)")

    # Auto-correct macOS onefile+windowed (PyInstaller deprecates this)
    if platform == Platform.MACOS and onefile and windowed:
        onefile = False

    # Load configuration from [app] section
    app_name = str(Context.Config.get("app", "name", "App"))
    entry_module = str(Context.Config.get("app", "entry_module", "src.app.main"))
    bundle_id = Context.Config.get("app", "identifier")

    root = Context.project_root
    src_dir = root / "src"
    assets_dir = Context.assets_dir

    # Keep all artifacts inside ./build
    build_root = root / "build"
    work_dir = build_root / "work"
    dist_dir = build_root / "dist"
    spec_dir = build_root
    work_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    # Convert module -> file path under src/
    module_for_path = entry_module[4:] if entry_module.startswith("src.") else entry_module
    script_path = (src_dir / module_for_path.replace(".", "/")).with_suffix(".py")
    if not script_path.exists():
        raise FileNotFoundError(f"Entry module not found: {entry_module} -> {script_path}")

    pyinstaller_exe = _ensure_pyinstaller()

    # Check if spec file exists
    spec_file = spec_dir / f"{app_name}.spec"

    # If using spec file and it exists, use it directly
    if use_spec and spec_file.exists():
        print(f"Using existing spec file: {spec_file}")
        cmd: list[str] = [
            pyinstaller_exe,
            str(spec_file),
            *(["--clean"] if clean else []),
        ]

        try:
            subprun(cmd, check=True)
        except FileNotFoundError as e:
            print(f"[build] ERROR: {e}")
            print("Tip: Is PyInstaller installed?")
            sysexit(1)
        except CalledProcessError as e:
            print(f"[build] PyInstaller exited with code {e.returncode}")
            sysexit(e.returncode)

        # Skip to packaging
        _handle_packaging(platform, app_name, dist_dir, build_root, package)
        return

    # Build base command (for generating spec or direct build)
    cmd: list[str] = [
        pyinstaller_exe,
        "--name", app_name,
        *(["--onefile"] if onefile else []),
        *(["--windowed"] if windowed else []),
        *_icon_args(platform, assets_dir),
        # Bundle resources:
        *_add_data_arg(assets_dir, "resources/assets"),
        *_add_data_arg(Context.config_path, "."),  # config.toml next to exe
        "--paths", str(src_dir),
        "--log-level", "WARN",
        "--specpath", str(spec_dir),
        "--workpath", str(work_dir),
        "--distpath", str(dist_dir),
        *(["--clean"] if clean else []),
    ]

    # Load optional build configuration from config.toml
    build_config = Context.Config.get_section("build")

    # Add additional data files
    for data_entry in build_config.get("add_data", []):
        # Support package-relative paths (e.g., whisper package assets)
        if "package" in data_entry:
            try:
                pkg = __import__(data_entry["package"])
                pkg_dir = Path(pkg.__file__).parent
                src = pkg_dir / data_entry["src"]
            except (ImportError, AttributeError) as e:
                if data_entry.get("required", False):
                    print(f"Required package not found: {data_entry['package']}")
                    sysexit(1)
                else:
                    print(f"Package {data_entry['package']} not found, skipping")
                    continue
        else:
            # Support absolute paths or relative to project root
            src_path = Path(data_entry["src"])
            src = src_path if src_path.is_absolute() else root / src_path

        if src.exists():
            cmd.extend(_add_data_arg(src, data_entry["dest"]))
        elif data_entry.get("required", False):
            print(f"Required data path not found: {src}")
            sysexit(1)

    # Add additional binaries
    for binary_entry in build_config.get("add_binary", []):
        binary_path = shutil.which(binary_entry["name"]) or binary_entry.get("path")
        if binary_path:
            cmd.extend(["--add-binary", f"{binary_path}{_sep()}{binary_entry.get('dest', '.')}"])
        elif binary_entry.get("required", False):
            print(f"Required binary not found: {binary_entry['name']}")
            sysexit(1)

    # Add hidden imports
    for hidden_import in build_config.get("hidden_imports", []):
        cmd.extend(["--hidden-import", hidden_import])

    print(f"Building for {platform.value}")

    # Add final arguments
    cmd.extend(["-y", str(script_path)])
    if bundle_id and platform == Platform.MACOS:
        cmd[1:1] = ["--osx-bundle-identifier", str(bundle_id)]

    try:
        subprun(cmd, check=True)
    except FileNotFoundError as e:
        print(f"[build] ERROR: {e}")
        print("Tip: Is PyInstaller installed?")
        sysexit(1)
    except CalledProcessError as e:
        print(f"[build] PyInstaller exited with code {e.returncode}")
        sysexit(e.returncode)

    # Notify about spec file generation
    if use_spec and spec_file.exists():
        print(f"Spec file generated: {spec_file}")
        print("     You can customize it and future builds will use it automatically.")

    # Handle packaging
    _handle_packaging(platform, app_name, dist_dir, build_root, package)



def main() -> None:
    parser = ArgumentParser(
        description=(
            "Build standalone binaries with PyInstaller.\n"
            "- Auto-detects current platform (macOS/Windows/Linux)\n"
            "- Debug mode: builds with console, onedir\n"
            "- Production mode (default): builds windowed, onefile, cleans cache\n"
            "- Package option creates distributable archives (zip/dmg)\n"
            "- Spec file support: generates .spec file on first build, then reuses it\n"
            "- Configuration via config.toml [build] section for custom data/binaries/imports"
        )
    )
    
    parser.add_argument("--debug", action="store_true",
                        help="Build in debug mode (onedir, with console)")
    parser.add_argument("--package", action="store_true",
                        help="Create distributable package (zip for all platforms, plus dmg for macOS)")
    parser.add_argument("--no-spec", action="store_true",
                        help="Don't use spec file (generate command line args each time)")
    args = parser.parse_args()

    try:
        build(debug=args.debug, package=args.package, use_spec=not args.no_spec)
    except Exception as e:
        print(f"[build] Unhandled error: {e.__class__.__name__}: {e}")
        sysexit(1)

if __name__ == "__main__":
    main()
