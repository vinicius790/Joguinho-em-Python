import datetime
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List

class DailyChallengeService:
    """Gerador de desafios diários para o Joguinho Apex."""
    
    def __init__(self, storage_path: str = "daily_challenges.json"):
        self.storage_path = Path(storage_path)

    def get_today_challenge(self) -> Dict[str, Any]:
        today_str = datetime.date.today().isoformat()
        seed = int(hashlib.sha256(today_str.encode()).hexdigest(), 16) % 10000
        
        challenges = [
            {"id": 1, "title": "Speed Run Apex", "description": "Complete any level in under 60 seconds.", "reward": 500, "target_score": 500},
            {"id": 2, "title": "No Damage Master", "description": "Pass a stage without taking damage.", "reward": 750, "target_score": 800},
            {"id": 3, "title": "Coin Collector", "description": "Collect at least 50 coins in a single run.", "reward": 400, "target_score": 600},
            {"id": 4, "title": "High Combo King", "description": "Achieve an 10x combo streak.", "reward": 600, "target_score": 700}
        ]
        
        selected = challenges[seed % len(challenges)]
        return {
            "date": today_str,
            "challenge": selected,
            "completed": False
        }

    def verify_completion(self, challenge_id: int, current_score: int) -> bool:
        today = self.get_today_challenge()
        if today["challenge"]["id"] == challenge_id:
            return current_score >= today["challenge"]["target_score"]
        return False
