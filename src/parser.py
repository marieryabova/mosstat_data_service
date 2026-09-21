import logging
import os

import requests
import urllib3
from bs4 import BeautifulSoup

from src.models import Indicator

# Отключение предупреждения о небезопасных SSL-сертификатах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class Parser:
    """
    Парсер для скачивания статистических отчетов с сайта Росстата/Мосстата

    Атрибуты класса:
        BASE_URL (str): URL сайта для формирования полных ссылок
        SAVE_DIR (str): Директория для сохранения скачанных сырых данных
        HEADERS (dict): Заголовки HTTP-запроса для имитации браузера
    """

    BASE_URL = "https://77.rosstat.gov.ru"
    SAVE_DIR = "data\\raw"

    HEADERS = {  # noqa: RUF012
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 YaBrowser/24.1.0.0 Safari/537.36"
    }

    def __init__(self, indicator: Indicator):
        """
        Инициализирует парсер для конкретного показателя

        Args:
            indicator (Indicator): Объект показателя данными для парсинга

        Raises:
            ValueError: Если объект Indicator содержит некорректные данные
        """
        self._validate_indicator(indicator)
        self.indicator = indicator

    def _validate_indicator(self, indicator: Indicator) -> None:
        """
        Проверяет корректность заполнения полей объекта Indicator

        Args:
            indicator (Indicator): Объект для валидации

        Raises:
            ValueError: Если какое-либо из обязательных полей пустое или URL некорректен
        """
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
        """
        Выполняет GET-запрос и возвращает HTML-код страницы

        Returns:
            str: HTML-содержимое страницы

        Raises:
            TimeoutError: Если превышено время ожидания ответа
            ConnectionError: Если произошла ошибка соединения
        """
        try:
            response = requests.get(
                self.indicator.url, headers=self.HEADERS, verify=False
            )
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

    def _find_document(self, soup: BeautifulSoup) -> str:
        """
        Ищет целевой документ на полученно   HTML-странице

        Находит секцию по названию, а внутри нее нужный документ по имени файла

        Args:
            soup (BeautifulSoup): Дерево HTML-документа

        Returns:
            str: Полный URL для скачивания файла

        Raises:
            LookupError: Если секция, документ, ссылка не найдены на странице
        """
        sections = soup.find_all("div", class_="toggle-card")
        target_section = None
        for section in sections:
            title_tag = section.find("div", class_="toggle-card__title")
            title = title_tag.get_text(strip=True) if title_tag else "нет заголовка"
            if self.indicator.section in title:
                target_section = section
                logger.info(f"Найдена секция: '{self.indicator.section}'")
                break
        if not target_section:
            raise LookupError(
                f"Секция '{self.indicator.section}' не найдена на странице"
            )
        documents = target_section.find_all("div", class_="document-list__item")
        logger.debug(f"Найдено документов в секции: {len(documents)}")

        for doc in documents:
            title_tag = doc.find("div", class_="document-list__item-title")
            title = title_tag.get_text(strip=True) if title_tag else "нет заголовка"

            if self.indicator.filename in title:
                logger.info(f"Найден документ: '{title}'")
                link_tag = doc.find("a", href=True)
                if not link_tag:
                    raise LookupError(
                        f"Ссылка на скачивание не найдена в документе '{title}'"
                    )
                href = link_tag["href"]
                full_url = f"{self.BASE_URL}{href}"
                logger.info(f"Сформирован URL для скачивания: {full_url}")
                return full_url
        raise LookupError(
            f"Документ '{self.indicator.filename}' не найден в секции "
            f"'{self.indicator.section}'"
        )

    def _download_file(self, full_url: str) -> str:
        """
        Скачивает файл по переданной ссылке и сохраняет его

        Args:
            full_url (str): Полный URL для скачивания файла

        Returns:
            str: Локальный путь к сохраненному файлу

        Raises:
            ConnectionError: Если не удалось скачать файл
            OSError: Если возникла ошибка при записи файла на диск
        """
        try:
            file_response = requests.get(full_url, headers=self.HEADERS, verify=False)
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Ошибка скачивания файла {full_url}") from e

        os.makedirs(self.SAVE_DIR, exist_ok=True)
        save_path = os.path.join(self.SAVE_DIR, f"{self.indicator.id}.xlsx")
        try:
            with open(save_path, "wb") as f:
                f.write(file_response.content)
        except OSError as e:
            raise OSError(f"Ошибка сохранения файла {save_path}") from e

        logger.info(f"Файл сохранён: {save_path} ({len(file_response.content)} байт)")
        return save_path

    def download(self) -> str:
        """
        Запускает полный процесс скачивания данных для текущего показателя

        Выполняет последовательность: загрузка страницы -> поиск документа -> скачивание файла

        Returns:
            str: Путь к успешно скачанному файлу
        """
        logger.info(f"Начало скачивания: {self.indicator.id}")
        html = self._get_page()
        soup = BeautifulSoup(html, "lxml")
        doc = self._find_document(soup)
        return self._download_file(doc)
