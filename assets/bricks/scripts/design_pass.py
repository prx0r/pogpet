# v2 "looks like her clothes" pass, from the source photos (uploads 1791464531700 pyjama / 1791464263859 dress)
import numpy as np,trimesh
Y,LB,BR,PK,TN,WH,BK,DB=range(8)
for k in ['pyjama','dress']:
    m=trimesh.load(f'prod/brick-figure-{k}-PLA-sub.stl',process=False); lab=np.load(f'prod/paint_{k}_clean.npy').copy()
    C=m.triangles_center; N=m.face_normals; x,y,z=C.T; body=np.abs(x)<8
    if k=='pyjama':
        front=N[:,1]<-0.7
        rect=front&(np.abs(x)<=4.1)&(z>=19.6)&(z<=29.4)
        lab[rect]=PK                                   # tee print: one clean pink panel
        shirt=body&(z>18.2)&(z<32.3)&~rect
        lab[shirt&np.isin(lab,[PK,TN,DB,WH])]=LB       # stray print specks off the tee
        legs=body&(z<15.9)
        lab[legs&(lab==DB)]=LB                         # crease noise off the pants
        lab[legs&(z>3)&(lab==TN)]=LB                   # tan specks above the shoes
        feat=front&(np.abs(x)<3.9)&(z>36)&(z<39.2)&(z>33.5)
        lab[feat&(lab==PK)]=BK                         # brows read dark
        lab[lab==DB]=LB                                # leftover seams (9 mm2) not worth a filament slot
    else:
        dress=(z>11.5)&(z<32.3)&body
        sw=lab.copy(); sw[dress&(lab==LB)]=WH; sw[dress&(lab==WH)]=LB; lab=sw   # white dress, blue flowers
        lab[body&(z<=11.5)&(lab==WH)]=TN               # plain tan boot tops
    np.save(f'prod/paint_{k}_v2.npy',lab)
    A=m.area_faces; print(k,{c:round(A[lab==c].sum(),1) for c in range(8) if (lab==c).any()})
