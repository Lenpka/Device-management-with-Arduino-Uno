# Многоканальное управление исполнительными устройствами (Arduino UNO + Python)

Программно-аппаратный комплекс: **Python** → USB Serial → **Arduino UNO** → **ULN2803A** (8 выходных каналов CH1…CH8, low-side) → **исполнительные устройства**.

Базовый элемент — **выходной канал транзисторного драйвера**, не реле и не сеть 220 В.

## Возможности
| Режим | Команда | Назначение |
|-------|---------|------------|
| Статика | `SET` | Постоянный логический уровень, все CH1…CH8 |
| Меандр | `FREQ` | Программное переключение с заданной частотой, все CH1…CH8 |
| ШИМ | `PWM` | `analogWrite()` — аппаратный PWM UNO на **CH2, CH4, CH5, CH6, CH7, CH8** |
| Опрос логики | `GET` → `STAT` | Уровень на пине Arduino (**не** состояние нагрузки) |

## Разводка (кратко)

| CH | Arduino | ULN IN | PWM (UNO R3) | Стенд по умолчанию | Питание |
|----|---------|--------|--------------|-------------------|---------|
| CH1 | D2 | IN1 | нет | LED + R | 5 V, GND общий |
| CH2 | D3 | IN2 | да | LED + R | 5 V |
| CH3 | D4 | IN3 | нет | LED + R | 5 V |
| CH4 | D5 | IN4 | да | LED + R | 5 V |
| CH5 | D6 | IN5 | да | LED + R | 5 V |
| CH6 | D11 | IN6 | да | LED + R | 5 V |
| CH7 | D9 | IN7 | да | LED + R | 5 V |
| CH8 | D10 | IN8 | да | LED + R | 5 V |

Полная таблица и схема канала: [docs/WIRING.md](docs/WIRING.md).

## Быстрый старт
1. Прошивка: `firmware/multi_channel_driver/` → Arduino UNO.
2. Подключить IN1…IN8 к пинам из таблицы, GND общий, нагрузки на OUT1…OUT8.
3. `pip install -r python/requirements.txt`
4. Примеры:
   ```bash
   python python/serial_controller.py COM3 on 1
   python python/serial_controller.py COM3 freq 1 2
   python python/serial_controller.py COM3 pwm 5 128
   python python/serial_controller.py COM3 stat
   python python/serial_controller.py COM3 monitor
   ```

## Документация
- [Проект, стенд, архитектура](docs/PROJECT.md)
- [Протокол SET / FREQ / PWM / GET](docs/PROTOCOL.md)
- [Разводка и режимы PWM vs FREQ](docs/WIRING.md)

## Авторы
Студенты 2 курса бакалавриата факультета наук о материалах МГУ: Константинов Л., Гумиров И.

## Лицензия
[LICENSE](LICENSE)
