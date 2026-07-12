import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")

headers = {
    "X-Auth-Token": API_KEY
}

url = "https://api.football-data.org/v4/competitions"

response = requests.get(
    url,
    headers=headers
)

print(response.status_code)

data = response.json()

print(response.status_code)
print(data)