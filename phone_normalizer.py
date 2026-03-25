"""
phone_normalizer.py — Нормализация и парсинг грязных данных из Битрикса/Excel

Логика:
  1. Читаем строку Excel (A=Имя, B=Должность, C=Компания, D=Телефон, E=Результат)
  2. Нормализуем телефон → +7XXXXXXXXXX
  3. Пытаемся вытащить телефон из колонки C если D пустой
  4. Очищаем имена/компании от лишних пробелов
  5. Классифицируем каждую строку: OK / SKIP / DUPLICATE
"""
import re
from dataclasses import dataclass, field
from typing import Optional


# ─── ТЕЛЕФОН ──────────────────────────────────────────────────────────────────

# Мусорные значения вместо телефона
_GARBAGE_PHONE = re.compile(
    r"(где|номер|нет|не\s+знаю|\?{2,}|нет\s+номера|no\s+number)",
    re.IGNORECASE
)

# Паттерн поиска телефона внутри строки (для колонки C)
_PHONE_IN_TEXT = re.compile(r"[\d\s\-\(\)\+\*]{10,}")

# Паттерн для разбиения строки на потенциальные телефонные блоки
_PHONE_BLOCK = re.compile(r"[\+\d][\d\s\-\(\)\*]{8,}")


def normalize_phone(raw) -> Optional[str]:
    """
    Привести любой формат к +7XXXXXXXXXX.
    Возвращает None если нормализовать не удалось.
    """
    if raw is None:
        return None

    # Число из Excel (например 79181675448)
    if isinstance(raw, (int, float)):
        raw = str(int(raw))

    raw = str(raw).strip()

    if not raw or _GARBAGE_PHONE.search(raw):
        return None

    # Вытащить только цифры и ведущий +
    digits_only = re.sub(r"[^\d]", "", raw)

    if not digits_only:
        return None

    # Обработка разных длин
    if len(digits_only) == 11:
        if digits_only.startswith("8"):
            digits_only = "7" + digits_only[1:]
        elif digits_only.startswith("7"):
            pass  # уже правильно
        else:
            return None  # неизвестный формат
    elif len(digits_only) == 10:
        digits_only = "7" + digits_only
    elif len(digits_only) == 7 or len(digits_only) == 6:
        # Городской без кода — не можем нормализовать
        return None
    else:
        return None

    # Итоговый формат: +7 (XXX) XXX-XX-XX
    if len(digits_only) == 11 and digits_only.startswith("7"):
        d = digits_only
        return f"+7 ({d[1:4]}) {d[4:7]}-{d[7:9]}-{d[9:11]}"

    return None


def extract_phone_from_text(text: str) -> tuple[Optional[str], str]:
    """
    Попытаться вытащить телефон из произвольного текста.
    Возвращает (нормализованный_телефон, текст_без_телефона).
    """
    if not text:
        return None, text

    # Ищем последовательность цифр/спецсимволов похожую на номер
    match = _PHONE_IN_TEXT.search(text)
    if not match:
        return None, text

    raw_phone = match.group(0).strip()
    phone = normalize_phone(raw_phone)
    if phone:
        clean_text = (text[:match.start()] + text[match.end():]).strip(" ,\t")
        return phone, clean_text

    return None, text


def extract_all_phones_from_text(text: str) -> tuple[list[str], str]:
    """
    Извлечь все нормализованные телефоны из текста.
    Возвращает ([телефоны], текст_без_телефонов).
    """
    if not text:
        return [], text

    phones = []
    remaining = str(text)
    seen = set()

    for match in list(_PHONE_BLOCK.finditer(remaining))[::-1]:  # справа налево чтобы индексы не сбивались
        raw = match.group(0).strip()
        phone = normalize_phone(raw)
        if phone and phone not in seen:
            phones.insert(0, phone)
            seen.add(phone)
            remaining = (remaining[:match.start()] + remaining[match.end():]).strip(" ,\t;/")

    return phones, remaining.strip()


# Признаки юридического лица в названии компании
_ORG_KEYWORDS = re.compile(
    r"\b(ООО|ОАО|ЗАО|АО|ПАО|ИП|ГУП|МУП|ФГУП|НКО|АНО|НАО|ТСЖ|СНТ|ПК|КФХ"
    r"|LLC|LTD|JSC|INC|CORP|GmbH)\b",
    re.IGNORECASE
)


def detect_contact_type(company: str, position: str) -> str:
    """Вернуть 'company' если признаки юр. лица, иначе 'person'."""
    if company and _ORG_KEYWORDS.search(company):
        return "company"
    if position:  # наличие должности → скорее всего юр. лицо
        return "company"
    return "person"


