import unittest

from scripts.hh_vacancy_scraper import parse_vacancy, vacancy_to_record


class VacancyParsingTest(unittest.TestCase):
    def test_parse_vacancy_extracts_visible_vacancy_attributes(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <html>
              <head>
                <title>Вакансия ML Engineer в Москве</title>
              </head>
              <body>
                <h1 data-qa="vacancy-title">ML Engineer</h1>
                <a data-qa="vacancy-company-name">Example AI</a>
                <div data-qa="vacancy-salary">
                  <span>от 300 000 ₽ на руки</span>
                </div>
                <p data-qa="work-experience-text">
                  Опыт работы: <span data-qa="vacancy-experience">3–6 лет</span>
                </p>
                <div data-qa="common-employment-text"><span>Полная занятость</span></div>
                <p data-qa="work-schedule-by-days-text">График: 5/2</p>
                <div data-qa="working-hours-text"><span>Рабочие часы: 8</span></div>
                <p data-qa="work-formats-text">Формат работы: удалённо</p>
                <div data-qa="vacancy-description">Build RAG systems</div>
                <span data-qa="bloko-tag__text">Python</span>
                <template>{"industries":[{"name":"Информационные технологии"}]}</template>
              </body>
            </html>
            """,
        )

        self.assertEqual(vacancy.salary, "от 300 000 ₽ на руки")
        self.assertEqual(vacancy.experience, "3–6 лет")
        self.assertEqual(vacancy.schedule, "Полная занятость; 5/2; 8; удалённо")
        self.assertEqual(vacancy.employer_industry, "Информационные технологии")

    def test_vacancy_record_preserves_vacancy_attributes(self) -> None:
        vacancy = parse_vacancy(
            "123",
            """
            <h1 data-qa="vacancy-title">ML Engineer</h1>
            <div data-qa="vacancy-salary">300 000 ₽</div>
            <span data-qa="vacancy-experience">3–6 лет</span>
            <p data-qa="work-formats-text">Формат работы: удалённо</p>
            <div data-qa="vacancy-description">Build RAG systems</div>
            """,
        )

        record = vacancy_to_record(vacancy, kept=True, reason="")

        self.assertEqual(record["salary"], "300 000 ₽")
        self.assertEqual(record["experience"], "3–6 лет")
        self.assertEqual(record["schedule"], "удалённо")
        self.assertEqual(record["employer_industry"], "")


if __name__ == "__main__":
    unittest.main()
