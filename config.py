# Clash of Clans Bot Configuration
# Define your exact deployment sequence here.
# The bot will execute these steps in order, dropping the specified 'count' of 'name' at the 'target' area.
# It will then wait 'delay' seconds before moving to the next step.

# Available targets:
# - "edge": Drops in a line along the red boundary
# - "single": Drops in a cluster on the red boundary
# - "core": Drops mathematically in the center of the base
# - "dynamic_dragon": Scans screen for live dragons to drop spells on
# - "dynamic_defense": Uses cached YOLO positions to drop on defenses
# - "townhall": Drops on the enemy Town Hall (YOLO cached)
# - "smart_freeze": Auto-targets highest-threat defenses (eagle > inferno > scatter > xbow > ad)

DEPLOYMENT_SEQUENCE = [
    # Phase 1: Main Push
    {"name": "dragon", "count": 20, "target": "edge", "delay": 0},
    
    # Phase 2: Heroes behind dragons
    {"name": "barbarian_king", "count": 1, "target": "single", "delay": 0},
    {"name": "archer_queen", "count": 1, "target": "single", "delay": 0},
    {"name": "grand_warden", "count": 1, "target": "single", "delay": 0},
    {"name": "minion_prince", "count": 1, "target": "single", "delay": 0},
    
    # Phase 3: Siege Machine -> Town Hall
    {"name": "stone_slammer", "count": 1, "target": "townhall", "delay": 0},
    
    # Phase 4: Rage on dragons
    {"name": "rage_spell", "count": 3, "target": "dynamic_dragon", "delay": 0},
    
    # Phase 5: Smart Freeze - auto-targets eagle, infernos, scattershots in priority order!
    {"name": "freeze_spell", "count": 5, "target": "smart_freeze", "delay": 5},
]
