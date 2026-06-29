# Telegram Rich Messages — Bot API 10.1 (полная техническая документация)

> **Для будущих агентов.** Это справочник по формату **Rich Messages** («Rich Text»),
> добавленному в **Bot API 10.1 (11 июня 2026, Telegram Desktop 6.9)**.
> Всё ниже сверено напрямую с официальным референсом
> <https://core.telegram.org/bots/api> (секции `#rich-messages`, `#sendrichmessage`,
> `#richtext`, `#richblock`) и проверено боевыми вызовами реального бота.
>
> Источник истины при сомнениях — официальный референс. НЕ выдумывайте поля.

---

## 0. TL;DR — главное, что ломает агентов с первого раза

1. **Rich Text ≠ `parse_mode=HTML`.** Старый `parse_mode` (`HTML` / `MarkdownV2`) даёт только
   инлайн-стили (жирный, курсив, цитата). Это НЕ Rich Text.
2. **Rich Text отправляется отдельным методом** `sendRichMessage`, а контент передаётся
   как **строка** в поле `rich_message.html` **или** `rich_message.markdown` —
   НЕ как массив блоков.
3. **`InputRichMessage` принимает строку, а не блоки.** Блоки (`RichBlockParagraph`,
   `RichBlockList`, …) — это то, как **сервер парсит** присланный вами HTML/Markdown и в каком
   виде вы их **получаете** во входящих сообщениях (`Message.rich_message`).
   Попытка отправить `{"blocks":[...]}` вернёт `400: rich message must be non-empty`.
4. **Ровно одно из** `html` / `markdown` должно быть задано в `InputRichMessage`.

```
Отправка (вы → Telegram):   строка html/markdown  ─парсит сервер→  RichMessage{ blocks: [...] }
Получение (Telegram → вы):  Message.rich_message = RichMessage{ blocks: [...] }
```

---

## 1. Объекты и методы

### 1.1 Методы

| Метод | Назначение | Ключевые параметры |
|---|---|---|
| `sendRichMessage` | Отправить rich-сообщение | `chat_id` (Yes), `rich_message: InputRichMessage` (Yes), `business_connection_id`, `message_thread_id`, `direct_messages_topic_id`, `disable_notification`, `protect_content`, `allow_paid_broadcast`, `message_effect_id`, `reply_parameters`, `reply_markup` |
| `sendRichMessageDraft` | **Стриминг** частичного сообщения (см. §6) | `chat_id` (Yes, только приватный чат), `draft_id` (Yes, non-zero), `rich_message` (Yes), `message_thread_id` |
| `editMessageText` (+`rich_message`) | Редактировать rich-сообщение | `rich_message: InputRichMessage` — обязателен, если не задан `text`; и наоборот |

`sendRichMessage` возвращает отправленный `Message`. При наличии медиа-блока у бота должно
быть право отправлять медиа в чат.

### 1.2 Типы

**`InputRichMessage`** — то, что вы ОТПРАВЛЯЕТЕ. Ровно одно из `html`/`markdown`.

| Поле | Тип | Описание |
|---|---|---|
| `html` | String | Контент в Rich **HTML**-синтаксисе (§3) |
| `markdown` | String | Контент в Rich **Markdown**-синтаксисе (§4) |
| `is_rtl` | Boolean | `True` → показать справа налево |
| `skip_entity_detection` | Boolean | `True` → отключить авто-детект URL/e-mail/@упоминаний/#хэштегов/телефонов/карт |

**`RichMessage`** — то, что вы ПОЛУЧАЕТЕ (`Message.rich_message`).

| Поле | Тип |
|---|---|
| `blocks` | Array of `RichBlock` |
| `is_rtl` | Boolean (optional) |

**`InputRichMessageContent`** — обёртка для inline / guest / Web App запросов:
поле `rich_message: InputRichMessage`.

---

## 2. Лимиты (Rich Message Limits)

| Лимит | Значение |
|---|---|
| Длина текста | **32 768** UTF-8 символов (включая alt-текст кастом-эмодзи и исходник формул) |
| Блоки | **500** (включая вложенные блоки, элементы списков, строки таблиц, цитаты, details) |
| Глубина вложенности | **16** уровней форматирования и блоков |
| Медиа-вложения | **50** всего (фото + видео + аудио) |
| Колонки таблицы | **20** |

Инлайн-текст обычного `text` сообщения по-прежнему ограничен 1–4096 символами;
Rich-текст — отдельный, гораздо больший лимит (32 768).

---

