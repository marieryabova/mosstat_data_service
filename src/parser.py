import os
import requests
from bs4 import BeautifulSoup
import urllib3
from src.models import Indicator
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class Parser:
    BASE_URL = "https://77.rosstat.gov.ru"
    SAVE_DIR = "data\\raw"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 YaBrowser/24.1.0.0 Safari/537.36"
    }

    def __init__(self, indicator: Indicator):
        self._validate_indicator(indicator)
        self.indicator = indicator

    def _validate_indicator(self, indicator: Indicator) -> None:
        if not indicator.id:
            raise ValueError("ID показателя не может быть пустым")
        if not indicator.url:
            raise ValueError("URL показателя не может быть пустым")
        if not indicator.url.startswith("http"):
            raise ValueError(f"URL должен начинаться с http: {indicator.url}")
        if not indicator.section:
            raise ValueError("Section показателя не может быть пустым")
        if not indicator.filename:
            raise ValueError("Filename показателя не может быть пустым")

    def _get_page(self) -> str:
        try:
            response = requests.get(self.indicator.url, headers=self.HEADERS, verify=False)
            response.raise_for_status()
            logger.info(f"Страница получена, размер: {len(response.text)} символов")
            return response.text
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"Таймаут соединения с {self.indicator.url}") from e
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Ошибка соединения с {self.indicator.url}") from e
        except requests.exceptions.HTTPError as e:
            raise ConnectionError(
                f"HTTP ошибка {response.status_code} для {self.indicator.url}"
            ) from e

    def _find_document(self, soup: BeautifulSoup):
        sections = soup.find_all('div', class_='toggle-card')
        target_section = None
        for section in sections:
            title_tag = section.find('div', class_='toggle-card__title')
            title = title_tag.get_text(strip=True) if title_tag else 'нет заголовка'
            if self.indicator.section in title:
                target_section = section
                logger.info(f"Найдена секция: '{self.indicator.section}'")
                break
        if not target_section:
            raise LookupError(
                f"Секция '{self.indicator.section}' не найдена на странице"
            )
        documents = target_section.find_all('div', class_='document-list__item')
        logger.debug(f"Найдено документов в секции: {len(documents)}")

        for doc in documents:
            title_tag = doc.find('div', class_='document-list__item-title')
            title = title_tag.get_text(strip=True) if title_tag else 'нет заголовка'

            if self.indicator.filename in title:
                logger.info(f"Найден документ: '{title}'")
                return doc
        raise LookupError(
            f"Документ '{self.indicator.filename}' не найден в секции "
            f"'{self.indicator.section}'"
        )

    def _download_file(self, doc) -> str:
        link_tag = doc.find('a', href=True)
        href = link_tag['href']
        full_url = f"{self.BASE_URL}{href}"
        try:
            file_response = requests.get(full_url, headers=self.HEADERS, verify=False)
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Ошибка скачивания файла {full_url}") from e

        os.makedirs(self.SAVE_DIR, exist_ok=True)
        save_path = os.path.join(self.SAVE_DIR, f"{self.indicator.id}.xlsx")
        try:
            with open(save_path, 'wb') as f:
                f.write(file_response.content)
        except OSError as e:
            raise OSError(f"Ошибка сохранения файла {save_path}") from e

        logger.info(f"Файл сохранён: {save_path} ({len(file_response.content)} байт)")
        return save_path

    def download(self) -> str:
        logger.info(f"Начало скачивания: {self.indicator.id}")
        html = self._get_page()
        soup = BeautifulSoup(html, 'lxml')
        doc = self._find_document(soup)
        return self._download_file(doc)
