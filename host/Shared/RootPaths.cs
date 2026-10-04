using System;
using System.IO;

namespace UStracker.Shared
{
    internal static class RootPaths
    {
        internal static string ProductRoot => Path.GetFullPath(AppDomain.CurrentDomain.BaseDirectory);
        internal static string RuntimePython => Path.Combine(ProductRoot, "Runtime", "pythonw.exe");
        internal static string StateDirectory => Path.Combine(ProductRoot, "UserData", "State");
        internal static string StateFile => Path.Combine(StateDirectory, "backend.json");
        internal static string WebView2Profile => Path.Combine(StateDirectory, "WebView2");
        internal static string WebView2Runtime => Path.Combine(ProductRoot, "Runtime", "WebView2");
        internal static string WebView2Installer => Path.Combine(ProductRoot, "Redist", "MicrosoftEdgeWebView2RuntimeInstallerX64.exe");
        internal static string ShellExecutable => Path.Combine(ProductRoot, "UStracker.Shell.exe");
    }
}
