// 此文件已被 CommandValidatorTests.cs 替代。
// 保留此文件以引用所有核心测试套件，确保测试发现器能找到所有测试。
namespace TiaWorker.Tests;

/// <summary>
/// 核心测试入口 — 参见以下测试文件：
/// - <see cref="CommandValidatorTests"/>: import-scl, compile, download, list-devices 命令验证
/// - <see cref="ArgumentParserTests"/>: 命令行参数解析
/// - <see cref="JsonHelperTests"/>: JSON 序列化辅助方法
/// - <see cref="DtoSerializationTests"/>: DTO 序列化/反序列化
/// </summary>
public class UnitTest1
{
    [Fact]
    public void TestSuite_IsDiscoverable()
    {
        // 确保测试项目可被发现
        Assert.True(true);
    }
}