// ============================================================
//  Flywheel Launcher Subsystem — simplified (no PI control)
//  Target: Arduino Uno/Nano
//  Interface: Raspberry Pi via USB Serial
// ============================================================
//
//  SERIAL COMMAND PROTOCOL (from RPi)
//  -----------------------------------
//  "SPIN"    → Spin flywheel at saved PWM duty
//  "FIRE"    → Feed one ball (only acts if READY)
//  "STOP"    → Stop flywheel, return to idle
//  "PING"    → Heartbeat; Arduino replies "PONG\n"
//  "SLAUNCH" → Auto sequence: spin up, fire 3 balls with 5s gap
//  "DLAUNCH" → Reserved, not yet implemented
//
//  SERIAL RESPONSES (from Arduino)
//  -----------------------------------
//  "PONG\n"            → Response to PING
//  "READY\n"           → Flywheel running (sent immediately on SPIN)
//  "FIRED\n"           → Single ball feed cycle complete
//  "STOPPED\n"         → Flywheel stopped
//  "ERR:NOT_READY\n"   → FIRE received while not in READY state
//  "LAUNCH_COMPLETE\n" → SLAUNCH sequence finished
// ============================================================

#include <Servo.h>
#include <GyverOLED.h>

// ── Pin Definitions ──────────────────────────────────────────
#define PIN_MOTOR_PWM   11    // MOSFET gate (Timer2 PWM)
#define PIN_SERVO       9     // Servo signal
#define PIN_POT         A0    // Potentiometer (config mode)
#define PIN_BUTTON      8     // Mode toggle (polled, external pull-down)

// ── Servo Config ─────────────────────────────────────────────
#define SERVO_REST_POS   10   // Degrees — ball NOT feeding
#define SERVO_FEED_POS  140   // Degrees — ball feeds into flywheel
#define SERVO_DWELL_MS  600   // Time (ms) servo holds feed position before retracting

// ── Motor Config ─────────────────────────────────────────────
#define PWM_MIN           0
#define PWM_MAX         255
#define PWM_DEFAULT     128   // Used if config mode has never been run

// ── SLAUNCH Config ───────────────────────────────────────────
#define SLAUNCH_BALLS        3     // Total balls to fire
#define SLAUNCH_SPINUP_MS  3000   // Flywheel spin-up wait before first ball (ms)
#define SLAUNCH_INTERVAL_MS 5000  // Wait between ball launches (ms), starts after servo retracts

// ── OLED / Button ────────────────────────────────────────────
#define OLED_REFRESH_MS 200   // 5 Hz
#define DEBOUNCE_MS      50

// ── Objects ──────────────────────────────────────────────────
Servo feederServo;
GyverOLED<SSH1106_128x64> oled;

// ── State ────────────────────────────────────────────────────
enum Mode     { MODE_RUN, MODE_CONFIG };
enum RunState { STATE_IDLE, STATE_READY, STATE_LAUNCHING, STATE_SLAUNCH };

Mode     currentMode = MODE_RUN;
RunState runState    = STATE_IDLE;

// ── Motor ────────────────────────────────────────────────────
int pwmDuty  = PWM_DEFAULT;
int pwmSaved = -1;            // -1 = not yet configured

// ── Servo ────────────────────────────────────────────────────
unsigned long servoFeedStart = 0;
bool          servoFeeding   = false;

// ── SLAUNCH sequence ─────────────────────────────────────────
uint8_t       slaunchBallsFired = 0;
unsigned long slaunchNextAction = 0;  // millis() timestamp for next fire

// ── OLED ─────────────────────────────────────────────────────
unsigned long lastOledUpdate = 0;

// ── Button ───────────────────────────────────────────────────
bool          lastButtonState = LOW;
unsigned long lastDebounce    = 0;
bool          buttonPressed   = false;

// ============================================================
//  Button polling
// ============================================================
void pollButton() {
  bool state = digitalRead(PIN_BUTTON);
  if (state == HIGH && lastButtonState == LOW) {
    unsigned long now = millis();
    if (now - lastDebounce > DEBOUNCE_MS) {
      buttonPressed = true;
      lastDebounce  = now;
    }
  }
  lastButtonState = state;
}

// ============================================================
//  Motor
// ============================================================
void setMotorPWM(int duty) {
  pwmDuty = constrain(duty, PWM_MIN, PWM_MAX);
  analogWrite(PIN_MOTOR_PWM, pwmDuty);
}

// ============================================================
//  Servo feed cycle (non-blocking)
//  Moves servo to feed position; updateServo() retracts it
//  after SERVO_DWELL_MS and handles post-retract logic.
// ============================================================
void startFeedCycle() {
  feederServo.write(SERVO_FEED_POS);
  servoFeedStart = millis();
  servoFeeding   = true;
}

void updateServo() {
  if (!servoFeeding) return;
  if (millis() - servoFeedStart < SERVO_DWELL_MS) return;

  // Dwell complete — retract servo immediately
  feederServo.write(SERVO_REST_POS);
  servoFeeding = false;

  if (runState == STATE_LAUNCHING) {
    // Manual FIRE — retract, return to ready
    runState = STATE_READY;
    Serial.println(F("FIRED"));

  } else if (runState == STATE_SLAUNCH) {
    // Servo fully retracted — count ball, start inter-ball wait
    // Next fire will not trigger until slaunchNextAction elapses
    // AND servoFeeding is false, guaranteeing full retract before reload
    slaunchBallsFired++;
    Serial.println(F("FIRED"));
    // If this was the LAST ball, wait only 2 seconds before stopping
    if (slaunchBallsFired >= SLAUNCH_BALLS) {
      slaunchNextAction = millis() + 2000;  // 2 seconds
    } else {
      slaunchNextAction = millis() + SLAUNCH_INTERVAL_MS;  // normal 5s
    }
  }
}

