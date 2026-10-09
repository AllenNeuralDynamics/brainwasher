import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).parent.parent
PACKAGE_NAME = "mixology"
SRC_DIR = ROOT_DIR / "src" / PACKAGE_NAME
DOCS_DIR = ROOT_DIR / "docs"
API_DIR = DOCS_DIR / "api"
MKDOCS_YML = ROOT_DIR / "mkdocs.yml"
API_LABEL = "API Reference"
INCLUDE_PRIVATE_MODULES = False

TO_COPY = ["examples", "LICENSE"]
log = logging.getLogger("mkdocs")


PACKAGE_DOCS = [
    ROOT_DIR / "instruments" / "brainslosher" / "docs",
    ROOT_DIR / "instruments" / "brainwasher" / "docs",
    ROOT_DIR / "instruments" / "seqflow" / "docs",
]

def discover_python_modules(package_root: Path, include_private: bool = False) -> list[str]:
    modules = []

    def _find_modules(current_path: Path, prefix: str = "") -> None:
        if not current_path.exists() or not current_path.is_dir():
            return

        for item in current_path.iterdir():
            if not item.is_dir():
                continue
            if not (item / "__init__.py").exists():
                continue

            if item.name.startswith("_") and not include_private:
                continue

            module_name = f"{prefix}{item.name}" if prefix else item.name
            modules.append(module_name)

            # Recursively search subdirectories for nested modules
            _find_modules(item, f"{module_name}.")

    _find_modules(package_root)
    return sorted(modules)


def discover_module_files(module_path: Path, include_private: bool = False) -> list[str]:
    files = []
    if not module_path.exists() or not module_path.is_dir():
        return files

    for item in module_path.iterdir():
        if not item.is_file() or item.suffix != ".py":
            continue
        if item.name.startswith("_") and not include_private:
            continue
        files.append(item.stem)

    return sorted(files)


def generate_api_structure() -> dict[str, list[dict[str, str]]]:
    api_structure: dict[str, list[dict[str, str]]] = {}
    modules = discover_python_modules(SRC_DIR, INCLUDE_PRIVATE_MODULES)

    if API_DIR.exists():
        shutil.rmtree(API_DIR)
    API_DIR.mkdir(parents=True, exist_ok=True)

    for item in SRC_DIR.iterdir():
        if item.is_file() and item.suffix == ".py":
            if item.name.startswith("_") and not INCLUDE_PRIVATE_MODULES:
                continue
            file_name = item.stem.replace("-", "_").replace(" ", "_")
            safe_file_name = item.stem.replace(".", "_")
            api_structure[file_name] = [{file_name: f"api/{safe_file_name}.md"}]

            with open(DOCS_DIR / f"api/{safe_file_name}.md", "w") as f:
                f.write(f"# {file_name}\n\n")
                f.write(f"::: {PACKAGE_NAME}.{file_name}\n")

    for module_name in modules:
        module_structure: list[dict[str, str]] = []
        module_path = SRC_DIR / module_name.replace(".", "/")

        # Add the module's __init__.py as the main module entry
        safe_module_name = module_name.replace(".", "_")
        module_structure.append({module_name: f"api/{safe_module_name}/{safe_module_name}.md"})

        module_files = discover_module_files(module_path, INCLUDE_PRIVATE_MODULES)
        for file_name in module_files:
            safe_file_name = file_name.replace(".", "_")
            module_structure.append({file_name: f"api/{safe_module_name}/{safe_file_name}.md"})

        (API_DIR / safe_module_name).mkdir(parents=True, exist_ok=True)

        with open(DOCS_DIR / f"api/{safe_module_name}/{safe_module_name}.md", "w") as f:
            f.write(f"# {module_name}\n\n")
            f.write(f"::: {PACKAGE_NAME}.{module_name}\n")

        for file_name in module_files:
            safe_file_name = file_name.replace(".", "_")
            with open(DOCS_DIR / f"api/{safe_module_name}/{safe_file_name}.md", "w") as f:
                f.write(f"# {module_name}.{file_name}\n\n")
                f.write(f"::: {PACKAGE_NAME}.{module_name}.{file_name}\n")

        api_structure[module_name] = module_structure
    return api_structure


