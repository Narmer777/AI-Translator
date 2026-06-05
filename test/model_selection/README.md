# Test Cases for AI Translator

Эта папка содержит ST-фрагменты для экспериментального сравнения AI-моделей.

## Структура тесткейса

- `source.txt` - исходный ST-фрагмент.
- `reference\il.txt` - место для эталонного IL, полученного ручным транслятором.
- `reference\ld.exp` - место для эталонного LD export, полученного ручным транслятором.
- `results.md` - таблица фиксации результатов по моделям.

## Группы тесткейсов

### Small

- `tc01_simple_assignment`
- `tc02_boolean_expression`
- `tc03_timer_assignment`
- `tc03_5_nested_boolean_il` - дополнительный IL-only тест после уточнения prompt-а
- `tc11_single_sided_if`

### Medium

- `tc04_state_latch_error`
- `tc05_product_states`
- `tc06_portion_counter`
- `tc07_modes_block`
- `tc08_mixer_block`

### Real

- `tc09_evaporation_full_fragment`
- `tc10_mixer_full_fragment`
- `tc12_mixer_pseudo_real`

## Используемые модели

- `openai/gpt-4o-mini`
- `google/gemini-2.5-flash`
- `z-ai/glm-4.5-air:free`
- `deepseek/deepseek-v3.2`
- `qwen/qwen3.6-flash`

## Исключенные модели

- `nvidia/nemotron-3-super-120b-a12b:free` - исключена после предварительного теста из-за высокой задержки ответа, ошибки `504 Provider returned error` и критических ошибок в тестах.

## Оценки

- `верно` - перевод совпадает с эталоном по логике и формату.
- `частично верно` - логика в основном сохранена, но есть исправимые форматные ошибки.
- `неверно` - потеряны операторы, нарушена логика или результат нельзя использовать.


