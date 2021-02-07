#!/usr/bin/env python3

"""
2D Controller Class to be used for the CARLA waypoint follower demo.
"""
import sys
import cutils
import numpy as np
import numpy.linalg as la
import math
from collections import deque

class Controller2D(object):
    def __init__(self, waypoints):
        self.vars                = cutils.CUtils()
        self._current_x          = 0
        self._current_y          = 0
        self._current_yaw        = 0
        self._current_speed      = 0
        self._desired_speed      = 0
        self._current_frame      = 0
        self._current_timestamp  = 0
        self._start_control_loop = False
        self._set_throttle       = 0
        self._set_brake          = 0
        self._set_steer          = 0
        self._waypoints          = waypoints
        self._conv_rad_to_steer  = 180.0 / 70.0 / np.pi
        self._pi                 = np.pi
        self._2pi                = 2.0 * np.pi


        self._e_buffer           = deque()
        self._se_buffer          = deque() 
        self._t_buffer           = deque([0,],maxlen=5)
        self.pe                  = 0
        self.pth_e               = 0
        self.x_previous          = 0
        self.y_previous          = 0
        self.tt                  = 0

    def update_values(self, x, y, yaw, speed, timestamp, frame):
        self._current_x         = x
        self._current_y         = y
        self._current_yaw       = yaw
        self._current_speed     = speed
        self._current_timestamp = timestamp
        self._current_frame     = frame
        if self._current_frame:
            self._start_control_loop = True

    def update_desired_speed(self):
        min_idx       = 0
        min_dist      = float("inf")
        desired_speed = 0
        for i in range(len(self._waypoints)):
            dist = np.linalg.norm(np.array([
                    self._waypoints[i][0] - self._current_x,
                    self._waypoints[i][1] - self._current_y]))
            if dist < min_dist:
                min_dist = dist
                min_idx = i
        if min_idx < len(self._waypoints)-1:
            desired_speed = self._waypoints[min_idx][2]
        else:
            desired_speed = self._waypoints[-1][2]
        self._desired_speed = desired_speed

    def update_waypoints(self, new_waypoints):
        self._waypoints = new_waypoints

    def get_commands(self):
        return self._set_throttle, self._set_steer, self._set_brake

    def set_throttle(self, input_throttle):
        # Clamp the throttle command to valid bounds
        throttle           = np.fmax(np.fmin(input_throttle, 1.0), 0.0)
        self._set_throttle = throttle

    def set_steer(self, input_steer_in_rad):
        # Covnert radians to [-1, 1]
        input_steer = self._conv_rad_to_steer * input_steer_in_rad

        # Clamp the steering command to valid bounds
        steer           = np.fmax(np.fmin(input_steer, 1.0), -1.0)
        self._set_steer = steer

    def set_brake(self, input_brake):
        # Clamp the steering command to valid bounds
        brake           = np.fmax(np.fmin(input_brake, 1.0), 0.0)
        self._set_brake = brake


    

    def update_controls(self):
        ######################################################
        # RETRIEVE SIMULATOR FEEDBACK
        ######################################################
        x               = self._current_x
        y               = self._current_y
        yaw             = self._current_yaw
        v               = self._current_speed
        self.update_desired_speed()
        v_desired       = self._desired_speed 
        t               = self._current_timestamp
        waypoints       = self._waypoints
        throttle_output = 0
        steer_output    = 0
        brake_output    = 0

        def pi_2_pi(angle):
            return (angle + math.pi) % (2 * math.pi) - math.pi

        def solve_DARE(A, B, Q, R):
            X = Q
            maxiter = 250
            eps = 0.01

            for i in range(maxiter):
                Xn = A.T @ X @ A - A.T @ X @ B @ \
                    la.inv(R + B.T @ X @ B) @ B.T @ X @ A + Q
                if (abs(Xn - X)).max() < eps:
                    break
                X = Xn
            
            print('iter =',i)

            return Xn

        def dlqr(A, B, Q, R):
            X = solve_DARE(A, B, Q, R)

            # compute the LQR gain
            K = la.inv(B.T @ X @ B + R) @ (B.T @ X @ A)

            eigVals, eigVecs = la.eig(A - B @ K)

            return K, X, eigVals













        self.vars.create_var('v_previous', 0.0)
        # Skip the first frame to store previous values properly
        if self._start_control_loop:

            ######################################################
            ######################################################
            #IMPLEMENTATION OF LONGITUDINAL CONTROLLER
            ######################################################
            ######################################################
            self._t_buffer.append(t)
            dt = 0.1
            Kp = 0.5
            Ki = 0.05
            Kd = 0.05
            e = (v_desired - v)
            dt = 0.02
            self._e_buffer.append(e)

            if len(self._e_buffer) >= 2:
                dt = self._t_buffer [-1] - self._t_buffer [-2]
                de = (self._e_buffer[-1] - self._e_buffer[-2]) /dt
                ie = sum(self._e_buffer) * dt
            else:
                de = 0.0
                ie = 0.0

            throttle_output = np.clip((Kp *e) + (Kd * de) + (Ki * ie), 0.0, 1.0)      
            brake_output    = 0

            ######################################################
            ######################################################
            #IMPLEMENTATION OF LATERAL CONTROLLER HERE
            ######################################################
            ######################################################

            k = 5
            kf = 6
            Kdd = 300
            vf = kf*v

            #Q = 20*np.array([[1, 0,0,0],[0,0,0,0],[0, 0,0,0],[0, 0,0,0]])
            Q = 0.1*np.ones((4,4))
            R = np.eye(1)
            L = 1

            pos = np.array([x,y])
            p1  = np.array(waypoints[0][:2])
            p2  = np.array(waypoints[1][:2])

            a = p1[1] - p2[1]
            b = p2[0] - p1[0]
            c = p2[0]*p1[1] - p1[0]*p2[1]
            o = np.clip(np.arctan2(-a,b),-0.5*self._pi,0.5*self._pi)


            #th_e = pi_2_pi(o - yaw)
            th_e = o -yaw


            e = la.norm(pos - p1)
            p1pos = pos - p1
            p1p2  = p2 - p1
            det = p1p2[0]*-p1pos[1] + p1p2[1]*p1pos[0]

            if det < 0:
                e = -e
                self.pe = -self.pe
            

            #if abs(e) < 2:
            #    e = 0
                




            A = np.zeros((4, 4))
            A[0, 0] = 1.0
            A[0, 1] = dt
            A[1, 2] = v
            A[2, 2] = 1.0
            A[2, 3] = dt
            # print(A)

            B = np.zeros((4, 1))
            B[3, 0] = (vf + Kdd) / L

            K, _, _ = dlqr(A, B, Q, R)

            xs = np.zeros((4, 1))

            xs[0, 0] = e
            xs[1, 0] = (e - self. pe) / dt
            xs[2, 0] = th_e
            xs[3, 0] = (th_e - self.pth_e) / dt



            #ff = -(o - yaw)
            #fb = 0
            ff = 0
            fb = pi_2_pi((-K @ xs)[0, 0])
            fb = -np.clip(fb,-0.5*self._pi,0.5*self._pi)
            

            steer_output = v*math.tan(ff + fb)/L
            #steer_output = ff+fb

            self.pe = e
            self.pth_e = th_e


            print("e1 =", e)
            print("det = ",det)
            #steer_output = phi
          
  ######################################################  ######################################################
            #k = 0.1
            #vf = k * v
            #L = int(np.floor(k*vf))
            #pos = np.array([x,y])
            #p1  = np.array(waypoints[0][:2])
            #p2  = np.array(waypoints[L][:2])
            #pos_previous = np.array([self.x_previous,self.y_previous])
            #a = np.cross(pos-pos_previous,pos - p2)
            #a = a/(np.linalg.norm(pos - pos_previous)*np.linalg.norm(pos - p2))
            #
            #steer_output = np.clip(np.arctan2(2*a,k*vf),-0.5*self._pi,0.5*self._pi)


            self.x_previous          = x
            self.y_previous          = y

            ######################################################
            # SET CONTROLS OUTPUT
            ######################################################
            self.set_throttle(throttle_output)  # in percent (0 to 1)
            self.set_steer(steer_output)        # in rad (-1.22 to 1.22)
            self.set_brake(brake_output)        # in percent (0 to 1)


        self.vars.v_previous = v  # Store forward speed to be used in next step
