#!/usr/bin/env python3
import cv2
import numpy
import os
import sys
import time
import copy
import json
import argparse
import serial
import threading
event = False

#
# For da blinkin lights
#
def led_thread(serd):
    global event
    while True:
        if (event == True):
            event = False
            if (serd != None):
                ser = serial.Serial(serd)
                time.sleep(2.0)
                ser.close()
        time.sleep(0.25)
    
def grab_and_baseline(cam, count):
    accum_frame = None
    accum_init = False
    for i in range(count):
        ret, frame = cam.read()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if accum_init == False:
            accum_frame = copy.deepcopy(frame)
            accum_frame = numpy.multiply(accum_frame, 0)
            accum_init = True
        accum_frame = numpy.add(accum_frame, frame)
    accum_frame = numpy.subtract(accum_frame, numpy.min(accum_frame))
    return accum_frame
    

def normalize_image(img, peak):
    img = numpy.divide(img, peak)
    return img
#
# Open a capture stream to desired camera index
#  (/dev/video{cndx})
#

parser = argparse.ArgumentParser(description='Detect Cosmic Muons via Webcam')
parser.add_argument ('--camera', type=int, help="Camera index", default=0)
parser.add_argument ('--threshold', type=float, help="Detection threshold as ratio", default=2.0)
parser.add_argument ('--prefix', help="File prefix", default="./")
parser.add_argument ('--latitude', type=float, help="Geographic latitude", default=44.9)
parser.add_argument ('--longitude', type=float, help="Geographic longitude", default=-76.03)
parser.add_argument ('--led-port', help="Serial port for LED indicator", default=None)
parser.add_argument ('--stack', help="Stacking factor", type=int, default=5)
args = parser.parse_args()


stack = args.stack

#
# Setup the camera for streaming
#
cndx = args.camera
cam = cv2.VideoCapture(cndx)

#
# Create a thread that blinks the front-panel LED for an event
#
notify_thread = threading.Thread(target=led_thread, args=(args.led_port,), daemon=True)
notify_thread.start()

#
# Zoom final dimension in X and Y
#
zoom=30

#
# Stacking factor
#
stack = 5
fmax = 0

#
# Initialize start time and frame counter
#
now = time.time()
count = 0

while ((time.time() - now) <= 5.0):
    frame = grab_and_baseline(cam, stack)
    fmax += numpy.max(frame)
    count += 1

frate = (stack*count)/5.0
print ("Apparent frame rate", frate)
#
# Reduce to average
#
fmax /= float(count)
threshold = args.threshold*fmax
print ("Threshhold ", threshold)

#
# Forever
#
# Grab frames, convert to Grayscale, evaluate
#   pixel max
#
frame_count = 0
while True:
    frame = grab_and_baseline(cam, stack)
    frame_count += 1
    if ((frame_count % int(1000/stack)) == 0):
        print ("Still getting frames at ", time.ctime())
    if ((frame_count % int(5000/stack)) == 0):
        nframe = copy.deepcopy(frame)
        nframe = normalize_image(nframe, stack)
        cv2.imwrite("check_frame.png", nframe)


    origframe = copy.deepcopy(frame)
    frame = numpy.array(frame)
    #
    # If max in this frame exceeds our "dark slide" estimate
    #   by a reasonable (command-line) factor, we have
    #   a possible hit.  Save a zoomed-in sub-frame as a .png
    #
    counter = 0
    xy_coordinates = []
    data = origframe
    izoom2 = int(zoom/2)
    frame_max = numpy.max(frame)
    if (frame_max > threshold):
        print ("Event detected at ", time.ctime())
        #
        # This stuff stolen from Credo-Linux
        #
        
        #
        # Pick up X/Y coordinates of bright "spot"
        #
        all_coordinate_x = list(numpy.where(data >= int(threshold))[1])
        all_coordinate_y = list(numpy.where(data >= int(threshold))[0])
        all_ziped = list(zip(all_coordinate_x,all_coordinate_y))
        all_ziped.sort()
        #
        # For all bright spots build-out xy_coordinates
        #
        while counter < len(all_ziped):
            if len(all_ziped) == 1:
                xy_coordinates.append(all_ziped[0])
                break
            elif counter == 0:
                xy_coordinates.append(all_ziped[counter])
                counter += 1
            elif all_ziped[counter][0] - (izoom2) < all_ziped[counter - 1][0]:
                counter += 1
            else:
                xy_coordinates.append(all_ziped[counter])
                counter += 1
        mcnt = 0
        
        #
        # For each of those X/Y pairs, construct a zoomed-in image
        #  that is (area*2)pixels in both X and Y
        #
        t = time.time()
        ltp = time.gmtime(t)
        fractions = t - float(int(t))
        secondsbit = float(ltp.tm_sec) + fractions
        for x, y in xy_coordinates:
            if x >= izoom2+1 and y >= izoom2+1:
                img_crop = data[y-izoom2:y + izoom2,
                           x-izoom2:x + izoom2]
                
                #
                # Signal the LED notifier thread
                #
                if (event != True):
                    event = True
                #
                # Resulting image is scaled appropriately
                #
                r = (zoom*2) / img_crop.shape[1]
                dim = (int(zoom*2), int(img_crop.shape[0] * r))
                if img_crop is None:
                    pass
                else:
                    img_crop = normalize_image(img_crop, stack)
                    img_zoom = cv2.resize(img_crop, dim, interpolation=cv2.INTER_LINEAR)
                    cv2.convertScaleAbs(img_zoom, img_zoom, 1.3, 0.0)
                    fn = "%s%04d%02d%02d-%02d%02d%05.2f-%d:%d" % (args.prefix, ltp.tm_year, ltp.tm_mon, ltp.tm_mday,
                    ltp.tm_hour, ltp.tm_min, secondsbit, cndx, mcnt)
                    jd = {'x' : int(x), 'y' : int(y), 'threshold' : threshold, 'zoom' : zoom,
                        'latitude' : args.latitude, 'longitude' : args.longitude, 'ratio' : frame_max/threshold}
                    js = json.dumps(jd, sort_keys=True, indent=4)
                    fp = open(fn+".json", "w")
                    fp.write(js+"\n")
                    fp.close()
                     
                    cv2.imwrite(fn+".png", img_zoom)
                    mcnt += 1
