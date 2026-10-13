from pathlib import Path


class Program:
    def __init__(self, name, source, files, flags=(), runnable=True):
        self.name = name
        self.source = source
        self.files = list(files)
        self.flags = list(flags)
        self.runnable = runnable


class Corpus:
    TACLE_CATEGORIES = ["kernel", "sequential", "app", "test"]
    EMBENCH_DEFINES = ["-DGLOBAL_SCALE_FACTOR=1", "-DCPU_MHZ=1", "-DWARMUP_HEAT=1"]

    def __init__(self, root):
        self.root = Path(root)

    def synthetic(self):
        files = sorted((self.root / "synthetic").glob("*.c"))
        return [Program(path.stem, "synthetic", [path]) for path in files]

    def taclebench(self):
        programs = []
        for category in self.TACLE_CATEGORIES:
            base = self.root / "tacle-bench" / "bench" / category
            if not base.exists():
                continue
            for folder in sorted(base.iterdir()):
                files = sorted(folder.glob("*.c")) if folder.is_dir() else []
                if files:
                    programs.append(Program(f"tacle_{folder.name}", "taclebench", files, [f"-I{folder}"]))
        return programs

    def embench(self):
        base = self.root / "embench-iot"
        if not (base / "src").exists():
            return []
        programs = []
        for folder in sorted((base / "src").iterdir()):
            files = sorted(folder.glob("*.c")) if folder.is_dir() else []
            if files:
                flags = [f"-I{folder}", f"-I{base / 'support'}"] + self.EMBENCH_DEFINES
                programs.append(Program(f"embench_{folder.name}", "embench", files, flags, runnable=False))
        return programs

    def programs(self):
        return self.synthetic() + self.taclebench() + self.embench()

    def runnable(self):
        return [program for program in self.programs() if program.runnable]
