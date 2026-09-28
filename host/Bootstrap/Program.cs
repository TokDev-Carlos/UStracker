using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using UStracker.Shared;

namespace UStracker.Bootstrap
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            using (var mutex = new Mutex(false, "Local\\UStracker.Launcher.1"))
            {
                if (!mutex.WaitOne(TimeSpan.FromSeconds(10))) return;
                try
                {
                    var root = RootPaths.ProductRoot;
                    if (!File.Exists(RootPaths.RuntimePython))
                        throw new FileNotFoundException("Runtime Python não encontrado.", RootPaths.RuntimePython);
                    var port = ReadHealthyPort();
                    if (port <= 0)
                    {
                        StartBackend(root);
                        port = WaitForBackend();
                    }
                    var shell = RootPaths.ShellExecutable;
                    if (!File.Exists(shell)) throw new FileNotFoundException("UStracker.Shell.exe não encontrado.", shell);
                    var shellProcess = Process.Start(new ProcessStartInfo(shell, port.ToString()) { UseShellExecute = false, WorkingDirectory = root });
                    if (shellProcess == null) throw new InvalidOperationException("Falha ao iniciar a janela do UStracker.");
                    shellProcess.WaitForExit();
                    StopBackend();
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ex.Message, "UStracker", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
                finally { try { mutex.ReleaseMutex(); } catch { } }
            }
        }

        private static void StartBackend(string root)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(RootPaths.StateFile));
            var psi = new ProcessStartInfo(RootPaths.RuntimePython,
                "-m ustracker.server --root \"" + root.TrimEnd('\\') + "\"")
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = root
            };
            var process = Process.Start(psi);
            if (process == null) throw new InvalidOperationException("Falha ao iniciar backend local.");
        }

        private static int WaitForBackend()
        {
            var until = DateTime.UtcNow.AddSeconds(30);
            while (DateTime.UtcNow < until)
            {
                var port = ReadHealthyPort();
                if (port > 0) return port;
                Thread.Sleep(250);
            }
            throw new TimeoutException("O backend local não respondeu no prazo esperado.");
        }

        private static int ReadHealthyPort()
        {
            try
            {
                if (!File.Exists(RootPaths.StateFile)) return -1;
                var json = File.ReadAllText(RootPaths.StateFile);
                var match = Regex.Match(json, "\\\"port\\\"\\s*:\\s*(\\d+)");
                if (!match.Success) return -1;
                var port = int.Parse(match.Groups[1].Value);
                using (var client = new HttpClient { Timeout = TimeSpan.FromSeconds(1) })
                {
                    var response = client.GetAsync("http://127.0.0.1:" + port + "/api/v1/health").GetAwaiter().GetResult();
                    return response.IsSuccessStatusCode ? port : -1;
                }
            }
            catch { return -1; }
        }

        private static void StopBackend()
        {
            try
            {
                if (!File.Exists(RootPaths.StateFile)) return;
                var json = File.ReadAllText(RootPaths.StateFile);
                var match = Regex.Match(json, "\"pid\"\\s*:\\s*(\\d+)");
                if (!match.Success) return;
                var pid = int.Parse(match.Groups[1].Value);
                using (var backend = Process.GetProcessById(pid))
                {
                    var executable = backend.MainModule?.FileName;
                    if (string.IsNullOrWhiteSpace(executable)) return;
                    if (!string.Equals(Path.GetFullPath(executable), Path.GetFullPath(RootPaths.RuntimePython), StringComparison.OrdinalIgnoreCase)) return;
                    backend.Kill();
                    backend.WaitForExit(5000);
                }
                try { File.Delete(RootPaths.StateFile); } catch { }
            }
            catch { }
        }
    }
}
