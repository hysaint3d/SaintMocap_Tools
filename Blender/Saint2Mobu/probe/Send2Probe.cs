using System;
using System.IO;
using System.Diagnostics;
using System.Text;
class Send2Probe {
 [STAThread] static void Main(string[] args) {
  string root=Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
  string dir=Path.Combine(root,"probe-logs"); Directory.CreateDirectory(dir);
  var s=new StringBuilder();
  s.AppendLine("utc="+DateTime.UtcNow.ToString("o"));
  s.AppendLine("pid="+Process.GetCurrentProcess().Id);
  s.AppendLine("cwd="+Environment.CurrentDirectory);
  s.AppendLine("NOTE: launch probe only; no SynHub handshake implemented");
  for(int i=0;i<args.Length;i++) s.AppendLine("arg["+i+"]="+args[i]);
  s.AppendLine("SYNHUB_CONFIG_PATH="+Environment.GetEnvironmentVariable("SYNHUB_CONFIG_PATH"));
  File.WriteAllText(Path.Combine(dir,DateTime.UtcNow.ToString("yyyyMMdd-HHmmss-fff")+".log"),s.ToString());
 }
}
