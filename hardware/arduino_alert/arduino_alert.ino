const int LED_PIN = 13;
const int BUZZER_PIN = 8;
String incoming = "";

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available()) {
    incoming = Serial.readStringUntil('\n');
    incoming.trim();
    if (incoming == "ALERT") {
      digitalWrite(LED_PIN, HIGH);
      tone(BUZZER_PIN, 800);
    } else if (incoming == "CLEAR") {
      digitalWrite(LED_PIN, LOW);
      noTone(BUZZER_PIN);
    }
  }
}
