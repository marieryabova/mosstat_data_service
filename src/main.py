import logging

from src.models import Indicator
from src.parser import Parser

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Список показателей для парсинга
INDICATORS = [
    Indicator(
        id="ipc",
        url="https://77.rosstat.gov.ru/folder/64640",
        section="Оперативная информация",
        filename="Динамика индекса потребительских цен на товары и услуги",
    ),
    Indicator(
        id="income",
        url="https://77.rosstat.gov.ru/folder/64641",
        section="Доходы, расходы и сбережения населения",
        filename="Динамика денежных доходов населения г. Москвы",
    ),
    Indicator(
        id="poverty",
        url="https://77.rosstat.gov.ru/folder/64641",
        section="Уровень бедности",
        filename="Доля населения с денежными доходами ниже прожиточного минимума и границы бедности",
    ),
    Indicator(
        id="disease",
        url="https://77.rosstat.gov.ru/folder/64643",
        section="Здравоохранение",
        filename="Заболеваемость населения по основным классам болезней",
    ),
    Indicator(
        id="medical_staff",
        url="https://77.rosstat.gov.ru/folder/64643",
        section="Здравоохранение",
        filename="Численность медицинских кадров",
    ),
]


def main():
    """
    Основная функция выполнения программы

    Проходит по списку INDICATORS, скачивает данные для каждого показателя,
    обрабатывает исключения и выводит отчет в консоль
    """
    results = {}

    for indicator in INDICATORS:
        print(f"\n--- Обработка: {indicator.id.upper()} ---")
        parser = Parser(indicator)

        try:
            path = parser.download()
            results[indicator.id] = ("Успех", path)
        except TimeoutError as e:
            results[indicator.id] = ("Таймаут", str(e))
        except ConnectionError as e:
            results[indicator.id] = ("Ошибка сети", str(e))
        except LookupError as e:
            results[indicator.id] = ("Не найдено", str(e))
        except ValueError as e:
            results[indicator.id] = ("Некорректные данные", str(e))
        except OSError as e:
            results[indicator.id] = ("Ошибка файла", str(e))
    print("\n" + "=" * 70)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 70)

    success_count = 0
    for ind_id, (status, message) in results.items():
        if status == "Успех":
            success_count += 1
            print(f"{ind_id:15} | {message}")
        else:
            print(f"{ind_id:15} | {status}: {message}")

    print("=" * 70)
    print(f"Всего обработано: {len(INDICATORS)}, Успешно: {success_count}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
