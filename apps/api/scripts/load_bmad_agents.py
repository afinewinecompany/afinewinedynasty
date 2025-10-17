#!/usr/bin/env python3
"""
BMAD Agent Loader and Manager
Loads and manages BMAD agents for the A Fine Wine Dynasty project
"""

import yaml
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class AgentRole(Enum):
    """BMAD Agent Roles"""
    ANALYST = "analyst"
    ARCHITECT = "architect"
    DEV = "dev"
    PM = "pm"
    PO = "po"
    QA = "qa"
    SM = "sm"
    UX_EXPERT = "ux-expert"
    BMAD_MASTER = "bmad-master"
    BMAD_ORCHESTRATOR = "bmad-orchestrator"

@dataclass
class BMADAgent:
    """Represents a BMAD Agent"""
    name: str
    id: str
    title: str
    icon: str
    role: str
    when_to_use: str
    commands: Dict[str, Any]
    dependencies: Dict[str, List[str]]
    persona: Dict[str, Any]
    file_path: str

class BMADAgentLoader:
    """Loads and manages BMAD agents"""

    def __init__(self, project_root: Optional[str] = None):
        """Initialize the BMAD Agent Loader"""
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Assume we're in the scripts directory
            self.project_root = Path(__file__).parent.parent.parent.parent

        self.bmad_core_path = self.project_root / ".bmad-core"
        self.agents_path = self.bmad_core_path / "agents"
        self.config_path = self.bmad_core_path / "core-config.yaml"

        self.agents: Dict[str, BMADAgent] = {}
        self.core_config: Dict[str, Any] = {}

    def load_core_config(self) -> Dict[str, Any]:
        """Load the core BMAD configuration"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Core config not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.core_config = yaml.safe_load(f)

        print(f"✅ Loaded core config from {self.config_path}")
        return self.core_config

    def parse_agent_file(self, file_path: Path) -> Optional[BMADAgent]:
        """Parse a single agent markdown file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract YAML block from markdown
            yaml_match = re.search(r'```yaml\n(.*?)\n```', content, re.DOTALL)
            if not yaml_match:
                print(f"⚠️  No YAML block found in {file_path.name}")
                return None

            yaml_content = yaml_match.group(1)
            agent_data = yaml.safe_load(yaml_content)

            # Extract agent information
            if 'agent' not in agent_data:
                print(f"⚠️  No 'agent' section in {file_path.name}")
                return None

            agent_info = agent_data['agent']

            return BMADAgent(
                name=agent_info.get('name', ''),
                id=agent_info.get('id', ''),
                title=agent_info.get('title', ''),
                icon=agent_info.get('icon', ''),
                role=agent_info.get('role', ''),
                when_to_use=agent_info.get('whenToUse', ''),
                commands=agent_data.get('commands', {}),
                dependencies=agent_data.get('dependencies', {}),
                persona=agent_data.get('persona', {}),
                file_path=str(file_path)
            )

        except Exception as e:
            print(f"❌ Error parsing {file_path.name}: {e}")
            return None

    def load_all_agents(self) -> Dict[str, BMADAgent]:
        """Load all BMAD agents from the agents directory"""
        if not self.agents_path.exists():
            raise FileNotFoundError(f"Agents directory not found: {self.agents_path}")

        agent_files = list(self.agents_path.glob("*.md"))
        print(f"\n🔍 Found {len(agent_files)} agent files in {self.agents_path}")

        for agent_file in agent_files:
            print(f"📄 Loading agent: {agent_file.name}")
            agent = self.parse_agent_file(agent_file)

            if agent:
                self.agents[agent.id] = agent
                print(f"   ✅ {agent.icon} {agent.name} ({agent.id}) - {agent.title}")
            else:
                print(f"   ❌ Failed to load {agent_file.name}")

        print(f"\n✅ Successfully loaded {len(self.agents)} agents")
        return self.agents

    def get_agent(self, agent_id: str) -> Optional[BMADAgent]:
        """Get a specific agent by ID"""
        return self.agents.get(agent_id)

    def list_agents(self):
        """List all loaded agents with their details"""
        print("\n" + "="*80)
        print("BMAD AGENTS ROSTER")
        print("="*80)

        for agent_id, agent in self.agents.items():
            print(f"\n{agent.icon} {agent.name.upper()}")
            print(f"   ID: {agent_id}")
            print(f"   Title: {agent.title}")
            print(f"   Role: {agent.role}")
            print(f"   When to use: {agent.when_to_use[:100]}...")

            # Handle commands which might be a list or dict
            if isinstance(agent.commands, dict):
                print(f"   Commands: {len(agent.commands)} available")
                cmd_list = list(agent.commands.keys())[:3]
                print(f"   Sample commands: {', '.join(cmd_list)}")
            elif isinstance(agent.commands, list):
                print(f"   Commands: {len(agent.commands)} available")
                # Extract command names from list items (which may be dicts with command: description)
                cmd_names = []
                for cmd in agent.commands[:3]:
                    if isinstance(cmd, dict):
                        # Get the first key from the dict (command name)
                        cmd_name = list(cmd.keys())[0] if cmd else ""
                        cmd_names.append(cmd_name)
                    else:
                        cmd_names.append(str(cmd))
                if cmd_names:
                    print(f"   Sample commands: {', '.join(cmd_names)}")

    def show_agent_commands(self, agent_id: str):
        """Show all commands for a specific agent"""
        agent = self.get_agent(agent_id)
        if not agent:
            print(f"❌ Agent '{agent_id}' not found")
            return

        print(f"\n{agent.icon} {agent.name} Commands:")
        print("-" * 60)

        if isinstance(agent.commands, dict):
            for cmd, details in agent.commands.items():
                if isinstance(details, dict):
                    desc = details.get('description', 'No description')
                    print(f"  *{cmd}: {desc}")
                else:
                    print(f"  *{cmd}")
        elif isinstance(agent.commands, list):
            for cmd in agent.commands:
                if isinstance(cmd, dict):
                    # Get the first key-value pair from the dict
                    for cmd_name, cmd_desc in cmd.items():
                        print(f"  *{cmd_name}: {cmd_desc}")
                else:
                    print(f"  *{cmd}")

    def load_team_bundle(self, bundle_name: str) -> List[str]:
        """Load a team bundle and return the list of agent IDs"""
        bundle_path = self.bmad_core_path / "agent-teams" / f"{bundle_name}.yaml"

        if not bundle_path.exists():
            print(f"❌ Team bundle not found: {bundle_path}")
            return []

        with open(bundle_path, 'r', encoding='utf-8') as f:
            bundle_data = yaml.safe_load(f)

        agents = bundle_data.get('agents', [])
        bundle_info = bundle_data.get('bundle', {})

        print(f"\n📦 Loading Team Bundle: {bundle_info.get('name', bundle_name)}")
        print(f"   {bundle_info.get('icon', '')} {bundle_info.get('description', '')}")
        print(f"   Agents in bundle: {', '.join(agents)}")

        return agents

    def activate_agent(self, agent_id: str):
        """Simulate agent activation (display activation message)"""
        agent = self.get_agent(agent_id)
        if not agent:
            print(f"❌ Cannot activate: Agent '{agent_id}' not found")
            return

        print("\n" + "="*80)
        print(f"ACTIVATING BMAD AGENT: {agent.name.upper()}")
        print("="*80)
        print(f"\n{agent.icon} Hello! I am {agent.name}, your {agent.title}.")
        print(f"\nRole: {agent.role}")
        print(f"When to use me: {agent.when_to_use}")

        if agent.persona.get('greeting'):
            print(f"\n{agent.persona['greeting']}")

        print("\n📋 Available Commands:")
        for cmd in list(agent.commands.keys())[:5]:
            print(f"   *{cmd}")

        print(f"\n💡 Type '*help' to see all available commands")
        print(f"💡 Type 'exit' to deactivate this agent")
        print("\n" + "="*80)

