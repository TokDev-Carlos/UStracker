using System;
using System.Diagnostics;
using System.IO;
using UStracker.Shared;

namespace UStracker.Updater
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            if (args.Length != 1 || !File.Exists(args[0]))
            {
                Console.Error.WriteLine("Uso: UStracker.Updater.exe <pacote.usup>");
                return 2;
            }
            var python = Path.Combine(RootPaths.ProductRoot, "Runtime", "python.exe");
            var psi = new ProcessStartInfo(python,
                "-m ustracker.apply_update \"" + Path.GetFullPath(args[0]) + "\" --root \"" + RootPaths.ProductRoot.TrimEnd('\\') + "\"")
            { UseShellExecute = false, WorkingDirectory = RootPaths.ProductRoot };
            var process = Process.Start(psi);
            process.WaitForExit();
            return process.ExitCode;
        }
    }
}
