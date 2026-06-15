import requests

try:
    response = requests.get('http://127.0.0.1:8000/jogador/raca/anao/')
    print("Status code:", response.status_code)
    print("Content length:", len(response.text))
    # check for some expected content
    if "raceDetailContainer" in response.text:
        print("Found raceDetailContainer!")
    else:
        print("WARNING: raceDetailContainer not found in response!")
    if "tab-content-regras" in response.text:
        print("Found tab-content-regras!")
    else:
        print("WARNING: tab-content-regras not found!")
except Exception as e:
    print("Error:", e)
