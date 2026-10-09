import sys, glob, subprocess
from PIL import Image
name, n = sys.argv[1], int(sys.argv[2]); O='/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/out/'
tiles=[Image.open(O+f'{name}_tile{i}_raw.png').convert('RGB') for i in range(n)][::-1]  # top first
W=tiles[0].width; Hh=sum(t.height for t in tiles); im=Image.new('RGB',(W,Hh)); y=0
for t in tiles: im.paste(t,(0,y)); y+=t.height
im.save(O+name+'_raw.png')
subprocess.run(['python3','/workspace/projects/791a7153-8d05-4c9b-b767-8f281ad46eb0/etsy_samples/post.py',O+name+'_raw.png',O+name+'.png','1600'])
print('stitched',im.size)
