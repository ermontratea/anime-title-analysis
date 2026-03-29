import asyncio
import httpx
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from collections import Counter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1"]
)

templates = Jinja2Templates(directory="templates")
#API nr1
ANILIST_URL = "https://graphql.anilist.co"

# funkcja analizująca japoński tytuł anime, czy zawiera on:
# - tylko hiraganę
# - tylko katakanę
# - tylko kanji
# - mieszankę tych trzech alfabetów
# - inaczej/brak tytułu
# na podstawie tej funkcji są potem zliczane tytuły w każdej kategorii
def analyze_title(title: str):
    if not title: return "none"
    has_hira = any('\u3040' <= c <= '\u309F' for c in title)
    has_kata = any('\u30A0' <= c <= '\u30FF' for c in title)
    has_kanji = any('\u4E00' <= c <= '\u9FFF' for c in title)
    has_romaji = any(('a' <= c <= 'z') or ('A' <= c <= 'Z') for c in title)
    if has_romaji:
        return "other"
    if has_hira and not has_kata and not has_kanji: return "hiragana"
    if has_kata and not has_hira and not has_kanji: return "katakana"
    if has_kanji and not has_hira and not has_kata: return "kanji"
    if has_hira or has_kata or has_kanji: return "mixed"
    return "other"

# zapytanie graph ql, zwraca 500 anime spełniających warunki (albo mniej),
# takie zapytanie jest wykonywane kilka razy (pagification - limit anime na stronę)
async def fetch_ani_list(client, year_from, year_to, genre, page):

    genre_filter = ", genre_in: [$genre]" if genre != "all" else ""
    query_params = "$startFrom: FuzzyDateInt, $startTo: FuzzyDateInt, $page: Int"
    if genre != "all":
        query_params += ", $genre: String"
        variables = {
            "startFrom": int(f"{year_from}0101"),
            "startTo": int(f"{year_to}1231"),
            "page": page,
            "genre": genre
        }
    else:
        variables = {
            "startFrom": int(f"{year_from}0101"),
            "startTo": int(f"{year_to}1231"),
            "page": page
        }
    query = f"""
    query ({query_params}) {{
      Page(page: $page, perPage: 50) {{
        media(startDate_greater: $startFrom, startDate_lesser: $startTo {genre_filter}, type: ANIME) {{
          title {{ native }}
          popularity
        }}
      }}
    }}
    """



    try:
        response = await client.post(ANILIST_URL, json={"query": query, "variables": variables}, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Błąd komunikacji z AniList: {e.response.status_code}")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="Serwis AniList nie odpowiedział w terminie.")

#pobieranie danych z Jisho API (API nr2) z obsługa wyjątków
async def get_kanji_details(client, kanji):
    url = f"https://jisho.org/api/v1/search/words?keyword={kanji}"
    try:
        res = await client.get(url, timeout=5.0)
        res.raise_for_status()
        data = res.json()

        if not data.get("data") or len(data["data"]) == 0:
            return {"reading": "N/A", "main_meaning": "Nie znaleziono", "words": []}

        first_match = data["data"][0]
        main_reading = first_match["japanese"][0].get("reading", "N/A")
        main_meaning = ", ".join(first_match["senses"][0].get("english_definitions", []))

        words_list = []
        for entry in data["data"][:3]:
            word = entry["japanese"][0].get("word", entry["japanese"][0].get("reading"))
            reading = entry["japanese"][0].get("reading", "")
            meaning = ", ".join(entry["senses"][0].get("english_definitions", [])[:2])
            words_list.append(f"{word} ({reading}) - {meaning}")

        return {
            "reading": main_reading,
            "main_meaning": main_meaning,
            "words": words_list
        }
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail=f"Timeout podczas szukania znaczenia znaku: {kanji}"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Błąd zewnętrznego API Jisho: Status {e.response.status_code}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Nieoczekiwany błąd podczas pobierania danych kanji: {str(e)}"
        )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Strona główna: tutaj można sprowadzić dane do wykonania analizy
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request,
                  yearFrom: int = Form(..., ge=1917,le=2026),
                  yearTo: int = Form(..., ge=1917, le=2026),
                  genre: str = Form(...)):
    """
    Używając podanego zakresu lat i gatunku analizuje japońskie tytuły anime.
    Dane o anime popiera z AniList (Graph QL).
    Sprawdza jakimi alfabetami są zapisane tytuły a następnie zwraca statystyki.
    Następnie wyświetla podstawowe informacje o najczęściej powtarzające się w tych tytułach znaki kanji -
    pobierając dane z Jisho API (REST).
    """
    async with httpx.AsyncClient() as client:
        #walidacja danych wejściowych
        if yearFrom > yearTo:
            raise HTTPException(status_code=400, detail="Rok początkowy nie może być większy niż końcowy.")
        #pobranie maksymalnie 10 stron anime (500 tytułów), wartość p można zmienić, ale zewnątrzny serwer API
        # ma limit zapytań na minutę, więc lepiej uważać
        #wszystkie zapytania wykonywane równolegle
        tasks = [fetch_ani_list(client, yearFrom, yearTo, genre, p) for p in range(1, 11)]
        responses = await asyncio.gather(*tasks)

        all_media = []
        for r in responses:
            if r.get("data") and r["data"]["Page"]["media"]:
                all_media.extend(r["data"]["Page"]["media"])

        valid_media = [m for m in all_media if m.get("title") and m["title"].get("native")]

        if not valid_media:
            return HTMLResponse("<h2>Nie znaleziono tytułów z nazwami japońskimi.</h2><a href='/'>Powrót</a>")

        most_popular_anime = max(valid_media, key=lambda x: x.get('popularity', 0))
        top_title = most_popular_anime['title']['native']

        stats = {"total": len(valid_media), "hiragana": 0, "katakana": 0, "kanji": 0, "mixed": 0, "none": 0, "other": 0}
        all_kanji_chars = []

        for anime in valid_media:
            title = anime["title"]["native"]
            if title is None:
                continue

            res = analyze_title(title)
            stats[res] += 1
            all_kanji_chars.extend([c for c in title if '\u4E00' <= c <= '\u9FFF'])

        most_common = Counter(all_kanji_chars).most_common(3)

        #tak jak wcześniej zapytania wykonywane równoglegle
        kanji_tasks = [get_kanji_details(client, char) for char, count in most_common]
        details_results = await asyncio.gather(*kanji_tasks)

        kanji_results = []
        for i, (char, count) in enumerate(most_common):
            kanji_results.append({
                "char": char,
                "count": count,
                "reading": details_results[i]["reading"],
                "main_meaning": details_results[i]["main_meaning"],
                "words": details_results[i]["words"]
            })

    return templates.TemplateResponse("results.html", {
        "request": request,
        "stats": stats,
        "kanji_results": kanji_results,
        "start_year": yearFrom,
        "end_year": yearTo,
        "genre": genre,
        "top_title": top_title
    })