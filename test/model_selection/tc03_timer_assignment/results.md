# TC03 Timer Assignment

Проверяет dotted identifier и отрицательный контакт.

| Модель | Целевой язык | Запуск | Результат | Ошибки | Примечание |
|---|---|---:|---|---|---|
| openai/gpt-4o-mini | IL | 1 | верно |  | Совпадает с эталоном. |
| openai/gpt-4o-mini | IL | 2 | верно |  | Совпадает с эталоном. |
| google/gemini-2.5-flash | IL | 1 | верно |  | Совпадает с эталоном. |
| google/gemini-2.5-flash | IL | 2 | верно |  | Совпадает с эталоном. |
| z-ai/glm-4.5-air:free | IL | 1 | верно |  | Совпадает с эталоном. |
| z-ai/glm-4.5-air:free | IL | 2 | верно |  | Совпадает с эталоном. |
| deepseek/deepseek-v3.2 | IL | 1 | верно |  | Совпадает с эталоном. |
| deepseek/deepseek-v3.2 | IL | 2 | верно |  | Совпадает с эталоном. |
| qwen/qwen3.6-flash | IL | 1 | верно |  | Совпадает с эталоном. |
| qwen/qwen3.6-flash | IL | 2 | верно |  | Совпадает с эталоном. |
| openai/gpt-4o-mini | LD | 1 | частично верно | сломан формат export; нет закрытия выражения | Логика сохранена, но перед `ENABLELIST` нет закрывающего `_EXPRESSION _POSITIV`. |
| openai/gpt-4o-mini | LD | 2 | частично верно | сломан формат export; нет закрытия выражения | Логика сохранена, но перед `ENABLELIST` нет закрывающего `_EXPRESSION _POSITIV`. |
| google/gemini-2.5-flash | LD | 1 | верно |  | Совпадает с эталоном. |
| google/gemini-2.5-flash | LD | 2 | верно |  | Совпадает с эталоном. |
| z-ai/glm-4.5-air:free | LD | 1 | верно |  | Совпадает с эталоном. |
| z-ai/glm-4.5-air:free | LD | 2 | верно |  | Совпадает с эталоном. |
| deepseek/deepseek-v3.2 | LD | 1 | верно |  | Совпадает с эталоном. |
| deepseek/deepseek-v3.2 | LD | 2 | верно |  | Совпадает с эталоном. |
| qwen/qwen3.6-flash | LD | 1 | верно |  | Совпадает с эталоном. |
| qwen/qwen3.6-flash | LD | 2 | верно |  | Совпадает с эталоном. |