## 3. Rich HTML-синтаксис (`rich_message.html`)

Поддерживаются **только** перечисленные теги. Инлайн-стили и блоки можно смешивать.

### 3.1 Inline text formatting

| Эффект | HTML | Parsed `RichText.type` |
|---|---|---|
| Bold | `<b>` / `<strong>` | `bold` |
| Italic | `<i>` / `<em>` | `italic` |
| Underline | `<u>` / `<ins>` | `underline` |
| Strikethrough | `<s>` / `<strike>` / `<del>` | `strikethrough` |
| Spoiler | `<tg-spoiler>` | `spoiler` |
| Marked (выделение) | `<mark>` | `marked` |
| Subscript | `<sub>` | `subscript` |
| Superscript | `<sup>` | `superscript` |
| Inline code | `<code>` | `code` |

### 3.2 Code & Pre

```html
<code>inline fixed-width code</code>
<pre>pre-formatted fixed-width code block</pre>
<pre><code class="language-python">print('hello')</code></pre>
```

- Inline → `RichText` type `code`.
- Блок → `RichBlockPreformatted` (`type: "pre"`, `text`, опц. `language`).
  Язык задаётся через `class="language-XXX"` на вложенном `<code>`.

### 3.3 Links & Mentions

| Что | HTML | Parsed type |
|---|---|---|
| Inline URL | `<a href="https://t.me/">text</a>` | `url` (поля `text`, `url`) |
| E-mail | `<a href="mailto:user@example.com">…</a>` | `email_address` |
| Phone | `<a href="tel:+123456789">…</a>` | `phone_number` |
| Mention по ID | `<a href="tg://user?id=123456789">…</a>` | `text_mention` |
| In-document link | `<a href="#chapter-1">…</a>` | `anchor_link` |
| Anchor (якорь) | `<a name="chapter-1"></a>` | блок `RichBlockAnchor` (`type: "anchor"`, `name`) |

**Авто-детектируемые сущности** (без тегов, если `skip_entity_detection` не `True`):
`@username` → `mention`, `#hashtag` → `hashtag`, `$USD` → `cashtag`,
`/command` → `bot_command`, телефоны → `phone_number`,
номера карт `4242 4242 4242 4242` → `bank_card_number`,
голые URL/e-mail. Клиент показывает предупреждение «Open this link?» перед открытием инлайн-ссылок.

### 3.4 Emoji, Dates & Math

```html
<!-- Кастомное эмодзи (нужен emoji-id премиум-стикерпака) -->
<tg-emoji emoji-id="5368324170671202286">🎲</tg-emoji>
<img src="tg://emoji?id=5368324170671202286" alt="🎲"/>

<!-- Дата/время (рендерится в локали пользователя) -->
<tg-time unix="1647531900" format="wDT">22:45 tomorrow</tg-time>

<!-- Инлайн-формула -->
<tg-math>x^2 + y^2</tg-math>

<!-- Блок-формула -->
<tg-math-block>E = mc^2</tg-math-block>
```

| Что | Parsed type | Ключевые поля |
|---|---|---|
| Custom emoji | `custom_emoji` | `custom_emoji_id`, `alternative_text` |
| Date-time | `date_time` | `unix_time`, `date_time_format` (см. §3.4.1) |
| Inline math | `mathematical_expression` | `expression` (LaTeX) |
| Block math | блок `RichBlockMathematicalExpression` (`type: "mathematical_expression"`, `expression`) |

#### 3.4.1 Формат date-time
Строка формата соответствует regex `r|w?[dD]?[tT]?`:
- `r` — относительное время («через 5 минут»). **Не комбинируется** с другими.
- `w` — день недели в локали пользователя.
- `d` — короткая дата (`17.03.22`); `D` — длинная (`March 17, 2022`).
- `t` — короткое время (`22:45`); `T` — длинное (`22:45:00`).
- Пустая строка → текст как есть, но пользователь видит дату в своей локали.

### 3.5 Structure (headings / paragraphs / quotes / lists / details / footer)

```html
<h1>Heading 1</h1> … <h6>Heading 6</h6>
<p>Paragraph text</p>
<footer>Footer text</footer>
<hr/>

<ul><li>unordered item</li></ul>
<ol><li>ordered item</li></ol>
<ol start="3" type="a" reversed><li>item</li></ol>
<ol><li value="7" type="i">item с явным номером</li></ol>

<blockquote>Строка 1<br>Строка 2<cite>The Author</cite></blockquote>
<aside>Pull quote<cite>The Author</cite></aside>

<details open><summary>Заголовок</summary>Скрытый контент</details>
```