def update_mkdocs_yml(api_structure: dict[str, list[dict[str, str]]]) -> None:
    with open(MKDOCS_YML, "r") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    nav: list[str | dict[str, Any]] = config.get("nav", [])

    for entry in nav:
        if isinstance(entry, dict) and API_LABEL in entry:
            api_ref: list[str | dict[str, list[dict[str, str]]]] = []
            for module_name, module_content in api_structure.items():
                display_name = module_name.replace("_", " ").title()
                api_ref.append({display_name: module_content})

            entry[API_LABEL] = api_ref

    with open(MKDOCS_YML, "w") as f:
        yaml.dump(config, f, sort_keys=False, default_flow_style=False)


def copy_assets() -> None:
    for file_or_dir in TO_COPY:
        src: Path = ROOT_DIR / file_or_dir
        dest: Path = DOCS_DIR / file_or_dir

        if src.exists():
            log.info("Copying %s to docs...", file_or_dir)

            if src.is_file():
                log.info("Copying file %s to %s", src, dest)
                shutil.copy(src, dest)
            else:
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
            log.info("%s copied successfully.", file_or_dir)
        else:
            log.warning("Source: %s not found, skipping.", file_or_dir)

def rewrite_api_paths(item: Any, package_name: str) -> Any:
    
    if isinstance(item, list):
        return [rewrite_api_paths(subitem, package_name) for subitem in item]
    if isinstance(item, dict):
        return {key: rewrite_api_paths(value, package_name) for key, value in item.items()}
    if isinstance(item, str) and item.startswith("api/"):
        return f"{package_name}_docs/api/{item[4:]}"
    return item

def generate_package_pages() -> None:

    config: dict[str, Any] = yaml.safe_load(MKDOCS_YML.read_text(encoding="utf-8"))
    nav: list[str | dict[str, Any]] = config.get("nav", [])
    packages: list[tuple[str, str, str, Any]] = []

    for package_docs in PACKAGE_DOCS:
        package_root = package_docs.parent
        readme_path = package_root / "README.md"
        package_mkdocs_yml = package_root / "mkdocs.yml"
        copied_docs_dir = DOCS_DIR / f"{package_root.name}_docs"

        package_name = package_root.name
        package_title = package_name.replace("_", " ").title()
        api_title = f"{package_title} API Reference"

        if copied_docs_dir.exists():
            shutil.rmtree(copied_docs_dir)
        shutil.copytree(package_docs, copied_docs_dir)
        snippets_dir = copied_docs_dir / ".snippets"
        snippets_dir.mkdir(exist_ok=True)
        copied_readme_path = snippets_dir / "README.md"
        shutil.copy2(readme_path, copied_readme_path)

        copied_index_path = copied_docs_dir / "index.md"
        if copied_index_path.exists():
            relative_copied_readme = copied_readme_path.relative_to(ROOT_DIR)
            copied_index_path.write_text(
                copied_index_path.read_text(encoding="utf-8").replace(
                    '--8<-- "README.md"',
                    f'--8<-- "{relative_copied_readme.as_posix()}"',
                ),
                encoding="utf-8",
            )

        package_config: dict[str, Any] = yaml.safe_load(package_mkdocs_yml.read_text(encoding="utf-8"))
        package_api_nav = next(
            (
                entry[API_LABEL]
                for entry in package_config.get("nav", [])
                if isinstance(entry, dict) and API_LABEL in entry
            ),
            [],
        )
        packages.append((package_name, package_title, api_title, package_api_nav))

    package_titles = {title for _, package_title, api_title, _ in packages for title in (package_title, api_title)}
    nav[:] = [
        entry
        for entry in nav
        if not (isinstance(entry, dict) and next(iter(entry.keys()), None) in package_titles)
    ]

    for package_name, package_title, api_title, package_api_nav in packages:
        nav.append({package_title: f"{package_name}_docs/index.md"})
        if package_api_nav:
            nav.append({api_title: rewrite_api_paths(package_api_nav, package_name)})

    MKDOCS_YML.write_text(
        yaml.dump(config, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

def main() -> None:
    log.info("Starting API documentation regeneration...")
    copy_assets()
    generate_package_pages()
    log.info("Regenerating API documentation...")
    api_structure: dict[str, list[dict[str, str]]] = generate_api_structure()
    update_mkdocs_yml(api_structure)
    log.info("API documentation regenerated successfully.")


if __name__ == "__main__":
    main()