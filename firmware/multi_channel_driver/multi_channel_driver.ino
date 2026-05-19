/*
 * 8 выходных каналов CH1..CH8 через ULN2803A (low-side)
 * Разводка: docs/WIRING.md
 *
 * SET  — статический логический уровень (digitalWrite)
 * FREQ — программный меандр (millis), любой канал
 * PWM  — аппаратный ШИМ (analogWrite), только пины ~3,5,6,9,10,11 на UNO R3
 */

const uint8_t CHANNEL_COUNT = 8;

// CH1..CH8 → пины Arduino (см. WIRING.md)
const uint8_t PIN_MAP[CHANNEL_COUNT] = {2, 3, 4, 5, 6, 11, 9, 10};
// Аппаратный PWM UNO R3: D3, D5, D6, D9, D10, D11
const bool PWM_CAPABLE[CHANNEL_COUNT] = {
  false, true, false, true, true, true, true, true
};

enum ChannelMode : uint8_t { MODE_OFF = 0, MODE_ON, MODE_FREQ, MODE_PWM };

ChannelMode channelMode[CHANNEL_COUNT];
bool outputLevel[CHANNEL_COUNT];
uint16_t freqHz[CHANNEL_COUNT];
uint8_t pwmDuty[CHANNEL_COUNT];
unsigned long lastToggleMs[CHANNEL_COUNT];

String inputLine;

bool isPwmCapable(uint8_t chIndex) {
  return PWM_CAPABLE[chIndex];
}

uint8_t pinForChannel(uint8_t chIndex) {
  return PIN_MAP[chIndex];
}

void applyPinLevel(uint8_t chIndex, bool high) {
  outputLevel[chIndex] = high;
  digitalWrite(pinForChannel(chIndex), high ? HIGH : LOW);
}

void stopPwmHardware(uint8_t chIndex) {
  if (isPwmCapable(chIndex)) {
    analogWrite(pinForChannel(chIndex), 0);
  }
}

void setChannelStatic(uint8_t chIndex, bool on) {
  stopPwmHardware(chIndex);
  channelMode[chIndex] = on ? MODE_ON : MODE_OFF;
  freqHz[chIndex] = 0;
  pwmDuty[chIndex] = 0;
  applyPinLevel(chIndex, on);
}

void setChannelFreq(uint8_t chIndex, uint16_t hz) {
  stopPwmHardware(chIndex);
  if (hz == 0) {
    setChannelStatic(chIndex, false);
    return;
  }
  channelMode[chIndex] = MODE_FREQ;
  freqHz[chIndex] = hz;
  pwmDuty[chIndex] = 0;
  lastToggleMs[chIndex] = millis();
  applyPinLevel(chIndex, false);
}

void setChannelPwm(uint8_t chIndex, uint8_t duty) {
  if (!isPwmCapable(chIndex)) {
    Serial.print(F("ERR PWM "));
    Serial.println(chIndex + 1);
    return;
  }
  channelMode[chIndex] = (duty == 0) ? MODE_OFF : MODE_PWM;
  freqHz[chIndex] = 0;
  pwmDuty[chIndex] = duty;
  if (duty == 0) {
    analogWrite(pinForChannel(chIndex), 0);
    outputLevel[chIndex] = false;
  } else {
    analogWrite(pinForChannel(chIndex), duty);
    outputLevel[chIndex] = (duty > 127);
  }
  Serial.print(F("ACK PWM "));
  Serial.print(chIndex + 1);
  Serial.print(' ');
  Serial.println(duty);
}

// STAT: логический уровень на выводе Arduino, не состояние исполнительного устройства
void sendStat() {
  Serial.print(F("STAT"));
  for (uint8_t i = 0; i < CHANNEL_COUNT; i++) {
    bool level = digitalRead(pinForChannel(i)) == HIGH;
    Serial.print(level ? F(",1") : F(",0"));
  }
  Serial.println();
}