| HTML | Block type | Поля |
|---|---|---|
| `<h1>`–`<h6>` | `heading` | `text`, `size` (1=крупнейший … 6=мельчайший) |
| `<p>` | `paragraph` | `text` |
| `<footer>` | `footer` | `text` |
| `<hr/>` | `divider` | — |
| `<ul>`/`<ol><li>` | `list` | `items: [RichBlockListItem]` |
| `<blockquote>` | `blockquote` | `blocks`, `credit` (из `<cite>`) |
| `<aside>` | `pullquote` | `text`, `credit` |
| `<details>` | `details` | `summary`, `blocks`, `is_open` (атрибут `open`) |

**`RichBlockListItem`**: `label` (String), `blocks` (Array of RichBlock),
`has_checkbox` / `is_checked` (для task-list), `value` (номер для ordered),
`type` (метка ordered: `"a"`/`"A"`/`"i"`/`"I"`/`"1"`).

### 3.6 Media

```html
<img   src="https://.../photo.jpg"/>
<video src="https://.../video.mp4"></video>
<audio src="https://.../audio.mp3"></audio>   <!-- .ogg → voice note -->
<video src="https://.../animation.gif"></video> <!-- gif → animation -->

<!-- Подпись + кредит -->
<figure><img src="https://.../photo.jpg" tg-spoiler/>
  <figcaption>Caption<cite>Credit</cite></figcaption></figure>

<!-- Коллаж / слайдшоу -->
<tg-collage><img src="a.jpg"/><video src="b.mp4"/></tg-collage>
<tg-slideshow><img src="a.jpg"/><video src="b.mp4"/></tg-slideshow>

<!-- Карта -->
<tg-map lat="41.9" long="12.5" zoom="14"/>
```

| HTML | Block type | Тип медиа-поля |
|---|---|---|
| `<img>` | `photo` | `photo: Array of PhotoSize`, `has_spoiler`, `caption` |
| `<video>` | `video` | `video: Video`, `has_spoiler`, `caption` |
| `<video src="*.gif">` | `animation` | `animation: Animation`, `has_spoiler`, `caption` |
| `<audio src="*.mp3">` | `audio` | `audio: Audio`, `caption` |
| `<audio src="*.ogg">` | `voice_note` | `voice_note: Voice`, `caption` |
| `<tg-collage>` | `collage` | `blocks`, `caption` |
| `<tg-slideshow>` | `slideshow` | `blocks`, `caption` |
| `<tg-map>` | `map` | `location: Location`, `zoom (13-20)`, `width`, `height`, `caption` |

`<figure>` оборачивает медиа + `<figcaption>` → `RichBlockCaption` (`text`, опц. `credit`).
`tg-spoiler` как атрибут медиа → `has_spoiler`. До **50** медиа на сообщение.

### 3.7 Advanced — таблицы, сноски/референсы, пулл-квоты

```html
<!-- Таблица -->
<table bordered striped>
  <caption>Table caption</caption>
  <tr><th>Header 1</th><th>Header 2</th></tr>
  <tr><td colspan="2" align="left">Value</td><td valign="top">V2</td></tr>
</table>

<!-- Сноска/референс (footnote): определение + ссылка -->
Текст с ссылкой<a href="#note-1">¹</a>.
<tg-reference name="note-1">Текст самой сноски</tg-reference>
```

**`RichBlockTable`** (`type: "table"`): `cells: Array of Array of RichBlockTableCell`,
`is_bordered`, `is_striped`, `caption`. До **20** колонок.
**`RichBlockTableCell`**: `text` (опц.; пусто → невидимая ячейка), `is_header`,
`colspan`, `rowspan`, `align` (`left`/`center`/`right`), `valign` (`top`/`middle`/`bottom`).

**Сноски/референсы** (parsed RichText):
- `RichTextReference` (`type: "reference"`, `text`, `name`) — определение сноски (`<tg-reference name>`).
- `RichTextReferenceLink` (`type: "reference_link"`, `text`, `reference_name`) — ссылка на неё (`<a href="#name">`).

**Pull quote** — `<aside>` → `RichBlockPullQuotation` (`type: "pullquote"`, `text`, `credit`), текст центрируется.

---

## 4. Rich Markdown-синтаксис (`rich_message.markdown`)

Эквивалент HTML, но Markdown. Передаётся в поле `markdown`.

