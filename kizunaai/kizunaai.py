import random
import numpy
import cv2

flag = True
while(flag):
    r = random.randint(0, 1)
    s = random.randint(0, 4)
    f = ""
    if r == 0:
        f += "listen/0"
    else:
        f += "speak/0"
    f += str(s)
    f += ".avi"
    cap = cv2.VideoCapture(f)
    while(cap.isOpened()):
        ret, frame = cap.read()
        if not(ret):
            break
        cv2.imshow("kizunaai", frame)
        if cv2.waitKey(33) == 27:
            flag = False
            break
    cap.release()
cv2.destroyAllWindows()