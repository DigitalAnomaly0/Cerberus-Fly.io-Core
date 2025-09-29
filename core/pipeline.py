
from typing import Dict, Any
from .models import DemoGovernor, DemoSeeder, DemoAntithesis
from .dedupe import group_duplicates

def run_pipeline(topic: str, seed_governor: int = 42, seed_seeder: int = 7, n: int = 5) -> Dict[str, Any]:
    gov = DemoGovernor()
    seed = DemoSeeder()
    anti = DemoAntithesis()

    claims = gov.run(topic=topic, seed=seed_governor, n=n)
    expanded = seed.run(claims, seed=seed_seeder)
    counters = anti.run(claims + expanded)

    dam_dup = group_duplicates(claims + expanded + counters)

    return {
        "topic": topic,
        "claims": claims,
        "expanded": expanded,
        "counters": counters,
        "dam_duplicate": dam_dup,
        "counts": {
            "claims": len(claims),
            "expanded": len(expanded),
            "counters": len(counters),
            "dup_groups": dam_dup["total_groups"]
        }
    }
