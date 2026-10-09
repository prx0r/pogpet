# Both figures on one plate, 6-filament painted Bambu Studio project 3MF (structure from BambuStudio's own calib 3MF, A1 profile)
import trimesh, numpy as np, json, zipfile, uuid, io, datetime, sys
from PIL import Image
sys.path.insert(0,'.'); from paint_map import PAL
VER='02.00.02.01'; today=datetime.date.today().isoformat()
CODES=['4','8','0C','1C','2C','3C','4C','5C']
NS='unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p"'
u=lambda: str(uuid.uuid4())
ALL={'pyjama':'Brick figure - pyjamas','dress':'Brick figure - dress'}
K=sys.argv[1]; figs=[(K,ALL[K],128)]
files={}; res=[]; build=[]; msobj=[]; inst=[]; asm=[]; rels=[]
for i,(k,title,cx) in enumerate(figs):
    m=trimesh.load(f'prod/brick-figure-{k}-PLA-sub.stl',process=False); m.merge_vertices(); assert m.is_watertight; lab=np.load(f'prod/paint_{k}_v2.npy')
    USED=[c for c in range(len(PAL)) if (lab==c).any()]; remap=np.full(len(PAL),-1); remap[USED]=np.arange(len(USED)); lab=remap[lab]; assert len(lab)==len(m.faces)
    m.vertices-=[m.bounds[:,0].mean(),m.bounds[:,1].mean(),m.bounds[0,2]]
    vs='\n'.join('     <vertex x="%.9g" y="%.9g" z="%.9g"/>'%tuple(v) for v in m.vertices)
    code=np.array(CODES)[lab]
    ts='\n'.join(f'     <triangle v1="{a}" v2="{b}" v3="{c}" paint_color="{p}"/>' for (a,b,c),p in zip(m.faces,code))
    mid=i+1; oid=10+i; path=f'/3D/Objects/object_{mid}.model'
    files[path[1:]]=f'<?xml version="1.0" encoding="UTF-8"?>\n<model {NS}>\n <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n  <object id="{mid}" p:UUID="{u()}" type="model">\n   <mesh>\n    <vertices>\n{vs}\n    </vertices>\n    <triangles>\n{ts}\n    </triangles>\n   </mesh>\n  </object>\n </resources>\n <build/>\n</model>\n'
    rels.append(f' <Relationship Target="{path}" Id="rel-{mid}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
    res.append(f'  <object id="{oid}" p:UUID="{u()}" type="model">\n   <components>\n    <component p:path="{path}" objectid="{mid}" p:UUID="{u()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n   </components>\n  </object>')
    build.append(f'  <item objectid="{oid}" p:UUID="{u()}" transform="1 0 0 0 1 0 0 0 1 {cx} 128 0" printable="1"/>')
    msobj.append(f'''  <object id="{oid}">
    <metadata key="name" value="{title}"/>
    <metadata key="extruder" value="1"/>
    <metadata face_count="{len(m.faces)}"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="{title}"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <metadata key="source_file" value="brick-figure-{k}.stl"/>
      <metadata key="source_object_id" value="0"/>
      <metadata key="source_volume_id" value="0"/>
      <metadata key="source_offset_x" value="0"/>
      <metadata key="source_offset_y" value="0"/>
      <metadata key="source_offset_z" value="0"/>
      <mesh_stat face_count="{len(m.faces)}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>''')
    inst.append(f'''    <model_instance>
      <metadata key="object_id" value="{oid}"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="{100+i*10}"/>
    </model_instance>''')
    asm.append(f'   <assemble_item object_id="{oid}" instance_id="0" transform="1 0 0 0 1 0 0 0 1 {cx} 128 0" offset="0 0 0" />')
    print(k,len(m.faces),'tris', np.bincount(lab,minlength=len(USED)))
files['3D/3dmodel.model']=f'''<?xml version="1.0" encoding="UTF-8"?>
<model {NS}>
 <metadata name="Application">BambuStudio-{VER}</metadata>
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <metadata name="Copyright"></metadata>
 <metadata name="CreationDate">{today}</metadata>
 <metadata name="Description"></metadata>
 <metadata name="Designer"></metadata>
 <metadata name="DesignerCover"></metadata>
 <metadata name="DesignerUserId"></metadata>
 <metadata name="License"></metadata>
 <metadata name="ModificationDate">{today}</metadata>
 <metadata name="Origin"></metadata>
 <metadata name="Thumbnail_Middle">/Metadata/plate_1.png</metadata>
 <metadata name="Thumbnail_Small">/Metadata/plate_1_small.png</metadata>
 <metadata name="Title">{ALL[K]}</metadata>
 <resources>
{chr(10).join(res)}
 </resources>
 <build p:UUID="{u()}">
{chr(10).join(build)}
 </build>
</model>
'''
files['3D/_rels/3dmodel.model.rels']='<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'+'\n'.join(rels)+'\n</Relationships>\n'
files['Metadata/model_settings.config']=f'''<?xml version="1.0" encoding="UTF-8"?>
<config>
{chr(10).join(msobj)}
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>
    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_1.png"/>
    <metadata key="top_file" value="Metadata/top_1.png"/>
    <metadata key="pick_file" value="Metadata/pick_1.png"/>
{chr(10).join(inst)}
  </plate>
  <assemble>
{chr(10).join(asm)}
  </assemble>
</config>
'''
NF=len(USED); ps=json.load(open('bambu_template/project_settings.config')); n0=len(ps['filament_colour'])
for key,v in list(ps.items()):
    if isinstance(v,list):
        if len(v)==n0: ps[key]=v[:NF]
        elif len(v)==n0*2: ps[key]=v[:NF*2]
        elif len(v)==n0*n0: ps[key]=[v[r*n0+c] for r in range(NF) for c in range(NF)]
ps['filament_colour']=[PAL[c][1] for c in USED]; ps['default_filament_colour']=['']*NF
ps['filament_self_index']=[str(i+1) for i in range(NF)]
ps['layer_height']='0.12'; ps['enable_support']='1'; ps['support_type']='tree(auto)'
files['Metadata/project_settings.config']=json.dumps(ps,indent=4)
files['Metadata/cut_information.xml']='<?xml version="1.0" encoding="utf-8"?>\n<objects>\n'+''.join(f' <object id="{i+1}">\n  <cut_id id="0" check_sum="1" connectors_cnt="0"/>\n </object>\n' for i in range(len(figs)))+'</objects>\n'
files['Metadata/slice_info.config']=open('bambu_template/src/Metadata/slice_info.config').read()
files['[Content_Types].xml']=open('bambu_template/src/[Content_Types].xml').read()
files['_rels/.rels']=open('bambu_template/src/_rels/.rels').read()
both=Image.open(f'prod/paint_{K}_front.png').convert('RGBA')
def png(sz):
    c=Image.new('RGBA',(sz,sz),(0,0,0,0)); t=both.copy(); t.thumbnail((sz,sz)); c.paste(t,((sz-t.width)//2,(sz-t.height)//2),t); b=io.BytesIO(); c.save(b,'PNG'); return b.getvalue()
for n,sz in [('plate_1',512),('plate_1_small',128),('plate_no_light_1',512),('top_1',512),('pick_1',512)]: files[f'Metadata/{n}.png']=png(sz)
out=f'prod/brick-figure-{K}-{NF}colour-bambu.3mf'; print('filaments',[PAL[c][0] for c in USED])
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for n,d in files.items(): z.writestr(n,d)
print(out)
