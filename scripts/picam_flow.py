import numpy as np
import picamera
import picamera.array
import cv2
from h2rMultiWii import MultiWii
import time
  
# RASPBERRY PI?
camera_matrix = np.array([[ 253.70549591,    0.,          162.39457585], 
                        [ 0.,          251.25243215,  126.5400089], 
                        [   0.,            0., 1.        ]])
dist_coeffs = np.array([ 0.20462996, -0.41924085,  0.00484044,  0.00776978,
                        0.27998478])


class AnalyzeFlow(picamera.array.PiMotionAnalysis):

    def analyse(self, a):
        start = time.time()
        x = a['x']
        y = a['y']
        sad = a['sad']

        ang_coefficient = 45000.0
        curr_time = time.time()
        diff_time = curr_time - self.prev_time
        self.prev_time = curr_time
        
        x_motion = np.sum(x) + np.arctan(self.ang_vx * diff_time) * ang_coefficient
        y_motion = np.sum(y) + np.arctan(self.ang_vy * diff_time) * ang_coefficient
        z_motion = np.sum(np.multiply(x, self.z_filter_x)) + \
                np.sum(np.multiply(y, self.z_filter_y))
        yaw_motion = np.sum(np.multiply(x, self.yaw_filter_x)) + \
                np.sum(np.multiply(y, self.yaw_filter_y))
       
        print 'XYZyaw:\t{},\t{},\t{}\t{}\t\t\t{}'.format( \
                x_motion,y_motion,z_motion,yaw_motion,time.time() - start)
    
    def set_angular_velocity(self, ang_vx, ang_vy):
        self.ang_vx = ang_vx
        self.ang_vy = ang_vy

    def get_z_filter(self, (width, height)):
        # computes a divergence filter to estimate z component of flow
        assert width%16 == 0 and height%16 == 0
        num_rows = height/16
        num_cols = width/16 
        mid_row = (num_rows - 1)/2.0
        mid_col = (num_cols - 1)/2.0
        # the picamera motion vectors have a buffer column each frame
        self.z_filter_x = np.zeros((num_rows,num_cols+1), dtype='float')
        self.z_filter_y = np.zeros((num_rows,num_cols+1), dtype='float')
        for i in range(num_cols):
            for j in range(num_rows):
                x = i - mid_col # center the coords around the middle
                y = j - mid_row
                self.z_filter_x[j,i] = x
                self.z_filter_y[j,i] = y
                # r = np.sqrt(x**2 + y**2)
                # theta = np.arctan(y/x)
                # print x,y,theta
                # z_filter_x[j,i] = r * np.cos(theta) 
                # z_filter_y[j,i] = r * np.sin(theta)
        self.z_filter_x /= np.linalg.norm(self.z_filter_x)
        self.z_filter_y /= np.linalg.norm(self.z_filter_y)
    
    def get_yaw_filter(self, (width, height)):
        self.yaw_filter_x = self.z_filter_y
        self.yaw_filter_y = -1 * self.z_filter_x

    def setup(self, camera_wh = (320,240)):
        self.get_z_filter(camera_wh)
        self.get_yaw_filter(camera_wh)
        self.ang_vx = 0
        self.ang_vy = 0
        self.prev_time = time.time()



if __name__ == '__main__':
    board = MultiWii("/dev/ttyACM0")
    
    with picamera.PiCamera(framerate=90) as camera:
        with AnalyzeFlow(camera) as flow_analyzer:
            camera.resolution = (320, 240)
            flow_analyzer.setup(camera.resolution)
            camera.start_recording(
                  '/dev/null', format='h264', motion_output=flow_analyzer)
            
            prev_angx = 0
            prev_angy = 0
            prev_time = time.time()
            while True:
                mw_data = board.getData(MultiWii.ATTITUDE)
                curr_angx = mw_data['angx'] / 180.0 * np.pi
                curr_angy = mw_data['angy'] / 180.0 * np.pi
                curr_time = time.time()
                flow_analyzer.set_angular_velocity(
                        (curr_angx - prev_angx)/(curr_time - prev_time),
                        (curr_angy - prev_angy)/(curr_time - prev_time))
                prev_angx = curr_angx
                prev_angy = curr_angy
                prev_time = curr_time

            camera.wait_recording(30)
            camera.stop_recording()