// ============================================================
//  SLAUNCH sequence state machine (non-blocking)
//  Timeline per ball:
//    [fire] → SERVO_DWELL_MS → [retract] → SLAUNCH_INTERVAL_MS → [fire next]
// ============================================================
void updateSlaunch() {
  if (runState != STATE_SLAUNCH) return;
  if (servoFeeding) return;                    // servo must be retracted first
  if (millis() < slaunchNextAction) return;    // inter-ball wait not elapsed

  if (slaunchBallsFired < SLAUNCH_BALLS) {
    startFeedCycle();                          // fire next ball
  } else {
    // All balls done
    setMotorPWM(0);
    runState = STATE_IDLE;
    Serial.println(F("LAUNCH_COMPLETE"));
  }
}

// ============================================================
//  OLED (5 Hz) — static labels drawn once in setup()
// ============================================================
const char* stateLabel() {
  if (currentMode == MODE_CONFIG) return "CONFIG  ";
  switch (runState) {
    case STATE_IDLE:      return "IDLE    ";
    case STATE_READY:     return "READY   ";
    case STATE_LAUNCHING: return "LAUNCH  ";
    case STATE_SLAUNCH:   return "SEQ     ";
    default:              return "???     ";
  }
}

void updateOLED() {
  if (millis() - lastOledUpdate < OLED_REFRESH_MS) return;
  lastOledUpdate = millis();

  oled.setCursor(40, 1);
  oled.print(F("   "));
  oled.setCursor(40, 1);
  oled.print(pwmDuty);

  oled.setCursor(40, 3);
  oled.print(F("N/A  "));   // RPM not yet implemented

  oled.setCursor(40, 5);
  oled.print(stateLabel());

  oled.update();
}

// ============================================================
//  Serial command parser
// ============================================================
void handleSerial() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  if (cmd == F("PING")) {
    Serial.println(F("PONG"));

  } else if (cmd == F("SPIN")) {
    if (currentMode == MODE_RUN && runState == STATE_IDLE) {
      int duty = (pwmSaved >= 0) ? pwmSaved : PWM_DEFAULT;
      setMotorPWM(duty);
      runState = STATE_READY;
      Serial.println(F("READY"));
    }

  } else if (cmd == F("FIRE")) {
    if (currentMode == MODE_RUN && runState == STATE_READY) {
      runState = STATE_LAUNCHING;
      startFeedCycle();
    } else {
      Serial.println(F("ERR:NOT_READY"));
    }

  } else if (cmd == F("STOP")) {
    setMotorPWM(0);
    runState = STATE_IDLE;
    Serial.println(F("STOPPED"));

  } else if (cmd == F("SLAUNCH")) {
    // Spin up and run sequence unconditionally
    int duty = (pwmSaved >= 0) ? pwmSaved : PWM_DEFAULT;
    setMotorPWM(duty);
    slaunchBallsFired = 0;
    slaunchNextAction = millis() + SLAUNCH_SPINUP_MS;  // wait for spinup first
    runState          = STATE_SLAUNCH;

  } else if (cmd == F("DLAUNCH")) {
    // TODO: implement DLAUNCH
  }
}

// ============================================================
//  Mode toggle
// ============================================================
void handleModeToggle() {
  if (!buttonPressed) return;
  buttonPressed = false;

  if (currentMode == MODE_RUN) {
    currentMode = MODE_CONFIG;
    runState    = STATE_IDLE;
    int pot = map(analogRead(PIN_POT), 0, 1023, PWM_MIN, PWM_MAX);
    setMotorPWM(pot);

  } else {
    pwmSaved    = pwmDuty;
    currentMode = MODE_RUN;
    setMotorPWM(0);
  }
}

// ============================================================
//  Config mode — pot drives motor live
// ============================================================
void handleConfigMode() {
  if (currentMode != MODE_CONFIG) return;
  int pot = map(analogRead(PIN_POT), 0, 1023, PWM_MIN, PWM_MAX);
  setMotorPWM(pot);
}

// ============================================================
//  setup()
// ============================================================
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);

  pinMode(PIN_MOTOR_PWM, OUTPUT);
  analogWrite(PIN_MOTOR_PWM, 0);

  feederServo.attach(PIN_SERVO);
  feederServo.write(SERVO_REST_POS);

  pinMode(PIN_BUTTON, INPUT);   // external pull-down

  // OLED — draw static labels once
  oled.init();
  oled.clear();
  oled.update();
  oled.setScale(1);
  oled.setCursor(5, 1);
  oled.print(F("PWM: "));
  oled.setCursor(5, 3);
  oled.print(F("RPM: "));
  oled.setCursor(5, 5);
  oled.print(F("Mode: "));
  oled.update();

  Serial.println(F("LAUNCHER_READY"));
}

// ============================================================
//  loop()
// ============================================================
void loop() {
  pollButton();
  handleModeToggle();
  handleSerial();
  handleConfigMode();
  updateServo();
  updateSlaunch();
  updateOLED();
}