def clean_name(raw) -> str:
    """Убрать лишние пробелы, нормализовать регистр не трогаем."""
    if not raw:
        return ""
    s = str(raw).strip()
    # Убрать двойные пробелы, неразрывные пробелы
    s = re.sub(r"[\xa0\u00a0]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


# ─── СТРОКА РЕЗУЛЬТАТА ────────────────────────────────────────────────────────

ROW_OK        = "ok"
ROW_NO_PHONE  = "no_phone"
ROW_EMPTY     = "empty"
ROW_DUPLICATE = "duplicate"
ROW_EXTRACTED = "extracted"  # телефон вытащен из другого поля


ROW_STATUS_LABELS = {
    ROW_OK:        "OK",
    ROW_NO_PHONE:  "Нет телефона",
    ROW_EMPTY:     "Пустая строка",
    ROW_DUPLICATE: "Дубликат",
    ROW_EXTRACTED: "Телефон извлечён",
}

ROW_STATUS_COLORS = {
    ROW_OK:        "#D4EDDA",
    ROW_NO_PHONE:  "#F8D7DA",
    ROW_EMPTY:     "#EEEEEE",
    ROW_DUPLICATE: "#FFF3CD",
    ROW_EXTRACTED: "#D1ECF1",
}


@dataclass
class ParsedRow:
    row_num:      int
    name:         str
    phone:        str          # нормализованный или ""
    phone_raw:    str          # оригинальный
    company:      str
    position:     str
    call_note:    str          # колонка E (старый результат обзвона)
    contact_type: str = "person"  # person / company
    status:       str = ROW_OK
    dup_of:       int = 0      # row_num оригинала если дубль


# ─── ПАРСЕР ───────────────────────────────────────────────────────────────────

def parse_excel(path: str) -> list[ParsedRow]:
    """
    Прочитать файл и вернуть список ParsedRow.
    Все строки включены (для предпросмотра), статус у каждой.
    """
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    results: list[ParsedRow] = []
    seen_phones: dict[str, int] = {}  # phone → row_num первого вхождения

    for row_num, row in enumerate(ws.iter_rows(values_only=True), start=1):
        # Дополнить до 5 колонок
        row = list(row) + [None] * 5
        col_a, col_b, col_c, col_d, col_e = row[0], row[1], row[2], row[3], row[4]

        name_raw    = col_a
        position    = clean_name(col_b)
        company_raw = col_c
        phone_raw   = col_d
        call_note   = clean_name(col_e)

        # Пустая строка?
        all_vals = [col_a, col_b, col_c, col_d, col_e]
        if all(v is None or str(v).strip() == "" for v in all_vals):
            results.append(ParsedRow(
                row_num=row_num, name="", phone="", phone_raw="",
                company="", position="", call_note="", status=ROW_EMPTY
            ))
            continue

        # Мусорные строки-метки (типа "декабрь")
        if (col_a and col_b is None and col_c is None and
                col_d is None and col_e is None):
            results.append(ParsedRow(
                row_num=row_num,
                name=clean_name(col_a), phone="", phone_raw="",
                company="", position="", call_note="", status=ROW_EMPTY
            ))
            continue

        name    = clean_name(name_raw)
        company = clean_name(company_raw)

        # Попытка нормализовать телефон из колонки D
        # Поддержка нескольких номеров и извлечения имени из телефонной ячейки
        phone_raw_str = str(phone_raw).strip() if phone_raw is not None else ""
        extracted = False

        phones_from_d, leftover_d = extract_all_phones_from_text(phone_raw_str)

        if phones_from_d:
            phone = "\n".join(phones_from_d)
            # Если имя пустое, а в телефонной ячейке остался текст — это имя
            if not name and leftover_d:
                name = clean_name(leftover_d)
        else:
            phone = ""

        # Если телефона нет — попробовать извлечь из колонки C (паттерн "Имя 918 xxx xxxx")
        if not phone and company:
            phone_from_c, company_clean = extract_phone_from_text(company)
            if phone_from_c:
                phone = phone_from_c
                company = company_clean
                extracted = True

        # Если телефона нет — попробовать из колонки B
        if not phone and position:
            phone_from_b, pos_clean = extract_phone_from_text(position)
            if phone_from_b:
                phone = phone_from_b
                position = pos_clean
                extracted = True

        if not phone:
            results.append(ParsedRow(
                row_num=row_num, name=name, phone="", phone_raw=phone_raw_str,
                company=company, position=position, call_note=call_note,
                contact_type=detect_contact_type(company, position),
                status=ROW_NO_PHONE
            ))
            continue

        # Проверка дубликата по первому номеру
        first_phone = phone.split("\n")[0]
        if first_phone in seen_phones:
            results.append(ParsedRow(
                row_num=row_num, name=name, phone=phone, phone_raw=phone_raw_str,
                company=company, position=position, call_note=call_note,
                contact_type=detect_contact_type(company, position),
                status=ROW_DUPLICATE, dup_of=seen_phones[first_phone]
            ))
            continue

        seen_phones[first_phone] = row_num
        status = ROW_EXTRACTED if extracted else ROW_OK
        ctype = detect_contact_type(company, position)

        results.append(ParsedRow(
            row_num=row_num, name=name, phone=phone, phone_raw=phone_raw_str,
            company=company, position=position, call_note=call_note,
            contact_type=ctype, status=status
        ))

    wb.close()
    return results


def get_importable(rows: list[ParsedRow]) -> list[ParsedRow]:
    """Только строки которые можно импортировать (OK + EXTRACTED)."""
    return [r for r in rows if r.status in (ROW_OK, ROW_EXTRACTED)]


def summary(rows: list[ParsedRow]) -> dict:
    from collections import Counter
    c = Counter(r.status for r in rows)
    return {
        "total":     len(rows),
        "ok":        c[ROW_OK],
        "extracted": c[ROW_EXTRACTED],
        "no_phone":  c[ROW_NO_PHONE],
        "duplicate": c[ROW_DUPLICATE],
        "empty":     c[ROW_EMPTY],
        "importable": c[ROW_OK] + c[ROW_EXTRACTED],
    }
