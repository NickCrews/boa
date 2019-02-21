#include <SoftwareSerial.h>
//Requires the library at
//https://github.com/bogde/HX711/blob/master/HX711.h
#include <HX711.h>

#define BT_TX 9
#define BT_RX 10
//this is the max baudrate that the SoftwareSerial library can handle
#define BT_BAUDRATE 9600

#define CLOCK_PIN A5
#define DATA_PIN A4
#define SERIAL_BAUDRATE 9600

SoftwareSerial bluetooth(BT_RX, BT_TX);

HX711 scale;
//look at https://github.com/bogde/HX711 for more info

void startupBlink(){
  pinMode(LED_BUILTIN, OUTPUT);
  for (int i=0; i<3; i++){
    digitalWrite(LED_BUILTIN, HIGH);
    delay(200);
    digitalWrite(LED_BUILTIN, LOW);
    delay(200);
  }
}

void setup() {
  //we just want the most basic thing possible. We can do any necessary conversions in python.
  startupBlink();
  Serial.begin(SERIAL_BAUDRATE);
  bluetooth.begin(BT_BAUDRATE);
  scale.begin(DATA_PIN, CLOCK_PIN, 128);
  scale.set_scale(1);
  scale.set_offset(0);
}

void loop() {
  long reading = scale.read();
  Serial.println(reading);
  bluetooth.println(reading);
}
