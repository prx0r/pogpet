# Build a Bambu Studio project 3MF (structure copied from BambuStudio's own resources/calib/pressure_advance/auto_pa_line_single.3mf, v02.00.02.01, A1 profile)
import trimesh, numpy as np, json, zipfile, uuid, io, datetime
from PIL import Image
VER='02.00.02.01'; today=datetime.date.today().isoformat()
NS='unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p"'
def u(): return str(uuid.uuid4())
for k,title in [('pyjama','Brick figure - pyjamas'),('dress','Brick figure - dress')]:
    m=trimesh.load(f'prod/brick-figure-{k}-PLA.stl')
    m.apply_translation([-m.bounds[:,0].mean(),-m.bounds[:,1].mean(),-m.bounds[0,2]])
    V=m.vertices; F=m.faces
    vs='\n'.join(f'     <vertex x="{x:.9g}" y="{y:.9g}" z="{z:.9g}"/>' for x,y,z in V)
    ts='\n'.join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a,b,c in F)
    obj=f'''<?xml version="1.0" encoding="UTF-8"?>
<model {NS}>
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <resources>
  <object id="1" p:UUID="{u()}" type="model">
   <mesh>
    <vertices>
{vs}
    </vertices>
    <triangles>
{ts}
    </triangles>
   </mesh>
  </object>
 </resources>
 <build/>
</model>
'''
    cx,cy=128,128
    main=f'''<?xml version="1.0" encoding="UTF-8"?>
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
 <metadata name="Title">{title}</metadata>
 <resources>
  <object id="2" p:UUID="{u()}" type="model">
   <components>
    <component p:path="/3D/Objects/object_1.model" objectid="1" p:UUID="{u()}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>
   </components>
  </object>
 </resources>
 <build p:UUID="{u()}">
  <item objectid="2" p:UUID="{u()}" transform="1 0 0 0 1 0 0 0 1 {cx} {cy} 0" printable="1"/>
 </build>
</model>
'''
    ms=f'''<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="2">
    <metadata key="name" value="{title}"/>
    <metadata key="extruder" value="1"/>
    <metadata face_count="{len(F)}"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="{title}"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
      <metadata key="source_file" value="brick-figure-{k}-PLA.stl"/>
      <metadata key="source_object_id" value="0"/>
      <metadata key="source_volume_id" value="0"/>
      <metadata key="source_offset_x" value="0"/>
      <metadata key="source_offset_y" value="0"/>
      <metadata key="source_offset_z" value="0"/>
      <mesh_stat face_count="{len(F)}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>
    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_1.png"/>
    <metadata key="top_file" value="Metadata/top_1.png"/>
    <metadata key="pick_file" value="Metadata/pick_1.png"/>
    <model_instance>
      <metadata key="object_id" value="2"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="100"/>
    </model_instance>
  </plate>
  <assemble>
   <assemble_item object_id="2" instance_id="0" transform="1 0 0 0 1 0 0 0 1 {cx} {cy} 0" offset="0 0 0" />
  </assemble>
</config>
'''
    ps=json.load(open('bambu_template/project_settings.config'))
    ps['enable_support']='1'; ps['support_type']='tree(auto)'
    ps['filament_colour']=['#F4D11A']+ps['filament_colour'][1:]
    img=Image.open(f'prod/final_{k}_front.png').convert('RGBA'); img.thumbnail((512,512))
    def png(sz):
        c=Image.new('RGBA',(sz,sz),(0,0,0,0)); t=img.copy(); t.thumbnail((sz,sz)); c.paste(t,((sz-t.width)//2,(sz-t.height)//2),t)
        b=io.BytesIO(); c.save(b,'PNG'); return b.getvalue()
    files={
     '[Content_Types].xml':open('bambu_template/src/[Content_Types].xml').read(),
     '_rels/.rels':open('bambu_template/src/_rels/.rels').read(),
     '3D/3dmodel.model':main,
     '3D/_rels/3dmodel.model.rels':'<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n <Relationship Target="/3D/Objects/object_1.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n',
     '3D/Objects/object_1.model':obj,
     'Metadata/model_settings.config':ms,
     'Metadata/project_settings.config':json.dumps(ps,indent=4),
     'Metadata/slice_info.config':open('bambu_template/src/Metadata/slice_info.config').read(),
     'Metadata/cut_information.xml':'<?xml version="1.0" encoding="utf-8"?>\n<objects>\n <object id="1">\n  <cut_id id="0" check_sum="1" connectors_cnt="0"/>\n </object>\n</objects>\n',
     'Metadata/plate_1.png':png(512),'Metadata/plate_1_small.png':png(128),'Metadata/plate_no_light_1.png':png(512),'Metadata/top_1.png':png(512),'Metadata/pick_1.png':png(512),
    }
    out=f'prod/brick-figure-{k}-bambu.3mf'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,d in files.items(): z.writestr(n,d)
    r=trimesh.load(out,force='mesh'); print(out,len(r.faces),r.is_watertight,r.extents.round(2),r.bounds[0].round(1))
