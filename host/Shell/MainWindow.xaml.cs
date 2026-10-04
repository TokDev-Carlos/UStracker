using Microsoft.Web.WebView2.Core;
using System;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Interop;
using UStracker.Shared;

namespace UStracker.Shell
{
    public partial class MainWindow : Window
    {
        private const int WmClose = 0x0010;
        private string _profile;
        private int _port;
        public MainWindow()
        {
            InitializeComponent();
            SourceInitialized += (_, __) => HwndSource.FromHwnd(new WindowInteropHelper(this).Handle)?.AddHook(WindowMessageHook);
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
            _profile = RootPaths.WebView2Profile;
            Directory.CreateDirectory(_profile);
            try
            {
                await EnsureWebViewAsync();
            }
            catch (WebView2RuntimeNotFoundException)
            {
                var installer = RootPaths.WebView2Installer;
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
            var runtime = Directory.Exists(RootPaths.WebView2Runtime) ? RootPaths.WebView2Runtime : null;
            var env = await CoreWebView2Environment.CreateAsync(runtime, _profile);
            await Browser.EnsureCoreWebView2Async(env);
            Browser.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
            Browser.CoreWebView2.Settings.AreDevToolsEnabled = false;
            Browser.CoreWebView2.Settings.AreDefaultContextMenusEnabled = false;
            Browser.CoreWebView2.Settings.IsStatusBarEnabled = false;
        }

        private void OnWebMessageReceived(object sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            if (e.TryGetWebMessageAsString() == "system-shutdown")
                Environment.Exit(0);
        }

        private IntPtr WindowMessageHook(IntPtr hwnd, int message, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if (message == WmClose)
            {
                handled = true;
                Environment.Exit(0);
            }
            return IntPtr.Zero;
        }

        private void OnClosed(object sender, EventArgs e)
        {
            Environment.Exit(0);
        }
    }
}
