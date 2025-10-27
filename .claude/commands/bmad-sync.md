# BMAD Sync Command

Sync BMAD (Baseball Model Analysis Dashboard) to the latest version.

## Usage
Run the BMAD sync utility to update all BMAD agents, tasks, workflows, and configurations to the latest version.

## Actions
1. Check current BMAD installation status
2. Compare with latest available version
3. Create backup of current installation
4. Download and sync latest BMAD files
5. Update Claude commands
6. Report sync status

## Script Location
The sync utility is located at: `apps/api/scripts/bmad_sync.py`

To run the sync:
```bash
cd apps/api/scripts
python bmad_sync.py --update
```

Or use the batch file:
```bash
apps/api/scripts/BMAD_SYNC.bat update
```