bool parseChannel(const char *token, uint8_t &chIndex) {
  if (token == nullptr || *token == '\0') return false;
  int ch = atoi(token);
  if (ch < 1 || ch > (int)CHANNEL_COUNT) return false;
  chIndex = (uint8_t)(ch - 1);
  return true;
}

void processCommand(const String &line) {
  if (line.length() == 0) return;

  char buf[48];
  line.toCharArray(buf, sizeof(buf));
  char *cmd = strtok(buf, " ");
  if (cmd == nullptr) return;

  if (strcmp(cmd, "GET") == 0) {
    sendStat();
    return;
  }

  if (strcmp(cmd, "SET") == 0) {
    uint8_t ch;
    if (!parseChannel(strtok(nullptr, " "), ch)) {
      Serial.println(F("ERR CHANNEL"));
      return;
    }
    char *stateTok = strtok(nullptr, " ");
    if (stateTok == nullptr) {
      Serial.println(F("ERR SYNTAX"));
      return;
    }
    int state = atoi(stateTok);
    setChannelStatic(ch, state != 0);
    Serial.print(F("ACK SET "));
    Serial.print(ch + 1);
    Serial.print(' ');
    Serial.println(state != 0 ? 1 : 0);
    return;
  }

  if (strcmp(cmd, "FREQ") == 0) {
    uint8_t ch;
    if (!parseChannel(strtok(nullptr, " "), ch)) {
      Serial.println(F("ERR CHANNEL"));
      return;
    }
    char *hzTok = strtok(nullptr, " ");
    if (hzTok == nullptr) {
      Serial.println(F("ERR SYNTAX"));
      return;
    }
    int hz = atoi(hzTok);
    if (hz < 0 || hz > 100) {
      Serial.println(F("ERR FREQ range"));
      return;
    }
    setChannelFreq(ch, (uint16_t)hz);
    Serial.print(F("ACK FREQ "));
    Serial.print(ch + 1);
    Serial.print(' ');
    Serial.println(hz);
    return;
  }

  if (strcmp(cmd, "PWM") == 0) {
    uint8_t ch;
    if (!parseChannel(strtok(nullptr, " "), ch)) {
      Serial.println(F("ERR CHANNEL"));
      return;
    }
    if (!isPwmCapable(ch)) {
      Serial.print(F("ERR PWM "));
      Serial.println(ch + 1);
      return;
    }
    char *dutyTok = strtok(nullptr, " ");
    if (dutyTok == nullptr) {
      Serial.println(F("ERR SYNTAX"));
      return;
    }
    int duty = atoi(dutyTok);
    if (duty < 0 || duty > 255) {
      Serial.println(F("ERR SYNTAX"));
      return;
    }
    setChannelPwm(ch, (uint8_t)duty);
    return;
  }

  Serial.println(F("ERR SYNTAX"));
}

void serviceFrequencyChannels() {
  unsigned long now = millis();
  for (uint8_t i = 0; i < CHANNEL_COUNT; i++) {
    if (channelMode[i] != MODE_FREQ || freqHz[i] == 0) continue;
    unsigned long halfPeriod = 500UL / freqHz[i];
    if (halfPeriod < 1) halfPeriod = 1;
    if (now - lastToggleMs[i] >= halfPeriod) {
      lastToggleMs[i] = now;
      applyPinLevel(i, !outputLevel[i]);
    }
  }
}

void setup() {
  Serial.begin(115200);
  inputLine.reserve(48);
  for (uint8_t i = 0; i < CHANNEL_COUNT; i++) {
    pinMode(pinForChannel(i), OUTPUT);
    channelMode[i] = MODE_OFF;
    outputLevel[i] = false;
    freqHz[i] = 0;
    pwmDuty[i] = 0;
    digitalWrite(pinForChannel(i), LOW);
  }
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      processCommand(inputLine);
      inputLine = "";
    } else if (inputLine.length() < 47) {
      inputLine += c;
    }
  }
  serviceFrequencyChannels();
}
