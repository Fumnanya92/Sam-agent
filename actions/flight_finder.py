# actions/flight_finder.py
# Flight Finder — adapted from Mark-XXX-main.
# Gemini calls replaced with agent/llm_bridge.py (Ollama-first, OpenAI fallback).
#
# Flow:
#   1. Parse origin, destination, date, passengers from parameters
#   2. Open Google Flights via browser_control
#   3. Scrape results via get_text
#   4. Parse with AI → structured flight data
#   5. Speak top results

import json
import re
import sys
import subprocess
import platform
from datetime import datetime, timedelta
from pathlib import Path


def _parse_date(raw: str) -> str:
    """Converts natural language date to YYYY-MM-DD."""
    raw = raw.strip()

    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw

    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    today = datetime.now()
    lower = raw.lower()
    relative_map = {
        "today":    today,
        "tomorrow": today + timedelta(days=1),
    }
    for key, val in relative_map.items():
        if key in lower:
            return val.strftime("%Y-%m-%d")

    # AI fallback for ambiguous dates
    try:
        from agent.llm_bridge import agent_llm_call
        today_str = today.strftime("%Y-%m-%d")
        result = agent_llm_call(
            "You convert date strings. Return ONLY the date in YYYY-MM-DD format, nothing else.",
            f"Today is {today_str}. Convert this date: '{raw}'",
            require_json=False,
        ).strip()
        if re.match(r"\d{4}-\d{2}-\d{2}", result):
            return result
    except Exception:
        pass

    month_map = {
        "january": 1,  "february": 2,  "march": 3,    "april": 4,
        "may": 5,      "june": 6,      "july": 7,     "august": 8,
        "september": 9,"october": 10,  "november": 11,"december": 12,
    }
    for month_name, month_num in month_map.items():
        if month_name in lower:
            day_match = re.search(r"\d{1,2}", raw)
            if day_match:
                day  = int(day_match.group())
                year = today.year if month_num >= today.month else today.year + 1
                return f"{year}-{month_num:02d}-{day:02d}"

    return today.strftime("%Y-%m-%d")


def _build_google_flights_url(
    origin:      str,
    destination: str,
    date:        str,
    return_date: str = None,
    passengers:  int = 1,
    cabin:       str = "economy",
) -> str:
    """Builds a Google Flights URL with pre-filled search parameters."""
    cabin_map = {
        "economy": "1", "premium": "2", "business": "3", "first": "4",
    }
    cabin_code = cabin_map.get(cabin.lower(), "1")
    base = "https://www.google.com/travel/flights"

    if return_date:
        url = (
            f"{base}?q=Flights+from+{origin}+to+{destination}"
            f"+on+{date}+returning+{return_date}"
        )
    else:
        url = f"{base}?q=Flights+from+{origin}+to+{destination}+on+{date}"

    return url


def _search_flights_browser(
    origin:      str,
    destination: str,
    date:        str,
    return_date: str,
    passengers:  int,
    cabin:       str,
) -> tuple:
    """Opens Google Flights in browser, waits, scrapes text. Returns (raw_text, page_url)."""
    from actions.browser_control import browser_control
    import time

    url = _build_google_flights_url(
        origin, destination, date, return_date, passengers, cabin
    )

    print(f"[FlightFinder] Opening: {url}")
    browser_control({"action": "go_to", "url": url})
    time.sleep(5)

    result = browser_control({"action": "get_text"})
    return result or "", url


def _parse_flights_with_ai(
    raw_text:    str,
    origin:      str,
    destination: str,
    date:        str,
) -> list:
    """Sends raw page text to AI and extracts structured flight data. Returns list of flight dicts."""
    from agent.llm_bridge import agent_llm_call

    truncated = raw_text[:12000]

    system_prompt = (
        "You are a flight data extraction expert. "
        "Extract flight information from raw webpage text. "
        "Return ONLY valid JSON array. No explanation, no markdown."
    )
    user_prompt = (
        f"Extract flight options from {origin} to {destination} on {date} "
        f"from this Google Flights page text:\n\n{truncated}\n\n"
        f"Return a JSON array of up to 5 flights:\n"
        f'[{{"airline": "...", "departure": "HH:MM", "arrival": "HH:MM", '
        f'"duration": "Xh Ym", "stops": 0, "price": "...", "currency": "..."}}]\n'
        f"If no flights found, return: []"
    )

    try:
        text    = agent_llm_call(system_prompt, user_prompt, require_json=True)
        text    = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
        flights = json.loads(text)
        return flights if isinstance(flights, list) else []
    except Exception as e:
        print(f"[FlightFinder] Parse failed: {e}")
        return []


