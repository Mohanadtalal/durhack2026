// Arduino UNO Q / App Lab: mirror SiteGuardian's hazard state on the LED matrix.
// Paste into the sketch/sketch.ino file of an Arduino App Lab app.

#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>

Arduino_LED_Matrix matrix;

uint8_t danger[104] = {
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,0,1,0,0,0,0,0,
  0,0,0,0,1,0,1,0,1,0,0,0,0,
  0,0,0,1,0,0,1,0,0,1,0,0,0,
  0,0,1,0,0,0,1,0,0,0,0,1,0,
  0,1,0,0,0,0,0,0,0,0,0,1,0,
  0,1,0,0,0,0,1,0,0,0,0,1,0,
  0,1,1,1,1,1,1,1,1,1,1,1,0
};

uint8_t blank[104] = {0};

volatile bool requestedDanger = false;
bool displayedDanger = false;

void setDanger(bool active) {
  requestedDanger = active;
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(1);
  matrix.draw(blank);

  Bridge.begin();
  Bridge.provide("set_danger", setDanger);
}

void loop() {
  bool active = requestedDanger;
  if (active != displayedDanger) {
    matrix.draw(active ? danger : blank);
    displayedDanger = active;
  }
  delay(20);
}
