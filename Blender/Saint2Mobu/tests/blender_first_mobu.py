from pyfbsdk import *
import pathlib,time,traceback
root=pathlib.Path(__file__).resolve().parents[1]
log=root/'work/blender-first-mobu.log'
app=FBApplication()
keep=FBModelCube('KeepInMobu');keep.Show=True
(root/'work/blender-first-ready').touch()
stage=0;started=time.monotonic()
def write(text):
 with log.open('a') as f:f.write(str(text)+'\n')
def idle(c,e):
 global stage,started
 try:
  mesh=FBFindModelByLabelName('BlenderFirstCube')
  if stage==0 and mesh:
   assert abs(mesh.Translation[0]-200)<.05,list(mesh.Translation)
   assert FBFindModelByLabelName('KeepInMobu') is not None
   write('FIRST_SEND_PASSED '+str(list(mesh.Translation)))
   stage=1;started=time.monotonic()
  elif stage==1 and time.monotonic()-started>3:
   mesh.Translation=FBVector3d(200,300,0)
   for model in FBSystem().Scene.Components:
    if isinstance(model,FBModel):model.Selected=model==mesh
   FBSystem().Scene.Evaluate()
   stage=2;started=time.monotonic()
  elif stage==2 and time.monotonic()-started>2:
   write('RETURN_UPDATE '+str(app.OneClickUpdateCurrentScene()))
   stage=3
  elif stage==3 and abs(mesh.Translation[0]-400)<.05:
   write('SECOND_SEND_PASSED');stage=4
 except:
  write(traceback.format_exc());stage=99
FBSystem().OnUIIdle.Add(idle)
