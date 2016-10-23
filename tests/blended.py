#! /usr/bin/env python

##########################################################################################
# blended.py
#
# Full impementation of blended shared control, with placeholders for future work
#
# NOTE: see excavator.py module, 'Blended SC Pseudocode' document
#
# Created: October 06, 2016
#   - Mitchell Allain
#   - allain.mitch@gmail.com
#
# Modified:
#   * October 17, 2016 - name changed to blended.py, all in place except predictor and controller
#
##########################################################################################

from excavator import *
import socket
import time
from sg_model_1022 import sg_model
from trajectories import *
from PID import PID


# Networking details
HOST, PORT = '', 9999

# Initialize PWM/servo classes and measurement classes, note: this zeros the encoder
temp = exc_setup()
actuators = temp[0]
measurements = temp[1]

# Initialize predictor, mode 0, alpha = 0.5, regen trajectories to start
predictor = TriggerPrediction(1, sg_model, 0.5)

# PI Controllers for each actuator
boom_PI = PID(1, 0, 0, 0, 0, 2, -2)
stick_PI = PID(1, 0, 0, 0, 0, 2, -2)
bucket_PI = PID(1, 0, 0, 0, 0, 2, -2)
swing_PI = PID(1, 0, 0, 0, 0, 2, -2)
controllers = [boom_PI, stick_PI, bucket_PI, swing_PI]

# Create a socket (SOCK_DGRAM means a UDP socket)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Initialize DataLogger class with mode 1 for manual
filename = raw_input('Name the output file (end with .csv) or press return to disable data logging: ')
if filename == '':
    print('No data storage selected')
else:
    print('Writing headers to: ' + filename)
    data = DataLogger(3, filename)

start = time.time()
step = 0
received_parsed = [0, 0, 0, 0]
p_dprev = [0, 0, 0, 0]

# Initialize integrator and derivator to zero
for c in controllers:
    c.setIntegrator(0)
    c.setDerivator(0)


try:
    # Connect to server and send data
    sock.bind((HOST, PORT))

    while True:
        loop_start = time.time()

        # Start by updating measurements
        for m in measurements:
            m.update_measurement()

        # # Receive joystick data from the server
        received_joysticks = sock.recv(4096)

        # Parse data (and apply joystick deadzone)
        try:
            received_parsed = parser(sock.recv(4096), received_parsed)
        except ValueError:
            pass

        # Initial prediction step
        sg, active = predictor.update_state([received_parsed[a.js_index] for a in actuators], [m.value for m in measurements])

        print 'Subgoal State: ', sg, active, '\n'

        # If active and need new trajectories
        if active and predictor.regen:
            # Get max duration and trajecotry coefficients
            dur = duration(sg_model[predictor.prev-1]['subgoal_pos'], sg_model[sg-1]['subgoal_pos'], [18, 27, 30, 0.9], [20]*4)
            coeff = quintic_coeff(dur, sg_model[predictor.prev-1]['subgoal_pos'], sg_model[sg-1]['subgoal_pos'])

            # Set flag to not regenerate trajectories
            predictor.regen = False
            print('Trajectory coeff: ', coeff)

            # Start a timer for the current trajectory
            active_timer = time.time()

        # If active, update PI set point and alpha
        if active:
            # Saturate time for set point
            t = time.time()-active_timer
            if t > dur:
                t = dur

            # Setpoint for controller
            for i, c in enumerate(controllers):
                c.setPoint(np.polyval(coeff[i][::-1], t))
            # alpha = predictor.alpha

        # Apply blending law, alpha will either be static or zero, set duty, and update servo
        for a, c, m in zip(actuators, controllers, measurements):
            u = blending_law(received_parsed[a.js_index], c.update(m.value), predictor.alpha*predictor.active)
            # u = blending_law(received_parsed[a.js_index], c.update(m.value), 0)
            a.duty_set = a.duty_span * u/(2) + a.duty_mid
            a.update_servo()

        try:
            data.log([loop_start-start] +                           # Run-time clock
                     received_parsed +                              # BM, ST, BK, SW joystick Cmd
                     [c.PID for c in controllers] +                 # BM, ST, BK, SW controller outputs
                     [a.duty_set for a in actuators] +              # BM, ST, BK, SW duty cycle command
                     [m.value for m in measurements] +              # BM, ST, BK, SW measurements
                     [predictor.subgoal, predictor.active])                        # Motion primitive and confidence
        except NameError:
            pass

except KeyboardInterrupt:
    print '\nQuitting'
finally:
    print '\nClosing PWM signals...'
    sock.close()
    for a in actuators:
        a.duty_set = a.duty_mid
        a.update_servo()
    time.sleep(1)
    for a in actuators:
        a.close_servo()
    if data:
        notes = raw_input('Notes about this trial: ')
        n = open('data/metadata.csv', 'a')
        n.write(filename + ',' + notes)
        n.close()