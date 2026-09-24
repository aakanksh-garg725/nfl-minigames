from collections import Counter
from app.providers.espn import ESPNProvider
from app.providers.base import ProviderError

provider = ESPNProvider()
for operation in ("state", "schedule", "projections", "results"):
    try:
        if operation == "state":
            print("Current contest:", provider.get_nfl_state())
        elif operation == "schedule":
            print("Scheduled games:", len(provider.get_schedule(2026, 3)))
        elif operation == "projections":
            rows = provider.get_week_projections(2026, 3)
            print("Projection counts:", dict(Counter(p.player.position for p in rows if p.projected_ppr > 0 and p.player.active)))
            print("Sample projections:", [(p.player.name, str(p.projected_ppr.quantize(__import__('decimal').Decimal('.01')))) for p in rows[:3]])
        else:
            previous = provider.get_week_results(2026, 2)
            print("Previous-week actual result count:", len(previous))
            print("Sample actuals:", [(r.player_id, str(r.actual_ppr)) for r in previous[:3]])
    except ProviderError as error:
        print(operation, str(error))