```markdown
**bold**   __bold__
*italic*   _italic_
~~strikethrough~~
`inline code`
==marked==
||spoiler||
[inline URL](https://t.me/)
[e-mail](mailto:user@example.com)
[phone](tel:+123456789)
[mention](tg://user?id=123456789)
![alt](tg://emoji?id=5368324170671202286)
![22:45 tomorrow](tg://time?unix=1647531900&format=wDT)
$x^2 + y^2$

# Heading 1
###### Heading 6
Paragraph text

```python
print('fenced code block with language')
```​

---

- unordered item
* unordered item
+ unordered item
1. ordered item
- [ ] task item
- [x] completed task item

> Block quotation line 1
>
> Block quotation line 2

![](https://.../photo.jpg "Photo caption")

| Header 1 | Header 2 |
|:---------|---------:|
| Value 1  | Value 2  |
```

- `---` → divider (`<hr/>`).
- ```` ```lang ```` fenced block → `RichBlockPreformatted` с `language`.
- `- [ ]` / `- [x]` → list item с `has_checkbox` / `is_checked`.
- `\#`, `\*` и т.п. — экранирование спец-символов обратным слешем.

> Старый `MarkdownV2` (`parse_mode`) — это ДРУГОЙ синтаксис (`*bold*`, `_italic_`, `__underline__`)
> и НЕ поддерживает структурные блоки. Не путать с rich-`markdown`.

---

## 5. Парсинг входящих: `RichText` и `RichBlock`

### 5.1 `RichText`
Может быть: `String` (плейн), `Array of RichText`, либо объект с `type`:

| type | Доп. поля |
|---|---|
| `bold`, `italic`, `underline`, `strikethrough`, `spoiler`, `marked`, `code`, `subscript`, `superscript` | `text` |
| `url` | `text`, `url` |
| `email_address`, `phone_number`, `bank_card_number`, `mention`, `hashtag`, `cashtag`, `bot_command` | `text` |
| `text_mention` | `text` (+ user id) |
| `custom_emoji` | `custom_emoji_id`, `alternative_text` |
| `date_time` | `text`, `unix_time`, `date_time_format` |
| `mathematical_expression` | `expression` |
| `reference` | `text`, `name` |
| `reference_link` | `text`, `reference_name` |
| `anchor` | (имя якоря) |
| `anchor_link` | `text` |

### 5.2 `RichBlock` (полный перечень `type`)
`paragraph`, `heading`, `pre`, `footer`, `divider`, `mathematical_expression`,
`anchor`, `list`, `blockquote`, `pullquote`, `collage`, `slideshow`, `table`,
`details`, `map`, `animation`, `audio`, `photo`, `video`, `voice_note`, `thinking`.

`RichBlockThinking` (`type: "thinking"`, тег `<tg-thinking>`) — плейсхолдер «Thinking…»;
**только** для `sendRichMessageDraft`, во входящих сообщениях не встречается.
Рекомендуются кастом-эмодзи из <https://t.me/addemoji/AIActions>.

---

## 6. Streaming (`sendRichMessageDraft`)

Стриминг частично сгенерированного (например, LLM) ответа в реальном времени.

- Работает **только в приватном чате** (`chat_id: Integer`).
- `draft_id` — non-zero. Изменения черновика с **тем же** `draft_id` **анимируются** (плавное дописывание).
- Черновик **эфемерный**: живёт как ~**30-секундный превью**. Возвращает `True`.
- **Чтобы сохранить результат**, после финализации необходимо вызвать `sendRichMessage`
  с полным сообщением — иначе он исчезнет.
- В черновиках можно использовать блок `thinking` (`<tg-thinking>`) как индикатор размышления.

**Типовой цикл стриминга:**
```
loop, пока генерируется ответ:
    sendRichMessageDraft(chat_id, draft_id=42, rich_message={html: <текущий частичный HTML>})
по завершении:
    sendRichMessage(chat_id, rich_message={html: <полный финальный HTML>})   # персистит в чат
```

---

## 7. Long Message — лимит и «части»

