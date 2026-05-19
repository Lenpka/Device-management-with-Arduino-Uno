# Многоканальное управление исполнительными устройствами (Arduino UNO + Python)

Программно-аппаратный комплекс для дистанционного управления **восемью независимыми каналами** нагрузки: верхний уровень на **Python** (команды по USB Serial), микроконтроллер **Arduino UNO**, силовая коммутация — **8-канальный транзисторный драйвер ULN2803A** (ключи «на землю»).

## Возможности
- статическое включение/выключение (`SET`);
- частотное переключение (`FREQ`);
- ШИМ на каналах с hardware PWM (`PWM`: каналы 2, 4, 5, 8);
- телеметрия (`GET` → `STAT`).

## Быстрый старт
1. Загрузить прошивку из `firmware/multi_channel_driver/` в Arduino UNO.
2. Соединить IN1…IN8 драйвера с пинами D2…D9, общий GND с Arduino и источником нагрузок.
3. `pip install -r python/requirements.txt`
4. Примеры:
   ```bash
   python python/serial_controller.py COM3 on 1
   python python/serial_controller.py COM3 freq 2 5
   python python/serial_controller.py COM3 stat
   python python/serial_controller.py COM3 monitor
   ```

## Документация
- [Архитектура, компоненты, защита проекта](docs/PROJECT.md)
- [Протокол Serial](docs/PROTOCOL.md)

## Авторы
Студенты 2 курса бакалавриата факультета наук о материалах МГУ: Константинов Л., Гумиров И.

## Лицензия
См. [LICENSE](LICENSE).
