"""Pin all dependencies in pyproject.toml to their currently installed versions.

Usage:
    uv run pin_versions.py [OPTIONS]
"""

# /// script
# requires-python = ">=3.10"
# dependencies = ["tomlkit", "click", "httpx"]
# ///

import asyncio
import json
import subprocess
from pathlib import Path

import click
import httpx
import tomlkit


def get_installed_versions(venv: Path) -> dict[str, str]:
    """Get a mapping of package name -> installed version."""
    cmd = ["uv", "pip", "list", "--format=json"]
    if venv.exists():
        cmd += ["--python", str(venv / "bin" / "python")]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    packages = json.loads(result.stdout)
    return {pkg["name"].lower(): pkg["version"] for pkg in packages}


async def get_latest_version(client: httpx.AsyncClient, package_name: str) -> str:
    """Get the latest version of a package from PyPI."""
    response = await client.get(f"https://pypi.org/pypi/{package_name}/json")
    response.raise_for_status()
    return response.json()["info"]["version"]


def extract_package_name(dep: str) -> str:
    """Extract the package name from a dependency string."""
    return dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].split("!")[0].split("~")[0].strip()


def has_version_constraint(dep: str) -> bool:
    """Check if a dependency string already has a version constraint."""
    return any(op in dep for op in [">=", "<=", "==", "!=", "~=", ">"])


async def resolve_missing_versions(
    client: httpx.AsyncClient,
    missing: list[str],
) -> dict[str, str]:
    """Fetch latest versions for all missing packages concurrently."""
    tasks = {name: get_latest_version(client, name) for name in missing}
    results = {}
    for name, coro in tasks.items():
        results[name] = await coro
    return results


def collect_unpinned_deps(data: dict) -> list[str]:
    """Collect all unpinned dependency names that aren't in the installed versions."""
    deps = []

    if "project" in data:
        if "dependencies" in data["project"]:
            deps.extend(data["project"]["dependencies"])
        if "optional-dependencies" in data["project"]:
            for group_deps in data["project"]["optional-dependencies"].values():
                deps.extend(group_deps)

    if "dependency-groups" in data:
        for group_deps in data["dependency-groups"].values():
            deps.extend(group_deps)

    return [
        extract_package_name(dep).lower().replace("_", "-")
        for dep in deps
        if not has_version_constraint(dep)
    ]


def pin_dependency(dep: str, versions: dict[str, str], operator: str, failed: list[str]) -> str:
    """Add version pin to a dependency string if it doesn't already have one."""
    if has_version_constraint(dep):
        return dep

    name = extract_package_name(dep)
    normalized = name.lower().replace("_", "-")

    version = versions.get(normalized)
    if version:
        return f"{dep}{operator}{version}"

    click.echo(f"  WARNING: no version found for '{name}', leaving unpinned")
    failed.append(name)
    return dep


def pin_list(deps, versions: dict[str, str], operator: str, failed: list[str]) -> None:
    """Pin all dependencies in a tomlkit array in place."""
    for i, dep in enumerate(deps):
        deps[i] = pin_dependency(dep, versions, operator, failed)


async def async_main(operator: str, pyproject: str, venv: str, pin_latest: bool, dry_run: bool):
    pyproject_path = Path(pyproject)
    data = tomlkit.loads(pyproject_path.read_text())
    versions = get_installed_versions(Path(venv))
    failed: list[str] = []

    if pin_latest:
        unpinned = collect_unpinned_deps(data)
        missing = [name for name in unpinned if name not in versions]
        if missing:
            click.echo(f"Looking up latest versions for {len(missing)} uninstalled packages...")
            async with httpx.AsyncClient() as client:
                latest = await resolve_missing_versions(client, missing)
            versions.update(latest)

    # Pin [project].dependencies
    if "project" in data and "dependencies" in data["project"]:
        click.echo("Pinning [project].dependencies:")
        pin_list(data["project"]["dependencies"], versions, operator, failed)
        for dep in data["project"]["dependencies"]:
            click.echo(f"  {dep}")

    # Pin [project.optional-dependencies]
    if "project" in data and "optional-dependencies" in data["project"]:
        for group, deps in data["project"]["optional-dependencies"].items():
            click.echo(f"\nPinning [project.optional-dependencies].{group}:")
            pin_list(deps, versions, operator, failed)
            for dep in deps:
                click.echo(f"  {dep}")

    # Pin [dependency-groups]
    if "dependency-groups" in data:
        for group, deps in data["dependency-groups"].items():
            click.echo(f"\nPinning [dependency-groups].{group}:")
            pin_list(deps, versions, operator, failed)
            for dep in deps:
                click.echo(f"  {dep}")

    if dry_run:
        click.echo("\nDry run — no changes written.")
    else:
        pyproject_path.write_text(tomlkit.dumps(data))
        click.echo(f"\nUpdated {pyproject_path}")

    if failed:
        raise SystemExit(1)


@click.command()
@click.option("--operator", "-o", default="==", help="Version pin operator (e.g. ==, >=, ~=)")
@click.option("--pyproject", "-p", default="pyproject.toml", type=click.Path(exists=True), help="Path to pyproject.toml")
@click.option("--venv", default=".venv", type=click.Path(), help="Path to the project virtualenv")
@click.option("--pin-latest", is_flag=True, default=False, help="Pin uninstalled packages to their latest PyPI version")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would change without modifying pyproject.toml")
def main(operator: str, pyproject: str, venv: str, pin_latest: bool, dry_run: bool):
    """Pin all unpinned dependencies in pyproject.toml to their installed versions."""
    asyncio.run(async_main(operator, pyproject, venv, pin_latest, dry_run))


if __name__ == "__main__":
    main()
