using System;
using System.Threading;
using System.Windows;

namespace UStracker.Shell
{
    public partial class App : Application
    {
        private Mutex _mutex;

        protected override void OnStartup(StartupEventArgs e)
        {
            bool created;
            _mutex = new Mutex(true, "Local\\UStracker.Shell.1", out created);
            if (!created)
            {
                Shutdown(0);
                return;
            }
            base.OnStartup(e);
        }

        protected override void OnExit(ExitEventArgs e)
        {
            try { _mutex?.ReleaseMutex(); } catch { }
            _mutex?.Dispose();
            base.OnExit(e);
        }
    }
}
