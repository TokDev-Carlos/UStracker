using System;
using System.IO;

namespace UStracker.Shared
{
    internal static class RootPaths
    {
        internal static string ProductRoot => Path.GetFullPath(AppDomain.CurrentDomain.BaseDirectory);
        internal static string RuntimePython => Path.Combine(ProductRoot, "Runtime", "pythonw.exe");
        internal static string StateFile => Path.Combine(ProductRoot, "UserData", "State", "backend.json");
    }
}
