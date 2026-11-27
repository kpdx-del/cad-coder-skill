// Read-only environment probe. Creates no CAD documents and changes no defaults.
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using SW = SolidWorks.Interop.sldworks;
class Probe {
    static int Main() {
        if (Process.GetProcessesByName("SLDWORKS").Length != 0) {
            Console.WriteLine("{\"status\":\"busy\",\"reason\":\"existing user session\"}"); return 4;
        }
        SW.ISldWorks app=null;
        try {
            var type=Type.GetTypeFromProgID("SldWorks.Application.31",true);
            app=(SW.ISldWorks)Activator.CreateInstance(type);
            app.Visible=false;
            Console.WriteLine("{\"status\":\"connected\",\"revision\":\""+app.RevisionNumber()+"\"}");
            return 0;
        } catch(Exception e) {
            Console.Error.WriteLine(e.ToString());
            Console.WriteLine("{\"status\":\"error\",\"reason\":\"COM connection failed; see stderr\"}");return 1;
        } finally {
            if(app!=null) { app.ExitApp();Marshal.FinalReleaseComObject(app); }
        }
    }
}
