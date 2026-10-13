using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Diagnostics;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using System.Web.Script.Serialization;
// SynHub transport only. All FBX IO is performed by Blender's built-in operators.
class NativeHost {
 [DllImport("kernel32", CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr LoadLibraryEx(string p,IntPtr h,uint f);
 [DllImport("kernel32", CharSet=CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr h,string n);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Init([MarshalAs(UnmanagedType.LPStr)] string n);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Zero();
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int End(IntPtr token);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Name();
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void LinkCB(IntPtr user,IntPtr link);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void MessageCB(IntPtr user,IntPtr link,IntPtr data,UIntPtr size);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int AddLink(IntPtr user,LinkCB cb);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int AddMessage(IntPtr link,IntPtr user,MessageCB cb);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Send(IntPtr link,byte[] data,UIntPtr size);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int StartLink(IntPtr link,int timeout);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate UIntPtr Existing(IntPtr appInfo,[Out] IntPtr[] buffer,UIntPtr count);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate UIntPtr AllInfos([Out] IntPtr[] buffer,UIntPtr count);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr InfoText(IntPtr appInfo);
 class Target {public int pid;}
 class Connecting {public IntPtr link;public int pid;public DateTime started;}
 static Dictionary<string,DateTime> discovery=new Dictionary<string,DateTime>();
 static string mobuExecutable;
 static Dictionary<string,Connecting> connecting=new Dictionary<string,Connecting>();
 static List<Target> Targets() {
  var result=new List<Target>();
  foreach(var process in Process.GetProcessesByName("motionbuilder")) {
   try {
    if(!String.Equals(Path.GetFullPath(process.MainModule.FileName),mobuExecutable,StringComparison.OrdinalIgnoreCase))continue;
    result.Add(new Target {pid=process.Id});
   }catch(System.ComponentModel.Win32Exception){}catch(InvalidOperationException){}
   finally{process.Dispose();}
  }
  result.Sort((a,b)=>a.pid.CompareTo(b.pid));return result;
 }
 static void ConnectionResult(string path,bool connected,long link,int pid,string error) {
  Atomic(path+".result",new {connected=connected,link=link,pid=pid,error=error});
  File.Move(path,path+".processed");connecting.Remove(path);discovery.Remove(path);
 }
 static void ConnectRequests() {
  foreach(string path in Directory.GetFiles(folder,"connect-*.json")) {
   try {
    Connecting pending;
    if(connecting.TryGetValue(path,out pending)) {

     int remote;
     if(links.TryGetValue(pending.link.ToInt64(),out remote)) {
      bool match=remote==pending.pid;
      ConnectionResult(path,match,pending.link.ToInt64(),remote,match?"":"Connected process does not match the chosen Mobu");
     }else if(!Alive(pending.pid)||(DateTime.UtcNow-File.GetLastWriteTimeUtc(path)).TotalSeconds>90)
      ConnectionResult(path,false,0,pending.pid,"Native MotionBuilder connection did not complete");
     else if((DateTime.UtcNow-pending.started).TotalSeconds>2&&Fn<End>("AppLink_getState")(pending.link)==0) {
      // Mobu advertises its process before its service/GUI finishes startup.
      // Retry stopped handshakes while the selected process becomes ready.
      connecting.Remove(path);
     }
     continue;
    }
    var request=json.Deserialize<Dictionary<string,object>>(File.ReadAllText(path));
    int pid=Convert.ToInt32(request["pid"]);
    var target=Targets().Find(item=>item.pid==pid);
    if(target==null) {
     if(!Alive(pid)||(DateTime.UtcNow-File.GetLastWriteTimeUtc(path)).TotalSeconds>90)
      ConnectionResult(path,false,0,pid,"The selected MotionBuilder process is no longer available");
     continue;
    }
    foreach(var peer in links) if(peer.Value==pid) {
     ConnectionResult(path,true,peer.Key,pid,"");target=null;break;
    }
    if(target==null)continue;
    // AppInfo and AppLink are distinct opaque IDs. Existing links must be
    // discovered using AppInfo IDs, then matched to the exact selected PID.
    DateTime next;
    if(discovery.TryGetValue(path,out next)&&DateTime.UtcNow<next)continue;
    discovery[path]=DateTime.UtcNow.AddMilliseconds(500);
    IntPtr[] infos=new IntPtr[256];
    ulong infoCount=Fn<AllInfos>("AppDir_getAllInfos")(infos,(UIntPtr)infos.Length).ToUInt64();
    IntPtr link=IntPtr.Zero;
    for(int i=0;i<(int)Math.Min(infoCount,(ulong)infos.Length)&&link==IntPtr.Zero;i++) {
     string executable=Marshal.PtrToStringAnsi(Fn<InfoText>("AppInfo_getExecutablePath")(infos[i]));
     if(!String.Equals(executable,mobuExecutable,StringComparison.OrdinalIgnoreCase))continue;
     IntPtr[] candidates=new IntPtr[256];
     ulong count=Fn<Existing>("AppLink_getExistingAppLinks")(infos[i],candidates,(UIntPtr)candidates.Length).ToUInt64();
     for(int j=0;j<(int)Math.Min(count,(ulong)candidates.Length);j++)
      if(Fn<End>("AppLink_getRemoteAppProcessId")(candidates[j])==pid){link=candidates[j];break;}
    }
    if(link==IntPtr.Zero) {
     if((DateTime.UtcNow-File.GetLastWriteTimeUtc(path)).TotalSeconds>90)
      ConnectionResult(path,false,0,pid,"MotionBuilder native service did not become ready");
     continue;
    }
    int result=Fn<StartLink>("AppLink_start")(link,5000); // handshake deadline in milliseconds; keep dispatching
    Log("CONNECT link="+link+" pid="+pid+" result="+result);
    if(result!=1)ConnectionResult(path,false,0,pid,"SynHub rejected the connection request");
    else connecting[path]=new Connecting {link=link,pid=pid,started=DateTime.UtcNow};
   }catch(Exception e){Log(e.ToString());ConnectionResult(path,false,0,0,e.Message);}
  }
 }
 static IntPtr dll; static string folder; static LinkCB onLink; static MessageCB onMessage;
 static JavaScriptSerializer json=new JavaScriptSerializer();
 static Dictionary<long,int> links=new Dictionary<long,int>();
 static T Fn<T>(string n) {
  IntPtr p=GetProcAddress(dll,"SynHub_"+n);
  if(p==IntPtr.Zero)throw new Exception("Missing SynHub export: "+n);
  return (T)(object)Marshal.GetDelegateForFunctionPointer(p,typeof(T));
 }
 static void Log(string text) { File.AppendAllText(Path.Combine(folder,"native.log"),DateTime.UtcNow.ToString("o")+" "+text+Environment.NewLine); }
 static void Atomic(string path,object value) {
  File.WriteAllText(path+".tmp",json.Serialize(value),new UTF8Encoding(false));
  for(int retry=0;;retry++) {
   try {if(File.Exists(path)) File.Replace(path+".tmp",path,null); else File.Move(path+".tmp",path);break;}
   catch(IOException){if(retry>=30)throw;Thread.Sleep(5);}
  }
 }
 static bool Alive(int pid) { try {using(var process=Process.GetProcessById(pid))return !process.HasExited;}catch{return false;} }
 static void Linked(IntPtr user,IntPtr link) {
  try {
   int pid=Fn<End>("AppLink_getRemoteAppProcessId")(link);
   links[link.ToInt64()]=pid; Log("LINK "+link+" PID "+pid);
   if(Fn<AddMessage>("AppLink_addMessageCallback")(link,IntPtr.Zero,onMessage)!=1)throw new Exception("Message callback registration failed");
  }catch(Exception e){Log(e.ToString());}
 }
 static void Message(IntPtr user,IntPtr link,IntPtr data,UIntPtr size) {
  try {
   ulong length=size.ToUInt64(); if(length>16777216)throw new Exception("Message exceeds 16 MB");
   byte[] bytes=new byte[(int)length];Marshal.Copy(data,bytes,0,bytes.Length);
   string id=DateTime.UtcNow.Ticks.ToString("D19")+"-"+Guid.NewGuid().ToString("N");
   Atomic(Path.Combine(folder,"in-"+id+".json"),new {link=link.ToInt64(), xml=Encoding.UTF8.GetString(bytes).TrimEnd('\0')});
   Log("RECEIVE "+link+" "+length);
  }catch(Exception e){Log(e.ToString());}
 }
 static void DispatchOutgoing() {
  string[] paths=Directory.GetFiles(folder,"out-*.json"); Array.Sort(paths,StringComparer.Ordinal);
  foreach(string path in paths) {
   bool ok=false; string error="";
   try {
    var request=json.Deserialize<Dictionary<string,object>>(File.ReadAllText(path));
    long link=Convert.ToInt64(request["link"]);
    if(!links.ContainsKey(link)||!Alive(links[link]))throw new Exception("MotionBuilder connection is no longer available");
    byte[] payload=Encoding.UTF8.GetBytes((string)request["xml"]+"\0");
    ok=Fn<Send>("AppLink_sendMessage")(new IntPtr(link),payload,(UIntPtr)payload.Length)==1;
    if(!ok)error="SynHub rejected message";
   }catch(Exception e){error=e.Message;}
   Atomic(path+".result",new {sent=ok,error=error});
   File.Move(path,path+".processed");Log("SEND "+Path.GetFileName(path)+" "+ok+" "+error);
  }
 }
 [STAThread] static void Main(string[] args) {
  try {
   if(args.Length<2) args=File.ReadAllLines(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"host-config.txt"));
   folder=Path.GetFullPath(args[0]);Directory.CreateDirectory(folder);
   mobuExecutable=Path.Combine(Path.GetDirectoryName(Path.GetFullPath(args[1])),"motionbuilder.exe");
   int parent=args.Length>2?int.Parse(args[2]):0;
   // A launch by Mobu without arguments joins the same configured Blender session.
   using(var singleton=new Mutex(false,"Local\\SaintMocapHost-"+Path.GetFileName(folder))) {
    if(!singleton.WaitOne(0))return;
    try {
     if(parent>0&&!Alive(parent))return;
     Log("START pid="+Process.GetCurrentProcess().Id);
     dll=LoadLibraryEx(Path.GetFullPath(args[1]),IntPtr.Zero,0x100|0x1000);
     if(dll==IntPtr.Zero)throw new Exception("LoadLibrary failed "+Marshal.GetLastWin32Error());
     IntPtr token=Fn<Init>("Init_initialize")("SaintMocap Send2Mobu");
     try {
      string identity=Marshal.PtrToStringAnsi(Fn<Name>("AppProcess_getLocalAppName")());
      if(identity!="Maya"&&identity!="3ds Max")throw new Exception("Emulation registration not found: "+identity);
      onLink=Linked;onMessage=Message;
      if(Fn<AddLink>("AppLink_addLinkStartedCallback")(IntPtr.Zero,onLink)!=1)throw new Exception("Link callback registration failed");
      Fn<Zero>("AppLink_startServer")();
      if(Fn<Zero>("AppLink_isServerRunning")()!=1)throw new Exception("SynHub server did not start");
      DateTime heartbeat=DateTime.MinValue;
      while(!File.Exists(Path.Combine(folder,"stop"))&&(parent==0||Alive(parent))) {
       Fn<Zero>("Dispatcher_dispatch")();ConnectRequests();DispatchOutgoing();
       if((DateTime.UtcNow-heartbeat).TotalSeconds>=0.5) {
        var peers=new List<object>();foreach(var item in links)if(Alive(item.Value))peers.Add(new {link=item.Key,pid=item.Value});
        Atomic(Path.Combine(folder,"status.json"),new {pid=Process.GetCurrentProcess().Id,heartbeat=(DateTime.UtcNow-new DateTime(1970,1,1)).TotalSeconds,identity=identity,peers=peers,targets=Targets()});
        heartbeat=DateTime.UtcNow;
       }
       Thread.Sleep(30);
      }
      Fn<Zero>("AppLink_stopServer")();
     }finally{Fn<End>("Init_finalize")(token);}
    }finally{singleton.ReleaseMutex();}
   }
  }catch(Exception e){if(folder!=null) {Log(e.ToString());Atomic(Path.Combine(folder,"fatal.json"),new {error=e.Message});}Environment.ExitCode=1;}
 }
}