> ⚠️ **Важно для тестов «part flag».** В Bot API 10.1 у Rich Messages **нет** документированного
> поля для авто-разбиения на части — есть **жёсткий лимит 32 768 символов** (и 500 блоков /
> 16 уровней / 50 медиа / 20 колонок). Контент, превышающий лимит, сервер **отклонит** ошибкой,
> а не «нарежет» автоматически.
>
> Если тест-кейс называется *«Exceeds inline byte limit to test part flag»* — он проверяет
> поведение на границе лимита. Корректная стратегия для длинного контента:
> 1. держаться в пределах 32 768 символов / 500 блоков на одно `sendRichMessage`;
> 2. для более длинного — **разбивать на несколько сообщений** на стороне бота
>    (по логическим блокам: заголовок-секция → отдельное сообщение);
> 3. для генерации «на лету» — использовать `sendRichMessageDraft` (§6), а финал
>    отправлять одним `sendRichMessage` в пределах лимита.
>
> Не выдумывайте поле `part` / `is_part` — его в спецификации нет. Если в вашей кодовой базе
> «part flag» — это внутренний флаг тест-харнесса, он относится к проверке именно граничного
> поведения 32 768-символьного лимита, а не к API Telegram.

---

## 8. Рабочие примеры (проверены на боевом боте)

### 8.1 Минимальный `sendRichMessage` (HTML)
```bash
curl -s "https://api.telegram.org/bot<TOKEN>/sendRichMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": 237324167,
    "rich_message": { "html": "<h2>Привет</h2><p>Это <b>rich</b> текст.</p>" }
  }'
```

### 8.2 Документ-стиль (все основные блоки), Python
```python
import json, urllib.request
TOKEN = "<TOKEN>"; CHAT = 237324167
html = """\
<h2>🚫 Заголовок секции</h2>
<p>Параграф с <b>жирным</b>, <i>курсивом</i> и <mark>выделением</mark>.</p>
<hr/>
<h3>Список сценариев</h3>
<ol>
  <li><b>Первый.</b> Описание.</li>
  <li><b>Второй.</b> Описание.</li>
</ol>
<blockquote>Цитата с автором<cite>Автор</cite></blockquote>
<details open><summary>🕵️ Раскрывающийся блок</summary>Скрытый контент.</details>
<aside>Пулл-квота как панчлайн<cite>Подпись</cite></aside>
<hr/>
<footer>💡 Подвал-CTA.</footer>"""

payload = json.dumps({"chat_id": CHAT, "rich_message": {"html": html}}).encode()
req = urllib.request.Request(
    f"https://api.telegram.org/bot{TOKEN}/sendRichMessage",
    data=payload, headers={"Content-Type": "application/json"})
try:
    print(urllib.request.urlopen(req).read().decode())
except urllib.error.HTTPError as e:
    print("ERROR:", e.read().decode())
```

### 8.3 Стриминг + финализация
```python
# 1) частичные апдейты (анимируются по одному draft_id)
draft = {"chat_id": CHAT, "draft_id": 42,
         "rich_message": {"html": "<tg-thinking>думаю…</tg-thinking>"}}
# POST .../sendRichMessageDraft (повторять с растущим html)
# 2) финал — обязателен, иначе превью исчезнет через ~30с
final = {"chat_id": CHAT, "rich_message": {"html": "<h2>Готово</h2><p>Полный ответ.</p>"}}
# POST .../sendRichMessage
```

---

## 9. Чек-лист и частые ошибки

| Симптом / ошибка | Причина | Решение |
|---|---|---|
| `400: rich message must be non-empty` | Отправили `{"blocks":[...]}` или неизвестные поля | Слать строку в `rich_message.html` **или** `.markdown` |
| `400: object expected as rich message` | `rich_message` — массив/строка | `rich_message` должен быть **объектом** `InputRichMessage` |
| Форматирование «как старый MD» | Использован `parse_mode=HTML` в `sendMessage` | Использовать метод `sendRichMessage` |
| Оба `html` и `markdown` заданы | Нарушено «ровно одно из» | Оставить только одно поле |
| Неизвестный тег проигнорирован/ошибка | Тег не из списка §3 | Использовать только поддерживаемые теги |
| Превью исчезло | Только `sendRichMessageDraft`, без финала | После генерации вызвать `sendRichMessage` |
| Авто-ссылки/хэштеги «лишние» | Авто-детект сущностей | Передать `skip_entity_detection: true` |

---

## 10. Источники
- Telegram Bot API — Rich messages: <https://core.telegram.org/bots/api#rich-messages>
- `sendRichMessage` / `sendRichMessageDraft`: <https://core.telegram.org/bots/api#sendrichmessage>
- `RichText` / `RichBlock` типы: <https://core.telegram.org/bots/api#richtext>
- Bot API changelog (10.1, 11 июня 2026): <https://core.telegram.org/bots/api-changelog>
- Анонс (Telegram Desktop 6.9): TechTimes, 11 июня 2026.

*Документ собран автоматически из живого API-референса и проверен боевыми вызовами.*
