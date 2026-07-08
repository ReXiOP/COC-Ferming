# Clash of Clans Bot Configuration
# Define your exact deployment sequence here.
# The bot will execute these steps in order, dropping the specified 'count' of 'name' at the 'target' area.
# It will then wait 'delay' seconds before moving to the next step.

# Available targets:
# - "edge": Drops in a line along the red boundary
# - "single": Drops in a cluster on the red boundary
# - "core": Drops mathematically in the center of the base
# - "dynamic_dragon": Scans screen for live dragons to drop spells on
# - "dynamic_defense": Scans screen for live infernos/air defenses to freeze
# - "townhall": Scans screen for the enemy Town Hall

DEPLOYMENT_SEQUENCE = [
    # Phase 1: Main Push
    {"name": "dragon", "count": 30, "target": "edge", "delay": 0},
    
    # Phase 2: Heroes behind dragons
    {"name": "barbarian_king", "count": 1, "target": "single", "delay": 0},
    {"name": "archer_queen", "count": 1, "target": "single", "delay": 0},
    {"name": "grand_warden", "count": 1, "target": "single", "delay": 0},
    {"name": "minion_prince", "count": 1, "target": "single", "delay": 0},
    
    # Phase 3: Support Troops (Now targeting the Town Hall with Siege!)
    {"name": "stone_slammer", "count": 1, "target": "townhall", "delay": 0},
    
    # Phase 4: Initial Spells (Dropped on dragons)
    {"name": "rage_spell", "count": 1, "target": "dynamic_dragon", "delay": 0},
    
    # Phase 5: Core Spells
    {"name": "rage_spell", "count": 1, "target": "dynamic_defense", "delay": 0},
    {"name": "freeze_spell", "count": 1, "target": "eagle", "delay": 10}, # Snipe the Eagle Artillery
    
    # Final Freezes
    {"name": "freeze_spell", "count": 3, "target": "inferno", "delay": 0, "verify": True}, # Freeze Infernos
]
