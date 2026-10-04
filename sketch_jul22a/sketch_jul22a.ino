	const int numSwitches = 24;
const int switchPins[numSwitches] = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25};
bool switchStates[numSwitches] = {1};

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < numSwitches; i++) {
    pinMode(switchPins[i], INPUT_PULLUP);
    switchStates[i] = digitalRead(switchPins[i]);
  }
}

void loop() {
  for (int i = 0; i < numSwitches; i++) {
    bool currentState = digitalRead(switchPins[i]);
    if (currentState != switchStates[i]) {
      switchStates[i] = currentState;
      Serial.print(i);
      Serial.print(" ");
      if (currentState == LOW) {
        Serial.print(0);
      } else {
        Serial.print(1);
      }
    }
  }
  delay(100); // small delay to debounce switches
}