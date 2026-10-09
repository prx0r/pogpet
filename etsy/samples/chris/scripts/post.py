import sys, cv2
raw, out, size = sys.argv[1], sys.argv[2], int(sys.argv[3])
im = cv2.imread(raw)
im = cv2.fastNlMeansDenoisingColored(im, None, 4, 4, 7, 21)
h, w = im.shape[:2]; im = cv2.resize(im, (size, int(size * h / w)), interpolation=cv2.INTER_AREA)
cv2.imwrite(out, im, [cv2.IMWRITE_PNG_COMPRESSION, 6])
print('post', out)
