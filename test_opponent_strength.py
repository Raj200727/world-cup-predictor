from pprint import pprint

from services.opponent_strength_service import (
    build_opponent_strength,
)

strengths = build_opponent_strength()

print(len(strengths))

pprint(strengths["France"])
pprint(strengths["Spain"])
pprint(strengths["Argentina"])
pprint(strengths["Morocco"])