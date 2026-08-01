using FluentAssertions;
using Xunit;

namespace TiaWorker.Tests
{
    public class DownloadInterfaceSelectorTests
    {
        [Fact]
        public void FilterAndOrder_KeepsOnlyPlcsimInterfaces()
        {
            var result = DownloadInterfaceSelector.FilterAndOrder(
                new[] { "Intel Ethernet", "PLCSIM", "PLCSIM Virtual Ethernet Adapter" },
                name => name);

            result.Should().Equal("PLCSIM", "PLCSIM Virtual Ethernet Adapter");
        }

        [Fact]
        public void FilterAndOrder_PrefersSoftbusAndKeepsStableOrder()
        {
            var result = DownloadInterfaceSelector.FilterAndOrder(
                new[]
                {
                    "PLCSIM Virtual Ethernet Adapter 1",
                    "PLCSIM Softbus A",
                    "PLCSIM Softbus B",
                    "PLCSIM Virtual Ethernet Adapter 2",
                },
                name => name);

            result.Should().Equal(
                "PLCSIM Softbus A",
                "PLCSIM Softbus B",
                "PLCSIM Virtual Ethernet Adapter 1",
                "PLCSIM Virtual Ethernet Adapter 2");
        }

        [Fact]
        public void FilterAndOrder_IsCaseInsensitive()
        {
            var result = DownloadInterfaceSelector.FilterAndOrder(
                new[] { "plcsim", "PlcSim virtual ethernet" },
                name => name);

            result.Should().HaveCount(2);
        }
    }
}
