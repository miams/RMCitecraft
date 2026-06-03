#!/usr/bin/env python3
"""
Deploy Census Quality Check skill to .claude/skills directory.

This script copies the census quality check skill files to the Claude skills
directory, making them available for Claude Code to use.

Usage:
    python scripts/deploy_census_quality_skill.py          # Deploy/update skill
    python scripts/deploy_census_quality_skill.py --check  # Check if update needed
    python scripts/deploy_census_quality_skill.py --remove # Remove skill
"""

import argparse
import shutil
import sys
from pathlib import Path


SKILL_NAME = "census-quality-check"
SKILL_FILES = [
    "scripts/census_quality_check_v2.py",
    "scripts/fix_census_titles.py",
    "scripts/fix_1930_missing_line.py",
    "scripts/fix_1930_bibliography_comma.py",
]
SKILL_MD = "scripts/skills/census-quality-check/SKILL.md"


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_skill_dir() -> Path:
    """Get the Claude skills directory."""
    return get_project_root() / ".claude" / "skills" / SKILL_NAME


def deploy_skill(dry_run: bool = False) -> bool:
    """Deploy skill files to .claude/skills directory."""
    project_root = get_project_root()
    skill_dir = get_skill_dir()

    if dry_run:
        print(f"Would deploy to: {skill_dir}")
    else:
        # Create skill directory
        skill_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created skill directory: {skill_dir}")

    # Copy SKILL.md
    skill_md_src = project_root / SKILL_MD
    skill_md_dst = skill_dir / "SKILL.md"

    if skill_md_src.exists():
        if dry_run:
            print(f"Would copy: {skill_md_src} -> {skill_md_dst}")
        else:
            shutil.copy2(skill_md_src, skill_md_dst)
            print(f"Copied: SKILL.md")
    else:
        print(f"Warning: SKILL.md not found at {skill_md_src}")
        return False

    # Copy script files
    scripts_dir = skill_dir / "scripts"
    if not dry_run:
        scripts_dir.mkdir(exist_ok=True)

    for script_path in SKILL_FILES:
        src = project_root / script_path
        if src.exists():
            dst = scripts_dir / src.name
            if dry_run:
                print(f"Would copy: {src} -> {dst}")
            else:
                shutil.copy2(src, dst)
                print(f"Copied: {src.name}")
        else:
            print(f"Warning: Script not found: {script_path}")

    print(f"\nSkill deployed successfully to: {skill_dir}")
    return True


def check_skill() -> bool:
    """Check if skill needs update."""
    project_root = get_project_root()
    skill_dir = get_skill_dir()

    if not skill_dir.exists():
        print("Skill not installed")
        return False

    needs_update = False

    # Check SKILL.md
    src = project_root / SKILL_MD
    dst = skill_dir / "SKILL.md"
    if src.exists() and dst.exists():
        if src.stat().st_mtime > dst.stat().st_mtime:
            print(f"SKILL.md needs update (source is newer)")
            needs_update = True
    elif src.exists():
        print("SKILL.md missing from skill directory")
        needs_update = True

    # Check scripts
    for script_path in SKILL_FILES:
        src = project_root / script_path
        dst = skill_dir / "scripts" / Path(script_path).name
        if src.exists() and dst.exists():
            if src.stat().st_mtime > dst.stat().st_mtime:
                print(f"{Path(script_path).name} needs update (source is newer)")
                needs_update = True
        elif src.exists():
            print(f"{Path(script_path).name} missing from skill directory")
            needs_update = True

    if not needs_update:
        print("Skill is up to date")

    return needs_update


def remove_skill() -> bool:
    """Remove skill from .claude/skills directory."""
    skill_dir = get_skill_dir()

    if not skill_dir.exists():
        print("Skill not installed")
        return True

    shutil.rmtree(skill_dir)
    print(f"Removed skill: {skill_dir}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy Census Quality Check skill to .claude/skills"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if skill needs update"
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove skill from .claude/skills"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )

    args = parser.parse_args()

    if args.check:
        needs_update = check_skill()
        return 0 if not needs_update else 1
    elif args.remove:
        return 0 if remove_skill() else 1
    else:
        return 0 if deploy_skill(dry_run=args.dry_run) else 1


if __name__ == "__main__":
    sys.exit(main())
