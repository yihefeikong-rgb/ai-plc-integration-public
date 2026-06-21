using FluentAssertions;
using Xunit;

namespace TiaWorker.Tests
{
    public class ArgumentParserTests
    {
        [Fact]
        public void Parse_NoArgs_Defaults()
        {
            var parser = new ArgumentParser();
            parser.Parse(Array.Empty<string>());

            parser.IsDryRun.Should().BeFalse();
            parser.IsAutoBackup.Should().BeTrue();
            parser.TiaMajorVersion.Should().Be("V18");
            parser.RemainingArgs.Should().BeEmpty();
        }

        [Fact]
        public void Parse_DryRun_SetsFlag()
        {
            var parser = new ArgumentParser();
            parser.Parse(new[] { "--dry-run" });

            parser.IsDryRun.Should().BeTrue();
        }

        [Fact]
        public void Parse_DryRun_CaseInsensitive()
        {
            var parser = new ArgumentParser();
            parser.Parse(new[] { "--DRY-RUN" });

            parser.IsDryRun.Should().BeTrue();
        }

        [Fact]
        public void Parse_NoAutoBackup_DisablesBackup()
        {
            var parser = new ArgumentParser();
            parser.Parse(new[] { "--no-auto-backup" });

            parser.IsAutoBackup.Should().BeFalse();
        }

        [Fact]
        public void Parse_BackupDir_WithEquals()
        {
            var parser = new ArgumentParser();
            parser.Parse(new[] { "--backup-dir=C:\\backups" });

            parser.BackupDir.Should().Be("C:\\backups");
        }

        [Fact]
        public void Parse_TiaMajorVersion_WithEquals()
        {
            var parser = new ArgumentParser();
            parser.Parse(new[] { "--tia-major-version=V21" });

            parser.TiaMajorVersion.Should().Be("V21");
        }

        [Fact]
        public void Parse_TiaMajorVersion_WithSeparateArg()
        {
            var parser = new ArgumentParser();
            parser.Parse(new[] { "--tia-major-version", "V19" });

            parser.TiaMajorVersion.Should().Be("V19");
        }

        [Fact]
        public void Parse_TiaMajorVersion_DefaultWhenNoValue()
        {
            var parser = new ArgumentParser();
            parser.Parse(new[] { "--tia-major-version" }); // no value after

            parser.TiaMajorVersion.Should().Be("V18"); // unchanged
        }

        [Fact]
        public void Parse_NonOptionArgs_ArePreserved()
        {
            var parser = new ArgumentParser();
            var remaining = parser.Parse(new[] { "import-scl", "input.json", "--dry-run" });

            remaining.Should().BeEquivalentTo(new[] { "import-scl", "input.json" }, options => options.WithStrictOrdering());
        }

        [Fact]
        public void Parse_MixedOptions_AllParsedCorrectly()
        {
            var parser = new ArgumentParser();
            var remaining = parser.Parse(new[] {
                "--tia-major-version=V21", "--dry-run", "--no-auto-backup",
                "compile", "config.json"
            });

            parser.TiaMajorVersion.Should().Be("V21");
            parser.IsDryRun.Should().BeTrue();
            parser.IsAutoBackup.Should().BeFalse();
            remaining.Should().BeEquivalentTo(new[] { "compile", "config.json" }, options => options.WithStrictOrdering());
        }

        [Fact]
        public void Parse_UnknownOptions_PassedAsRemaining()
        {
            var parser = new ArgumentParser();
            var remaining = parser.Parse(new[] { "--unknown-flag", "value" });

            remaining.Should().BeEquivalentTo(new[] { "--unknown-flag", "value" });
        }

        [Fact]
        public void Parse_AllOptions_ProducesCorrectRemaining()
        {
            var parser = new ArgumentParser();
            var remaining = parser.Parse(new[] {
                "--dry-run", "list-blocks", "project.json", "--tia-major-version=V21"
            });

            remaining.Should().BeEquivalentTo(new[] { "list-blocks", "project.json" }, options => options.WithStrictOrdering());
        }
    }
}