from services.fixture_service import load_api_fixtures

fixtures = load_api_fixtures()

print(f"Loaded {len(fixtures)} fixtures")
print()
for f in fixtures:
    if f["stage"] != "GROUP_STAGE":
        print(f["stage"], f["home_team_name"], "vs", f["away_team_name"])