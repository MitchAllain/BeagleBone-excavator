from excavator import *
import socket
import time
from sg_model import sg_model
from trajectories import *
from PID import PID


# Networking details
# HOST, PORT = '', 9999

# Initialize PWM/servo classes and measurement classes, note: this zeros the encoder
# temp = exc_setup()
# actuators = temp[0]
# measurements = temp[1]

measurements = measurement_setup()

# Initialize predictor, mode 0, alpha = 0.5, regen trajectories to start
predictor = TriggerPrediction(0, sg_model, 0.5)

# # PI Controllers for each actuator
# boom_PI = PID(0.25, 0.02, 0, 0, 0, 2, -2)
# stick_PI = PID(0.25, 0.02, 0, 0, 0, 2, -2)
# bucket_PI = PID(0.25, 0.02, 0, 0, 0, 2, -2)
# swing_PI = PID(0.35, 0.02, 0, 0, 0, 2, -2)
# controllers = [boom_PI, stick_PI, bucket_PI, swing_PI]

# # Create a socket (SOCK_DGRAM means a UDP socket)
# sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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

# # Initialize integrator and derivator to zero
# for c in controllers:
#     c.setIntegrator(0)
#     c.setDerivator(0)


try:
    # Connect to server and send data
    # sock.bind((HOST, PORT))

    while True:
        loop_start = time.time()

        # Start by updating measurements
        for m in measurements:
            m.update_measurement()

        # # Receive joystick data from the server
        # received_joysticks = sock.recv(4096)

        # Parse data (and apply joystick deadzone)
        # try:
        #     received_parsed = parser(sock.recv(4096), received_parsed)
        # except ValueError:
        #     pass

        # Initial prediction step
        sg, active = predictor.update_state([received_parsed[i] for i in range(4)], [m.value for m in measurements])

        print sg, active

        # # If active and need new trajectories
        # if active and predictor.regen:
        #     dt, amax, tf, Dmin, vmax = sine_traj(sg_model[predictor.prev]['subgoal_pos'], sg_model[sg]['subgoal_pos'], [0]*4, [18, 27, 30, 0.9], [10]*4)
        #     predictor.regen = False
        #     active_timer = time.time()

        # # If active and already generated trajectories
        # if active:
        #     p_d, _, _, _ = sine_func_v([active_timer-time.time()]*4, dt, tf, amax, vmax, sg_model[predictor.prev]['subgoal_pos'], [0]*4, [0]*4, sg_model[sg]['subgoal_pos'], p_dprev, (time.time()-step), Dmin)
        #     step = time.time()
        #     p_dprev = p_d
        #     # Setpoint for controller
        #     for i, c in enumerate(controllers):
        #         c.setPoint(p_d[i])
        #     alpha = predictor.alpha

        # # Apply blending law, alpha will either be static or zero, set duty, and update servo
        # for a, m, c in zip(actuators, controllers, measurements):
        #     # u = blending_law(received_parsed[a.js_index], c.update(m.value), predictor.alpha*predictor.active)
        #     u = blending_law(received_parsed[a.js_index], c.update(m.value), 0)
        #     a.duty_set = a.duty_span * u/(2) + a.duty_mid
        #     a.update_servo()

        # print(active, predictor.subgoal, [a.duty_set for a in actuators])

        try:
            data.log([loop_start-start] +                           # Run-time clock
                     received_parsed +                              # BM, ST, BK, SW joystick Cmd
                     [c.PID for c in controllers] +                 # BM, ST, BK, SW controller outputs
                     [a.duty_set for a in actuators] +              # BM, ST, BK, SW duty cycle command
                     [m.value for m in measurements] +              # BM, ST, BK, SW measurements
                     [predictor.subgoal, 0])                        # Motion primitive and confidence
        except NameError:
            pass

except KeyboardInterrupt:
    print '\nQuitting'
