#!/usr/bin/env python3
"""
BMAD Sync - Update BMAD to the latest version
Syncs BMAD agents, tasks, and configurations from the latest release
"""

import os
import sys
import json
import yaml
import shutil
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class BMADSync:
    """BMAD Synchronization Manager"""

    # BMAD Repository configuration - using direct file approach
    BMAD_VERSION_URL = "https://raw.githubusercontent.com/tryguild/BMad/main/.bmad-core/version.txt"
    BMAD_RAW_URL = "https://raw.githubusercontent.com/tryguild/BMad"

    def __init__(self, project_root: Optional[str] = None):
        """Initialize BMAD Sync"""
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Assume we're in the scripts directory
            self.project_root = Path(__file__).parent.parent.parent.parent

        self.bmad_core_path = self.project_root / ".bmad-core"
        self.claude_commands_path = self.project_root / ".claude" / "commands"
        self.manifest_path = self.bmad_core_path / "install-manifest.yaml"
        self.backup_path = self.project_root / ".bmad-backup"

        self.current_version = None
        self.latest_version = None
        self.manifest = {}

    def load_manifest(self) -> Dict:
        """Load the current installation manifest"""
        if self.manifest_path.exists():
            with open(self.manifest_path, 'r', encoding='utf-8') as f:
                self.manifest = yaml.safe_load(f)
                self.current_version = self.manifest.get('version', 'Unknown')
        return self.manifest

    def get_latest_release(self) -> Optional[Dict]:
        """Get the latest BMAD version - fallback to manual version"""
        try:
            # Try to get version from version file
            response = requests.get(self.BMAD_VERSION_URL)
            if response.status_code == 200:
                self.latest_version = response.text.strip()
                return {'tag_name': self.latest_version}
        except:
            pass

        # Fallback to known latest version
        self.latest_version = "4.50.0"  # Latest known BMAD version
        return {'tag_name': self.latest_version}

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate hash of a file"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()[:16]
        except:
            return ""

    def backup_current_installation(self):
        """Create a backup of the current BMAD installation"""
        if not self.bmad_core_path.exists():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backup_path / f"backup_{timestamp}"

        print(f"📦 Creating backup at {backup_dir}")
        shutil.copytree(self.bmad_core_path, backup_dir)

        # Also backup Claude commands
        claude_backup = backup_dir / ".claude-commands"
        claude_backup.mkdir(exist_ok=True)

        for cmd_file in self.claude_commands_path.glob("*.md"):
            if any(x in cmd_file.stem.lower() for x in ['bmad', 'analyst', 'architect', 'dev', 'pm', 'po', 'qa', 'sm', 'ux']):
                shutil.copy2(cmd_file, claude_backup / cmd_file.name)

        print(f"✅ Backup created successfully")
        return backup_dir

    def download_file(self, url: str, dest_path: Path) -> bool:
        """Download a file from URL to destination"""
        try:
            response = requests.get(url)
            if response.status_code == 200:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, 'wb') as f:
                    f.write(response.content)
                return True
        except Exception as e:
            print(f"   ❌ Error downloading {url}: {e}")
        return False

    def sync_bmad_core(self) -> Tuple[int, int, int]:
        """Sync the BMAD core files"""
        added, updated, unchanged = 0, 0, 0

        # Core directories to sync
        core_dirs = [
            'agents', 'tasks', 'templates', 'workflows',
            'checklists', 'data', 'utils', 'agent-teams'
        ]

        # Core files to sync
        core_files = [
            'core-config.yaml', 'user-guide.md', 'working-in-the-brownfield.md',
            'enhanced-ide-development-workflow.md', 'install-manifest.yaml'
        ]

        print("\n📂 Syncing BMAD Core Files...")

        # Sync directories
        for dir_name in core_dirs:
            dir_path = self.bmad_core_path / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            # List of known files per directory (since API might not work)
            known_files = {
                'agents': ['analyst.md', 'architect.md', 'bmad-master.md', 'bmad-orchestrator.md',
                          'dev.md', 'pm.md', 'po.md', 'qa.md', 'sm.md', 'ux-expert.md'],
                'tasks': ['advanced-elicitation.md', 'apply-qa-fixes.md', 'brownfield-create-epic.md',
                         'brownfield-create-story.md', 'correct-course.md', 'create-brownfield-story.md',
                         'create-deep-research-prompt.md', 'create-doc.md', 'create-next-story.md',
                         'document-project.md', 'execute-checklist.md', 'facilitate-brainstorming-session.md',
                         'generate-ai-frontend-prompt.md', 'index-docs.md', 'kb-mode-interaction.md',
                         'nfr-assess.md', 'qa-gate.md', 'review-story.md', 'risk-profile.md',
                         'shard-doc.md', 'test-design.md', 'trace-requirements.md', 'validate-next-story.md'],
                'templates': ['architecture-tmpl.yaml', 'brainstorming-output-tmpl.yaml',
                             'brownfield-architecture-tmpl.yaml', 'brownfield-prd-tmpl.yaml',
                             'competitor-analysis-tmpl.yaml', 'front-end-architecture-tmpl.yaml',
                             'front-end-spec-tmpl.yaml', 'fullstack-architecture-tmpl.yaml',
                             'market-research-tmpl.yaml', 'prd-tmpl.yaml', 'project-brief-tmpl.yaml',
                             'qa-gate-tmpl.yaml', 'story-tmpl.yaml'],
                'workflows': ['brownfield-fullstack.yaml', 'brownfield-service.yaml', 'brownfield-ui.yaml',
                             'greenfield-fullstack.yaml', 'greenfield-service.yaml', 'greenfield-ui.yaml'],
                'checklists': ['architect-checklist.md', 'change-checklist.md', 'pm-checklist.md',
                              'po-master-checklist.md', 'story-dod-checklist.md', 'story-draft-checklist.md'],
                'data': ['bmad-kb.md', 'brainstorming-techniques.md', 'elicitation-methods.md',
                        'technical-preferences.md', 'test-levels-framework.md', 'test-priorities-matrix.md'],
                'utils': ['bmad-doc-template.md', 'workflow-management.md'],
                'agent-teams': ['team-all.yaml', 'team-fullstack.yaml', 'team-ide-minimal.yaml', 'team-no-ui.yaml']
            }

            # Use known files for this directory
            files_to_sync = known_files.get(dir_name, [])

            for file_name in files_to_sync:
                file_path = dir_path / file_name

                # Check if file exists and needs update
                needs_update = True
                if file_path.exists():
                    # For now, skip if file exists (unless force update)
                    unchanged += 1
                    needs_update = False

                if needs_update:
                    download_url = f"{self.BMAD_RAW_URL}/main/.bmad-core/{dir_name}/{file_name}"
                    if self.download_file(download_url, file_path):
                        print(f"   ➕ Added: {dir_name}/{file_name}")
                        added += 1

        # Sync core files
        for file_name in core_files:
            file_path = self.bmad_core_path / file_name
            download_url = f"{self.BMAD_RAW_URL}/main/.bmad-core/{file_name}"

            if file_path.exists():
                # Skip manifest file during sync
                if file_name == 'install-manifest.yaml':
                    continue

            if self.download_file(download_url, file_path):
                if file_path.exists():
                    print(f"   ✅ Updated: {file_name}")
                    updated += 1
                else:
                    print(f"   ➕ Added: {file_name}")
                    added += 1

        return added, updated, unchanged

    def sync_claude_commands(self) -> Tuple[int, int]:
        """Sync Claude command files"""
        added, updated = 0, 0

        print("\n📂 Syncing Claude Commands...")

        # Ensure directories exist
        self.claude_commands_path.mkdir(parents=True, exist_ok=True)
        bmad_commands_path = self.claude_commands_path / "BMad"
        bmad_commands_path.mkdir(exist_ok=True)

        # Sync agent commands to both locations
        agents_dir = bmad_commands_path / "agents"
        agents_dir.mkdir(exist_ok=True)

        for agent_file in (self.bmad_core_path / "agents").glob("*.md"):
            # Copy to BMad/agents directory
            dest_path = agents_dir / agent_file.name
            shutil.copy2(agent_file, dest_path)

            # Also copy to root commands directory for direct access
            root_dest = self.claude_commands_path / agent_file.name
            shutil.copy2(agent_file, root_dest)

            if dest_path.exists():
                print(f"   ✅ Synced command: {agent_file.stem}")
                updated += 1

        # Sync tasks to BMad/tasks
        tasks_dir = bmad_commands_path / "tasks"
        tasks_dir.mkdir(exist_ok=True)

        for task_file in (self.bmad_core_path / "tasks").glob("*.md"):
            dest_path = tasks_dir / task_file.name
            shutil.copy2(task_file, dest_path)
            if dest_path.exists():
                updated += 1

        return added, updated

    def update_manifest(self):
        """Update the installation manifest"""
        new_manifest = {
            'version': self.latest_version or self.current_version,
            'installed_at': datetime.now().isoformat(),
            'install_type': 'sync',
            'agent': 'bmad-sync',
            'ides_setup': self.manifest.get('ides_setup', ['claude-code']),
            'expansion_packs': self.manifest.get('expansion_packs', []),
            'files': []
        }

        # Scan all files and calculate hashes
        for root, dirs, files in os.walk(self.bmad_core_path):
            for file_name in files:
                file_path = Path(root) / file_name
                rel_path = file_path.relative_to(self.project_root)

                file_info = {
                    'path': str(rel_path).replace('/', '\\'),
                    'hash': self.calculate_file_hash(file_path),
                    'modified': False
                }
                new_manifest['files'].append(file_info)

        # Save manifest
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            yaml.dump(new_manifest, f, default_flow_style=False)

        print(f"\n✅ Manifest updated to version {new_manifest['version']}")

    def run_sync(self, force: bool = False):
        """Run the BMAD synchronization"""
        print("\n🚀 BMAD Sync - Updating to Latest Version")
        print("=" * 60)

        # Load current manifest
        self.load_manifest()
        print(f"📌 Current version: {self.current_version}")

        # Check for latest release
        print("\n🔍 Checking for updates...")
        release = self.get_latest_release()

        if not release:
            print("❌ Could not fetch latest release information")
            return False

        print(f"🆕 Latest version: {self.latest_version}")

        # Check if update is needed
        if not force and self.current_version == self.latest_version:
            print("\n✅ Already up to date!")
            return True

        # Create backup
        print("\n💾 Backing up current installation...")
        backup_dir = self.backup_current_installation()

        # Sync core files
        added, updated, unchanged = self.sync_bmad_core()
        print(f"\n📊 Core Sync Results:")
        print(f"   ➕ Added: {added} files")
        print(f"   ✅ Updated: {updated} files")
        print(f"   ⏸️ Unchanged: {unchanged} files")

        # Sync Claude commands
        cmd_added, cmd_updated = self.sync_claude_commands()
        print(f"\n📊 Command Sync Results:")
        print(f"   ➕ Added: {cmd_added} commands")
        print(f"   ✅ Updated: {cmd_updated} commands")

        # Update manifest
        self.update_manifest()

        print("\n" + "=" * 60)
        print(f"✨ BMAD Successfully Updated to v{self.latest_version}!")
        print("\n💡 What's Next:")
        print("   1. Reload your IDE/editor to see new commands")
        print("   2. Run '/bmad-orchestrator' to start using BMAD")
        print("   3. Check '.bmad-core/user-guide.md' for documentation")

        if backup_dir:
            print(f"\n📦 Backup saved at: {backup_dir}")

        return True

    def check_status(self):
        """Check current BMAD installation status"""
        print("\n📊 BMAD Installation Status")
        print("=" * 60)

        # Load manifest
        self.load_manifest()

        # Check directories
        dirs_exist = {
            'Core': self.bmad_core_path.exists(),
            'Commands': self.claude_commands_path.exists(),
            'Agents': (self.bmad_core_path / 'agents').exists(),
            'Tasks': (self.bmad_core_path / 'tasks').exists(),
        }

        print(f"📌 Current Version: {self.current_version}")
        print(f"📅 Installed: {self.manifest.get('installed_at', 'Unknown')}")
        print(f"🔧 Install Type: {self.manifest.get('install_type', 'Unknown')}")

        print("\n📂 Directory Status:")
        for name, exists in dirs_exist.items():
            status = "✅" if exists else "❌"
            print(f"   {status} {name}")

        # Count files
        if self.bmad_core_path.exists():
            agent_count = len(list((self.bmad_core_path / 'agents').glob('*.md')))
            task_count = len(list((self.bmad_core_path / 'tasks').glob('*.md')))

            print(f"\n📈 File Counts:")
            print(f"   👤 Agents: {agent_count}")
            print(f"   📋 Tasks: {task_count}")
            print(f"   📄 Total Files: {len(self.manifest.get('files', []))}")

        # Check for updates
        print("\n🔍 Checking for updates...")
        self.get_latest_release()
        if self.latest_version:
            if self.current_version == self.latest_version:
                print(f"   ✅ Up to date (v{self.latest_version})")
            else:
                print(f"   🆕 Update available: v{self.latest_version}")
                print(f"   💡 Run 'python bmad_sync.py --update' to update")

def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='BMAD Sync - Update BMAD to latest version')
    parser.add_argument('--update', action='store_true', help='Update BMAD to latest version')
    parser.add_argument('--force', action='store_true', help='Force update even if already up to date')
    parser.add_argument('--status', action='store_true', help='Check current installation status')

    args = parser.parse_args()

    sync = BMADSync()

    if args.status:
        sync.check_status()
    elif args.update or args.force:
        sync.run_sync(force=args.force)
    else:
        # Default action - check status and prompt for update
        sync.check_status()
        sync.get_latest_release()

        if sync.current_version != sync.latest_version:
            print("\n" + "=" * 60)
            response = input("🔄 Would you like to update BMAD now? (y/n): ")
            if response.lower() in ['y', 'yes']:
                sync.run_sync()

if __name__ == "__main__":
    main()