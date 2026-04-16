#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN 9
#define SS_PIN 10
#define GREEN_LED 4
#define RED_LED 5
#define BUZZER_PIN 6

MFRC522 rfid(SS_PIN, RST_PIN);

void beepCardTap() {
  tone(BUZZER_PIN, 900, 120);
  delay(160);
}

void beepSuccess() {
  tone(BUZZER_PIN, 700, 100); delay(140);
  tone(BUZZER_PIN, 1000, 100); delay(140);
  tone(BUZZER_PIN, 1400, 220); delay(280);
}

void beepWrongUID() {
  for (int i = 0; i < 3; i++) {
    tone(BUZZER_PIN, 270, 450);
    delay(550);
  }
}

void beepWrongFace() {
  for (int i = 0; i < 4; i++) {
    tone(BUZZER_PIN, 400, 180);
    delay(260);
  }
}

void setup() {
  Serial.begin(9600);
  SPI.begin();
  rfid.PCD_Init();

  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(GREEN_LED, LOW);
  digitalWrite(RED_LED, LOW);

  // Startup beep
  tone(BUZZER_PIN, 500, 80); delay(110);
  tone(BUZZER_PIN, 800, 80); delay(110);
  tone(BUZZER_PIN, 1100, 160); delay(200);

  Serial.println("READY");
}

void loop() {
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;

  // Build UID string
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();  // toUpperCase returns void, modifies in place

  beepCardTap();
  Serial.println("CARD:" + uid);

  unsigned long start = millis();
  while (millis() - start < 15000) {
    if (Serial.available()) {
      String resp = Serial.readStringUntil('\n');
      resp.trim();

      if (resp == "OK") {
        beepSuccess();
        digitalWrite(GREEN_LED, HIGH);
        delay(3000);
        digitalWrite(GREEN_LED, LOW);
      } else if (resp == "FAIL_FACE") {
        for (int i = 0; i < 4; i++) {
          tone(BUZZER_PIN, 400, 180);
          digitalWrite(RED_LED, HIGH);
          delay(220);
          noTone(BUZZER_PIN);
          digitalWrite(RED_LED, LOW);
          delay(160);
        }
      } else if (resp == "FAIL_CARD") {
        beepWrongUID();
        digitalWrite(RED_LED, HIGH);
        delay(1800);
        digitalWrite(RED_LED, LOW);
      }
      break;  // Exit waiting for response
    }
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}