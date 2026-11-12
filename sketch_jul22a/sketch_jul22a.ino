// Reads one switch per table (24 tables) on an Arduino Mega 2560 and reports
// every change to the PC over USB serial.
//
// Message format, one per line:  "<table index> <state>\n"
//   state 1 = pin HIGH (table running), 0 = pin LOW (table stopped)
//
// Each switch is debounced on its own: a new state is reported only after the
// pin has stayed at it for DEBOUNCE_MS. Nothing blocks, so all 24 switches are
// checked many times per millisecond.

const uint8_t NUM_SWITCHES = 24;
const uint8_t SWITCH_PINS[NUM_SWITCHES] = {2,  3,  4,  5,  6,  7,  8,  9,  10, 11, 12, 13,
                                           14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25};
const unsigned long DEBOUNCE_MS = 50;

bool reportedState[NUM_SWITCHES];    // last state sent to the PC
bool lastReading[NUM_SWITCHES];      // raw pin value on the previous pass
unsigned long changedAt[NUM_SWITCHES];  // when the raw value last changed

void setup() {
  Serial.begin(9600);
  for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
    pinMode(SWITCH_PINS[i], INPUT_PULLUP);
    reportedState[i] = digitalRead(SWITCH_PINS[i]);
    lastReading[i] = reportedState[i];
    changedAt[i] = millis();
  }
}

void loop() {
  unsigned long now = millis();

  for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
    bool reading = digitalRead(SWITCH_PINS[i]);

    if (reading != lastReading[i]) {
      // The contact is still bouncing or just moved: restart this switch's timer.
      lastReading[i] = reading;
      changedAt[i] = now;
    } else if (reading != reportedState[i] && now - changedAt[i] >= DEBOUNCE_MS) {
      // Stable long enough: report it. Unsigned subtraction also works when millis() wraps.
      reportedState[i] = reading;
      Serial.print(i);
      Serial.print(' ');
      Serial.println(reading == LOW ? 0 : 1);
    }
  }
}