def main():
    """Main function to demonstrate BMAD agent loading"""
    print("🚀 BMAD Agent Loader - A Fine Wine Dynasty")
    print("="*80)

    # Initialize the loader
    loader = BMADAgentLoader()

    # Load core configuration
    try:
        config = loader.load_core_config()
        print(f"   Project uses PRD v{config['prd']['prdVersion']}")
        print(f"   Slash prefix: /{config.get('slashPrefix', 'BMad')}")
    except Exception as e:
        print(f"❌ Failed to load core config: {e}")
        return

    # Load all agents
    try:
        agents = loader.load_all_agents()
    except Exception as e:
        print(f"❌ Failed to load agents: {e}")
        return

    # List all agents
    loader.list_agents()

    # Show available team bundles
    print("\n📦 Available Team Bundles:")
    team_bundles = ["team-all", "team-fullstack", "team-no-ui", "team-ide-minimal"]
    for bundle in team_bundles:
        bundle_path = loader.bmad_core_path / "agent-teams" / f"{bundle}.yaml"
        if bundle_path.exists():
            print(f"   - {bundle}")

    # Example: Load a specific team
    print("\n" + "="*80)
    print("LOADING FULLSTACK TEAM")
    print("="*80)
    team_agents = loader.load_team_bundle("team-fullstack")

    # Example: Activate the orchestrator
    print("\n" + "="*80)
    print("EXAMPLE: ACTIVATING ORCHESTRATOR")
    print("="*80)
    loader.activate_agent("bmad-orchestrator")

    # Show commands for dev agent
    print("\n" + "="*80)
    print("DEV AGENT COMMANDS")
    print("="*80)
    loader.show_agent_commands("dev")

    print("\n✅ BMAD Agents loaded and ready!")
    print("\n💡 Usage in your code:")
    print("   from load_bmad_agents import BMADAgentLoader")
    print("   loader = BMADAgentLoader()")
    print("   agents = loader.load_all_agents()")
    print("   dev_agent = loader.get_agent('dev')")
    print("   loader.activate_agent('dev')")

if __name__ == "__main__":
    main()