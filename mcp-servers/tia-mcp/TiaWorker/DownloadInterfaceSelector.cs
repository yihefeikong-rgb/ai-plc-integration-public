using System;
using System.Collections.Generic;
using System.Linq;

namespace TiaWorker
{
    public static class DownloadInterfaceSelector
    {
        public static IReadOnlyList<T> FilterAndOrder<T>(
            IEnumerable<T> interfaces,
            Func<T, string> nameSelector)
        {
            if (interfaces == null) throw new ArgumentNullException(nameof(interfaces));
            if (nameSelector == null) throw new ArgumentNullException(nameof(nameSelector));

            return interfaces
                .Where(item => IsPlcsim(nameSelector(item)))
                .OrderBy(item => IsSoftbus(nameSelector(item)) ? 0 : 1)
                .ToArray();
        }

        static bool IsPlcsim(string name) =>
            (name ?? "").IndexOf("PLCSIM", StringComparison.OrdinalIgnoreCase) >= 0;

        static bool IsSoftbus(string name)
        {
            name = name ?? "";
            return name.IndexOf("Ethernet", StringComparison.OrdinalIgnoreCase) < 0 &&
                   name.IndexOf("Virtual", StringComparison.OrdinalIgnoreCase) < 0;
        }
    }
}
