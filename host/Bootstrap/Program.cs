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
            using (var mutex = new Mutex(false, "Local\\UStracker.Launcher.1.00.00.000"))
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
                    var shell = Path.Combine(root, "UStracker.Shell.exe");
                    if (!File.Exists(shell)) throw new FileNotFoundException("UStracker.Shell.exe não encontrado.", shell);
                    Process.Start(new ProcessStartInfo(shell, port.ToString()) { UseShellExecute = false, WorkingDirectory = root });
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
    }
}
