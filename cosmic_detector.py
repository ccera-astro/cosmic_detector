#!/usr/bin/env python3
import cv2
import numpy
import os
import sys
import time
import copy
import json
import argparse

#
# Open a capture stream to desired camera index
#  (/dev/video{cndx})
#

parser = argparse.ArgumentParser(description='Detect Cosmic Muons via Webcam')
parser.add_argument ('camera', type=int, help="Camera index", default=0)
parser.add_argument ('threshold', type=float, help="Detection threshold as ratio", default=2.0)
parser.add_argument ('prefix', help="File prefix", default="./")
parser.add_argument ('latitude', type=float, help="Geographic latitude", default=44.9)
parser.add_argument ('longitude', type=float, help="Geographic longitude", default=-76.03)
args = parser.parse_args()

#
# Setup the camera for streaming
#
cndx = args.camera
cam = cv2.VideoCapture(cndx)


#
# Zoom final dimension in X and Y
#
zoom=30

fmax = 0

#
# Initialize start time and frame counter
#
now = time.time()
count = 0

#
# Build up an average of the max pixels
#  Do this for about 5 seconds
#
while ((time.time() - now) <= 5.0):
    rv, frame = cam.read()
    #
    # Convert to GrayScale
    #
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    frame = numpy.array(frame)
    fmax += numpy.max(frame)
    count += 1
    
print ("Apparent frame rate ", float(count)/5.0)
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
    rv, frame = cam.read()
    frame_count += 1
    if (frame_count >= 1000):
        print ("Still getting frames at ", time.ctime())
        frame_count = 0
    #
    # Convert to GrayScale
    #
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
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
    if (numpy.max(frame) > threshold):
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
            elif all_ziped[counter][0] - 10 < all_ziped[counter - 1][0]:
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
            izoom2 = int(zoom/2)
            if x >= (zoom/2)+1 and y >= (zoom/2)+1:
                img_crop = data[y-izoom2:y + izoom2,
                           x-izoom2:x + izoom2]
                #
                # Resulting image is scaled appropriately
                #
                r = (zoom*2) / img_crop.shape[1]
                dim = (int(zoom*2), int(img_crop.shape[0] * r))
                if img_crop is None:
                    pass
                else:
                    img_zoom = cv2.resize(img_crop, dim, interpolation=cv2.INTER_LINEAR)
                    fn = "%s%04d%02d%02d-%02d%02d%05.2f-%d:%d" % (args.prefix, ltp.tm_year, ltp.tm_mon, ltp.tm_mday,
                    ltp.tm_hour, ltp.tm_min, secondsbit, cndx, mcnt)
                    jd = {'x' : x, 'y' : y, 'threshold' : threshold, 'zoom' : zoom,
                        'latitude' : args.latitude, 'longitude' : args.longitude}
                    js = json.dumps(jd, sort_keys=True, indent=4)
                    fp = open(fn+".json", "w")
                    fp.write(js)
                    fp.close()
                     
                    cv2.imwrite(fn+".png", img_zoom)
                    mcnt += 1
