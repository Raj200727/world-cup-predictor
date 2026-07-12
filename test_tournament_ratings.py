from pprint import pprint

from services.tournament_rating_service import (
    build_tournament_ratings,
)

ratings = build_tournament_ratings()

print(len(ratings))
print()

pprint(ratings["France"])