using Xunit;
using FluentAssertions;
using System.Text.Json;

namespace TiaWorker.Tests
{
    public class JsonHelperTests
    {
        [Fact]
        public void JsonOk_ReturnsValidJson()
        {
            var result = JsonHelpers.JsonOk(new { value = 42 });
            using var doc = JsonDocument.Parse(result);
            var root = doc.RootElement;

            root.GetProperty("ok").GetBoolean().Should().BeTrue();
            root.TryGetProperty("error", out var err).Should().BeTrue();
            err.ValueKind.Should().Be(JsonValueKind.Null);
        }

        [Fact]
        public void JsonOk_IncludesResultData()
        {
            var result = JsonHelpers.JsonOk(new { name = "test", count = 123 });

            result.Should().Contain("test");
            result.Should().Contain("123");
        }

        [Fact]
        public void JsonOk_NullData_ProducesValidJson()
        {
            var result = JsonHelpers.JsonOk(null!);
            using var doc = JsonDocument.Parse(result);
            var root = doc.RootElement;

            root.GetProperty("ok").GetBoolean().Should().BeTrue();
        }

        [Fact]
        public void JsonError_ReturnsErrorJson()
        {
            var result = JsonHelpers.JsonError("Something went wrong");
            using var doc = JsonDocument.Parse(result);
            var root = doc.RootElement;

            root.GetProperty("ok").GetBoolean().Should().BeFalse();
            root.GetProperty("error").GetString().Should().Be("Something went wrong");
        }

        [Fact]
        public void JsonError_EmptyMessage()
        {
            var result = JsonHelpers.JsonError("");
            using var doc = JsonDocument.Parse(result);
            doc.RootElement.GetProperty("error").GetString().Should().Be("");
        }

        [Fact]
        public void JsonError_SpecialCharacters()
        {
            var result = JsonHelpers.JsonError("路径错误: D:\\test\\file.scl");
            using var doc = JsonDocument.Parse(result);

            doc.RootElement.GetProperty("error").GetString().Should().Contain("路径错误");
        }

        [Fact]
        public void DryRunResult_ReturnsOkJson()
        {
            var result = JsonHelpers.DryRunResult("import-scl", new { file = "test.scl" });
            using var doc = JsonDocument.Parse(result);

            doc.RootElement.GetProperty("ok").GetBoolean().Should().BeTrue();
        }

        [Fact]
        public void JsonOk_And_JsonError_HaveConsistentKeys()
        {
            var okResult = JsonHelpers.JsonOk(new { x = 1 });
            var errResult = JsonHelpers.JsonError("err");

            using var okDoc = JsonDocument.Parse(okResult);
            using var errDoc = JsonDocument.Parse(errResult);

            var okKeys = okDoc.RootElement.EnumerateObject().Select(p => p.Name).OrderBy(n => n);
            var errKeys = errDoc.RootElement.EnumerateObject().Select(p => p.Name).OrderBy(n => n);

            okKeys.Should().BeEquivalentTo(errKeys);
        }

        [Fact]
        public void JsonOk_WithObject_HasResultProperty()
        {
            var result = JsonHelpers.JsonOk(new { name = "test" });
            using var doc = JsonDocument.Parse(result);

            var resultProp = doc.RootElement.GetProperty("result");
            resultProp.GetProperty("name").GetString().Should().Be("test");
        }

        [Fact]
        public void JsonOk_WithList_SerializesCorrectly()
        {
            var result = JsonHelpers.JsonOk(new[] { "a", "b" });
            using var doc = JsonDocument.Parse(result);

            var arr = doc.RootElement.GetProperty("result").EnumerateArray().ToList();
            arr.Should().HaveCount(2);
            arr[0].GetString().Should().Be("a");
        }
    }
}