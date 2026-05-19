import requests


class SefariaApi:
    def __init__(self) -> None:
        self.base_url = "https://www.sefaria.org/api/"
        self.headers = {"accept": "application/json"}

    def _get_json(self, url: str):
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {url}: {e}")
            return None
        if response.status_code != 200:
            print(f"Non-200 status {response.status_code} for {url}")
            return None
        try:
            return response.json()
        except ValueError as e:
            print(f"Failed to parse JSON from {url}: {e}")
            return None

    def table_of_contents(self) -> list:
        url = f"{self.base_url}index/"
        return self._get_json(url) or []

    def get_book(self, book_title: str, lang: str = "hebrew") -> dict:
        url = f"{self.base_url}v3/texts/{book_title}?version={lang}"
        return self._get_json(url) or {}

    def get_shape(self, book_title: str):
        url = f"{self.base_url}shape/{book_title}"
        return self._get_json(url)

    def get_index(self, book_title: str):
        url = f"{self.base_url}v2/index/{book_title}"
        return self._get_json(url)

    def get_name(self, book_title: str) -> dict:
        url = f"{self.base_url}name/{book_title}?limit=0"
        return self._get_json(url) or {}

    def get_links(self, book_title: str) -> list[dict[str, str | list | dict] | None] | None:
        url = f"{self.base_url}links/{book_title}?with_text=0"
        print(book_title)
        return self._get_json(url)

    def get_terms(self, name: str) -> dict:
        url = f"{self.base_url}terms/{name}"
        return self._get_json(url) or {}