def _format_spoken(
    flights:     list,
    origin:      str,
    destination: str,
    date:        str,
) -> str:
    """Formats flights for spoken output."""
    if not flights:
        return (
            f"I couldn't find any flights from {origin} to {destination} "
            f"on {date}. The page may not have loaded correctly."
        )

    lines = [f"Here are the flights from {origin} to {destination} on {date}."]

    for i, f in enumerate(flights[:5], 1):
        airline   = f.get("airline",   "Unknown airline")
        departure = f.get("departure", "--:--")
        arrival   = f.get("arrival",   "--:--")
        duration  = f.get("duration",  "")
        stops     = f.get("stops",     0)
        price     = f.get("price",     "")
        currency  = f.get("currency",  "")

        stop_str  = "non-stop" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
        price_str = f"{price} {currency}".strip() if price else "price unavailable"
        dur_str   = f", {duration}" if duration else ""

        lines.append(
            f"Option {i}: {airline}, departing {departure}, arriving {arrival}"
            f"{dur_str}, {stop_str}, {price_str}."
        )

    cheapest = min(
        (f for f in flights if f.get("price")),
        key=lambda x: re.sub(r"[^\d]", "", str(x.get("price", "99999"))) or "99999",
        default=None,
    )
    if cheapest:
        lines.append(
            f"The cheapest option is {cheapest.get('airline')} "
            f"at {cheapest.get('price')} {cheapest.get('currency', '')}."
        )

    return " ".join(lines)


def _format_notepad(
    flights:     list,
    origin:      str,
    destination: str,
    date:        str,
    return_date: str,
    page_url:    str,
) -> str:
    """Formats flights for text file — detailed and readable."""
    lines = [
        "Sam — Flight Search Results",
        "─" * 50,
        f"Route     : {origin} -> {destination}",
        f"Date      : {date}",
    ]
    if return_date:
        lines.append(f"Return    : {return_date}")
    lines += [
        f"Searched  : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Source    : {page_url}",
        "─" * 50,
        "",
    ]

    if not flights:
        lines.append("No flights found.")
    else:
        for i, f in enumerate(flights, 1):
            stops    = f.get("stops", 0)
            stop_str = "Non-stop" if stops == 0 else f"{stops} stop(s)"
            lines += [
                f"Flight {i}:",
                f"  Airline   : {f.get('airline', 'N/A')}",
                f"  Departure : {f.get('departure', 'N/A')}",
                f"  Arrival   : {f.get('arrival', 'N/A')}",
                f"  Duration  : {f.get('duration', 'N/A')}",
                f"  Stops     : {stop_str}",
                f"  Price     : {f.get('price', 'N/A')} {f.get('currency', '')}",
                "",
            ]

    return "\n".join(lines)


def _save_to_notepad(content: str, origin: str, destination: str) -> str:
    """Saves flight results to Desktop and opens in default text editor."""
    from agent.utils import save_to_desktop_text
    prefix = f"flights_{origin}_{destination}".replace(" ", "_")
    return save_to_desktop_text(content, prefix)


def flight_finder(
    parameters:    dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    """
    Flight Finder — searches Google Flights and speaks results.

    Parameters:
        origin       (str, required) — departure city or airport (e.g. "Abuja", "ABV")
        destination  (str, required) — arrival city or airport (e.g. "London", "LHR")
        date         (str, required) — departure date (any format)
        return_date  (str, optional) — return date for round trips
        passengers   (int, optional) — number of passengers (default: 1)
        cabin        (str, optional) — economy | premium | business | first (default: economy)
        save         (bool, optional) — save results to Desktop (default: False)
    """
    params = parameters or {}

    origin      = params.get("origin",      "").strip()
    destination = params.get("destination", "").strip()
    date_raw    = params.get("date",        "").strip()
    return_raw  = params.get("return_date", "").strip()
    passengers  = int(params.get("passengers", 1))
    cabin       = params.get("cabin", "economy").strip()
    save        = params.get("save", False)

    if not origin or not destination:
        return "Please provide both origin and destination."
    if not date_raw:
        return "Please provide a departure date."

    date        = _parse_date(date_raw)
    return_date = _parse_date(return_raw) if return_raw else None

    if player:
        player.write_log(f"[FlightFinder] {origin} -> {destination} on {date}")

    if speak:
        speak(f"Searching flights from {origin} to {destination} on {date}.")

    print(f"[FlightFinder] {origin} -> {destination} | {date} | {cabin} | {passengers} pax")

    try:
        raw_text, page_url = _search_flights_browser(
            origin, destination, date, return_date, passengers, cabin
        )

        if not raw_text:
            return "Could not retrieve flight data. The page may not have loaded."

        if speak:
            speak("Analysing the results now.")

        flights = _parse_flights_with_ai(raw_text, origin, destination, date)

        spoken = _format_spoken(flights, origin, destination, date)
        if speak:
            speak(spoken)

        result = spoken

        if save and flights:
            notepad_content = _format_notepad(
                flights, origin, destination, date, return_date, page_url
            )
            saved_path = _save_to_notepad(notepad_content, origin, destination)
            result += f" Results saved to Desktop: {saved_path}"

        return result

    except Exception as e:
        print(f"[FlightFinder] Error: {e}")
        return f"Flight search failed: {e}"
