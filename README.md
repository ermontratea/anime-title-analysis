
# Anime Title Analyzer

This is a web application built with **FastAPI** that analyzes the writing systems used in Japanese anime titles. It fetches data from the **AniList API** (GraphQL) and provides linguistic insights, including a breakdown of Hiragana, Katakana, and Kanji usage.

## Key Features
* **Multi-API Integration:** Combines AniList (GraphQL) for anime data and Jisho (REST) for Kanji definitions.
* **Automated Analysis:** Categorizes titles into Hiragana, Katakana, Kanji, or Mixed scripts based on Unicode ranges.
* **Kanji Insights:** Identifies the top 3 most frequent Kanji characters in your search results and displays their readings and meanings.
* **Asynchronous Performance:** Uses `httpx` and `asyncio.gather` to handle multiple API requests concurrently for faster results.

## How It Works
1. **Filter:** Select a year range and a genre.
2. **Fetch:** The app retrieves up to 500 anime titles matching your criteria.
3. **Analyze:** It counts the occurrences of different scripts and specific Kanji characters.
4. **Display:** Shows statistics and detailed dictionary entries for the most common characters found.

## Tech Stack
* **Backend:** FastAPI (Python)
* **HTTP Client:** Httpx (Async)
* **Templating:** Jinja2
* **APIs:** AniList (GraphQL), Jisho.org (REST)

## Preview

![]()
![]()



## Installation & Setup
1. Clone the repository:
   ```bash
   git clone (https://github.com/ermontratea/anime-title-analysis.git)
2. Install dependencies:
  ```bash
pip install -r requirements.txt
```
3. Start the server:
  ```bash
  `uvicorn main:app --reload`
  ```
4. Access the app at http://127.0.0.1:8000.

5. Automatically generated documentation (Swagger) available at  `http://127.0.0.1:8000/docs`

## Project Structure
- `main.py`: Main application logic and title analysis.
- templates/: HTML files for the search form and results page.
- `requirements.txt`: List of Python dependencies required to run the app.
