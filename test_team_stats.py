from services.team_stats_service import build_team_stats
from pprint import pprint

stats = build_team_stats()

print(len(stats))


pprint(stats["France"])

print()

pprint(stats["England"])

print()

pprint(stats["Argentina"])