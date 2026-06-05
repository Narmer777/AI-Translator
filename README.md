# AiTranslator

## Русский

AiTranslator - экспериментальный AI-транслятор ST-кода в IL или LD через OpenRouter.

Основное практическое направление проекта - перевод `ST -> IL` для CoDeSys 2.3. Трансляция в LD поддерживается, но по результатам тестирования LD export оказался менее надежным из-за строгого и громоздкого формата CoDeSys.

### Запуск

Требуется Python 3.11 или новее. Внешние зависимости не используются.

```powershell
python main.py path\to\source.txt
python main.py IL path\to\source.txt
python main.py LD path\to\source.txt
```

Если целевой язык не указан, используется `IL`.


Для IL результат сохраняется в папку `results\translation_IL_DD_MM_YY_HH_MM_SS`. Внутри создаются два файла: `translation.txt` с чистым IL-кодом и `translation.exp` с export-шапкой `PROGRAM PLC_IL_PRG_TR` и завершающим `END_PROGRAM`.

### Правила входного ST-файла

Исходный ST-файл разбивается на логические блоки по пустым строкам. Один блок - это группа непустых строк между пустыми строками.

Рекомендуемые блоки:

- одно прямое присваивание `V := Expr;`;
  - несколько коротких присваиваний можно объединять в один блок, но сложное присваивание лучше выносить отдельно, если в выражении больше 5 переменных, есть вложенные скобки или длинная цепочка `AND` / `OR` / `NOT`.
- один полный блок `IF ... END_IF;`;
- один полный блок `IF ... ELSIF ... END_IF;`;
- один псевдооператорный раздел из присваиваний вида `_V := V;`.

Псевдооператорный раздел можно и нужно отправлять целиком, потому что он состоит из простых присваиваний и не создает большой логической нагрузки на модель. Чтобы он был одним chunk-ом, не ставьте пустые строки внутри псевдооператорного раздела.


## English

AiTranslator is an experimental AI-assisted translator from Structured Text to IL or LD through OpenRouter.

The main practical direction is `ST -> IL` translation for CoDeSys 2.3. LD translation is supported, but testing showed that LD export is less reliable because the CoDeSys export format is strict and verbose.

### Usage

Python 3.11 or newer is required. No external dependencies are used.

```powershell
python main.py path\to\source.txt
python main.py IL path\to\source.txt
python main.py LD path\to\source.txt
```

If the target language is not specified, `IL` is used.

For IL, the result is saved to `results\translation_IL_DD_MM_YY_HH_MM_SS`. The folder contains two files: `translation.txt` with plain IL code and `translation.exp` with the `PROGRAM PLC_IL_PRG_TR` export header and final `END_PROGRAM`.


### Input ST Rules

The source ST file is split into logical chunks by blank lines. One chunk is a group of non-empty lines between blank lines.

Recommended chunks:

- one direct assignment `V := Expr;`;
  - several short assignments may be grouped into one chunk, but a complex assignment should be isolated when the expression contains more than 5 variables, nested parentheses, or a long `AND` / `OR` / `NOT` chain.
- one complete `IF ... END_IF;` block;
- one complete `IF ... ELSIF ... END_IF;` block;
- one pseudo-operator section with assignments like `_V := V;`.

The pseudo-operator section should be sent as one chunk. It is simple and does not overload the model. To keep it as one chunk, do not put blank lines inside the pseudo-operator section.
