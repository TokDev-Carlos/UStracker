using Microsoft.Web.WebView2.Core;
using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using UStracker.Shared;

namespace UStracker.Shell
{
    public partial class MainWindow : Window
    {
        private string _profile;
        private int _port;
        public MainWindow()
        {
            InitializeComponent();
            Loaded += async (_, __) => await InitializeBrowserAsync();
            Closed += OnClosed;
        }

        private async Task InitializeBrowserAsync()
        {
            if (Environment.GetCommandLineArgs().Length < 2 || !int.TryParse(Environment.GetCommandLineArgs()[1], out _port))
            {
                MessageBox.Show("Porta do backend não informada.", "UStracker", MessageBoxButton.OK, MessageBoxImage.Error);
                Close(); return;
            }
            _profile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "UStracker", "WebView2", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_profile);
            try
            {
                await EnsureWebViewAsync();
            }
            catch (WebView2RuntimeNotFoundException)
            {
                var installer = Path.Combine(RootPaths.ProductRoot, "Redist", "MicrosoftEdgeWebView2RuntimeInstallerX64.exe");
                if (!File.Exists(installer)) throw;
                var proc = Process.Start(new ProcessStartInfo(installer, "/silent /install") { UseShellExecute = true });
                if (proc == null) throw new InvalidOperationException("Falha ao iniciar instalador offline do WebView2.");
                proc.WaitForExit();
                if (proc.ExitCode != 0 && proc.ExitCode != -2147219416 && proc.ExitCode != -2147219187)
                    throw new InvalidOperationException("Instalador WebView2 retornou codigo " + proc.ExitCode);
                await EnsureWebViewAsync();
            }
            Browser.Source = new Uri("http://127.0.0.1:" + _port + "/");
        }

        private async Task EnsureWebViewAsync()
        {
            var env = await CoreWebView2Environment.CreateAsync(null, _profile);
            await Browser.EnsureCoreWebView2Async(env);
            Browser.CoreWebView2.Settings.AreDevToolsEnabled = false;
            Browser.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
            Browser.CoreWebView2.Settings.IsStatusBarEnabled = false;
        }

        private void OnClosed(object sender, EventArgs e)
        {
            try
            {
                if (Browser?.CoreWebView2 != null)
                    Browser.CoreWebView2.ExecuteScriptAsync("fetch('/api/v1/shell/detach',{method:'POST',credentials:'include',keepalive:true}).catch(()=>{})");
            }
            catch { }
            try { Browser?.Dispose(); } catch { }
            var profile = _profile;
            Task.Run(() =>
            {
                for (var i = 0; i < 10 && !string.IsNullOrEmpty(profile); i++)
                {
                    try { if (Directory.Exists(profile)) Directory.Delete(profile, true); return; }
                    catch { Thread.Sleep(500); }
                }
            });
        }
    }
}
