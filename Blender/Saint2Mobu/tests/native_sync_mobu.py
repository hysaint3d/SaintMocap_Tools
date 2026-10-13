from pyfbsdk import *
import pathlib,time,traceback,os
root=pathlib.Path(__file__).resolve().parents[1]
log=root/'work/native-sync-mobu.log'
def write(s):
 with log.open('a') as f:f.write(str(s)+'\n')
app=FBApplication();app.FileOpen(str(root/'work/rig.fbx'),False)
def select_all():
 for c in FBSystem().Scene.Components:
  if isinstance(c,FBModel) and not isinstance(c,FBCamera):c.Selected=True
select_all()
started=time.monotonic();stage=0
write('START '+str([(c.LongName,type(c).__name__) for c in FBSystem().Scene.Components if isinstance(c,FBModel) and c.Selected]))
def idle(c,e):
 global stage,started
 try:
  if stage==0 and time.monotonic()-started>4:
   stage=1;write('SEND_NEW '+str(app.OneClickSendAsNewScene((FBOneClickApplication.kFBOneClick3dsMax if os.environ.get('SEND2_TEST_PRODUCT')=='3ds Max' else FBOneClickApplication.kFBOneClickMaya))))
  elif stage==1:
   mesh=FBFindModelByLabelName('SyncSkin')
   if mesh and abs(mesh.Translation[0]-250)<0.05:
    stage=2;started=time.monotonic()
    FBPlayerControl().Goto(FBTime(0,0,0,10));FBSystem().Scene.Evaluate()
    bone=FBFindModelByLabelName('Hips')
    position=FBVector3d();bone.GetVector(position,FBModelTransformationType.kModelTranslation,True)
    assert abs(position[0]-125)<0.05, list(position)
    write('BONE_WORLD '+str(list(position)))
    write('BLENDER_TO_MOBU_PASSED mesh='+str(list(mesh.Translation))+' hips='+str(list(bone.Translation)))
    mesh.Translation=FBVector3d(250,125,0)
    added=FBModelCube('AddedInMobu');added.Show=True;added.Scaling=FBVector3d(10,10,10)
    select_all()
  elif stage==2 and time.monotonic()-started>3:
   stage=3;write('SEND_UPDATE '+str(app.OneClickUpdateCurrentScene()))
  elif stage==3 and (root/'work/native-sync-blender-ok').exists():
   stage=4;write('END_TO_END_PASSED')
 except:
  write(traceback.format_exc());stage=99
FBSystem().OnUIIdle.Add(idle)
